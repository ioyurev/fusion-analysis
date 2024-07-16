from matplotlib import patheffects
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

from ..segment_data import FilteredData, SegmentData

PATH_EFFECT = [
    patheffects.Stroke(linewidth=2, foreground="black"),
    patheffects.Normal(),
]


class SegmentArtist(Line2D):
    index: int


class SegmentHandler:
    line: SegmentArtist
    filtered_data: FilteredData | None = None

    def __init__(self, data: SegmentData):
        self.data = data

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
    is_time_xaxis = True

    def min_x(self):
        if self.filtered_data is not None:
            data = self.filtered_data
        else:
            data = self.data
        if self.is_time_xaxis:
            return data.min_time
        else:
            return data.min_temp

    def max_x(self):
        if self.filtered_data is not None:
            data = self.filtered_data
        else:
            data = self.data
        if self.is_time_xaxis:
            return data.max_time
        else:
            return data.max_temp

    def switch_xaxis(self):
        self.is_time_xaxis = not self.is_time_xaxis
        self.set_xdata()

    def set_xdata(self):
        if self.is_time_xaxis:
            self.set_xdata_to_time()
        else:
            self.set_xdata_to_temp()

    def set_xdata_to_time(self):
        if self.filtered_data is not None:
            time = self.filtered_data.time
        else:
            time = self.data.time
        self.line.set_xdata(time)

    def set_xdata_to_temp(self):
        if self.filtered_data is not None:
            temp = self.filtered_data.temp
        else:
            temp = self.data.temp
        self.line.set_xdata(temp)


class SegmentHandlerDTA(SegmentHandlerXSwitchable):
    def __init__(self, data: SegmentData, index: int):
        super().__init__(data)
        self.line = SegmentArtist(data.time, data.dta, color="blue", lw=1)
        self.line.index = index

    def min_y(self):
        if self.filtered_data is not None:
            return self.filtered_data.min_dta
        else:
            return self.data.min_dta

    def max_y(self):
        if self.filtered_data is not None:
            return self.filtered_data.max_dta
        else:
            return self.data.max_dta

    def set_filter(self):
        if self.is_time_xaxis:
            xdata = self.filtered_data.time
        else:
            xdata = self.filtered_data.temp
        self.line.set_data(xdata, self.filtered_data.dta)


class SegmentHandlerMass(SegmentHandlerXSwitchable):
    def __init__(self, data: SegmentData, index: int):
        super().__init__(data)
        self.line = SegmentArtist(data.time, data.mass, color="green", lw=1)
        self.line.index = index

    def min_y(self):
        if self.filtered_data is not None:
            return self.filtered_data.min_mass
        else:
            return self.data.min_mass

    def max_y(self):
        if self.filtered_data is not None:
            return self.filtered_data.max_mass
        else:
            return self.data.max_mass


class SegmentHandlerTemp(SegmentHandler):
    def __init__(self, data: SegmentData, index: int):
        super().__init__(data)
        self.line = SegmentArtist(
            data.time, data.temp, color="red", linestyle=":", lw=1
        )
        self.line.index = index

    def set_filter(self):
        self.line.set_data(self.filtered_data.time, self.filtered_data.temp)

    def min_x(self):
        if self.filtered_data is not None:
            return self.filtered_data.min_time
        else:
            return self.data.min_time

    def max_x(self):
        if self.filtered_data is not None:
            return self.filtered_data.max_time
        else:
            return self.data.max_time

    def min_y(self):
        if self.filtered_data is not None:
            return self.filtered_data.min_temp
        else:
            return self.data.min_temp

    def max_y(self):
        if self.filtered_data is not None:
            return self.filtered_data.max_temp
        else:
            return self.data.max_temp
