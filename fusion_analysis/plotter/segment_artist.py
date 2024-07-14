from matplotlib import patheffects
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

from ..segment_data import SegmentData

PATH_EFFECT = [
    patheffects.Stroke(linewidth=2, foreground="black"),
    patheffects.Normal(),
]


class SegmentArtist(Line2D):
    index: int


class SegmentHandler:
    line: SegmentArtist

    def add_to_ax(self, ax: plt.Axes):
        ax.add_line(self.line)

    def set_pick_effect(self, enabled: bool):
        if enabled:
            self.line.set_path_effects(PATH_EFFECT)
        else:
            self.line.set_path_effects(None)

    def set_enabled(self, b: bool):
        self.line.set_visible(b)


class SegmentHandlerXSwitchable(SegmentHandler):
    def __init__(self, data: SegmentData):
        self.time = data.time
        self.temp = data.temp
        if self.temp is not None:
            self.min_temp = min(self.temp)
            self.max_temp = max(self.temp)
        self.min_time = min(self.time)
        self.max_time = max(self.time)

    def set_xdata_to_time(self):
        self.line.set_xdata(self.time)
        self.min_x = self.min_time
        self.max_x = self.max_time

    def set_xdata_to_temp(self):
        self.line.set_xdata(self.temp)
        self.min_x = self.min_temp
        self.max_x = self.max_temp


class SegmentHandlerDTA(SegmentHandlerXSwitchable):
    def __init__(self, data: SegmentData, index: int):
        super().__init__(data)
        self.line = SegmentArtist(data.time, data.dta, color="blue", lw=1)
        self.line.index = index
        self.min_x = self.min_time
        self.max_x = self.max_time
        self.min_y = min(data.dta)
        self.max_y = max(data.dta)


class SegmentHandlerMass(SegmentHandlerXSwitchable):
    def __init__(self, data: SegmentData, index: int):
        super().__init__(data)
        self.line = SegmentArtist(data.time, data.mass, color="green", lw=1)
        self.line.index = index
        if data.mass is not None:
            self.min_y = min(data.mass)
            self.max_y = max(data.mass)


class SegmentHandlerTemp(SegmentHandler):
    def __init__(self, data: SegmentData, index: int):
        self.line = SegmentArtist(
            data.time, data.temp, color="red", linestyle=":", lw=1
        )
        self.line.index = index
        self.min_x = min(data.time)
        self.max_x = max(data.time)
        if data.temp is not None:
            self.min_y = min(data.temp)
            self.max_y = max(data.temp)
