from helpers import find_nearest, make_peakbaseline, np, derivative, PolyArea, swap_values, sround, calc_peakonset, baseline_temp, xand_gate
import matplotlib.patheffects as path_effects
from matplotlib.patches import Polygon
from matplotlib.text import Annotation
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import pandas as pd
from libn2f import UREG
import itertools

PATH_EFFECT = [path_effects.Stroke(linewidth=4, foreground='black'), path_effects.Normal()]

colors = itertools.cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])
def get_next_color():
    return next(colors)

class Segment(Line2D):
    line_ddta: Line2D
    index: int
    _visible: bool
    def __init__(self, df: pd.DataFrame, plotter, index: int, Type: int, *args, **kwargs):
        self.Type = Type
        self.df = df
        xdata = self.df['Time'].values
        ydata = self.df['DTA'].values
        self.df['dDTA/dTime'] = derivative(xdata, ydata)
        self.df['dDTA/dTemp'] = derivative(self.df['Temp.'].to_numpy(), ydata)
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
        self.dsegment = Line2D(xdata=xdata, ydata=self.df['dDTA/dTime'], color=color, lw=1)
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
        xaxis = segment.xaxis
        # наследуем данные для кривой из сегмента
        segment_data_t = self.segment.get_xdata()
        self.i1 = find_nearest(segment_data_t, t1)
        self.i2 = find_nearest(segment_data_t, t2)
        if self.i1 > self.i2:
            self.i1, self.i2 = swap_values(self.i1, self.i2)
        self.df = pd.DataFrame()
        self.df['Time'] = self.segment.df['Time'][self.i1:self.i2].values
        self.df['Temp.'] = self.segment.df['Temp.'][self.i1:self.i2].values
        self.df['DTA'] = self.segment.df['DTA'][self.i1:self.i2].values
        self.df['dDTA/dTime'] = self.segment.df['dDTA/dTime'][self.i1:self.i2].values
        self.df['dDTA/dTemp'] = self.segment.df['dDTA/dTemp'][self.i1:self.i2].values

        # наследуем данные для базовой линии
        self.df_baseline = pd.DataFrame()
        self.df_baseline['Time'] = self.df['Time']
        self.df_baseline['Temp.'] = self.df['Temp.']

        # расчитываем базовую линию
        baseline, self.baseline_time_expr = make_peakbaseline(
            baselinetype=baseline_type,
            i1=self.i1, i2=self.i2,
            xdata=self.segment.df['Time'].to_list(),
            ydata=self.segment.df['DTA'].to_list()
            )
        self.baseline_temp_expr = baseline_temp(data_temp=self.df['Temp.'], data_dta=baseline)
        self.df_baseline['DTA'] = baseline

        # определяем знак площади пика
        bools = self.df['DTA'].to_numpy() > self.df_baseline['DTA'].to_numpy()
        count = np.count_nonzero(bools)
        if count > self.df_baseline['DTA'].size // 2:
            self.peak_exo = 1
        else:
            self.peak_exo = 0
        self.peak_effect = xand_gate(self.peak_exo, self.segment.plotter.measurement_exo)

        # инициализируем родительский класс
        super().__init__(self.get_data_by_xaxis('Time'), hatch = '//', edgecolor=self.segment._color, facecolor='none', lw=1, *args, **kwargs)
        self.set_picker(5)
        self.set_antialiased(False)

        # считаем площадь и делаем аннотацию
        area = PolyArea(self.get_xy()) * 60 
        self.area = sround(area, 3) * UREG('J/g') * (2 * self.peak_effect - 1)
        self.anni = len(self.df_baseline[xaxis]) // 2
        xy = (self.df_baseline[xaxis][self.anni], self.df_baseline['DTA'][self.anni])
        self.ann = MyAnn(
            parent=self,
            text=f'Площадь: {str(self.area).replace(" / ", "/")}',
            xy=xy, xytext=(0, self.df_baseline['DTA'][self.anni]),
            color=self.segment._color,
            arrowprops=dict(arrowstyle="-", color=self.segment._color)
            )
        self.segment.plotter.ax.add_artist(self.ann)
        self.ann.draggable()

        self.set_data(xaxis)

    def onset(self, t1: float, t2: float, is_onset: bool):
        xaxis = self.segment.xaxis
        if xaxis == 'Time':
            baseline_expr = self.baseline_time_expr
            data_ddta = self.df['dDTA/dTime'].values
        elif xaxis == 'Temp.':
            baseline_expr = self.baseline_temp_expr
            data_ddta = self.df['dDTA/dTemp'].values
        ci, bi = calc_peakonset(
            t1=t1,
            t2=t2,
            data_t=self.df[xaxis].values,
            data_dta=self.df['DTA'].values,
            data_ddta=data_ddta,
            expr_baseline=baseline_expr,
            is_onset=is_onset,
            peak_exo=self.peak_exo
            )
        self.onset_lines.append(OnsetLine(peak=self, ci=ci, bi=bi, color=self.segment._color, is_onset=is_onset))
        self.segment.plotter.ax.add_line(self.onset_lines[-1])

    def remove(self):
        self.segment.peaks.remove(self)
        self.ann.remove()
        line: OnsetLine
        for line in self.onset_lines:
            line.remove()
        super().remove()

    def get_data_by_xaxis(self, xaxis=None) -> list:
        if xaxis is None:
            xaxis = self.segment.xaxis
        xdata_curve = self.df[xaxis].to_list()
        xdata_baseline = list(reversed(xdata_curve))
        ydata_curve = self.df['DTA'].to_list()
        ydata_baseline = list(reversed(self.df_baseline['DTA'].to_list()))
        data = list(zip(
            xdata_curve + xdata_baseline,
            ydata_curve + ydata_baseline
            ))
        return data

    def set_visible(self, b: bool) -> None:
        self.set_picker(5 if b else b)
        self.ann.set_visible(b)
        if self.onset_lines:
            for line in self.onset_lines:
                line.set_visible(b)
        # self.ann.set_picker(b)
        return super().set_visible(b)

    def set_data(self, xaxis):
        self.set_xy(self.get_data_by_xaxis())
        self.ann.set(x=self.df_baseline[xaxis][self.anni])
        self.ann.xy = (self.df_baseline[xaxis][self.anni], self.ann.xy[1])
        line: OnsetLine
        if self.onset_lines:
            for line in self.onset_lines:
                line.updateXdata(xaxis)
        self.segment.plotter.canvas.draw_idle()

    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)

