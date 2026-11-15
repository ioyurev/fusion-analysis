from __future__ import annotations

import importlib.resources
from typing import TYPE_CHECKING

from fusion_common import resolve_ui_icon
from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

from fusion_analysis.measurement_data import (
    ThermalType,
    classify_segment_thermal_type,
)
from fusion_analysis.segment import (
    CurveSegment,
    OnsetLine,
    Peak,
    SegmentDTA,
)
from fusion_analysis.segment_properties_window import (
    OnsetPropertiesWindow,
    PeakPropertiesWindow,
    SegmentPropertiesWindow,
)


def load_asset_icon(filename: str, size: int = 32) -> QtGui.QIcon:
    """Рендерит векторную SVG-иконку из assets/ с адаптацией currentColor к светлой и тёмной теме."""
    stem = filename.removesuffix(".png").removesuffix(".svg")
    svg_text = (
        importlib.resources.files("fusion_analysis")
        .joinpath(f"assets/{stem}.svg")
        .read_text(encoding="utf-8")
    )
    is_dark = (
        QtGui.QGuiApplication.styleHints().colorScheme() == QtCore.Qt.ColorScheme.Dark
    )
    fg_hex = "#F1F5F9" if is_dark else "#1E293B"
    themed_svg = svg_text.replace("currentColor", fg_hex)

    img = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(img)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(themed_svg.encode("utf-8")))
    renderer.render(painter, QtCore.QRectF(0, 0, size, size))
    painter.end()
    return QtGui.QIcon(QtGui.QPixmap.fromImage(img))


if TYPE_CHECKING:
    from fusion_analysis.plotter import Selector


def update_child_items_state(item: QtWidgets.QTreeWidgetItem) -> None:
    parent_state = item.checkState(0)
    for i in range(item.childCount()):
        child_item = item.child(i)
        if child_item is not None:
            child_item.setCheckState(0, parent_state)
            update_child_items_state(child_item)


class MySpinBox(QtWidgets.QDoubleSpinBox):
    selector: Selector | None = None

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.valueChanged.connect(self.handle_value_changed)

    def handle_value_changed(self, x: float) -> None:
        if self.isVisible() and self.selector is not None:
            self.selector.set_x(x=x, update_spinbox_value=False)

    def setValue(self, val: float, block_signal: bool = False) -> None:  # type: ignore[override]
        if block_signal:
            self.blockSignals(True)
            super().setValue(val)
            self.blockSignals(False)
        else:
            super().setValue(val)


class RemoveAction(QtGui.QAction):
    obj: CurveSegment | Peak | OnsetLine | None = None
    signal_removed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.EditDelete,
                QtWidgets.QStyle.StandardPixmap.SP_TrashIcon,
            ),
            "Удалить",
            parent,
        )
        self.triggered.connect(self.remove_object)

    def remove_object(self) -> None:
        if self.obj is not None:
            self.obj.remove(redraw=True)
            self.signal_removed.emit()


