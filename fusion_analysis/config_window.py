from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtGui, QtWidgets

if TYPE_CHECKING:
    from fusion_analysis.config import AnalysisConfig


def _rgb_floats_to_hex(rgb: list[float]) -> str:
    r_f, g_f, b_f, *_ = [*rgb, 0.0, 0.0, 0.0][:3]
    return QtGui.QColor(int(255 * r_f), int(255 * g_f), int(255 * b_f)).name()


class ConfigWindow(QtWidgets.QDialog):
    def __init__(
        self,
        config: AnalysisConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.config = config.model_copy(deep=True)
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(440, 200)
        self.changes_are_made = False

        grid = QtWidgets.QGridLayout(self)
        title_lbl = QtWidgets.QLabel("<b>Конфигурация по умолчанию</b>")
        grid.addWidget(title_lbl, 0, 0, 1, 4)

        self.checkbox_autocolor = QtWidgets.QCheckBox(
            "Индивидуальный цвет сегментов при открытии нового измерения"
        )
        grid.addWidget(self.checkbox_autocolor, 1, 0, 1, 4)

        self.checkbox_antialias = QtWidgets.QCheckBox(
            "Сглаживание линий графиков (антиалиазинг)"
        )
        grid.addWidget(self.checkbox_antialias, 2, 0, 1, 4)

        grid.addWidget(QtWidgets.QLabel("Цвет сегмента нагрева:"), 3, 0)
        self.w_color_heat = QtWidgets.QWidget()
        self.w_color_heat.setMinimumSize(24, 24)
        self.btn_color_heat = QtWidgets.QPushButton("Изменить")
        grid.addWidget(self.w_color_heat, 3, 1)
        grid.addWidget(self.btn_color_heat, 3, 2)

        grid.addWidget(QtWidgets.QLabel("Цвет сегмента охлаждения:"), 4, 0)
        self.w_color_cool = QtWidgets.QWidget()
        self.w_color_cool.setMinimumSize(24, 24)
        self.btn_color_cool = QtWidgets.QPushButton("Изменить")
        grid.addWidget(self.w_color_cool, 4, 1)
        grid.addWidget(self.btn_color_cool, 4, 2)
        grid.setColumnStretch(3, 1)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        grid.addWidget(btns, 5, 0, 1, 4)

        heat_hex = _rgb_floats_to_hex(self.config.Plotter.default_heat_color)
        self.w_color_heat.setStyleSheet(f"background-color: {heat_hex};")

        cool_hex = _rgb_floats_to_hex(self.config.Plotter.default_cool_color)
        self.w_color_cool.setStyleSheet(f"background-color: {cool_hex};")

        self.checkbox_autocolor.setChecked(self.config.Plotter.autocolor)
        self.checkbox_autocolor.stateChanged.connect(self.change_autocolor)
        self.checkbox_antialias.setChecked(self.config.Plotter.antialias)
        self.checkbox_antialias.stateChanged.connect(self.change_antialias)
        self.btn_color_heat.clicked.connect(
            lambda: self.change_color(w_color=self.w_color_heat, is_heat=True)
        )
        self.btn_color_cool.clicked.connect(
            lambda: self.change_color(w_color=self.w_color_cool, is_heat=False)
        )

    def change_color(self, w_color: QtWidgets.QWidget, is_heat: bool) -> None:
        dlg = QtWidgets.QColorDialog(self)
        color = dlg.getColor()
        if color.isValid():
            self.color = color
            w_color.setStyleSheet(f"background-color: {color.name()};")
            rgb = [
                color.red() / 255.0,
                color.green() / 255.0,
                color.blue() / 255.0,
            ]
            if is_heat:
                self.config.Plotter.default_heat_color = rgb
            else:
                self.config.Plotter.default_cool_color = rgb
            self.set_changed()

    def change_autocolor(self, _state: int) -> None:
        self.config.Plotter.autocolor = self.checkbox_autocolor.isChecked()
        self.set_changed()

    def change_antialias(self, _state: int) -> None:
        self.config.Plotter.antialias = self.checkbox_antialias.isChecked()
        self.set_changed()

    def set_changed(self) -> None:
        if not self.changes_are_made:
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")
