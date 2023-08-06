from PySide6 import QtWidgets, QtGui, QtCore
from Plotter import Selector
from Segment import Segment, Peak, OnsetLine
from PropertiesWindows import SegmentPropetiesWindow, PeakPropertiesWindow

class MySpinBox(QtWidgets.QDoubleSpinBox):
    selectors: list[Selector] = []
    def __init__(self, parent: QtWidgets.QWidget | None = ...) -> None:
        super().__init__(parent)
        self.valueChanged.connect(self.handle_value_changed)

    def handle_value_changed(self, x: float):
        if self.isVisible():
            self.selectors[0].set_x(x=x, update_spinbox_value=False)
            self.selectors[1].set_x(x=x, update_spinbox_value=False)

    def setValue(self, val: float, block_signal: bool = False):
        if block_signal:
            self.blockSignals(True)
            super().setValue(val)
            self.blockSignals(False)
        else:
            super().setValue(val)

class RemoveAction(QtGui.QAction):
    obj: Segment | Peak | OnsetLine = None

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__('Удалить', parent)
        self.triggered.connect(lambda: self.obj.remove(redraw=True))

class PropertiesAction(QtGui.QAction):
    obj: Segment | Peak | OnsetLine = None
    signal_prop_applied = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__('Свойства', parent)
        self.triggered.connect(self.show_window)        

    def show_window(self):
        if isinstance(self.obj, Segment):
            w = SegmentPropetiesWindow(self.obj)
            result = w.exec()
            if result == QtWidgets.QDialog.Accepted and w.changes_are_made:
                self.obj.set_color((
                    w.color.red()/255,
                    w.color.green()/255,
                    w.color.blue()/255
                ))
                self.signal_prop_applied.emit()
            elif result == QtWidgets.QDialog.Rejected:
                pass
            else:
                raise RuntimeError("Непрерудсмотренное значение")
        elif isinstance(self.obj, Peak):
            w = PeakPropertiesWindow(self.obj)
            w.checkbox_label.setChecked(self.obj.label_enabled)
            result = w.exec()
            if result == QtWidgets.QDialog.Accepted and w.changes_are_made:
                self.obj.label_enabled = w.checkbox_label.isChecked()
                if self.obj.label_enabled:
                    label = 'Площадь: '
                else:
                    label = ''
                self.obj.ann.set_text(f'{label}{self.obj.area}')
                self.signal_prop_applied.emit()
            elif result == QtWidgets.QDialog.Rejected:
                pass
        del w
