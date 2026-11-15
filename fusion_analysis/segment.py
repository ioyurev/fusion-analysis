from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui

from fusion_analysis.helpers import (
    baseline_temp,
    calc_peakonset,
    centered_moving_average,
    compute_glass_transition_metrics,
    compute_melting_range_and_tau_metrics,
    derivative_data,
    estimate_fraser_suzuki_asymmetry,
    find_nearest,
    format_peak_quantity,
    make_peakbaseline,
    second_derivative_data,
)
from fusion_analysis.measurement_data import (
    SegmentTable,
    ThermalType,
    classify_segment_thermal_type,
)

if TYPE_CHECKING:
    from fusion_analysis.plotter import Plotter

LW = 1.6


def to_qcolor(color: Any) -> QtGui.QColor:
    if isinstance(color, QtGui.QColor):
        return color
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        r_f, g_f, b_f, *_ = color
        if max(float(r_f), float(g_f), float(b_f)) <= 1.0:
            return QtGui.QColor(
                int(255 * float(r_f)),
                int(255 * float(g_f)),
                int(255 * float(b_f)),
            )
        return QtGui.QColor(int(r_f), int(g_f), int(b_f))
    return QtGui.QColor(str(color))


class _BaseCurveItem:
    """Базовая обёртка кривой PyQtGraph с поддержкой выделения и hit-test."""

    def __init__(
        self,
        xdata: np.ndarray,
        ydata: np.ndarray,
        color: Any,
        lw: float = LW,
        pen_style: QtCore.Qt.PenStyle = QtCore.Qt.PenStyle.SolidLine,
    ) -> None:
        self._xdata = np.asarray(xdata, dtype=float)
        self._ydata = np.asarray(ydata, dtype=float)
        self._color = to_qcolor(color)
        self._base_lw = float(lw)
        self._pen_style = pen_style
        self._picked = False
        self._visible = True
        self.xmin = float(self._xdata.min()) if len(self._xdata) else 0.0
        self.xmax = float(self._xdata.max()) if len(self._xdata) else 0.0
        self.curve = pg.PlotCurveItem(self._xdata, self._ydata, pen=self._make_pen())
        self.vb: pg.ViewBox | None = None

    def _make_pen(self) -> QtGui.QPen:
        w = self._base_lw + 2.0 if self._picked else self._base_lw
        return pg.mkPen(self._color, width=w, style=self._pen_style)

    def attach_to(self, vb: pg.ViewBox) -> None:
        self.vb = vb
        vb.addItem(self.curve)

    def detach(self) -> None:
        if self.vb is not None:
            self.vb.removeItem(self.curve)
            self.vb = None

    def get_xdata(self) -> np.ndarray:
        return self._xdata

    def get_ydata(self) -> np.ndarray:
        return self._ydata

    def set_ydata(self, y: Any) -> None:
        self.set_data(self._xdata, y)

    def set_data(self, x: Any, y: Any) -> None:
        self._xdata = np.asarray(x, dtype=float)
        self._ydata = np.asarray(y, dtype=float)
        self.xmin = float(self._xdata.min()) if len(self._xdata) else 0.0
        self.xmax = float(self._xdata.max()) if len(self._xdata) else 0.0
        self.curve.setData(self._xdata, self._ydata, skipFiniteCheck=True)

    def get_visible(self) -> bool:
        return self._visible

    def set_visible(self, b: bool) -> None:
        self._visible = bool(b)
        self.curve.setVisible(self._visible)

    def get_color(self) -> str:
        return self._color.name()

    def set_color(self, color: Any) -> None:
        self._color = to_qcolor(color)
        self.curve.setPen(self._make_pen())

    def setPickEffect(self, active: bool) -> None:
        self._picked = bool(active)
        self.curve.setPen(self._make_pen())

    def hit_test(self, scene_pos: QtCore.QPointF) -> bool:
        if not self._visible or self.vb is None or not self.vb.isVisible():
            return False
        if len(self._xdata) == 0:
            return False
        pt = self.vb.mapSceneToView(scene_pos)
        vr = self.vb.viewRect()
        dx_tol = max(1e-9, vr.width() * 0.015)
        dy_tol = max(1e-9, vr.height() * 0.025)
        norm_d2 = ((self._xdata - pt.x()) / dx_tol) ** 2 + (
            (self._ydata - pt.y()) / dy_tol
        ) ** 2
        return bool(np.min(norm_d2) <= 1.0)


