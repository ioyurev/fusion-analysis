from PySide6 import QtWidgets, QtGui
from .ui.Config import Ui_Dialog


class ConfigWindow(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, config: dict, parent=None):
        self.config = config.copy()
        super().__init__(parent)
        self.setupUi(self)
        self.setFixedWidth(self.width())
        self.setFixedHeight(self.height())
        self.changes_are_made = False
        color = QtGui.QColor(
            *[255 * n for n in self.config["Plotter"]["default_heat_color"]]
        ).name()
        self.w_color_heat.setStyleSheet(f"""background-color: {color};""")
        color = QtGui.QColor(
            *[255 * n for n in self.config["Plotter"]["default_cool_color"]]
        ).name()
        self.w_color_cool.setStyleSheet(f"""background-color: {color};""")
        self.checkbox_autocolor.setChecked(self.config["Plotter"]["autocolor"])
        self.checkbox_autocolor.stateChanged.connect(self.change_autocolor)
        self.btn_color_heat.clicked.connect(
            lambda: self.change_color(w_color=self.w_color_heat, k="default_heat_color")
        )
        self.btn_color_cool.clicked.connect(
            lambda: self.change_color(w_color=self.w_color_cool, k="default_cool_color")
        )

    def change_color(self, w_color: QtWidgets.QWidget, k: str):
        w = QtWidgets.QColorDialog(self)
        color = w.getColor()
        if color.isValid():
            self.setWindowTitle(f"{self.windowTitle()} *")
            self.color = color
            w_color.setStyleSheet(f"background-color: {color.name()};")
            self.config["Plotter"][k] = [
                color.red() / 255,
                color.green() / 255,
                color.blue() / 255,
            ]
            self.set_changed()

    def change_autocolor(self, state):
        self.config["Plotter"]["autocolor"] = self.checkbox_autocolor.isChecked()
        self.set_changed()

    def set_changed(self):
        if not self.changes_are_made:
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")
