from PySide6 import QtGui, QtWidgets, QtCore
from Segment import Segment, Peak, OnsetLine
from PropertiesWindows import SegmentPropetiesWindow

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
            # print(result)