from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from loguru import logger as log
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PySide6 import QtWidgets

from .c2a import c2a
from .filtered_data_file import FilteredData, pick_save_path
from .helpers import derivative_data, error_message
from .ui.DenoiseWindow import Ui_MainWindow


def moving_average(data: np.ndarray, window: int):
    if window > len(data):
        raise ValueError("Window size is greater than the length of the numbers list")
    return np.convolve(data, np.ones(window) / window, "same")


class DenoiseWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    layout_is_set = True
    window: int

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.fig = plt.figure()
        self.fig.set_visible(False)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.ax = self.fig.add_subplot(111)
        ax2: plt.Axes = self.ax.twinx()

        self.line_original = self.ax.plot([], [], label="Исходные данные")[0]
        self.line_smoothed = self.ax.plot([], [], color="black", label="Сглаженные")[0]
        self.line_dydx_smoothed = ax2.plot(
            [], [], color="black", alpha=0.5, label="Производная"
        )[0]
        self.line_delta = ax2.plot([], [], alpha=0.5, label="Разница")[0]
        self.ax.legend(loc=1)
        ax2.legend(loc=3)

        self.denoise_spinbox.setMinimum(1)
        self.denoise_spinbox.setMaximum(500)
        self.denoise_spinbox.valueChanged.connect(self.update_smoothed)

        self.plot_layout.addWidget(self.canvas)
        self.plot_layout.addWidget(self.toolbar)
        self.layout_is_set = True

        self.action_save.triggered.connect(self.save_measurement)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.layout_is_set:
            self.fig.tight_layout()

    def open_measurement(self, path: Path):
        self.measurement = c2a(path=path)
        self.ydata = self.measurement.segments[0]["DTA"].values
        self.xdata = self.measurement.segments[0]["Time"].values
        self.dta_units = self.measurement.units["DTA"]
        self.line_original.set_data(self.xdata, self.ydata)
        min_x = self.xdata[0]
        max_x = self.xdata[-1]
        min_y = min(self.ydata)
        max_y = max(self.ydata)
        r_y = max_y - min_y
        self.ax.set_xlim(min_x, max_x)
        self.ax.set_ylim(min_y - 0.1 * r_y, max_y + 0.1 * r_y)

        self.denoise_spinbox.setEnabled(True)
        self.fig.set_visible(True)
        self.denoise_spinbox.setValue(8)
        plt.tight_layout()
        self.canvas.draw()

    def save_measurement(self):
        try:
            savepath = pick_save_path()
            if savepath == "":
                return
            time = self.line_smoothed.get_xdata()
            dta = self.line_smoothed.get_ydata()
            segment = self.measurement.segments[0]
            if "EMF" in segment.columns:
                emf = segment["EMF"].values[self.window : -self.window]
            else:
                emf = None
            if "Temp." in segment.columns:
                temp = segment["Temp."].values[self.window : -self.window]
            else:
                temp = None

            FilteredData(
                time=time, dta=dta, emf=emf, temp=temp, dta_units=self.dta_units
            ).to_file(savepath)
        except Exception as e:
            error_message(str(e))
            log.exception(e)

    def update_smoothed(self, window: int):
        len_data = len(self.ydata)
        self.window = 10 * window
        if self.layout_is_set is False:
            return
        if self.window > len_data:
            return

        ydata_average = moving_average(self.ydata, self.window)
        dydx = derivative_data(self.xdata, ydata_average)
        ydata_delta = (
            self.ydata[self.window : -self.window]
            - ydata_average[self.window : -self.window]
        )

        self.line_smoothed.set_data(
            self.xdata[self.window : -self.window],
            ydata_average[self.window : -self.window],
        )
        self.line_dydx_smoothed.set_data(
            self.xdata[self.window : -self.window], dydx[self.window : -self.window]
        )
        self.line_delta.set_data(self.xdata[self.window : -self.window], ydata_delta)

        self.canvas.draw()