class CurveSegment(_BaseCurveItem):
    """Равноправная кривая любого канала сегмента (поддерживает сдвиг, пики, онсеты и сглаживание)."""

    parent_segment: SegmentDTA

    def __init__(
        self,
        xdata: np.ndarray,
        ydata: np.ndarray,
        parent_segment: SegmentDTA | None,
        channel_name: str,
        color: Any,
        lw: float = LW,
        pen_style: QtCore.Qt.PenStyle = QtCore.Qt.PenStyle.SolidLine,
        is_derivative: bool = False,
        deriv_source_col: str = "",
        deriv_order: int = 1,
    ) -> None:
        self.parent_segment = (
            parent_segment if parent_segment is not None else self  # type: ignore[assignment]
        )
        self.channel_name = channel_name
        self.y_col = channel_name
        self.is_derivative = is_derivative
        self.deriv_source_col = deriv_source_col
        self.deriv_order = deriv_order
        self.dy: float = 0.0
        self.peaks: list[Peak] = []
        super().__init__(
            xdata=xdata,
            ydata=ydata,
            color=color,
            lw=lw,
            pen_style=pen_style,
        )

    @property
    def plotter(self) -> Plotter:
        return self.parent_segment._plotter

    @property
    def df(self) -> SegmentTable:
        return self.parent_segment._df

    @property
    def temp_axis(self) -> str:
        return self.parent_segment._temp_axis

    @property
    def xaxis(self) -> str:
        return self.parent_segment._xaxis

    def shifty(self, dy: float) -> None:
        step = dy / 10.0
        self.dy += step
        self.set_ydata(self.get_ydata() - step)
        for peak in self.peaks:
            peak.shifty(step)

    def addPeak(self, t1: float, t2: float, baseline_type: int) -> Peak:
        peak = Peak(segment=self, t1=t1, t2=t2, baseline_type=baseline_type)
        self.peaks.append(peak)
        target_vb = self.vb if self.vb is not None else self.plotter.main_vb
        peak.attach_to(target_vb)
        return peak

    def peaksSetData(self, xaxis: str) -> None:
        for peak in self.peaks:
            peak.set_data(xaxis=xaxis)

    def sync_curve_axes(self, xaxis: str) -> None:
        if xaxis in self.df and self.channel_name in self.df:
            self.set_data(self.df[xaxis], self.df[self.channel_name])
            self.dy = 0.0
            self.peaksSetData(xaxis)

    def set_visible(self, b: bool) -> None:
        super().set_visible(b)
        for peak in self.peaks:
            peak.set_visible(b)

    def set_color(self, color: Any) -> None:
        for peak in self.peaks:
            peak.set_edgecolor(color)
        super().set_color(color)

    def detach_all(self) -> None:
        self.detach()
        for pk in self.peaks:
            pk.detach()

    def remove(self, redraw: bool = False) -> None:
        _ = redraw
        for pk in list(self.peaks):
            pk.remove()
        self.detach()
        if self in self.plotter.items:
            self.plotter.items.remove(self)
        self.parent_segment.curves.pop(self.channel_name, None)
        self.plotter.on_remove()


