from PySide6 import QtWidgets, QtGui, QtCore
from app.Plotter import Selector
from app.Segment import SegmentDTA, Peak, OnsetLine
from app.PropertiesWindows import (
    SegmentPropetiesWindow,
    PeakPropertiesWindow,
    OnsetPropertiesWindow,
)
from app.libfusiondata import ThermalType


def update_child_items_state(item: QtWidgets.QTreeWidgetItem):
    # Получаем состояние родительского элемента
    parent_state = item.checkState(0)
    # Устанавливаем состояние для всех вложенных элементов
    for i in range(item.childCount()):
        child_item = item.child(i)
        child_item.setCheckState(0, parent_state)
        # Рекурсивно вызываем функцию для вложенных элементов
        update_child_items_state(child_item)


class MySpinBox(QtWidgets.QDoubleSpinBox):
    selector: Selector

    def __init__(self, parent: QtWidgets.QWidget | None = ...) -> None:
        super().__init__(parent)
        self.valueChanged.connect(self.handle_value_changed)

    def handle_value_changed(self, x: float):
        if self.isVisible():
            self.selector.set_x(x=x, update_spinbox_value=False)

    def setValue(self, val: float, block_signal: bool = False):
        if block_signal:
            self.blockSignals(True)
            super().setValue(val)
            self.blockSignals(False)
        else:
            super().setValue(val)


class RemoveAction(QtGui.QAction):
    obj: SegmentDTA | Peak | OnsetLine = None

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__("Удалить", parent)
        self.triggered.connect(lambda: self.obj.remove(redraw=True))


class PropertiesAction(QtGui.QAction):
    obj: SegmentDTA | Peak | OnsetLine = None
    signal_prop_applied = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__("Свойства", parent)
        self.triggered.connect(self.show_window)

    def show_window(self):
        match self.obj:
            case SegmentDTA():
                w = SegmentPropetiesWindow(self.obj)
                result = w.exec()
                if result == QtWidgets.QDialog.Accepted and w.changes_are_made:
                    self.obj.set_color(
                        (
                            w.color.red() / 255,
                            w.color.green() / 255,
                            w.color.blue() / 255,
                        )
                    )
                    self.signal_prop_applied.emit()
                elif result == QtWidgets.QDialog.Rejected:
                    pass
                else:
                    raise RuntimeError("Непрерудсмотренное значение")
            case Peak():
                w = PeakPropertiesWindow(self.obj)
                w.checkbox_label.setChecked(self.obj.label_enabled)
                result = w.exec()
                if result == QtWidgets.QDialog.Accepted and w.changes_are_made:
                    self.obj.label_enabled = w.checkbox_label.isChecked()
                    if self.obj.label_enabled:
                        label = "Площадь: "
                    else:
                        label = ""
                    self.obj.ann.set_text(f"{label}{self.obj.area}")
                    self.signal_prop_applied.emit()
                elif result == QtWidgets.QDialog.Rejected:
                    pass
            case OnsetLine():
                w = OnsetPropertiesWindow(onsetline=self.obj)
                result = w.exec()
                if result == QtWidgets.QDialog.Accepted and w.changes_are_made:
                    if self.obj.label_enabled:
                        label = f"{self.obj.t}: "
                    else:
                        label = ""
                    if self.obj.label_time_enabled:
                        label_time = f"{self.obj.info['Time']} {self.obj.units['Time']}"
                    else:
                        label_time = ""
                    if self.obj.label_temp_enabled:
                        label_temp = f"{self.obj.info[self.obj.temp_axis]} {self.obj.units[self.obj.temp_axis]}"
                        if self.obj.label_time_enabled:
                            label_temp = f", {label_temp}"
                    else:
                        label_temp = ""
                    if self.obj.label_dta_enabled:
                        label_dta = f"{self.obj.info['DTA']} {self.obj.units['DTA']}"
                        if self.obj.label_temp_enabled:
                            label_dta = f", {label_dta}"
                    else:
                        label_dta = ""
                    self.obj.ann.set_text(f"{label}{label_time}{label_temp}{label_dta}")
                    self.signal_prop_applied.emit()
                elif result == QtWidgets.QDialog.Rejected:
                    pass
        del w


class SegmentItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent: QtWidgets.QListWidget, artist: SegmentDTA):
        super().__init__(parent)
        self.artist = artist
        if artist.thermal_type == ThermalType.HEAT:
            self.setIcon(0, QtGui.QIcon(":/icon_heat.png"))
        elif artist.thermal_type == ThermalType.COOL:
            self.setIcon(0, QtGui.QIcon(":/icon_cool.png"))
        elif artist.thermal_type == ThermalType.ISOTHERMAL:
            self.setIcon(0, QtGui.QIcon(":/icon_isothermal.png"))
        self.setCheckState(0, QtCore.Qt.CheckState.Checked)
        t1 = round(artist.df[artist.temp_axis].values[0])
        t2 = round(artist.df[artist.temp_axis].values[-1])
        self.setText(0, f"{t1} - {t2}")


class DTAItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent: SegmentItem):
        super().__init__(parent)
        self.setText(0, "DTA")
        self.setCheckState(0, QtCore.Qt.Checked)
        self.artist = parent.artist


class MassItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent: SegmentItem):
        super().__init__(parent)
        self.setText(0, "Mass")
        self.setCheckState(0, QtCore.Qt.Checked)
        self.artist = parent.artist.mass_segment


class TempItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent: SegmentItem):
        super().__init__(parent)
        self.setText(0, "Temp.")
        self.setCheckState(0, QtCore.Qt.Checked)
        self.artist = parent.artist.temp_segment
