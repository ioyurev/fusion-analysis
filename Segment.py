from helpers import find_nearest, make_peakbaseline, np, get_next_color, derivative, PolyArea, swap_values, sround, calc_peakonset, baseline_temp
import matplotlib.patheffects as path_effects
from matplotlib.patches import Polygon
from matplotlib.text import Annotation
from matplotlib.lines import Line2D
import pandas as pd
from libn2f import UREG

PATH_EFFECT = [path_effects.Stroke(linewidth=4, foreground='black'), path_effects.Normal()]


class Segment(Line2D):
    line_ddta: Line2D
    index: int
    _visible: bool
    def __init__(self, df: pd.DataFrame, plotter, index: int, *args, **kwargs):
        self.df = df
        xdata = self.df['Time'].values
        ydata = self.df['DTA'].values
        self.xaxis = 'Time'
        self.xmax = xdata.max()
        self.xmin = xdata.min()
        self.ymax = ydata.max()
        self.ymin = ydata.min()
        self.plotter = plotter
        self.index = index
        self.peaks = []
        color = get_next_color()
        super().__init__(xdata=xdata, ydata=ydata, color=color, lw=1, *args, **kwargs)
        self.dsegment = Line2D(xdata=xdata, ydata=derivative(xdata, ydata), color=color, lw=1)
        self.dsegment.set_antialiased(False)
        self.set_picker(5)
        self.set_antialiased(False)

    def peaksSetData(self, xaxis):
        peak: Peak
        for peak in self.peaks:
            peak.set_data(xaxis=xaxis)

    def set_visible(self, visible:bool):
        super().set_visible(visible)
        self.dsegment.set_visible(visible)
        self.set_visible_peaks(visible)
        self.set_picker(5 if visible else visible)

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
        self.peaks.append(Peak(segment=self, t1=t1, t2=t2, baseline_type=self.plotter.parent.combobox_baselinetype.currentIndex()))
        self.plotter.ax.add_patch(self.peaks[-1])
    
    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)