class SegmentDTA(CurveSegment):
    """Временной сегмент измерения, содержащий словарь всех своих кривых curves."""

    mass_segment: CurveSegment

    def __init__(
        self,
        df: SegmentTable,
        plotter: Plotter,
        index: int,
        thermal_type: ThermalType | int,
        color: Any,
        temp_axis: str = "Temp.",
    ) -> None:
        self._plotter = plotter
        self.thermal_type = thermal_type
        self.index = index
        self._temp_axis = temp_axis
        self._xaxis = "Time"
        seg_copy: SegmentTable = {
            k: np.asarray(v, dtype=float).copy() for k, v in df.items()
        }
        self._df = seg_copy
        primary_col: str = (
            "DTA"
            if "DTA" in seg_copy
            else (
                temp_axis
                if temp_axis in seg_copy
                else next(
                    (k for k in seg_copy if k != "Time" and not k.startswith("__")),
                    "Time",
                )
            )
        )
        super().__init__(
            xdata=seg_copy["Time"],
            ydata=seg_copy[primary_col],
            parent_segment=None,
            channel_name=primary_col,
            color=color,
            lw=LW,
        )
        self.curves: dict[str, CurveSegment] = {primary_col: self}

        self.temp_segment = CurveSegment(
            xdata=seg_copy["Time"],
            ydata=seg_copy[self._temp_axis],
            parent_segment=self,
            channel_name=self._temp_axis,
            color="#EF4444",
            lw=1.5,
        )
        if self._temp_axis not in self.curves:
            self.curves[self._temp_axis] = self.temp_segment

        self.has_massdata = "Mass" in seg_copy
        if self.has_massdata:
            self.mass_segment = CurveSegment(
                xdata=seg_copy["Time"],
                ydata=seg_copy["Mass"],
                parent_segment=self,
                channel_name="Mass",
                color="#16A34A",
                lw=1.4,
            )
            self.curves["Mass"] = self.mass_segment

        self.deriv_channel = primary_col
        d_col_name = f"d({self.deriv_channel})/d({self._xaxis})"
        init_d = derivative_data(seg_copy["Time"], seg_copy[primary_col])
        self.dsegment = CurveSegment(
            xdata=seg_copy[self._xaxis],
            ydata=init_d,
            parent_segment=self,
            channel_name=d_col_name,
            color="#64748B",
            lw=1.3,
            pen_style=QtCore.Qt.PenStyle.DashLine,
            is_derivative=True,
            deriv_source_col=primary_col,
            deriv_order=1,
        )
        self.dsegment.set_visible(False)

        for extra_col, arr in list(seg_copy.items()):
            if (
                extra_col not in ("Time", primary_col, self._temp_axis, "Mass")
                and not extra_col.startswith("__")
                and extra_col not in self.curves
            ):
                is_d = extra_col.startswith("d")
                c_seg = CurveSegment(
                    xdata=seg_copy["Time"],
                    ydata=arr,
                    parent_segment=self,
                    channel_name=extra_col,
                    color="#8B5CF6" if is_d else "#0284C7",
                    lw=1.4,
                    pen_style=(
                        QtCore.Qt.PenStyle.DashLine
                        if is_d
                        else QtCore.Qt.PenStyle.SolidLine
                    ),
                    is_derivative=is_d,
                )
                self.curves[extra_col] = c_seg

    def add_or_update_derivative_curve(
        self,
        source_col: str,
        xaxis: str,
        order: int = 1,
    ) -> CurveSegment:
        col_name = (
            f"d({source_col})/d({xaxis})"
            if order == 1
            else f"d²({source_col})/d({xaxis})²"
        )
        x_arr = np.asarray(self._df[xaxis], dtype=float)
        y_arr = np.asarray(self._df[source_col], dtype=float)
        raw_d = (
            derivative_data(x_arr, y_arr)
            if order == 1
            else second_derivative_data(x_arr, y_arr)
        )
        self._df[f"__raw__{col_name}"] = raw_d.copy()
        d_win = int(getattr(self._plotter, "smoothing_windows", {}).get(col_name, 1))
        d_arr = centered_moving_average(raw_d, 10 * d_win) if d_win > 1 else raw_d
        self._df[col_name] = d_arr.copy()

        palette = ("#64748B", "#8B5CF6", "#D97706", "#0D9488", "#EC4899")
        deriv_count = sum(1 for c in self.curves.values() if c.is_derivative)
        color = palette[deriv_count % len(palette)]

        if col_name in self.curves:
            c_seg = self.curves[col_name]
            c_seg.deriv_source_col = source_col
            c_seg.deriv_order = order
            c_seg.set_data(x_arr, d_arr)
            c_seg.set_visible(True)
        else:
            c_seg = CurveSegment(
                xdata=x_arr,
                ydata=d_arr,
                parent_segment=self,
                channel_name=col_name,
                color=color,
                lw=1.4,
                pen_style=QtCore.Qt.PenStyle.DashLine,
                is_derivative=True,
                deriv_source_col=source_col,
                deriv_order=order,
            )
            c_seg.set_visible(True)
            self.curves[col_name] = c_seg
        self.dsegment = c_seg
        self.deriv_channel = source_col
        return c_seg

    def recompute_dependent_derivatives(
        self, changed_col: str, xaxis: str
    ) -> list[str]:
        updated: list[str] = []
        queue = [changed_col]
        visited: set[str] = set()
        while queue:
            src = queue.pop(0)
            if src in visited:
                continue
            visited.add(src)
            for c_name, c_seg in list(self.curves.items()):
                if c_seg.is_derivative and (
                    c_seg.deriv_source_col == src
                    or c_name.startswith((f"d({src})/", f"d²({src})/"))
                ):
                    ord_v = 2 if c_name.startswith("d²(") else c_seg.deriv_order
                    src_col = c_seg.deriv_source_col or src
                    if src_col in self._df and xaxis in self._df:
                        self.add_or_update_derivative_curve(src_col, xaxis, order=ord_v)
                        updated.append(c_name)
                        queue.append(c_name)
        return updated

    def split(self, x: float) -> tuple[SegmentDTA, SegmentDTA]:
        i = find_nearest(self._df["Time"], x)
        df1: SegmentTable = {k: v[:i].copy() for k, v in self._df.items()}
        df2: SegmentTable = {k: v[i:].copy() for k, v in self._df.items()}
        t_type1, _ = classify_segment_thermal_type(df1[self._temp_axis])  # noqa: PU001
        t_type2, _ = classify_segment_thermal_type(df2[self._temp_axis])  # noqa: PU001
        seg1 = SegmentDTA(
            df=df1,
            plotter=self._plotter,
            index=self.index,
            thermal_type=t_type1,
            color=self._plotter.resolve_segment_color(t_type1),
            temp_axis=self._temp_axis,
        )
        seg2 = SegmentDTA(
            df=df2,
            plotter=self._plotter,
            index=self.index + 1,
            thermal_type=t_type2,
            color=self._plotter.resolve_segment_color(t_type2),
            temp_axis=self._temp_axis,
        )
        return seg1, seg2

    def set_visible_all(self, visible: bool) -> None:
        for curve in self.curves.values():
            curve.set_visible(bool(visible))

    def set_axes(self, xaxis: str, yaxis: str) -> None:
        target_y = yaxis if yaxis in self._df else self.y_col
        self.y_col = target_y
        self.channel_name = target_y
        self._xaxis = xaxis
        for curve in self.curves.values():
            curve.sync_curve_axes(xaxis)
        self.set_data(self._df[xaxis], self._df[target_y])
        self.dy = 0.0

    def remove(self, redraw: bool = False) -> None:
        _ = redraw
        for curve in list(self.curves.values()):
            curve.detach_all()
        self._plotter.on_remove()


