from typing import TYPE_CHECKING

from matplotlib import patheffects
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

if TYPE_CHECKING:
    from ..segment import Segment

PATH_EFFECT = [
    patheffects.Stroke(linewidth=2, foreground="black"),
    patheffects.Normal(),
]


class SegmentArtist(Line2D):
    index: int


class SegmentHandler:
    line: SegmentArtist

    def __init__(self, segment: "Segment"):
        self.segment = segment
        self.line = SegmentArtist([], [], lw=1)
        self.line.index = segment.index

    def remove(self):
        self.line.remove()

    def add_to_ax(self, ax: plt.Axes):
        ax.add_line(self.line)

    def set_pick_effect(self, enabled: bool):
        if enabled:
            self.line.set_path_effects(PATH_EFFECT)
        else:
            self.line.set_path_effects(None)

    def set_enabled(self, b: bool):
        self.line.set_visible(b)

    def _min_time(self) -> float:
        return self.segment.get_data().min_time

    def _max_time(self) -> float:
        return self.segment.get_data().max_time

    def _min_dta(self) -> float:
        return self.segment.get_data().min_dta

    def _max_dta(self) -> float:
        return self.segment.get_data().max_dta

    def _min_temp(self) -> float:
        return self.segment.get_data().min_temp

    def _max_temp(self) -> float:
        return self.segment.get_data().max_temp

    def _min_mass(self) -> float:
        return self.segment.get_data().min_mass

    def _max_mass(self) -> float:
        return self.segment.get_data().max_mass


class SegmentHandlerXSwitchable(SegmentHandler):
    is_time_xaxis = True

    def min_x(self):
        if self.is_time_xaxis:
            return self._min_time()
        else:
            return self._min_temp()

    def max_x(self):
        if self.is_time_xaxis:
            return self._max_time()
        else:
            return self._max_temp()

    def switch_xaxis(self):
        self.is_time_xaxis = not self.is_time_xaxis
        self.set_xdata()

    def set_xdata(self):
        if self.is_time_xaxis:
            self.line.set_xdata(self.segment.get_data().time)
        else:
            self.line.set_xdata(self.segment.get_data().temp)


class SegmentHandlerDTA(SegmentHandlerXSwitchable):
    def __init__(self, segment: "Segment"):
        super().__init__(segment=segment)
        data = segment.get_data()
        self.line.set_data(data.time, data.dta)
        self.line.set_color("blue")
        self.min_y = self._min_dta
        self.max_y = self._max_dta

    def set_filter(self):
        if self.is_time_xaxis:
            xdata = self.segment.filtered_data.time
        else:
            xdata = self.segment.filtered_data.temp
        self.line.set_data(xdata, self.segment.filtered_data.dta)

    def unfilter(self):
        if self.is_time_xaxis:
            xdata = self.segment.get_data().time
        else:
            xdata = self.segment.get_data().temp
        self.line.set_data(xdata, self.segment.get_data().dta)


class SegmentHandlerMass(SegmentHandlerXSwitchable):
    def __init__(self, segment: "Segment"):
        super().__init__(segment)
        data = segment.get_data()
        self.line.set_data(data.time, data.mass)
        self.line.set_color("green")
        self.min_y = self._min_mass
        self.max_y = self._max_mass


class SegmentHandlerTemp(SegmentHandler):
    def __init__(self, segment: "Segment"):
        super().__init__(segment=segment)
        data = segment.get_data()
        self.line.set_data(data.time, data.temp)
        self.line.set_color("red")
        self.line.set_linestyle(":")
        self.min_x = self._min_time
        self.max_x = self._max_time
        self.min_y = self._min_temp
        self.max_y = self._max_temp

    def set_filter(self):
        self.line.set_data(
            self.segment.filtered_data.time, self.segment.filtered_data.temp
        )

    def unfilter(self):
        self.line.set_data(self.segment.get_data().time, self.segment.get_data().temp)