class OnsetLine(Line2D):
    def __init__(self, peak, ci, bi, is_onset, *args, **kwargs) -> None:
        self.peak: Peak = peak
        self.is_onset = is_onset
        xaxis = peak.segment.xaxis
        self.ci = ci
        self.bi = bi
        self.info = dict()
        self.info['Temp.'] = int(round(self.peak.df_baseline['Temp.'][bi], 0))
        self.info['Time'] = self.peak.df_baseline['Time'][bi]
        self.info['DTA'] = self.peak.df_baseline['DTA'][bi]
        xdata = [self.info[xaxis],
                 self.peak.df[xaxis][ci]]
        ydata = [self.info['DTA'],
                 self.peak.df['DTA'][ci]]

        super().__init__(xdata=xdata, ydata=ydata, *args, **kwargs)
        xy = [xdata[0], ydata[0]]
        if is_onset:
            t = 'Начало'
        else:
            t = 'Конец'
        self.ann = MyAnn(parent=self, text=f'{t}: {self.info[xaxis]}', xy=xy, xytext=xy,
            arrowprops=dict(arrowstyle="-", color=self.peak.segment._color), color=self.peak.segment._color)
        self.peak.segment.plotter.ax.add_artist(self.ann)
        self.ann.draggable()

    def updateXdata(self, xaxis) -> None:
        xb = self.info[xaxis]
        xc = self.peak.df[xaxis].values[self.ci]
        super().set_xdata([xb, xc])
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
