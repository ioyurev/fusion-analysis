from PySide6 import QtWidgets, QtGui
from fusion_analysis.Segment import SegmentDTA, Peak, OnsetLine
from matplotlib.colors import to_hex
from ui.OnsetProperties import Ui_Dialog as Ui_OnsetDialog
from ui.PeakProperties import Ui_Dialog as Ui_PeakDialog
from ui.SegmentProperties import Ui_Dialog as Ui_SegmentDialog


class SegmentPropetiesWindow(QtWidgets.QDialog, Ui_SegmentDialog):
    def __init__(self, segment: SegmentDTA, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setFixedWidth(self.width())
        self.setFixedHeight(self.height())
        self.changes_are_made = False
        self.color = QtGui.QColor(to_hex(segment.get_color()))
        self.w_color.setStyleSheet(f"background-color: {self.color.name()};")
        self.btn_color.clicked.connect(self.change_color)

    def change_color(self):
        w = QtWidgets.QColorDialog(self)
        w.setCurrentColor(self.color)
        color = w.getColor()
        if color.isValid():
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")
            self.color = color
            self.w_color.setStyleSheet(f"background-color: {self.color.name()};")


class PeakPropertiesWindow(QtWidgets.QDialog, Ui_PeakDialog):
    def __init__(self, peak: Peak, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setFixedWidth(self.width())
        self.setFixedHeight(self.height())
        self.changes_are_made = False
        self.checkbox_label.stateChanged.connect(self.change_label)

    def change_label(self):
        if self.changes_are_made is False:
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")


class OnsetPropertiesWindow(QtWidgets.QDialog, Ui_OnsetDialog):
    def __init__(self, onsetline: OnsetLine, parent=None):
        self.onsetline = onsetline
        super().__init__(parent)
        self.setupUi(self)
        self.setFixedWidth(self.width())
        self.setFixedHeight(self.height())
        self.changes_are_made = False
        self.checkbox_label.setChecked(self.onsetline.label_enabled)
        self.checkbox_time.setChecked(self.onsetline.label_time_enabled)
        self.checkbox_temp.setChecked(self.onsetline.label_temp_enabled)
        self.checkbox_dta.setChecked(self.onsetline.label_dta_enabled)
        self.checkbox_label.stateChanged.connect(self.change_label)
        self.checkbox_time.stateChanged.connect(self.change_label)
        self.checkbox_temp.stateChanged.connect(self.change_label)
        self.checkbox_dta.stateChanged.connect(self.change_label)
        if self.onsetline.is_onset:
            self.setWindowTitle("Свойства начала пика")
        else:
            self.setWindowTitle("Свойства конца пика")

    def change_label(self):
        if self.changes_are_made is False:
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")

    def exec(self) -> int:
        result = super().exec()
        self.onsetline.label_enabled = self.checkbox_label.isChecked()
        self.onsetline.label_time_enabled = self.checkbox_time.isChecked()
        self.onsetline.label_temp_enabled = self.checkbox_temp.isChecked()
        self.onsetline.label_dta_enabled = self.checkbox_dta.isChecked()
        return result
