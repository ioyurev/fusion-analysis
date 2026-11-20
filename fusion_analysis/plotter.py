from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pyqtgraph as pg
from fusion_common import resolve_ui_icon
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets

from .helpers import centered_moving_average, compute_padded_limits, find_nearest
from .measurement_data import SegmentTable, ThermalType, raw_key_for
from .segment import (
    CurveSegment,
    MyAnn,
    OnsetLine,
    Peak,
    SegmentDTA,
    to_qcolor,
)

if TYPE_CHECKING:
    from .config import PlotterSettings
    from .custom_widgets import MySpinBox


@dataclass(frozen=True)
class PlotterControls:
    """Набор связанных с плоттером виджетов главного окна."""

    spinbox_t: MySpinBox
    spinbox_T1: MySpinBox
    spinbox_T2: MySpinBox
    spinbox_onsettool_T1: MySpinBox
    spinbox_onsettool_T2: MySpinBox
    combobox_xaxis: QtWidgets.QComboBox
    combobox_baselinetype: QtWidgets.QComboBox


class Selector:
    """Вертикальная линия-селектор на базе pg.InfiniteLine с синхронизацией со спинбоксом."""

    def __init__(
        self,
        vb: pg.ViewBox,
        x: float,
        spinbox: MySpinBox,
        limit_x1: float,
        limit_x2: float,
    ) -> None:
        self.vb = vb
        self.spinbox = spinbox
        self.spinbox.selector = self
        self.limit_x1 = min(float(limit_x1), float(limit_x2))
        self.limit_x2 = max(float(limit_x1), float(limit_x2))
        self.spinbox.setRange(self.limit_x1, self.limit_x2)
        self.spinbox.setValue(float(x), block_signal=True)
        self.line = pg.InfiniteLine(
            pos=float(x),
            angle=90,
            movable=True,
            bounds=(self.limit_x1, self.limit_x2),
            pen=pg.mkPen("#0284C7", width=1.8),
            hoverPen=pg.mkPen("#EF4444", width=2.4),
        )
        self.line.sigPositionChanged.connect(self._on_line_dragged)
        self.vb.addItem(self.line)

    def _on_line_dragged(self) -> None:
        val = float(self.line.value())
        self.spinbox.setValue(val, block_signal=True)

    def setPickEffect(self, _active: bool) -> None:
        pass

    def set_x(self, x: float, update_spinbox_value: bool = True) -> None:
        clamped = max(self.limit_x1, min(self.limit_x2, float(x)))
        self.line.blockSignals(True)
        self.line.setValue(clamped)
        self.line.blockSignals(False)
        if update_spinbox_value:
            self.spinbox.setValue(clamped, block_signal=True)

    def get_xdata(self) -> np.ndarray:
        v = float(self.line.value())
        return np.array([v, v], dtype=float)

    def remove(self) -> None:
        self.vb.removeItem(self.line)

    def hit_test(self, _scene_pos: QtCore.QPointF) -> bool:
        return False


PickedArtist = CurveSegment | Peak | OnsetLine | MyAnn | Selector


class PlotCanvas(pg.PlotWidget):
    """Виджет графика PyQtGraph с поддержкой кликов и перетаскивания подписей."""

    def __init__(self, plotter: Plotter) -> None:
        super().__init__()
        self._plotter = plotter
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)

    def draw(self) -> None:
        self.viewport().update()

    def mousePressEvent(self, ev: QtGui.QMouseEvent) -> None:
        scene_pos = self.mapToScene(ev.position().toPoint())
        global_pos = self.mapToGlobal(ev.position().toPoint())
        if self._plotter.handle_mouse_press(scene_pos, global_pos, ev.button()):
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QtGui.QMouseEvent) -> None:
        if ev.buttons() & QtCore.Qt.MouseButton.LeftButton and isinstance(
            self._plotter.holding_item, MyAnn
        ):
            scene_pos = self.mapToScene(ev.position().toPoint())
            vb = self._plotter.holding_item.vb or self._plotter.main_vb
            pt = vb.mapSceneToView(scene_pos)
            self._plotter.holding_item.set_position((pt.x(), pt.y()))
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        self._plotter.holding_item = None
        super().mouseReleaseEvent(ev)


