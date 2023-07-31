from helpers import find_nearest, make_peakbaseline, np, derivative_data, PolyArea, swap_values, sround, calc_peakonset, baseline_temp, xand_gate
import matplotlib.patheffects as path_effects
from matplotlib.patches import Polygon
from matplotlib.text import Annotation
from matplotlib.lines import Line2D
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
import pandas as pd
from libn2f import UREG
import itertools

PATH_EFFECT = [path_effects.Stroke(linewidth=2, foreground='black'), path_effects.Normal()]
LW = 0.5

colors = itertools.cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])
def get_next_color():
    return next(colors)

class Segment(Line2D):
    line_ddta: Line2D
    index: int
    ax: Axes
    def __init__(self, df: pd.DataFrame, plotter, index: int, Type: int, *args, **kwargs):
        self.ax = plotter.ax
        self.dy: float = 0
        self.Type = Type
        self.df = df
        xdata = self.df['Time'].values
        ydata = self.df['DTA'].values
        self.df['dDTA/dTime'] = derivative_data(xdata, ydata)
        self.df['dDTA/dTemp'] = derivative_data(self.df['Temp.'].to_numpy(), ydata)
        self.xaxis = 'Time'
        self.xmax = xdata.max()
        self.xmin = xdata.min()
        self.ymax = ydata.max()
        self.ymin = ydata.min()
        self.plotter = plotter
        self.index = index
        self.peaks : list[Peak] = []
        color = get_next_color()
        self.dsegment = Line2D(xdata=xdata, ydata=self.df['dDTA/dTime'], color=color, lw=1)
        super().__init__(xdata=xdata, ydata=ydata, color=color, lw=LW, *args, **kwargs)
        self.dsegment.set_antialiased(False)
        self.set_picker(5)
        self.set_antialiased(False)
    
    def shifty(self, dy):
        self.dy += dy/10
        self.set_ydata(self.get_ydata() - dy/10)
        if self.peaks:
            for peak in self.peaks:
                peak.shifty(dy/10)

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
        self.dy = 0

    def addPeak(self, t1:float, t2:float, baseline_type:int):
        peak = Peak(segment=self, t1=t1, t2=t2, baseline_type=baseline_type)
        self.peaks.append(peak)
        self.ax.add_patch(peak)
    
    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)

    def set_color(self, color) -> None:
        self.dsegment.set_color(color)
        if self.peaks:
            for peak in self.peaks:
                peak.set_edgecolor(color)
        return super().set_color(color)

class Peak(Polygon):
    ann = None

    def __init__(self, segment: Segment, t1:float, t2:float, baseline_type=0, *args, **kwargs) -> None:
        self.onset_lines: list[OnsetLine] = []
        self.ax = segment.ax
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
        self.df['DTA'] = self.segment.df['DTA'][self.i1:self.i2].values # self.segment.get_ydata()[self.i1:self.i2]
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
        super().__init__(self.get_data_by_xaxis('Time'), hatch = '//', edgecolor=self.segment._color, facecolor='none', lw=LW, *args, **kwargs)
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
            arrowprops=dict(arrowstyle="-", color=self.segment._color, antialiased=False, lw=LW)
            )
        self.ax.add_artist(self.ann)
        self.ann.draggable()
        self.set_data(xaxis)
        self.shifty(self.segment.dy)

    def shifty(self, dy:float):
        if dy != 0:
            self.set_xy([(x, y - dy) for x, y in self.get_xy()])
            self.ann.shifty(dy)
            line: OnsetLine
            if self.onset_lines:
                for line in self.onset_lines:
                    line.shifty(dy)

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
        self.ax.add_line(self.onset_lines[-1])

    def remove(self, redraw=False) -> None:
        self.segment.peaks.remove(self)
        self.ann.remove()
        line: OnsetLine
        for line in self.onset_lines:
            line.remove()
        super().remove()
        if redraw:
            self.segment.plotter.canvas.draw_idle()

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
        self.ann.updateXdata(xaxis)
        # self.ann.xy = (self.df_baseline[xaxis][self.anni], self.ann.xy[1])
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

    def set_edgecolor(self, color) -> None:
        if self.ann is not None:
            self.ann.set_color(color)
            # self.ann.arrow_patch: FancyArrowPatch()
        if self.onset_lines:
            for line in self.onset_lines:
                line.set_color(color)
        return super().set_edgecolor(color)