class Peak(Polygon):
    def __init__(self, segment: Segment, t1, t2, baseline_type=0, *args, **kwargs) -> None:
        self.onset_lines = []
        self.segment = segment
        curve_data_temp = self.segment.df['Temp.'].to_list()
        curve_data_time = self.segment.df['Time'].to_list()
        curve_data_dta = self.segment.df['DTA'].to_list()
        segment_data_t = self.segment.get_xdata()
        self.i1 = find_nearest(segment_data_t, t1)
        self.i2 = find_nearest(segment_data_t, t2)
        if self.i1 > self.i2:
            self.i1, self.i2 = swap_values(self.i1, self.i2)
        self.curve_data_ddta_dtime = list(self.segment.dsegment.get_ydata()[self.i1:self.i2])
        self.curve_data_ddta_dtemp = list(derivative(curve_data_temp[self.i1:self.i2], curve_data_dta[self.i1:self.i2]))
        self.updateXdata('Time')
        baseline, self.baseline_time_expr = make_peakbaseline(
            baselinetype=baseline_type,
            i1=self.i1, i2=self.i2,
            xdata=curve_data_time,
            ydata=curve_data_dta
            )
        self.baseline_temp_expr = baseline_temp(data_temp=curve_data_temp[self.i1:self.i2], data_dta=baseline)
        self.curve_data_dta = curve_data_dta[self.i1:self.i2]
        self.baseline_data_dta = list(reversed(baseline))
        xdata = list(self.curve_data_t) + list(self.baseline_data_t)
        ydata = list(self.curve_data_dta) + list(self.baseline_data_dta)
        data = np.array([xdata, ydata]).transpose()
        super().__init__(data, hatch = '//', edgecolor=self.segment._color, facecolor='none', lw=1, *args, **kwargs)
        self.set_antialiased(False)
        area = PolyArea(self.get_xy()) * 60
        self.area = sround(area, 3) * UREG('J/g')
        print(f"* площадь пика {self.area}")
        self.anni = len(self.baseline_data_t) // 2
        xy = (self.baseline_data_t[self.anni], self.baseline_data_dta[self.anni])
        if self.baseline_data_dta[self.anni] < self.curve_data_dta[self.anni]:
            up = -1
        else:
            up = 1
        ylim = self.segment.plotter.ax.get_ylim()
        ry = ylim[1] - ylim[0]
        self.ann = MyAnn(parent=self, text=f'Площадь: {str(self.area).replace(" / ", "/")}', xy=xy, xytext=(0, self.baseline_data_dta[self.anni]+up*ry*0.05),
                                         arrowprops=dict(arrowstyle="-", color=self.segment._color), color=self.segment._color)
        self.segment.plotter.ax.add_artist(self.ann)
        self.ann.draggable()
        self.set_data(self.segment.plotter.getCurrentXaxis())
        self.set_picker(5)
        
        # self.onset(t1 = self.curve_xdata[0], t2 = self.baseline_xdata[self.anni])

    def onset(self, t1: float, t2: float):
        if self.segment.xaxis == 'Time':
            baseline_expr = self.baseline_time_expr
            data_ddta = self.curve_data_ddta_dtime
        elif self.segment.xaxis == 'Temp.':
            baseline_expr = self.baseline_temp_expr
            data_ddta = self.curve_data_ddta_dtemp
        xi, yi, xt, yt = calc_peakonset(
            t1=t1,
            t2=t2,
            data_t=self.curve_data_t,
            data_dta=self.curve_data_dta,
            data_ddta=data_ddta,
            expr_baseline=baseline_expr
            )
        self.onset_lines.append(OnsetLine(peak=self, xdata=[xi, xt], ydata=[yi, yt], color=self.segment._color))
        self.segment.plotter.ax.add_line(self.onset_lines[-1])

    def remove(self):
        self.segment.peaks.remove(self)
        self.ann.remove()
        for line in self.onset_lines:
            line.remove()
        super().remove()

    def updateXdata(self, xaxis):
        self.curve_data_t = self.segment.df[xaxis][self.i1:self.i2].to_list()
        self.baseline_data_t = list(reversed(self.curve_data_t))

    def set_visible(self, b: bool) -> None:
        self.set_picker(5 if b else b)
        self.ann.set_visible(b)
        if self.onset_lines:
            for line in self.onset_lines:
                line.set_visible(b)
        # self.ann.set_picker(b)
        return super().set_visible(b)

    def set_data(self, xaxis):
        self.updateXdata(xaxis)
        self.set_xy(list(zip(
            self.curve_data_t + self.baseline_data_t,
            self.curve_data_dta + self.baseline_data_dta)))
        self.ann.set(x=self.baseline_data_t[self.anni])
        self.ann.xy = (self.baseline_data_t[self.anni], self.ann.xy[1])
        if self.onset_lines:
            for line in self.onset_lines:
                line.updateXdata()
        self.segment.plotter.canvas.draw_idle()

    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)

class OnsetLine(Line2D):
    def __init__(self, peak, xdata, ydata,  *args, **kwargs) -> None:
        self.peak: Peak = peak
        xdata = xdata
        ydata = ydata
        self.ci = self.peak.curve_data_dta.index(ydata[1])
        self.bi = find_nearest(self.peak.baseline_data_dta, ydata[0])
        ydata[0] = self.peak.baseline_data_dta[self.bi]
        super().__init__(xdata=xdata, ydata=ydata, *args, **kwargs)
        xy = [xdata[0], ydata[0]]
        if peak.segment.xaxis == 'Time':
            x = xdata[0] * 60
        elif peak.segment.xaxis == 'Temp.':
            x = round(xdata[0])
        self.ann = MyAnn(parent=self, text=f'Начало: {x}', xy=xy, xytext=xy,
            arrowprops=dict(arrowstyle="-", color=self.peak.segment._color), color=self.peak.segment._color)
        self.peak.segment.plotter.ax.add_artist(self.ann)
        self.ann.draggable()

    def updateXdata(self) -> None:
        xb = self.peak.baseline_data_t[self.bi]
        super().set_xdata([xb, self.peak.curve_data_t[self.ci]])
        self.ann.set(x=xb)
        self.ann.xy = (xb, self.ann.xy[1])

    def set_visible(self, b: bool) -> None:
        self.ann.set_visible(b)
        return super().set_visible(b)
    
    def remove(self) -> None:
        self.ann.remove()
        return super().remove()

class MyAnn(Annotation):
    def __init__(self, parent, *args, **kwargs) -> None:
        self.parent: Peak | OnsetLine = parent
        super().__init__(*args, **kwargs)
        self.set_picker(5)