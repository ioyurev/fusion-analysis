from PySide6 import QtWidgets, QtGui, QtUiTools
from Segment import Segment, Peak
from matplotlib.colors import to_hex

Ui_SegmentDialog = QtUiTools.loadUiType('ui/SegmentProperties.ui')[0]
Ui_PeakDialog = QtUiTools.loadUiType('ui/PeakProperties.ui')[0]

class SegmentPropetiesWindow(QtWidgets.QDialog, Ui_SegmentDialog):
    btn_color: QtWidgets.QPushButton
    w_color: QtWidgets.QWidget

    def __init__(self, segment: Segment, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setFixedWidth(self.width())
        self.setFixedHeight(self.height())
        self.changes_are_made = False
        self.color = QtGui.QColor(to_hex(segment.get_color()))
        self.w_color.setStyleSheet(f'background-color: {self.color.name()};')
        self.btn_color.clicked.connect(self.change_color)

    def change_color(self):
        w = QtWidgets.QColorDialog(self)
        w.setCurrentColor(self.color)
        color = w.getColor()
        if color.isValid():
            self.changes_are_made = True
            self.setWindowTitle(f'{self.windowTitle()} *')
            self.color = color
            self.w_color.setStyleSheet(f'background-color: {self.color.name()};')

class PeakPropertiesWindow(QtWidgets.QDialog, Ui_PeakDialog):
    checkbox_label: QtWidgets.QCheckBox

    def __init__(self, peak: Peak, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setFixedWidth(self.width())
        self.setFixedHeight(self.height())
        self.changes_are_made = False
        self.checkbox_label.stateChanged.connect(self.change_label)

    def change_label(self):
        if self.changes_are_made == False:
            self.changes_are_made = True
            self.setWindowTitle(f'{self.windowTitle()} *')