class Peak:
    ann: MyAnn
    area: Any

    def __init__(
        self,
        segment: CurveSegment,
        t1: float,
        t2: float,
        baseline_type: int = 0,
    ) -> None:
        self.ann = None  # type: ignore[assignment]
        self.onset_lines: list[OnsetLine] = []
        self.segment = segment
        self.temp_axis = segment.temp_axis
        self.baseline_type = baseline_type
        self._visible = True
        self._picked = False
        self._color = to_qcolor(segment.get_color())
        xaxis = segment.xaxis

        seg_x = self.segment.get_xdata()
        self.i1 = find_nearest(seg_x, t1)
        self.i2 = find_nearest(seg_x, t2)
        if self.i1 > self.i2:
            self.i1, self.i2 = self.i2, self.i1

        self.t1_time = float(self.segment.df["Time"][self.i1])
        self.t2_time = float(self.segment.df["Time"][self.i2])

        y_col = self.segment.channel_name
        self.df: SegmentTable = {
            "Time": self.segment.df["Time"][self.i1 : self.i2 + 1].copy(),
            "DTA": self.segment.df[y_col][self.i1 : self.i2 + 1].copy(),
            self.temp_axis: self.segment.df[self.temp_axis][
                self.i1 : self.i2 + 1
            ].copy(),
        }
        self.df_baseline: SegmentTable = {
            "Time": self.df["Time"].copy(),
            self.temp_axis: self.df[self.temp_axis].copy(),
        }

        base_curve = make_peakbaseline(
            baselinetype=baseline_type,
            i1=self.i1,
            i2=self.i2,
            xdata=self.segment.df["Time"].tolist(),
            ydata=self.segment.df[y_col].tolist(),
        )
        baseline = base_curve.values
        self.baseline_time_expr = base_curve.expr
        self.baseline_temp_expr = baseline_temp(
            data_temp=self.df[self.temp_axis],
            data_dta=baseline,
        )
        self.df_baseline["DTA"] = np.asarray(baseline, dtype=float)

        signed_integral = float(
            np.trapezoid(self.df["DTA"] - self.df_baseline["DTA"], self.df["Time"])
        )
        self.peak_exo = 1 if signed_integral >= 0.0 else 0
        self.peak_effect = int(
            bool(self.peak_exo) == bool(self.segment.plotter.measurement_exo)
        )

        self._y_shift: float = 0.0
        x_init = self.df[xaxis]
        self.top_curve = pg.PlotCurveItem(
            x_init, self.df["DTA"].copy(), pen=pg.mkPen(self._color, width=1.4)
        )
        self.base_curve = pg.PlotCurveItem(
            x_init,
            self.df_baseline["DTA"].copy(),
            pen=pg.mkPen(self._color, width=1.2, style=QtCore.Qt.PenStyle.DashLine),
        )
        self.fill_item = pg.FillBetweenItem(
            self.top_curve, self.base_curve, brush=self._make_brush()
        )
        self.vb: pg.ViewBox | None = None

        self.label_enabled = True
        diff_curve = self.df["DTA"] - self.df_baseline["DTA"]
        dev = np.abs(diff_curve)
        peak_rel_i = int(np.argmax(dev)) if len(dev) > 0 else 0
        self.t_peak = float(self.df["Time"][peak_rel_i])
        self.temp_peak = float(self.df[self.temp_axis][peak_rel_i])
        self.peak_height = float(diff_curve[peak_rel_i]) if len(diff_curve) > 0 else 0.0
        half_max = 0.5 * float(dev[peak_rel_i]) if len(dev) > 0 else 0.0
        above_half = self.df[self.temp_axis][dev >= half_max]
        self.fwhm_temp = float(np.ptp(above_half)) if len(above_half) >= 2 else 0.0

        dx_t = np.diff(self.df["Time"])
        trap_steps = 0.5 * (dev[:-1] + dev[1:]) * np.abs(dx_t)
        cum_int = np.concatenate((np.array([0.0]), np.cumsum(trap_steps)))
        total_int = float(cum_int[-1]) if len(cum_int) > 0 else 0.0  # noqa: MI001
        self.conversion_alpha = (
            np.clip(cum_int / total_int, 0.0, 1.0)
            if total_int > 1e-12
            else np.linspace(0.0, 1.0, len(dev))
        )
        half_i = (
            int(np.argmin(np.abs(self.conversion_alpha - 0.5)))
            if len(self.conversion_alpha) > 0
            else 0
        )
        self.temp_half = float(self.df[self.temp_axis][half_i])
        self.conversion_rate = derivative_data(self.df["Time"], self.conversion_alpha)
        self.asymmetry_a3 = estimate_fraser_suzuki_asymmetry(
            self.df[self.temp_axis], dev, peak_rel_i
        )
        self.tg_metrics = compute_glass_transition_metrics(
            self.segment.df[self.temp_axis],
            self.segment.df[y_col],
            self.i1,
            self.i2,
        )
        self.melting_metrics = compute_melting_range_and_tau_metrics(
            self.df["Time"],
            self.df[self.temp_axis],
            dev,
            peak_rel_i,
        )

        y_vals = self.df["DTA"]
        self.delta_y = (
            float(y_vals[-1] - y_vals[0])  # noqa: MI001
            if len(y_vals) >= 2
            else 0.0
        )
        mass_mg_val = self.segment.plotter.sample_mass_mg
        y_u = (
            self.segment.plotter.get_units(y_col)
            if y_col in self.segment.plotter.units
            else ""
        )
        self.delta_mass_mg: float | None = (
            float(mass_mg_val) * self.delta_y / 100.0
            if (
                mass_mg_val is not None
                and mass_mg_val > 0.0
                and y_col == "Mass"
                and "%" in y_u
            )
            else None
        )
        self.show_delta_y_in_label = False

        sign_factor = 2 * self.peak_effect - 1
        mass_mg = self.segment.plotter.sample_mass_mg
        self.area = format_peak_quantity(
            raw_integral_min=signed_integral,
            y_unit_raw=y_u,
            sign_factor=sign_factor,
            mass_mg=mass_mg,
        )

        self.sync_mass_start_pct: float | None = None
        self.sync_mass_change_pct: float | None = None
        self.sync_mass_change_mg: float | None = None
        self.effect_per_reacted_mass: Any = None
        if "Mass" in self.segment.df:
            m_slice = self.segment.df["Mass"][self.i1 : self.i2 + 1]
            if len(m_slice) >= 2:
                m_start = float(m_slice[0])  # noqa: MI001
                m_end = float(m_slice[-1])  # noqa: MI001
                dm_pct = m_end - m_start
                self.sync_mass_start_pct = m_start
                self.sync_mass_change_pct = dm_pct
                if mass_mg is not None and mass_mg > 0.0:
                    dm_mg = float(mass_mg) * dm_pct / 100.0
                    self.sync_mass_change_mg = dm_mg
                    if abs(dm_mg) > 1e-4:
                        self.effect_per_reacted_mass = format_peak_quantity(
                            raw_integral_min=signed_integral,
                            y_unit_raw=y_u,
                            sign_factor=sign_factor,
                            mass_mg=abs(dm_mg),
                        )

        self.anni = len(self.df_baseline[xaxis]) // 2
        x_ann = float(self.df_baseline[xaxis][self.anni])
        y_ann = float(self.df_baseline["DTA"][self.anni])
        self.ann = MyAnn(
            parent=self,
            text=self.format_label_text(),
            xy=(x_ann, y_ann),
            xytext=(x_ann, y_ann),
        )
        self.set_data(xaxis)
        self.shifty(self.segment.dy)

    def _make_brush(self) -> QtGui.QBrush:
        alpha = 95 if self._picked else 45
        return pg.mkBrush(
            self._color.red(), self._color.green(), self._color.blue(), alpha
        )

    def attach_to(self, vb: pg.ViewBox) -> None:
        self.vb = vb
        vb.addItem(self.fill_item)
        vb.addItem(self.base_curve)
        vb.addItem(self.top_curve)
        self.ann.attach_to(vb)

    def detach(self) -> None:
        if self.vb is not None:
            self.vb.removeItem(self.fill_item)
            self.vb.removeItem(self.base_curve)
            self.vb.removeItem(self.top_curve)
            self.vb = None
        self.ann.detach()

    def format_label_text(self) -> str:
        if not self.label_enabled:
            return ""
        if self.show_delta_y_in_label:
            y_ch = self.segment.channel_name
            y_u = (
                self.segment.plotter.get_units(y_ch)
                if y_ch in self.segment.plotter.units
                else ""
            )
            base_s = f"Δ{y_ch}: {self.delta_y:+.3f} {y_u}".strip()
            if self.delta_mass_mg is not None:
                return f"{base_s} ({self.delta_mass_mg:+.3f} мг)"
            return base_s
        t_unit = self.segment.plotter.get_units(self.temp_axis)
        area_s = str(self.area).replace(" / ", "/")
        return f"Площадь: {area_s} (Tp: {self.temp_peak:.1f} {t_unit})"

    def _sync_curves(self, xaxis: str | None = None) -> None:
        ax_key = xaxis if xaxis is not None else self.segment.xaxis
        x_arr = self.df[ax_key]
        self.top_curve.setData(
            x_arr, self.df["DTA"] - self._y_shift, skipFiniteCheck=True
        )
        self.base_curve.setData(
            x_arr, self.df_baseline["DTA"] - self._y_shift, skipFiniteCheck=True
        )

    def shifty(self, dy: float) -> None:
        if dy != 0.0:
            self._y_shift += dy
            self._sync_curves()
            self.ann.shifty(dy)
            for line in self.onset_lines:
                line.shifty(dy)

    def onset(self, t1: float, t2: float, is_onset: bool) -> OnsetLine:
        xaxis = self.segment.xaxis
        baseline_expr = (
            self.baseline_time_expr if xaxis == "Time" else self.baseline_temp_expr
        )
        data_ddta = derivative_data(self.df[xaxis], self.df["DTA"])
        onset_idx = calc_peakonset(
            t1=t1,
            t2=t2,
            data_t=self.df[xaxis],
            data_dta=self.df["DTA"],
            data_ddta=data_ddta,
            expr_baseline=baseline_expr,
            is_onset=is_onset,
            peak_exo=self.peak_exo,
        )
        line = OnsetLine(
            peak=self,
            ci=onset_idx.tangent_idx,
            bi=onset_idx.baseline_idx,
            is_onset=is_onset,
        )
        self.onset_lines.append(line)
        if self.vb is not None:
            line.attach_to(self.vb)
        return line

    def remove(self, redraw: bool = False) -> None:
        _ = redraw
        if self in self.segment.peaks:
            self.segment.peaks.remove(self)
        if self in self.segment.plotter.items:
            self.segment.plotter.items.remove(self)
        if self.ann in self.segment.plotter.items:
            self.segment.plotter.items.remove(self.ann)
        for line in list(self.onset_lines):
            line.remove(exclude_from_list=False)
        self.onset_lines.clear()
        self.detach()

    def get_visible(self) -> bool:
        return self._visible

    def set_visible(self, b: bool) -> None:
        self._visible = bool(b)
        self.fill_item.setVisible(self._visible)
        self.base_curve.setVisible(self._visible)
        self.top_curve.setVisible(self._visible)
        self.ann.set_visible(self._visible)
        for line in self.onset_lines:
            line.set_visible(self._visible)

    def set_data(self, xaxis: str) -> None:
        self._sync_curves(xaxis)
        self.ann.updateXdata(xaxis)
        for line in self.onset_lines:
            line.updateXdata(xaxis)

    def setPickEffect(self, active: bool) -> None:
        self._picked = bool(active)
        w = 2.6 if self._picked else 1.4
        self.top_curve.setPen(pg.mkPen(self._color, width=w))
        self.base_curve.setPen(
            pg.mkPen(self._color, width=w, style=QtCore.Qt.PenStyle.DashLine)
        )
        self.fill_item.setBrush(self._make_brush())

    def set_edgecolor(self, color: Any) -> None:
        self._color = to_qcolor(color)
        self.setPickEffect(self._picked)
        if self.ann is not None:
            self.ann.set_color(color)
        for line in self.onset_lines:
            line.set_color(color)

    def hit_test(self, scene_pos: QtCore.QPointF) -> bool:
        if not self._visible or self.vb is None:
            return False
        pt = self.vb.mapSceneToView(scene_pos)
        x_arr = self.df[self.segment.xaxis]
        if len(x_arr) < 2:
            return False
        x_lo, x_hi = float(np.min(x_arr)), float(np.max(x_arr))
        if not (x_lo <= pt.x() <= x_hi):
            return False
        idx = find_nearest(x_arr, pt.x())
        y_top = float(self.df["DTA"][idx]) - self._y_shift
        y_bot = float(self.df_baseline["DTA"][idx]) - self._y_shift
        vr = self.vb.viewRect()
        tol = max(1e-9, vr.height() * 0.025)
        return (min(y_top, y_bot) - tol) <= pt.y() <= (max(y_top, y_bot) + tol)