class OnsetLine(Line2D):
    def __init__(self, peak, ci, bi, is_onset, *args, **kwargs) -> None:
        self.peak: Peak = peak
        self.is_onset = is_onset
        xaxis = peak.segment.xaxis
        self.ci = ci
        self.bi = bi
        self.info = dict()
        self.info['Temp.'] = int(round(self.peak.df_baseline['Temp.'][bi], 0))
        self.info['Time'] = round(self.peak.df_baseline['Time'][bi], 5)
        self.info['DTA'] = round(self.peak.df_baseline['DTA'][bi], 5)
        xdata = [self.info[xaxis],
                 self.peak.df[xaxis][ci]]
        ydata = [self.info['DTA'],
                 self.peak.df['DTA'][ci]]

        xy = [xdata[0], ydata[0]]
        if is_onset:
            self.t = 'Начало'
        else:
            self.t = 'Конец'
        self.ann = MyAnn(parent=self, text=f'{self.t}: {self.info[xaxis]}', xy=xy, xytext=xy, color=self.peak.segment._color,
                         arrowprops=dict(arrowstyle="-", color=self.peak.segment._color, antialiased=False, lw=LW)
                         )

        super().__init__(xdata=xdata, ydata=ydata, lw=LW, *args, **kwargs)
        self.set_antialiased(False)
        self.peak.segment.plotter.ax.add_artist(self.ann)
        self.ann.draggable()
        self.shifty(self.peak.segment.dy)

    def shifty(self, dy):
        self.set_ydata(np.array(self.get_ydata()) - dy)
        self.ann.shifty(dy)

    def updateXdata(self, xaxis) -> None:
        self.xb = self.info[xaxis]
        self.xc = self.peak.df[xaxis].values[self.ci]
        self.yb = self.peak.df_baseline['DTA'].values[self.bi]
        self.yc = self.peak.df['DTA'].values[self.ci]
        self.set_xdata([self.xb, self.xc])
        self.set_ydata([self.yb, self.yc])
        self.ann.updateXdata()
        # self.ann.set(x=self.xb, y=self.yb)
        # self.ann.xy = (self.xb, self.yb)

    def set_visible(self, b: bool) -> None:
        self.ann.set_visible(b)
        return super().set_visible(b)
    
    def remove(self, redraw=False) -> None:
        self.ann.remove()
        self.peak.onset_lines.remove(self)
        super().remove()
        if redraw:
            self.peak.segment.plotter.canvas.draw_idle()

    def set_color(self, color) -> None:
        self.ann.set_color(color)
        return super().set_color(color)

class MyAnn(Annotation):
    def __init__(self, parent, *args, **kwargs) -> None:
        self.parent: Peak | OnsetLine = parent
        super().__init__(*args, **kwargs)
        self.set_picker(5)

    def shifty(self, dy):
        self.xy = (self.xy[0], self.xy[1] - dy)
        xytext = list(self.get_position())
        xytext[1] -= dy
        self.set_position(xytext)

    def updateXdata(self, xaxis=None):
        if isinstance(self.parent, OnsetLine):
            # xc = self.parent.xc
            xb = self.parent.xb
            # yc = self.parent.yc
            yb = self.parent.yb
        elif isinstance(self.parent, Peak):
            xb = self.parent.df_baseline[xaxis].values[self.parent.anni]
            yb = self.parent.df_baseline['DTA'].values[self.parent.anni]
        else:
            raise RuntimeError(f"Не предусмотренный родительский класс {self.parent.__class__.__name__}")
        self.set(x=xb, y=yb)
        self.xy = (xb, yb)

    def set_color(self, color) -> None:
        self.arrow_patch.set_color(color)
        return super().set_color(color)