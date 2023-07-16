from helpers import find_nearest, make_peakbaseline, np, get_next_color, derivative, PolyArea, swap_values
import matplotlib.patheffects as path_effects
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
import pandas as pd

PATH_EFFECT = [path_effects.Stroke(linewidth=4, foreground='black'), path_effects.Normal()]

class DSegment(Line2D):
    def __init__(self, xdata, ydata, color, *args, **kwargs) -> None:
        super().__init__(xdata=xdata, ydata=ydata, color=color, *args, **kwargs)


class Segment(Line2D):
    line: Line2D
    line_ddta: Line2D
    index: int
    def __init__(self, df: pd.DataFrame, plotter, index: int, *args, **kwargs):
        self.df = df
        xdata = self.df['Time'].values
        ydata = self.df['DTA'].values
        self.xmax = xdata.max()
        self.xmin = xdata.min()
        self.ymax = ydata.max()
        self.ymin = ydata.min()
        self.plotter = plotter
        self.index = index
        self.peaks = []
        color = get_next_color()
        super().__init__(xdata=xdata, ydata=ydata, color=color, *args, **kwargs)
        self.dsegment = DSegment(xdata=xdata, ydata=derivative(xdata, ydata), color=color)
        self.set_visible(True)

    def peaksSetData(self, xaxis):
        peak: Peak
        for peak in self.peaks:
            peak.set_data(xaxis=xaxis)

    def set_visible(self, visible):
        super().set_visible(visible)
        self.dsegment.set_visible(visible)
        self.set_visible_peaks(visible)
        self.make_pickable(visible)
    
    def make_pickable(self, bool):
        self.set_picker(bool)
        if bool:
            self.set_pickradius(5)

    def set_visible_peaks(self, visible: bool):
        peak: Peak
        if self.peaks:
            for peak in self.peaks:
                peak.set_visible(visible)

    def set_axes(self, xaxis: str, yaxis: str):
        self.xaxis = xaxis
        xdata = self.df[xaxis].values
        ydata = self.df[yaxis].values
        self.xmax = xdata.max()
        self.xmin = xdata.min()
        self.ymax = ydata.max()
        self.ymin = ydata.min()
        self.set_data(xdata, ydata)
        self.dsegment.set_xdata(xdata)

    def addPeak(self, t1, t2):
        print("* добавляем пик")
        self.peaks.append(Peak(segment=self, t1=t1, t2=t2))
        self.plotter.ax.add_patch(self.peaks[-1])
        if self.index == self.plotter.pickedSegment:
            self.peaks[-1].setPickEffect(True)
    
    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)
        if self.peaks:
            for peak in self.peaks:
                peak.setPickEffect(bool)

class Peak(Polygon):
    def __init__(self, segment, t1, t2, *args, **kwargs) -> None:
        self.segment = segment
        curve_xdata = self.segment.df['Time'].to_list()
        curve_ydata = self.segment.df['DTA'].to_list()
        segment_xdata = self.segment.get_xdata()
        self.i1 = find_nearest(segment_xdata, t1)
        self.i2 = find_nearest(segment_xdata, t2)
        if self.i1 > self.i2:
            self.i1, self.i2 = swap_values(self.i1, self.i2)
        self.updateXdata('Time')
        baseline, self.baseline_expr = make_peakbaseline(
            baselinetype=0,
            i1=self.i1, i2=self.i2,
            xdata=curve_xdata,
            ydata=curve_ydata
            )
        self.curve_ydata = curve_ydata[self.i1:self.i2]
        self.baseline_ydata = list(reversed(baseline))
        xdata = list(self.curve_xdata) + list(self.baseline_xdata)
        ydata = list(self.curve_ydata) + list(self.baseline_ydata)
        data = np.array([xdata, ydata]).transpose()
        super().__init__(data, hatch = '//', edgecolor=self.segment._color, facecolor='none', lw=1, *args, **kwargs)
        self.set_data(self.segment.plotter.getCurrentXaxis())
        # self.area = PathPatch(Path(self.get_xy())).get_path().area * 60
        self.area = PolyArea(self.get_xy())
        print(f"* площадь пика {self.area}")

    def updateXdata(self, xaxis):
        self.curve_xdata = self.segment.df[xaxis][self.i1:self.i2].to_list()
        self.baseline_xdata = list(reversed(self.curve_xdata))

    def set_data(self, xaxis):
        self.updateXdata(xaxis)
        self.set_xy(list(zip(
            self.curve_xdata + self.baseline_xdata,
            self.curve_ydata + self.baseline_ydata)))
        self.segment.plotter.canvas.draw_idle()

    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)
