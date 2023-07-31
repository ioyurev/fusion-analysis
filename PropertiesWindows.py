from PySide6 import QtWidgets, QtGui, QtUiTools
from Segment import Segment
from matplotlib.colors import to_hex

Ui_Dialog = QtUiTools.loadUiType('SegmentProperties.ui')[0]

class SegmentPropetiesWindow(QtWidgets.QDialog, Ui_Dialog):
    btn_color: QtWidgets.QPushButton
    w_color: QtWidgets.QWidget
    label_changes_made: QtWidgets.QLabel

    def __init__(self, segment: Segment, parent=None):
        # print('* загрузка интерфейса')
        super().__init__(parent)
        self.setupUi(self)
        # print(segment)
        self.changes_are_made = False
        self.color = QtGui.QColor(to_hex(segment.get_color()))
        self.w_color.setStyleSheet(f'background-color: {self.color.name()};')
        self.btn_color.clicked.connect(self.change_color)

    def change_color(self):
        w = QtWidgets.QColorDialog(self)
        # w.exec()
        w.setCurrentColor(self.color)
        color = w.getColor()
        if color.isValid():
            self.changes_are_made = True
            self.setWindowTitle(f'{self.windowTitle()} *')
            self.color = color
            # print(self.color)
            self.w_color.setStyleSheet(f'background-color: {self.color.name()};')
            
        # self.show()