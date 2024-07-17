from loguru import logger as log
from matplotlib import pyplot as plt
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PySide6 import QtCore

from ..helpers import find_nearest
from ..segment import Segment
from .segment_artist import SegmentArtist
from .selector import SelectorArtist


class Plotter(QtCore.QObject):
    selection_changed = QtCore.Signal(int)
    is_time_xaxis = True
    items: list[SegmentArtist | SelectorArtist] = []
    selector: SelectorArtist | None = None
    cid_btn_move: int | None = None
    segment_to_split: Segment

    def __init__(self, segments: list[Segment], has_mass: bool, parent=None):
        super().__init__(parent)
        self.has_mass = has_mass
        self.segments = segments
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, parent=parent)
        self.toolbar.home = self.home
        self.toolbar._actions["configure_subplots"].setVisible(False)
        self.toolbar._actions["edit_parameters"].setVisible(False)

        # self.canvas.mpl_connect("button_release_event", self.on_button_release)
        # self.canvas.mpl_connect("motion_notify_event", self.on_move)
        self.cid_btn_press = self.canvas.mpl_connect(
            "button_press_event", self.on_button_press_segments
        )

        self.ax_dta = self.fig.add_subplot(111)
        self.ax_mass: plt.Axes = self.ax_dta.twinx()
        self.ax_temp: plt.Axes = self.ax_dta.twinx()

        if not self.has_mass:
            self.ax_mass.set_visible(False)

        self.ax_mass.spines["bottom"].set_visible(False)
        self.ax_temp.spines["bottom"].set_visible(False)

        self.ax_dta.set_xlabel("Время, мин")
        self.ax_dta.set_ylabel("ДТА, мВ", color="blue")
        self.ax_dta.yaxis.set_tick_params(color="blue")
        self.ax_dta.tick_params(colors="blue", axis="y")
        self.ax_dta.spines["left"].set_color("blue")
        self.ax_dta.spines["right"].set_visible(False)

        self.ax_mass.set_ylabel("Масса, %", color="green")
        self.ax_mass.yaxis.set_tick_params(color="green")
        self.ax_mass.spines["right"].set_color("green")
        self.ax_mass.tick_params(colors="green", axis="y")
        self.ax_mass.spines["left"].set_visible(False)

        self.ax_temp.set_ylabel("Температура, °С", color="red")
        self.ax_temp.yaxis.set_tick_params(color="red")
        self.ax_temp.spines["right"].set_color("red")
        self.ax_temp.tick_params(colors="red", axis="y")
        self.ax_temp.spines["left"].set_visible(False)

        for segment in self.segments:
            self.add_segment(segment)

        self.update_all_axes_limits()
        self.update_axes_spines_position()

    def add_segment(self, s: Segment):
        s.updated_artists.connect(self.canvas.draw)
        s.artist_dta.add_to_ax(self.ax_dta)
        s.artist_temp.add_to_ax(self.ax_temp)
        if self.has_mass:
            s.artist_mass.add_to_ax(self.ax_mass)
        if s.filtered_data is not None:
            s.set_filter()
        self.items.append(s.artist_dta.line)
        self.items.append(s.artist_temp.line)
        if self.has_mass:
            self.items.append(s.artist_mass.line)

    def remove_segment(self, s: Segment):
        s.remove()
        self.items.remove(s.artist_dta.line)
        self.items.remove(s.artist_temp.line)
        if self.has_mass:
            self.items.remove(s.artist_mass.line)

    def start_split_tool(self):
        self.segment_to_split: Segment = self.picked_segment  # type: ignore
        xlim = self.ax_dta.get_xlim()
        x_center = (xlim[0] + xlim[1]) / 2
        xdata = self.segment_to_split.artist_dta.line.get_xdata()
        i = find_nearest(array=xdata, value=x_center)
        x1 = self.segment_to_split.artist_dta.min_x()
        x2 = self.segment_to_split.artist_dta.max_x()
        selector = SelectorArtist(x=xdata[i], limit_x1=x1, limit_x2=x2, ax=self.ax_dta)
        self.items.append(selector)
        self.canvas.mpl_disconnect(self.cid_btn_press)
        self.cid_btn_press = self.canvas.mpl_connect(
            "button_press_event", self.on_button_press_selector
        )
        self.cid_btn_move = self.canvas.mpl_connect(
            "motion_notify_event", self.on_mouse_move_selector
        )

    def stop_split_tool(self):
        self.canvas.mpl_disconnect(self.cid_btn_move)
        self.canvas.mpl_disconnect(self.cid_btn_press)
        self.cid_btn_press = self.canvas.mpl_connect(
            "button_press_event", self.on_button_press_segments
        )
        self.selector = None
        for item in self.items:
            if isinstance(item, SelectorArtist):
                x = item.get_xdata()[0]
                item.remove()
                self.items.remove(item)
                return x

    def on_mouse_move_selector(self, event: MouseEvent):
        if self.selector is None:
            return
        if not event.inaxes:
            return
        x = event.xdata
        if not ((self.selector.limit_x1 < x) and (x < self.selector.limit_x2)):
            return
        if event.button == 1:
            self.selector.set_xdata([x, x])
            self.canvas.draw()

    def home(self):
        self.update_all_axes_limits()
        self.toolbar.set_history_buttons()
        self.canvas.draw()

    def tight_layout(self):
        try:
            self.fig.tight_layout()
            self.canvas.draw()
        except RuntimeError as _:
            pass

    def on_button_press_segments(self, event: MouseEvent):
        item = self.pick(event)
        if item is None:
            self.selection_changed.emit(-1)
            self.picked_segment = None
        else:
            self.selection_changed.emit(item.index)
            self.picked_segment = self.segments[item.index]

    def on_button_press_selector(self, event: MouseEvent):
        self.selector: SelectorArtist | None = self.pick(event=event)

    def pick(self, event: MouseEvent):
        if not event.inaxes:
            return None
        picked = [item for item in self.items if item if item.contains(event)[0]]
        if not picked:
            item = None
        else:
            item = picked[0]
        return item

    def update_axes_spines_position(self):
        shift = 0
        if self.has_mass:
            shift = 48
        self.ax_temp.spines["right"].set_position(("outward", shift))

    def update_ax_limits_dta(self):
        min_x = float("inf")
        max_x = float("-inf")
        min_y = float("inf")
        max_y = float("-inf")

        for segment in self.segments:
            if segment.is_enabled:
                min_x = min(min_x, segment.artist_dta.min_x())
                max_x = max(max_x, segment.artist_dta.max_x())
                min_y = min(min_y, segment.artist_dta.min_y())
                max_y = max(max_y, segment.artist_dta.max_y())
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
                min_y = min(min_y, segment.artist_temp.min_y())
                max_y = max(max_y, segment.artist_temp.max_y())
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
                min_y = min(min_y, segment.artist_mass.min_y())
                max_y = max(max_y, segment.artist_mass.max_y())
        if max_y == float("-inf"):
            return
        range_y = max_y - min_y

        # self.ax_mass.set_xlim(min_x, max_x)
        self.ax_mass.set_ylim(min_y - 0.05 * range_y, max_y + 0.05 * range_y)

    def update_all_axes_limits(self):
        self.update_ax_limits_dta()
        if self.has_mass:
            self.update_ax_limits_mass()
        self.update_ax_limits_temp()
        self.update_axes_spines_position()

    def switch_xaxis(self):
        self.is_time_xaxis = not self.is_time_xaxis
        self.ax_temp.set_visible(self.is_time_xaxis)
        if self.is_time_xaxis:
            xaxis = "Время, мин"
            color = "black"
        else:
            xaxis = "Температура, °С"
            color = "red"

        for segment in self.segments:
            segment.artist_dta.switch_xaxis()
            if self.has_mass:
                segment.artist_mass.switch_xaxis()

        log.debug(f"Выбрана ось: {xaxis}")
        self.ax_dta.set_xlabel(xaxis, color=color)
        self.ax_dta.spines["bottom"].set_color(color)
        self.ax_dta.tick_params(colors=color, axis="x")
        self.ax_dta.xaxis.set_tick_params(color=color)
        self.update_all_axes_limits()
