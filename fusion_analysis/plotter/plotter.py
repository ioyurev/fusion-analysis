from loguru import logger as log
from matplotlib import pyplot as plt
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PySide6 import QtCore

from ..segment import Segment
from .segment_artist import SegmentArtist


class Plotter(QtCore.QObject):
    selection_changed = QtCore.Signal(int)

    def __init__(self, segments: list[Segment], parent=None):
        super().__init__(parent)
        self.segments = segments
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, parent=parent)

        # self.canvas.mpl_connect("button_release_event", self.on_button_release)
        # self.canvas.mpl_connect("motion_notify_event", self.on_move)
        self.canvas.mpl_connect("button_press_event", self.on_button_press)

        self.ax_mass = self.fig.add_subplot(111)
        self.ax_temp: plt.Axes = self.ax_mass.twinx()
        self.ax_dta: plt.Axes = self.ax_mass.twinx()

        self.ax_mass.set_xlabel("Время, мин")

        self.ax_dta.set_ylabel("ДТА, мВ", color="blue")
        self.ax_dta.yaxis.set_tick_params(color="blue")
        self.ax_dta.tick_params(colors="blue", axis="y")
        self.ax_dta.spines["right"].set_color("blue")
        self.ax_dta.spines["left"].set_visible(False)

        self.ax_temp.set_ylabel("Температура, °С", color="red")
        self.ax_temp.yaxis.set_tick_params(color="red")
        self.ax_temp.spines["right"].set_color("red")
        self.ax_temp.tick_params(colors="red", axis="y")
        self.ax_temp.spines["left"].set_visible(False)

        self.ax_mass.set_ylabel("Масса, %", color="green")
        self.ax_mass.yaxis.set_tick_params(color="green")
        self.ax_mass.spines["left"].set_color("green")
        self.ax_mass.tick_params(colors="green", axis="y")

        self.items: list[SegmentArtist] = []

        for segment in self.segments:
            segment.artist_dta.add_to_ax(self.ax_dta)
            segment.artist_temp.add_to_ax(self.ax_temp)
            segment.artist_mass.add_to_ax(self.ax_mass)

            self.items.append(segment.artist_dta.line)
            # self.items.append(segment.artist_temp.line)
            # self.items.append(segment.artist_mass.line)

        self.update_all_axes_limits()
        self.update_axes_spines_position()

    def tight_layout(self):
        self.fig.tight_layout()
        self.canvas.draw()

    def on_button_press(self, event: MouseEvent):
        if not event.inaxes:
            return
        picked = [item for item in self.items if item if item.contains(event)[0]]
        if not picked:
            item = None
            self.selection_changed.emit(-1)
        else:
            item = picked[0]
            self.selection_changed.emit(item.index)
        # self.on_pick(item, event)
        # self.holding_item = item

    def update_axes_spines_position(self):
        shift = 0
        if self.ax_temp.get_visible():
            shift = 48
        #     self.ax_temp.spines["right"].set_position(("outward", shift))
        #     shift += 48
        # if self.ax_dta.get_visible():
        self.ax_dta.spines["right"].set_position(("outward", shift))
        # shift += 48
        # if self.ax_ddta.get_visible():
        #     self.ax_ddta.spines["right"].set_position(("outward", shift))

    def update_ax_limits_dta(self):
        min_x = float("inf")
        max_x = float("-inf")
        min_y = float("inf")
        max_y = float("-inf")

        for segment in self.segments:
            if segment.is_enabled:
                min_x = min(min_x, segment.artist_dta.min_x)
                max_x = max(max_x, segment.artist_dta.max_x)
                min_y = min(min_y, segment.artist_dta.min_y)
                max_y = max(max_y, segment.artist_dta.max_y)
        if max_y == float("-inf"):
            return
        range_y = max_y - min_y

        self.ax_dta.set_xlim(min_x, max_x)
        self.ax_dta.set_ylim(min_y - 0.05 * range_y, max_y + 0.05 * range_y)

    def update_ax_limits_temp(self):
        # min_x = float('inf')
        # max_x = float('-inf')
        min_y = float("inf")
        max_y = float("-inf")

        for segment in self.segments:
            if segment.is_enabled:
                # min_x = min(min_x, segment.artist_temp.min_x)
                # max_x = max(max_x, segment.artist_temp.max_x)
                min_y = min(min_y, segment.artist_temp.min_y)
                max_y = max(max_y, segment.artist_temp.max_y)
        if max_y == float("-inf"):
            return
        range_y = max_y - min_y

        # self.ax_temp.set_xlim(min_x, max_x)
        self.ax_temp.set_ylim(min_y - 0.05 * range_y, max_y + 0.05 * range_y)

    def update_ax_limits_mass(self):
        # min_x = float('inf')
        # max_x = float('-inf')
        min_y = float("inf")
        max_y = float("-inf")

        for segment in self.segments:
            if segment.is_enabled:
                # min_x = min(min_x, segment.artist_mass.min_x)
                # max_x = max(max_x, segment.artist_mass.max_x)
                min_y = min(min_y, segment.artist_mass.min_y)
                max_y = max(max_y, segment.artist_mass.max_y)
        if max_y == float("-inf"):
            return
        range_y = max_y - min_y

        # self.ax_mass.set_xlim(min_x, max_x)
        self.ax_mass.set_ylim(min_y - 0.05 * range_y, max_y + 0.05 * range_y)

    def update_all_axes_limits(self):
        self.update_ax_limits_dta()
        self.update_ax_limits_mass()
        self.update_ax_limits_temp()
        self.update_axes_spines_position()

    def set_xaxis(self, xaxis_index: int):
        is_time = xaxis_index == 0
        self.ax_temp.set_visible(is_time)
        if is_time:
            xaxis = "Время, мин"
            for segment in self.segments:
                segment.artist_dta.set_xdata_to_time()
                segment.artist_mass.set_xdata_to_time()
        else:
            xaxis = "Температура, °С"
            for segment in self.segments:
                segment.artist_dta.set_xdata_to_temp()
                segment.artist_mass.set_xdata_to_temp()
        log.debug(f"Выбрана ось: {xaxis}")
        self.ax_mass.set_xlabel(xaxis)
        self.update_all_axes_limits()
