import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PySide6 import QtCore, QtWidgets

from .helpers import derivative_data
from .segment import Segment
from .ui.FilterWindow import Ui_Dialog


def moving_average(data: np.ndarray, window: int):
    if window > len(data):
        raise ValueError("Window size is greater than the length of the numbers list")
    return np.convolve(data, np.ones(window) / window, "same")


class FilterWindow(QtWidgets.QDialog, Ui_Dialog):
    layout_is_set = False

    def __init__(self, segment: Segment, parent):
        super().__init__(parent)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setupUi(self)
        self.segment = segment
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, parent=parent)
        self.verticalLayout.addWidget(self.canvas)
        self.verticalLayout.addWidget(self.toolbar)
        self.ax_dta = self.fig.add_subplot(121)
        self.ax_temp = self.fig.add_subplot(122)
        self.ax_ddta: plt.Axes = self.ax_dta.twinx()
        self.ax_dtemp: plt.Axes = self.ax_temp.twinx()

        self.xdata = self.segment.data.time
        self.ydata_dta = self.segment.data.dta
        self.ydata_temp = self.segment.data.temp

        self.line_dta_original = self.ax_dta.plot(
            self.xdata, self.ydata_dta, label="Исходные данные"
        )[0]
        self.line_dta_filtered = self.ax_dta.plot([], [], label="Сглаженные данные")[0]
        self.line_dta_derivative = self.ax_ddta.plot([], [], label="Производная")[0]

        self.line_temp_original = self.ax_temp.plot(
            self.xdata, self.ydata_temp, label="Исходные данные"
        )[0]
        self.line_temp_filtered = self.ax_temp.plot([], [], label="Сглаженные данные")[
            0
        ]
        self.line_temp_derivative = self.ax_dtemp.plot([], [], label="Производная")[0]

        self.ax_ddta.set_ylim(-2, 2)
        self.ax_dtemp.set_ylim(-2, 2)

        self.spinBox.setMinimum(1)
        self.spinBox.valueChanged.connect(self.update_filter)

        self.ax_dta.set_xlabel("Время")
        self.ax_dta.set_ylabel("ДТА")
        self.ax_temp.set_ylabel("Температура")
        self.fig.tight_layout()
        self.layout_is_set = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.layout_is_set:
            self.fig.tight_layout()

    def update_filter(self):
        window = self.spinBox.value()
        self.avg_window = window
        xdata = self.xdata[window:-window]
        ydata_dta = moving_average(self.ydata_dta, window)[window:-window]
        ydata_temp = moving_average(self.ydata_temp, window)[window:-window]
        dydx_dta = derivative_data(xdata, ydata_dta)
        dydx_temp = derivative_data(xdata, ydata_temp)

        self.line_dta_filtered.set_data(xdata, ydata_dta)
        self.line_temp_filtered.set_data(xdata, ydata_temp)
        self.line_dta_derivative.set_data(xdata, dydx_dta)
        self.line_temp_derivative.set_data(xdata, dydx_temp)
        self.canvas.draw()