class OnsetLine(_BaseCurveItem):
    xb: float

    def __init__(self, peak: Peak, ci: int, bi: int, is_onset: bool) -> None:
        self.peak = peak
        self.temp_axis = peak.temp_axis
        self.label_enabled = True
        self.label_dta_enabled = False
        self.is_onset = is_onset
        xaxis = peak.segment.xaxis
        self.label_time_enabled = xaxis == "Time"
        self.label_temp_enabled = not self.label_time_enabled
        self.ci = ci
        self.bi = bi
        self.info: dict[str, float] = {
            self.temp_axis: float(self.peak.df_baseline[self.temp_axis][bi]),
            "Time": round(float(self.peak.df_baseline["Time"][bi]), 5),
            "DTA": round(float(self.peak.df_baseline["DTA"][bi]), 5),
        }
        self.units: dict[str, str] = {
            self.temp_axis: self.peak.segment.plotter.get_units(self.temp_axis),
            "Time": self.peak.segment.plotter.get_units("Time"),
            "DTA": self.peak.segment.plotter.get_units(self.peak.segment.channel_name),
        }
        x_b = self.info[xaxis]
        x_c = float(self.peak.df[xaxis][ci])
        y_b = self.info["DTA"]
        y_c = float(self.peak.df["DTA"][ci])
        self.xb = x_b
        self.t = "Начало" if is_onset else "Конец"
        self.ann: MyAnn = None  # type: ignore[assignment]
        super().__init__(
            xdata=np.array([x_b, x_c], dtype=float),
            ydata=np.array([y_b, y_c], dtype=float),
            color=self.peak.segment.get_color(),
            lw=1.8,
        )
        xy = (x_b, y_b)
        self.ann = MyAnn(
            parent=self,
            text=f"{self.t}: {round(x_b, 3)} {self.units[xaxis]}",
            xy=xy,
            xytext=xy,
        )
        self.shifty(self.peak.segment.dy)

    def attach_to(self, vb: pg.ViewBox) -> None:
        super().attach_to(vb)
        self.ann.attach_to(vb)

    def detach(self) -> None:
        super().detach()
        self.ann.detach()

    def shifty(self, dy: float) -> None:
        self.set_ydata(self.get_ydata() - dy)
        self.ann.shifty(dy)

    def updateXdata(self, xaxis: str) -> None:
        self.xb = self.info[xaxis]
        xc = float(self.peak.df[xaxis][self.ci])
        yb = float(self.peak.df_baseline["DTA"][self.bi]) - self.peak._y_shift
        yc = float(self.peak.df["DTA"][self.ci]) - self.peak._y_shift
        self.set_data([self.xb, xc], [yb, yc])
        self.ann.updateXdata(xaxis)

    def set_visible(self, b: bool) -> None:
        self.ann.set_visible(b)
        super().set_visible(b)

    def remove(
        self,
        redraw: bool = False,
        exclude_from_list: bool = True,
    ) -> None:
        _ = redraw
        if exclude_from_list and self in self.peak.onset_lines:
            self.peak.onset_lines.remove(self)
        if self in self.peak.segment.plotter.items:
            self.peak.segment.plotter.items.remove(self)
        if self.ann in self.peak.segment.plotter.items:
            self.peak.segment.plotter.items.remove(self.ann)
        self.detach()

    def set_color(self, color: Any) -> None:
        if self.ann is not None:
            self.ann.set_color(color)
        super().set_color(color)