class PropertiesAction(QtGui.QAction):
    obj: CurveSegment | Peak | OnsetLine | None = None
    signal_prop_applied = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.DocumentProperties,
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
            "Свойства",
            parent,
        )
        self.triggered.connect(self.show_window)

    def show_window(self) -> None:
        match self.obj:
            case CurveSegment():
                w_seg = SegmentPropertiesWindow(self.obj)
                res_seg = w_seg.exec()
                if (
                    res_seg == QtWidgets.QDialog.DialogCode.Accepted
                    and w_seg.changes_are_made
                ):
                    self.obj.set_color(
                        (
                            w_seg.color.red() / 255.0,
                            w_seg.color.green() / 255.0,
                            w_seg.color.blue() / 255.0,
                        )
                    )
                    self.signal_prop_applied.emit()
            case Peak():
                w_peak = PeakPropertiesWindow(self.obj)
                res_peak = w_peak.exec()
                if (
                    res_peak == QtWidgets.QDialog.DialogCode.Accepted
                    and w_peak.changes_are_made
                ):
                    self.obj.label_enabled = w_peak.checkbox_label.isChecked()
                    self.obj.show_delta_y_in_label = (
                        w_peak.checkbox_delta_mode.isChecked()
                    )
                    if self.obj.ann is not None:
                        self.obj.ann.set_text(self.obj.format_label_text())
                    self.signal_prop_applied.emit()
            case OnsetLine():
                w_on = OnsetPropertiesWindow(onsetline=self.obj)
                res_on = w_on.exec()
                if (
                    res_on == QtWidgets.QDialog.DialogCode.Accepted
                    and w_on.changes_are_made
                ):
                    label = f"{self.obj.t}: " if self.obj.label_enabled else ""
                    label_time = (
                        f"{self.obj.info['Time']} {self.obj.units['Time']}"
                        if self.obj.label_time_enabled
                        else ""
                    )
                    if self.obj.label_temp_enabled:
                        t_val = round(self.obj.info[self.obj.temp_axis], 3)
                        t_unit = self.obj.units[self.obj.temp_axis]
                        label_temp = f"{t_val} {t_unit}"
                        if self.obj.label_time_enabled:
                            label_temp = f", {label_temp}"
                    else:
                        label_temp = ""
                    if self.obj.label_dta_enabled:
                        label_dta = f"{self.obj.info['DTA']} {self.obj.units['DTA']}"
                        if self.obj.label_temp_enabled or self.obj.label_time_enabled:
                            label_dta = f", {label_dta}"
                    else:
                        label_dta = ""
                    self.obj.ann.set_text(f"{label}{label_time}{label_temp}{label_dta}")
                    self.signal_prop_applied.emit()


class SegmentItem(QtWidgets.QTreeWidgetItem):
    artist: SegmentDTA

    def __init__(
        self,
        parent: QtWidgets.QTreeWidget,
        artist: SegmentDTA,
    ) -> None:
        super().__init__(parent)
        self.artist = artist
        self.refresh_icon()
        self.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked
            if artist.get_visible()
            else QtCore.Qt.CheckState.Unchecked,
        )
        _, label_text = classify_segment_thermal_type(  # noqa: PU001
            artist.df[artist.temp_axis]
        )
        self.setText(0, f"Сегмент {artist.index}: {label_text}")

    def refresh_icon(self) -> None:
        if self.artist.thermal_type == ThermalType.HEAT:
            self.setIcon(0, load_asset_icon("icon_heat.svg"))
        elif self.artist.thermal_type == ThermalType.COOL:
            self.setIcon(0, load_asset_icon("icon_cool.svg"))
        elif self.artist.thermal_type == ThermalType.ISOTHERMAL:
            self.setIcon(0, load_asset_icon("icon_isothermal.svg"))


class CurveItem(QtWidgets.QTreeWidgetItem):
    artist: CurveSegment

    def __init__(self, parent: SegmentItem, curve: CurveSegment) -> None:
        super().__init__(parent)
        self.artist = curve
        self.refresh_icon()
        self.setText(0, curve.channel_name)
        self.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked
            if curve.get_visible()
            else QtCore.Qt.CheckState.Unchecked,
        )

    def refresh_icon(self) -> None:
        icon_name = "derivative.svg" if self.artist.is_derivative else "smooth.svg"
        self.setIcon(0, load_asset_icon(icon_name))


class PeakItem(QtWidgets.QTreeWidgetItem):
    artist: Peak

    def __init__(self, parent: CurveItem | SegmentItem, peak: Peak) -> None:
        super().__init__(parent)
        self.artist = peak
        self.refresh_icon()
        self.setText(0, f"Пик (Tp={peak.temp_peak:.1f})")
        self.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked
            if peak.get_visible()
            else QtCore.Qt.CheckState.Unchecked,
        )

    def refresh_icon(self) -> None:
        self.setIcon(0, load_asset_icon("peak.svg"))


class OnsetItem(QtWidgets.QTreeWidgetItem):
    artist: OnsetLine

    def __init__(self, parent: PeakItem, onset_line: OnsetLine) -> None:
        super().__init__(parent)
        self.artist = onset_line
        self.refresh_icon()
        t_val = onset_line.info.get(onset_line.temp_axis, 0.0)
        self.setText(0, f"{onset_line.t}: {t_val:.1f}")
        self.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked
            if onset_line.get_visible()
            else QtCore.Qt.CheckState.Unchecked,
        )

    def refresh_icon(self) -> None:
        self.setIcon(
            0,
            load_asset_icon("onset.svg" if self.artist.is_onset else "end.svg"),
        )