class Plotter(QtCore.QObject):
    measurement_exo: int = 1
    sample_mass_mg: float | None = None
    units: dict[str, Any]
    picked_item: PickedArtist | None = None
    picked_curve: CurveSegment | None = None
    picked_segment: SegmentDTA | None = None
    picked_peak: Peak | None = None
    holding_item: PickedArtist | None = None
    config: PlotterSettings | None = None
    signal_pick = QtCore.Signal(object)
    signal_cm = QtCore.Signal(tuple)
    signal_split = QtCore.Signal(tuple)
    spinbox_T1: MySpinBox
    spinbox_T2: MySpinBox
    spinbox_onsettool_T1: MySpinBox
    spinbox_onsettool_T2: MySpinBox
    spinbox_t: MySpinBox
    combobox_xaxis: QtWidgets.QComboBox
    combobox_baselinetype: QtWidgets.QComboBox
    selectMode: int

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        scale: float,
        controls: PlotterControls | None = None,
    ) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)
        self.scale = scale
        self.units = {}
        self.deriv_channel: str = "DTA"
        self.current_yaxis: str = "DTA"
        self.smoothing_windows: dict[str, int] = {}
        self.ghost_lines: list[tuple[pg.ViewBox, pg.PlotCurveItem]] = []
        self.extra_axes: dict[str, tuple[pg.AxisItem, pg.ViewBox]] = {}
        self._next_axis_col: int = 3
        if controls is not None:
            self.spinbox_t = controls.spinbox_t
            self.spinbox_T1 = controls.spinbox_T1
            self.spinbox_T2 = controls.spinbox_T2
            self.spinbox_onsettool_T1 = controls.spinbox_onsettool_T1
            self.spinbox_onsettool_T2 = controls.spinbox_onsettool_T2
            self.combobox_xaxis = controls.combobox_xaxis
            self.combobox_baselinetype = controls.combobox_baselinetype

        self.canvas = PlotCanvas(self)
        p_item = self.canvas.getPlotItem()
        if p_item is None:
            raise RuntimeError("PlotItem is missing")
        self.main_plot = p_item
        self.main_vb = self.main_plot.vb

        self.exo_text = pg.TextItem(text="", anchor=(0.0, 0.0))
        self.main_vb.addItem(self.exo_text, ignoreBounds=True)

        self.main_vb.sigResized.connect(self._sync_aux_viewboxes)
        self.main_vb.sigRangeChanged.connect(self._update_exo_pos)
        self.canvas.scene().sigMouseMoved.connect(self._on_mouse_moved)

        self.toolbar = self._build_toolbar()
        self.segments_dta: list[SegmentDTA] = []
        self.items: list[PickedArtist | None] = []

        style_hints = QtGui.QGuiApplication.styleHints()
        style_hints.colorSchemeChanged.connect(self._apply_color_scheme)
        self._apply_color_scheme(style_hints.colorScheme())
        self.set_visible(False)

    def _build_toolbar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(bar)
        row.setContentsMargins(0, 2, 0, 2)
        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        btn_home = QtWidgets.QPushButton(
            resolve_ui_icon(ti.ZoomFitBest, st.SP_DialogResetButton),
            "Автомасштаб",
        )
        btn_save = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentSaveAs, st.SP_DialogSaveButton),
            "Сохранить PNG",
        )
        btn_home.clicked.connect(lambda: self.autoscale())
        btn_save.clicked.connect(self._export_png_dialog)
        row.addWidget(btn_home)
        row.addWidget(btn_save)
        row.addStretch()
        self.lbl_coords = QtWidgets.QLabel("Курсор: —")
        self.lbl_coords.setStyleSheet("font-family: Consolas, monospace;")
        row.addWidget(self.lbl_coords)
        return bar

    def _on_mouse_moved(self, scene_pos: QtCore.QPointF) -> None:
        if not self.main_vb.sceneBoundingRect().contains(scene_pos):
            return
        xaxis = (
            self.getCurrentXaxis() if hasattr(self, "combobox_xaxis") else "Time"
        ) or "Time"
        x_u = self.get_units(xaxis)
        p_main = self.main_vb.mapSceneToView(scene_pos)
        parts = [f"{xaxis}={p_main.x():.2f} {x_u}".strip()]
        if self.segments_dta:
            y_u = self.get_units(self.current_yaxis)
            parts.append(f"{self.current_yaxis}={p_main.y():.3f} {y_u}".strip())
            for ch_name, (ax, vb) in self.extra_axes.items():
                if ax.isVisible():
                    pt = vb.mapSceneToView(scene_pos)
                    u_s = self.get_units(ch_name)
                    parts.append(f"{ch_name}={pt.y():.3f} {u_s}".strip())
        self.lbl_coords.setText(" | ".join(parts))

    def _ensure_channel_axis(
        self, channel_name: str, color_hex: str = "#64748B"
    ) -> tuple[pg.AxisItem, pg.ViewBox]:
        if channel_name in self.extra_axes:
            ax, vb = self.extra_axes[channel_name]  # noqa: PU001
            u_s = self.get_units(channel_name)
            lbl = f"{channel_name}, {u_s}" if u_s else channel_name
            ax.setLabel(lbl, color=color_hex)
            return ax, vb

        ax = pg.AxisItem("right")
        vb = pg.ViewBox()
        self.main_plot.layout.addItem(ax, 2, self._next_axis_col)
        self._next_axis_col += 1
        self.main_plot.scene().addItem(vb)
        ax.linkToView(vb)
        vb.setXLink(self.main_vb)
        is_dark = (
            QtGui.QGuiApplication.styleHints().colorScheme()
            == QtCore.Qt.ColorScheme.Dark
        )
        fg_hex = "#CBD5E1" if is_dark else "#1E293B"
        ax.setPen(fg_hex)
        ax.setTextPen(fg_hex)
        u_s = self.get_units(channel_name)
        lbl = f"{channel_name}, {u_s}" if u_s else channel_name
        ax.setLabel(lbl, color=color_hex)
        vb.setGeometry(self.main_vb.sceneBoundingRect())
        self.extra_axes[channel_name] = (ax, vb)
        return ax, vb

    def apply_antialias(self, enabled: bool) -> None:
        flag = bool(enabled)
        pg.setConfigOptions(antialias=flag)
        for seg in self.segments_dta:
            for c_seg in seg.curves.values():
                c_seg.curve.opts["antialias"] = flag
                c_seg.curve.update()

    def _export_png_dialog(self) -> None:
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(  # noqa: PU001
            self.canvas, "Сохранить изображение графика", "plot.png", "PNG (*.png)"
        )
        if fname:
            self.canvas.grab().save(fname, "PNG")

    def _apply_color_scheme(self, scheme: QtCore.Qt.ColorScheme) -> None:
        is_dark = scheme == QtCore.Qt.ColorScheme.Dark
        bg_hex = "#0F172A" if is_dark else "#FFFFFF"
        fg_hex = "#CBD5E1" if is_dark else "#1E293B"
        self.canvas.setBackground(bg_hex)
        for ax_name in ("bottom", "left"):
            ax = self.main_plot.getAxis(ax_name)
            ax.setPen(fg_hex)
            ax.setTextPen(fg_hex)
        for extra_ax, _ in self.extra_axes.values():
            extra_ax.setPen(fg_hex)
            extra_ax.setTextPen(fg_hex)
        self.exo_text.setColor(fg_hex)

    def _sync_aux_viewboxes(self) -> None:
        rect = self.main_vb.sceneBoundingRect()
        for _, vb in self.extra_axes.values():
            vb.setGeometry(rect)
            vb.linkedViewChanged(self.main_vb, vb.XAxis)
        self._update_exo_pos()

    def _update_exo_pos(self) -> None:
        vr = self.main_vb.viewRect()
        self.exo_text.setPos(
            vr.left() + vr.width() * 0.015,
            vr.bottom() - vr.height() * 0.02,
        )

    def target_vb_for_curve(self, curve: CurveSegment) -> pg.ViewBox:
        ch = curve.channel_name
        if ch == self.current_yaxis:
            return self.main_vb
        _, vb = self._ensure_channel_axis(ch, color_hex=curve.get_color())  # noqa: PU001
        return vb

    def on_close(self) -> None:
        self.clear_smoothing_ghost(redraw=False)
        self.items.clear()
        self.picked_item = None
        self.picked_curve = None
        self.picked_segment = None
        self.picked_peak = None
        self.holding_item = None
        self.clear()
        self.remove_segments()
        for ax, vb in self.extra_axes.values():
            ax.setVisible(False)
            vb.setVisible(False)
        self.set_visible(False)

    def _unpick_all(self) -> None:
        if self.picked_item is not None:
            self.picked_item.setPickEffect(False)
        if self.picked_curve is not None:
            self.picked_curve.setPickEffect(False)
        if self.picked_peak is not None:
            self.picked_peak.setPickEffect(False)
        if self.picked_segment is not None:
            self.picked_segment.setPickEffect(False)
        for seg in self.segments_dta:
            for c_seg in seg.curves.values():
                c_seg.setPickEffect(False)
                for pk in c_seg.peaks:
                    pk.setPickEffect(False)

    def clear_selection(self) -> None:
        self._unpick_all()
        self.picked_item = None
        self.picked_curve = None
        self.picked_peak = None
        self.picked_segment = None
        self.signal_pick.emit(None)

    def handle_mouse_press(
        self,
        scene_pos: QtCore.QPointF,
        global_pos: QtCore.QPoint,
        button: QtCore.Qt.MouseButton,
    ) -> bool:
        if button not in (
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.RightButton,
        ):
            return False
        ordered_layers = (MyAnn, OnsetLine, Peak, CurveSegment)
        for layer_cls in ordered_layers:
            for candidate in reversed(self.items):
                if isinstance(candidate, layer_cls) and candidate.hit_test(scene_pos):
                    self._select_picked_item(
                        candidate,
                        global_pos,
                        is_right=(button == QtCore.Qt.MouseButton.RightButton),
                    )
                    self.holding_item = candidate
                    return True
        if button == QtCore.Qt.MouseButton.LeftButton and not any(
            isinstance(it, Selector) for it in self.items
        ):
            self.clear_selection()
        return False

    def select_curve_directly(self, curve: CurveSegment) -> None:
        self._unpick_all()
        self.picked_item = curve
        self.picked_curve = curve
        self.picked_segment = curve.parent_segment
        self.picked_peak = None
        curve.setPickEffect(True)

    def select_peak_directly(self, peak: Peak) -> None:
        self._unpick_all()
        self.picked_item = peak
        self.picked_peak = peak
        self.picked_curve = peak.segment
        self.picked_segment = peak.segment.parent_segment
        peak.setPickEffect(True)

    def _select_picked_item(
        self,
        item: PickedArtist,
        global_pos: QtCore.QPoint,
        is_right: bool,
    ) -> None:
        self._unpick_all()
        self.picked_peak = None
        self.picked_curve = None
        self.picked_segment = None
        match item:
            case MyAnn():
                pass
            case CurveSegment():
                self.picked_curve = item
                self.picked_segment = item.parent_segment
                item.setPickEffect(True)
            case Peak():
                self.picked_peak = item
                self.picked_curve = item.segment
                self.picked_segment = item.segment.parent_segment
                item.setPickEffect(True)
        if is_right:
            target = item.parent if isinstance(item, MyAnn) else item
            self.signal_cm.emit((target, global_pos))
        self.picked_item = item
        self.signal_pick.emit(item)

    def set_exo(self) -> None:
        arrow = "↑" if self.measurement_exo else "↓"
        self.exo_text.setText(f"exo{arrow}")
        self._update_exo_pos()

    def set_xlabel(self, xaxis: str) -> None:
        self.main_plot.setLabel("bottom", f"{xaxis}, {self.get_units(xaxis)}")

    def get_units(self, axis: str) -> str:
        unit = str(self.units.get(axis, ""))
        return unit.replace(" ", "") if "/" in unit else unit

    def set_visible(self, visible: bool) -> None:
        self.canvas.setVisible(True)
        self.toolbar.setEnabled(visible)

    def autoscale(self, redraw: bool = True) -> None:
        _ = redraw
        self.autoscale_xaxis()
        self._autoscale_vb(self.main_vb)
        for ax, vb in self.extra_axes.values():
            if ax.isVisible():
                self._autoscale_vb(vb)
        self._update_exo_pos()

    def _autoscale_vb(self, target_vb: pg.ViewBox) -> None:
        visible_lines = [
            c_seg
            for seg in self.segments_dta
            for c_seg in seg.curves.values()
            if c_seg.get_visible() and c_seg.vb is target_vb
        ]
        y_arrays = [line.get_ydata() for line in visible_lines]
        limits = compute_padded_limits(y_arrays, pad_fraction=0.05)
        if limits is not None:
            target_vb.setYRange(limits[0], limits[1], padding=0.0)  # noqa: MI001

    def autoscale_xaxis(self) -> None:
        if not self.segments_dta:
            return
        x_arrays = [
            c_seg.get_xdata()
            for seg in self.segments_dta
            for c_seg in seg.curves.values()
            if c_seg.get_visible()
        ]
        limits = compute_padded_limits(x_arrays, pad_fraction=0.03)
        if limits is not None:
            self.main_vb.setXRange(limits[0], limits[1], padding=0.0)  # noqa: MI001

    def getCurrentXaxis(self) -> str:
        if hasattr(self, "combobox_xaxis"):
            return self.combobox_xaxis.currentText()
        return "Time"

    def sync_aux_axes_visibility(self) -> None:
        xaxis = self.getCurrentXaxis()
        for ch_name, (ax, vb) in list(self.extra_axes.items()):
            if ch_name in (self.current_yaxis, xaxis):
                ax.setVisible(False)
                vb.setVisible(False)
                continue
            vis_curves = [
                seg.curves[ch_name]
                for seg in self.segments_dta
                if ch_name in seg.curves and seg.curves[ch_name].get_visible()
            ]
            has_vis = len(vis_curves) > 0
            ax.setVisible(has_vis)
            vb.setVisible(has_vis)
            if vis_curves:
                u_s = self.get_units(ch_name)
                lbl = f"{ch_name}, {u_s}" if u_s else ch_name
                ax.setLabel(lbl, color=vis_curves[0].get_color())  # noqa: MI001

    def _reattach_segment_curves(self, seg: SegmentDTA) -> None:
        for c_seg in seg.curves.values():
            c_seg.detach_all()
            vb = self.target_vb_for_curve(c_seg)
            c_seg.attach_to(vb)
            for pk in c_seg.peaks:
                pk.attach_to(vb)
                for ol in pk.onset_lines:
                    ol.attach_to(vb)
            if c_seg not in self.items:
                self.items.append(c_seg)

    def updateAxes(self) -> None:
        xaxis = self.getCurrentXaxis()
        yaxis = self.current_yaxis
        self.set_xlabel(xaxis)
        self.main_plot.setLabel(
            "left",
            f"{yaxis}, {self.get_units(yaxis) if yaxis in self.units else ''}",
            color="#0284C7",
        )
        for segment in self.segments_dta:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            self._reattach_segment_curves(segment)
        self.sync_aux_axes_visibility()
        self._sync_aux_viewboxes()
        self.autoscale()

    def add_derivative_for_channel(
        self,
        source_col: str,
        order: int = 1,
    ) -> str:
        xaxis = self.getCurrentXaxis() or "Time"
        self.deriv_channel = source_col
        col_name = (
            f"d({source_col})/d({xaxis})"
            if order == 1
            else f"d²({source_col})/d({xaxis})²"
        )
        for seg in self.segments_dta:
            d_curve = seg.add_or_update_derivative_curve(source_col, xaxis, order=order)
            d_curve.detach_all()
            vb = self.target_vb_for_curve(d_curve)
            d_curve.attach_to(vb)
            if d_curve not in self.items:
                self.items.append(d_curve)
        self.sync_aux_axes_visibility()
        self._sync_aux_viewboxes()
        self.autoscale()
        return col_name

    def remove_derivative_channel(self, col_name: str) -> None:
        for seg in self.segments_dta:
            c_seg = seg.curves.pop(col_name, None)
            if c_seg is not None:
                c_seg.detach_all()
                if c_seg in self.items:
                    self.items.remove(c_seg)
            seg.df.pop(col_name, None)
            seg.df.pop(raw_key_for(col_name), None)
        self.sync_aux_axes_visibility()
        self.autoscale()

    def show_smoothing_ghost(self, channel: str) -> None:
        self.clear_smoothing_ghost(redraw=False)
        rk = raw_key_for(channel)
        xaxis = self.getCurrentXaxis() or "Time"
        for seg in self.segments_dta:
            c_seg = seg.curves.get(channel)
            if c_seg is None or not c_seg.get_visible():
                continue
            raw_arr = seg.df.get(rk, seg.df.get(channel))
            if raw_arr is None or xaxis not in seg.df:
                continue
            x_arr = np.asarray(seg.df[xaxis], dtype=float)
            y_raw = np.asarray(raw_arr, dtype=float)
            target_vb = c_seg.vb or self.main_vb
            col = to_qcolor(c_seg.get_color())
            col.setAlpha(75)
            ghost = pg.PlotCurveItem(x_arr, y_raw, pen=pg.mkPen(col, width=1.2))
            target_vb.addItem(ghost)
            self.ghost_lines.append((target_vb, ghost))

    def clear_smoothing_ghost(self, redraw: bool = True) -> None:
        _ = redraw
        for vb, ghost in self.ghost_lines:
            vb.removeItem(ghost)
        self.ghost_lines.clear()

    def apply_live_smoothing(self, channel: str, window_spin: int) -> None:
        self.smoothing_windows[channel] = int(window_spin)
        win_pts = max(1, 10 * int(window_spin)) if int(window_spin) > 1 else 1
        rk = raw_key_for(channel)
        xaxis = self.getCurrentXaxis() or "Time"
        for seg in self.segments_dta:
            raw_arr = seg.df.get(rk, seg.df.get(channel))
            if raw_arr is not None:
                if rk not in seg.df:
                    seg.df[rk] = np.asarray(raw_arr, dtype=float).copy()
                seg.df[channel] = (
                    centered_moving_average(seg.df[rk], win_pts)
                    if win_pts > 1
                    else seg.df[rk].copy()
                )
            if channel in seg.curves:
                seg.curves[channel].sync_curve_axes(xaxis)
            updated_derivs = seg.recompute_dependent_derivatives(channel, xaxis)
            for d_col in updated_derivs:
                d_curve = seg.curves[d_col]
                if d_curve.vb is None:
                    d_curve.attach_to(self.target_vb_for_curve(d_curve))
        self.show_smoothing_ghost(channel)
        self.autoscale()

    def remove_segments(self) -> None:
        self.segments_dta.clear()

    def plot(
        self,
        xaxis: str,
        yaxis: str,
        has_massdata: bool = True,
        has_tempdata: bool = True,
    ) -> None:
        _ = (has_massdata, has_tempdata)
        self.current_yaxis = yaxis
        self.clear()
        for segment in self.segments_dta:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            self._reattach_segment_curves(segment)

        self.set_xlabel(xaxis)
        self.main_plot.setLabel(
            "left", f"{yaxis}, {self.get_units(yaxis)}", color="#0284C7"
        )
        if self.config is not None:
            self.apply_antialias(self.config.antialias)
        self.sync_aux_axes_visibility()
        self._sync_aux_viewboxes()
        self.autoscale()

    def on_remove(self) -> None:
        self.picked_peak = None
        self.picked_curve = None
        self.picked_segment = None
        self.sync_aux_axes_visibility()
        self.signal_pick.emit(None)

    def resolve_segment_color(self, thermal_type: Any) -> Any:
        if self.config is not None and self.config.autocolor:
            if thermal_type == ThermalType.HEAT:
                return tuple(self.config.default_heat_color)
            if thermal_type == ThermalType.COOL:
                return tuple(self.config.default_cool_color)
        return "#0284C7"

    def addSegment(
        self,
        df: SegmentTable,
        index: int,
        thermal_type: Any,
        temp_axis: str,
    ) -> SegmentDTA:
        segment = SegmentDTA(
            df=df,
            plotter=self,
            index=index,
            thermal_type=thermal_type,
            color=self.resolve_segment_color(thermal_type),
            temp_axis=temp_axis,
        )
        self.segments_dta.append(segment)
        for c_seg in segment.curves.values():
            self.items.append(c_seg)
        return segment

    def clear(self) -> None:
        for seg in self.segments_dta:
            for c_seg in seg.curves.values():
                c_seg.detach_all()
        self.exo_text.setText("")

    def gridSetVisible(self, visible: bool) -> None:
        self.main_plot.showGrid(x=visible, y=visible, alpha=0.3)

    def spawn_split_selector(
        self, t: float, limit_x1: float, limit_x2: float
    ) -> Selector:
        selector = Selector(
            vb=self.main_vb,
            x=t,
            limit_x1=limit_x1,
            limit_x2=limit_x2,
            spinbox=self.spinbox_t,
        )
        self.items.append(selector)
        return selector

    def splittool_start(self) -> None:
        segment = self.picked_segment
        if segment is None:
            return
        xdata = segment.get_xdata()
        vr = self.main_vb.viewRect()
        ax_i1 = find_nearest(xdata, vr.left())
        ax_i2 = find_nearest(xdata, vr.right())
        lo_i, hi_i = min(ax_i1, ax_i2), max(ax_i1, ax_i2)
        i = lo_i + max(0, (hi_i - lo_i) // 2)
        self.selectMode = 1
        self.selector_split = self.spawn_split_selector(
            t=float(xdata[i]), limit_x1=segment.xmin, limit_x2=segment.xmax
        )

    def splittool_done(self, apply: bool) -> None:
        self.spinbox_t.selector = None
        self.selector_split.remove()
        if self.selector_split in self.items:
            self.items.remove(self.selector_split)
        del self.selector_split
        if apply:
            self.apply_split()

    def apply_split(self) -> None:
        if self.picked_segment is None:
            raise ValueError("picked_segment is None")
        x = self.spinbox_t.value()
        log.bind(segment_index=self.picked_segment.index, x=x).info("Splitting segment")
        segment1, segment2 = self.picked_segment.split(x=x)  # noqa: PU001
        start_i = self.picked_segment.index
        for i in range(start_i + 1, len(self.segments_dta)):
            self.segments_dta[i].index += 1
        for old_c in list(self.picked_segment.curves.values()):
            if old_c in self.items:
                self.items.remove(old_c)
        self.picked_segment.remove()
        for seg_new in (segment1, segment2):
            self._reattach_segment_curves(seg_new)
        self.segments_dta[start_i] = segment2
        self.segments_dta.insert(start_i, segment1)
        self.sync_aux_axes_visibility()
        self.signal_split.emit((segment1, segment2, start_i))

    def onsettool_done(self, apply: bool) -> None:
        if self.picked_peak is None:
            raise RuntimeError("Peak not picked")
        self.spinbox_onsettool_T1.selector = None
        self.spinbox_onsettool_T2.selector = None
        if apply:
            t1 = self.spinbox_onsettool_T1.value()
            t2 = self.spinbox_onsettool_T2.value()
            line = self.picked_peak.onset(t1=t1, t2=t2, is_onset=self.is_onset)
            self.items.append(line)
            self.items.append(line.ann)
        self.despawn_selectors()

    def onsettool_start(self, is_onset: bool) -> None:
        self.is_onset = is_onset
        peak = self.picked_peak
        if peak is None:
            raise RuntimeError("Peak not picked")
        peak_xdata = peak.df_baseline[self.getCurrentXaxis()]
        first_x = float(peak_xdata[0])  # noqa: MI001
        last_x = float(peak_xdata[-1])  # noqa: MI001
        ci = len(peak_xdata) // 2
        xc = float(peak_xdata[ci])
        t_lo, t_hi = (
            (min(first_x, xc), max(first_x, xc))
            if is_onset
            else (min(xc, last_x), max(xc, last_x))
        )
        self.spawn_selectors(t1=t_lo, t2=t_hi, selectMode=1)
        self.spinbox_onsettool_T1.setValue(t_lo)
        self.spinbox_onsettool_T2.setValue(t_hi)

    def peaktool_start(self) -> None:
        curve = self.picked_curve or self.picked_segment
        if curve is None:
            return
        x1 = curve.xmin
        x2 = curve.xmax
        vr = (curve.vb or self.main_vb).viewRect()
        if vr.width() > 0:
            x1 = max(x1, vr.left())
            x2 = min(x2, vr.right())
        r = x2 - x1
        t1 = round(x1 + r / 3, 1)
        t2 = round(x1 + 2 * r / 3, 1)
        self.spawn_selectors(t1=t1, t2=t2, selectMode=0)
        self.spinbox_T1.setValue(t1)
        self.spinbox_T2.setValue(t2)

    def spawn_selectors(self, t1: float, t2: float, selectMode: int) -> None:
        self.selectMode = selectMode
        if self.selectMode == 0:
            curve = self.picked_curve or self.picked_segment
            if curve is None:
                raise RuntimeError("No picked curve")
            limit_x1 = curve.xmin
            limit_x2 = curve.xmax
            spinbox1 = self.spinbox_T1
            spinbox2 = self.spinbox_T2
            target_vb = curve.vb or self.main_vb
        else:
            xaxis = self.getCurrentXaxis()
            if self.picked_peak is None:
                raise ValueError("No picked peak")
            arr = self.picked_peak.df_baseline[xaxis]
            first_v, *_, last_v = arr
            limit_x1 = float(min(first_v, last_v))
            limit_x2 = float(max(first_v, last_v))
            spinbox1 = self.spinbox_onsettool_T1
            spinbox2 = self.spinbox_onsettool_T2
            target_vb = self.picked_peak.vb or self.main_vb
        self.selector1 = Selector(
            vb=target_vb,
            x=t1,
            limit_x1=limit_x1,
            limit_x2=limit_x2,
            spinbox=spinbox1,
        )
        self.selector2 = Selector(
            vb=target_vb,
            x=t2,
            limit_x1=limit_x1,
            limit_x2=limit_x2,
            spinbox=spinbox2,
        )
        self.items.append(self.selector1)
        self.items.append(self.selector2)

    def despawn_selectors(self) -> None:
        self.selector1.remove()
        self.selector2.remove()
        if self.selector1 in self.items:
            self.items.remove(self.selector1)
        if self.selector2 in self.items:
            self.items.remove(self.selector2)
        del self.selector1
        del self.selector2

    def peaktool_done(self, apply: bool) -> None:
        if apply:
            curve = self.picked_curve or self.picked_segment
            if curve is None:
                raise RuntimeError("No picked curve")
            t1, *_ = self.selector1.get_xdata()
            t2, *_ = self.selector2.get_xdata()
            log.bind(channel=curve.channel_name, t1=float(t1), t2=float(t2)).info(
                "Adding peak on selected interval"
            )
            peak = curve.addPeak(
                t1=float(t1),
                t2=float(t2),
                baseline_type=self.combobox_baselinetype.currentIndex(),
            )
            self.items.append(peak)
            self.items.append(peak.ann)
        self.spinbox_T1.selector = None
        self.spinbox_T2.selector = None
        self.despawn_selectors()

    def export_analysis_state(self) -> dict[str, Any]:
        split_times: list[float] = []
        for seg in self.segments_dta[:-1]:
            t_vals = seg.df["Time"]
            if len(t_vals) > 0:
                *_, last_t = t_vals
                split_times.append(float(last_t))

        segments_meta: list[dict[str, Any]] = []
        for seg in self.segments_dta:
            curves_meta: dict[str, Any] = {}
            for ch_name, c_seg in seg.curves.items():
                peaks_meta: list[dict[str, Any]] = []
                for pk in c_seg.peaks:
                    onsets_meta = [
                        {
                            "ci": int(ol.ci),
                            "bi": int(ol.bi),
                            "is_onset": bool(ol.is_onset),
                            "label_enabled": bool(ol.label_enabled),
                            "label_time_enabled": bool(ol.label_time_enabled),
                            "label_temp_enabled": bool(ol.label_temp_enabled),
                            "label_dta_enabled": bool(ol.label_dta_enabled),
                        }
                        for ol in pk.onset_lines
                    ]
                    peaks_meta.append(
                        {
                            "t1": float(pk.t1_time),
                            "t2": float(pk.t2_time),
                            "baseline_type": int(pk.baseline_type),
                            "label_enabled": bool(pk.label_enabled),
                            "onsets": onsets_meta,
                        }
                    )
                curves_meta[ch_name] = {
                    "color": to_qcolor(c_seg.get_color()).name(),
                    "dy": float(c_seg.dy),
                    "visible": bool(c_seg.get_visible()),
                    "peaks": peaks_meta,
                }
            segments_meta.append(
                {
                    "color": to_qcolor(seg.get_color()).name(),
                    "dy": float(seg.dy),
                    "peaks": curves_meta.get(seg.channel_name, {}).get("peaks", []),
                    "curves": curves_meta,
                }
            )
        return {
            "deriv_channel": self.deriv_channel,
            "split_times": split_times,
            "segments": segments_meta,
        }

    def restore_analysis_state(self, state: dict[str, Any]) -> list[str]:
        warnings_out: list[str] = []
        if not state or not self.segments_dta:
            return warnings_out
        for split_t in state.get("split_times", []):
            try:
                target_seg = self.segments_dta[-1]  # noqa: MI001
                self.picked_segment = target_seg
                self.spinbox_t.setValue(float(split_t), block_signal=True)
                self.apply_split()
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                log.bind(split_t=split_t, error=str(exc)).warning(
                    "Failed to restore split point from analysis_state"
                )
                warnings_out.append(
                    f"Не удалось восстановить точку разделения сегмента ({split_t}): {exc}"
                )
        self.picked_segment = None

        seg_list = state.get("segments", [])
        for seg, meta in zip(self.segments_dta, seg_list, strict=False):
            if not isinstance(meta, dict):
                continue
            curves_meta = meta.get("curves", {})
            if not curves_meta:
                curves_meta = {
                    seg.channel_name: {
                        "color": meta.get("color", seg.get_color()),
                        "dy": meta.get("dy", 0.0),
                        "peaks": meta.get("peaks", []),
                    }
                }
            for ch_name, c_meta in curves_meta.items():
                if not isinstance(c_meta, dict):
                    continue
                c_seg = seg.curves.get(ch_name)
                if c_seg is None:
                    continue
                if "color" in c_meta:
                    try:
                        c_seg.set_color(c_meta["color"])
                    except (TypeError, ValueError) as exc:
                        warnings_out.append(
                            f"Некорректный цвет кривой '{ch_name}': {exc}"
                        )
                if "visible" in c_meta:
                    c_seg.set_visible(bool(c_meta["visible"]))
                for pk_meta in c_meta.get("peaks", []):
                    try:
                        peak = c_seg.addPeak(
                            t1=float(pk_meta["t1"]),
                            t2=float(pk_meta["t2"]),
                            baseline_type=int(pk_meta.get("baseline_type", 0)),
                        )
                    except (KeyError, TypeError, ValueError, IndexError) as exc:
                        log.bind(
                            channel=ch_name,
                            peak_meta=pk_meta,
                            error=str(exc),
                        ).warning("Failed to restore peak from analysis_state")
                        warnings_out.append(
                            f"Пик на канале '{ch_name}' пропущен: {exc}"
                        )
                        continue
                    peak.label_enabled = bool(pk_meta.get("label_enabled", True))
                    self.items.append(peak)
                    self.items.append(peak.ann)
                    for ol_meta in pk_meta.get("onsets", []):
                        try:
                            ol = OnsetLine(
                                peak=peak,
                                ci=int(ol_meta["ci"]),
                                bi=int(ol_meta["bi"]),
                                is_onset=bool(ol_meta.get("is_onset", True)),
                            )
                        except (KeyError, TypeError, ValueError, IndexError) as exc:
                            log.bind(
                                channel=ch_name,
                                onset_meta=ol_meta,
                                error=str(exc),
                            ).warning("Failed to restore onset from analysis_state")
                            warnings_out.append(
                                f"Линия начала/конца пика на канале '{ch_name}' пропущена: {exc}"
                            )
                            continue
                        ol.label_enabled = bool(ol_meta.get("label_enabled", True))
                        if "label_time_enabled" in ol_meta:
                            ol.label_time_enabled = bool(ol_meta["label_time_enabled"])
                        if "label_temp_enabled" in ol_meta:
                            ol.label_temp_enabled = bool(ol_meta["label_temp_enabled"])
                        if "label_dta_enabled" in ol_meta:
                            ol.label_dta_enabled = bool(ol_meta["label_dta_enabled"])
                        peak.onset_lines.append(ol)
                        ol.attach_to(c_seg.vb or self.main_vb)
                        self.items.append(ol)
                        self.items.append(ol.ann)
                try:
                    dy_val = float(c_meta.get("dy", 0.0))
                    if abs(dy_val) > 1e-9:
                        c_seg.shifty(dy_val * 10.0)
                except (TypeError, ValueError) as exc:
                    warnings_out.append(
                        f"Некорректный сдвиг по Y кривой '{ch_name}': {exc}"
                    )
        self.sync_aux_axes_visibility()
        self.autoscale()
        return warnings_out