class MyAnn:
    """Перетаскиваемая подпись пика или онсета с соединительной линией на PyQtGraph."""

    def __init__(
        self,
        parent: Peak | OnsetLine,
        text: str,
        xy: tuple[float, float],
        xytext: tuple[float, float],
    ) -> None:
        self.parent = parent
        color = (
            parent.segment.get_color()
            if isinstance(parent, Peak)
            else parent.peak.segment.get_color()
        )
        self._color = to_qcolor(color)
        self._text = text
        self.xy = (float(xy[0]), float(xy[1]))  # noqa: MI001
        self._pos = (float(xytext[0]), float(xytext[1]))  # noqa: MI001
        self._visible = True
        self.text_item = pg.TextItem(
            text=self._text, color=self._color, anchor=(0.5, 1.0)
        )
        self.text_item.setPos(*self._pos)
        self.leader_line = pg.PlotCurveItem(
            [self.xy[0], self._pos[0]],  # noqa: MI001
            [self.xy[1], self._pos[1]],  # noqa: MI001
            pen=pg.mkPen(self._color, width=0.9),
        )
        self.vb: pg.ViewBox | None = None

    def attach_to(self, vb: pg.ViewBox) -> None:
        self.vb = vb
        vb.addItem(self.leader_line)
        vb.addItem(self.text_item)

    def detach(self) -> None:
        if self.vb is not None:
            self.vb.removeItem(self.leader_line)
            self.vb.removeItem(self.text_item)
            self.vb = None

    def _sync_leader(self) -> None:
        self.text_item.setPos(*self._pos)
        self.leader_line.setData(
            np.array([self.xy[0], self._pos[0]], dtype=float),  # noqa: MI001
            np.array([self.xy[1], self._pos[1]], dtype=float),  # noqa: MI001
            skipFiniteCheck=True,
        )

    def set_position(self, pos: tuple[float, float]) -> None:
        self._pos = (float(pos[0]), float(pos[1]))  # noqa: MI001
        self._sync_leader()

    def set_text(self, text: str) -> None:
        self._text = str(text)
        self.text_item.setText(self._text, color=self._color)

    def shifty(self, dy: float) -> None:
        self.xy = (self.xy[0], self.xy[1] - dy)  # noqa: MI001
        self._pos = (self._pos[0], self._pos[1] - dy)  # noqa: MI001
        self._sync_leader()

    def updateXdata(self, xaxis: str | None = None) -> None:
        if isinstance(self.parent, OnsetLine):
            xb = self.parent.xb
        else:
            axis_key = xaxis if xaxis is not None else self.parent.segment.xaxis
            xb = float(self.parent.df_baseline[axis_key][self.parent.anni])
        self.xy = (xb, self.xy[1])  # noqa: MI001
        self._pos = (xb, self._pos[1])  # noqa: MI001
        self._sync_leader()

    def set_visible(self, b: bool) -> None:
        self._visible = bool(b)
        self.text_item.setVisible(self._visible)
        self.leader_line.setVisible(self._visible)

    def setPickEffect(self, _active: bool) -> None:
        pass

    def set_color(self, color: Any) -> None:
        self._color = to_qcolor(color)
        self.text_item.setColor(self._color)
        self.leader_line.setPen(pg.mkPen(self._color, width=0.9))

    def hit_test(self, scene_pos: QtCore.QPointF) -> bool:
        if not self._visible or not self._text:
            return False
        local_pt = self.text_item.mapFromScene(scene_pos)
        return bool(self.text_item.boundingRect().contains(local_pt))
