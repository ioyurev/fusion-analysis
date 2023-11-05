from numpy.typing import ArrayLike
from helpers import find_nearest, make_peakbaseline, np, derivative_data, PolyArea, sround, calc_peakonset, baseline_temp, xand_gate
import matplotlib.patheffects as path_effects
from matplotlib.patches import Polygon
from matplotlib.text import Annotation
from matplotlib.lines import Line2D
from matplotlib.axes import Axes
import pandas as pd
from libn2f import UREG
from PySide6 import QtCore

PATH_EFFECT = [path_effects.Stroke(linewidth=2, foreground='black'), path_effects.Normal()]
LW = 0.5

class Segment(Line2D):
    ax: Axes

    def __init__(self, df: pd.DataFrame, plotter, index: int, Type: int, color, mode: bool, *args, **kwargs):
        """
        mode: 0 - DTA, 1 - temp, 2 - mass
        """
        self.plotter = plotter
        self.df = df
        self.Type = Type
        self.index = index
        xdata = self.df['Time'].values
        if mode == 0:
            ydata = self.df['DTA'].values
            self.ax = plotter.ax
        elif mode == 2:
            ydata = self.df['Mass'].values
            self.ax = plotter.ax2
        self.xmax = float(xdata.max())
        self.xmin = float(xdata.min())
        self.ymax = float(ydata.max())
        self.ymin = float(ydata.min())
        super().__init__(xdata=xdata, ydata=ydata, color=color, lw=LW, *args, **kwargs)
        self.set_picker(5)
        self.set_antialiased(False)

    def set_visible(self, b: bool) -> None:
        super().set_visible(b)
        self.set_picker(5 if b else b)

    def set_axes(self, xaxis: str, yaxis: str):
        self.xaxis = xaxis
        xdata = self.df[xaxis].values
        ydata = self.df[yaxis].values
        self.xmax = float(xdata.max())
        self.xmin = float(xdata.min())
        self.ymax = float(ydata.max())
        self.ymin = float(ydata.min())
        self.set_data(xdata, ydata)
    
    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)

class SegmentMass(Line2D):
    def __init__(self, xdata: pd.Series, ydata: pd.Series, *args, **kwargs):
        self.xmax = xdata.max()
        self.xmin = xdata.min()
        self.ymax = ydata.max()
        self.ymin = ydata.min()
        super().__init__(xdata=xdata, ydata=ydata, color='green', lw=LW, *args, **kwargs)
        self.set_antialiased(False)

    def set_xdata(self, x: ArrayLike) -> None:
        self.xmin = x.min()
        self.xmax = x.max()
        return super().set_xdata(x)

class SegmentDTA(Segment, QtCore.QObject):
    def __init__(self, df: pd.DataFrame, plotter, index: int, Type: int, color, temp_axis='Temp.', *args, **kwargs):
        self.temp_axis = temp_axis
        df['dDTA/dTime'] = derivative_data(df['Time'].to_numpy(), df['DTA'].to_numpy())
        df[f'dDTA/d{self.temp_axis}'] = derivative_data(df[self.temp_axis].to_numpy(), df['DTA'].to_numpy())
        self.xaxis = 'Time'
        self.dsegment = SegmentDDTA(xdata=df[self.xaxis], ydata=df['dDTA/dTime'])
        self.temp_segment = SegmentTemp(xdata=df['Time'], ydata=df[self.temp_axis])
        self.has_massdata = 'Mass' in df.columns
        if self.has_massdata:
            self.mass_segment = SegmentMass(xdata=df['Time'], ydata=df['Mass'])
        self.peaks : list[Peak] = []
        super().__init__(df=df, plotter=plotter, index=index, Type=Type, color=color, mode=0, *args, **kwargs)
        self.dy: float = 0
    
    def split(self, x: float):
        i = find_nearest(self.df['Time'].values, x)
        df1 = self.df.iloc[:i].copy()
        df2 = self.df.iloc[i:].copy()
        segment1 = SegmentDTA(df=df1, plotter=self.plotter, index=self.index, Type=self.Type, color='blue', temp_axis=self.temp_axis)
        segment2 = SegmentDTA(df=df2, plotter=self.plotter, index=self.index+1, Type=self.Type, color='blue', temp_axis=self.temp_axis)
        return segment1, segment2

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
        # self.temp_segment.set_visible(visible)
        self.set_visible_peaks(visible)

    def set_visible_peaks(self, visible: bool):
        if self.peaks:
            for peak in self.peaks:
                peak.set_visible(visible)

    def set_axes(self, xaxis: str, yaxis: str):
        super().set_axes(xaxis=xaxis, yaxis=yaxis)
        self.dsegment.set_xdata(self.df[xaxis].values)
        if self.has_massdata:
            self.mass_segment.set_xdata(self.df[xaxis].values)
        self.dy = 0

    def addPeak(self, t1:float, t2:float, baseline_type:int):
        peak = Peak(segment=self, t1=t1, t2=t2, baseline_type=baseline_type)
        self.peaks.append(peak)
        self.ax.add_patch(peak)
        return peak
    
    def setPickEffect(self, bool):
        if bool:
            self.set_path_effects(PATH_EFFECT)
        else:
            self.set_path_effects(None)

    def set_color(self, color) -> None:
        if self.peaks:
            for peak in self.peaks:
                peak.set_edgecolor(color)
        return super().set_color(color)
    
    def remove(self) -> None:
        self.dsegment.remove()
        self.temp_segment.remove()
        if self.has_massdata:
            self.mass_segment.remove()
        self.plotter.on_remove()
        return super().remove()

class SegmentDDTA(Line2D):
    def __init__(self, xdata: pd.Series, ydata: pd.Series):
        self.xmax = xdata.max()
        self.xmin = xdata.min()
        self.ymax = ydata.max()
        self.ymin = ydata.min()
        super().__init__(xdata=xdata, ydata=ydata, color='black', lw=1, linestyle='--')
        self.set_antialiased(False)

    def set_xdata(self, x: ArrayLike) -> None:
        self.xmin = x.min()
        self.xmax = x.max()
        return super().set_xdata(x)

class SegmentTemp(Line2D):
    def __init__(self, xdata: pd.Series, ydata: pd.Series):
        self.xmax = xdata.max()
        self.xmin = xdata.min()
        self.ymax = ydata.max()
        self.ymin = ydata.min()
        super().__init__(xdata=xdata, ydata=ydata, color='red', lw=1, linestyle=':')
        self.set_antialiased(False)

class Peak(Polygon):
    ann = None

    def __init__(self, segment: SegmentDTA, t1:float, t2:float, baseline_type=0, *args, **kwargs) -> None:
        self.onset_lines: list[OnsetLine] = []
        self.ax = segment.ax
        self.segment = segment
        self.temp_axis = segment.temp_axis
        xaxis = segment.xaxis
        # наследуем данные для кривой из сегмента
        segment_data_t = self.segment.get_xdata()
        self.i1 = find_nearest(segment_data_t, t1)
        self.i2 = find_nearest(segment_data_t, t2)
        if self.i1 > self.i2:
            self.i1, self.i2 = self.i2, self.i1
        self.df = pd.DataFrame()
        self.df['Time'] = self.segment.df['Time'][self.i1:self.i2].values
        self.df['DTA'] = self.segment.df['DTA'][self.i1:self.i2].values # self.segment.get_ydata()[self.i1:self.i2]
        self.df['dDTA/dTime'] = self.segment.df['dDTA/dTime'][self.i1:self.i2].values
        self.df[self.temp_axis] = self.segment.df[self.temp_axis][self.i1:self.i2].values
        self.df[f'dDTA/d{self.temp_axis}'] = self.segment.df[f'dDTA/d{self.temp_axis}'][self.i1:self.i2].values
        
        # наследуем данные для базовой линии
        self.df_baseline = pd.DataFrame()
        self.df_baseline['Time'] = self.df['Time']
        self.df_baseline[self.temp_axis] = self.df[self.temp_axis]

        # расчитываем базовую линию
        baseline, self.baseline_time_expr = make_peakbaseline(
            baselinetype=baseline_type,
            i1=self.i1, i2=self.i2,
            xdata=self.segment.df['Time'].to_list(),
            ydata=self.segment.df['DTA'].to_list()
            )
        self.baseline_temp_expr = baseline_temp(data_temp=self.df[self.temp_axis], data_dta=baseline)
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
        self.label_enabled = True
        area = PolyArea(self.get_xy())
        xaxis_units = UREG(self.segment.plotter.get_units('Time')).to('s')
        yaxis_units = UREG(self.segment.plotter.get_units('DTA'))
        if yaxis_units.check('mW/mg'):
            units = (yaxis_units * xaxis_units).to('J/g')
        else:
            units = yaxis_units * xaxis_units
        self.area = sround(area, 3) * units * (2 * self.peak_effect - 1)
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
        elif xaxis == self.temp_axis:
            baseline_expr = self.baseline_temp_expr
            data_ddta = self.df[f'dDTA/d{self.temp_axis}'].values
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
        line = OnsetLine(peak=self, ci=ci, bi=bi, color=self.segment._color, is_onset=is_onset)
        self.onset_lines.append(line)
        self.ax.add_line(self.onset_lines[-1])
        return line

    def remove(self, redraw=False) -> None:
        self.segment.peaks.remove(self)
        self.segment.plotter.items.remove(self)
        self.segment.plotter.items.remove(self.ann)
        self.ann.remove()
        for line in self.onset_lines:
            line.remove(exclude_from_list=False)
        self.onset_lines = []
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
    def __init__(self, peak: Peak, ci: int, bi: int, is_onset: bool, *args, **kwargs) -> None:
        self.peak = peak
        self.temp_axis = peak.temp_axis
        self.label_enabled = True
        self.label_dta_enabled = False
        self.is_onset = is_onset
        xaxis = peak.segment.xaxis
        self.label_time_enabled = xaxis == 'Time'
        self.label_temp_enabled = not self.label_time_enabled
        self.ci = ci
        self.bi = bi
        self.info = dict()
        self.info[self.temp_axis] = int(round(self.peak.df_baseline[self.temp_axis][bi], 0))
        self.info['Time'] = round(self.peak.df_baseline['Time'][bi], 5)
        self.info['DTA'] = round(self.peak.df_baseline['DTA'][bi], 5)
        self.units = {self.temp_axis: self.peak.segment.plotter.get_units(self.temp_axis),
                      'Time': self.peak.segment.plotter.get_units('Time'),
                      'DTA': self.peak.segment.plotter.get_units('DTA')}
        xdata = [self.info[xaxis],
                 self.peak.df[xaxis][ci]]
        ydata = [self.info['DTA'],
                 self.peak.df['DTA'][ci]]

        xy = [xdata[0], ydata[0]]
        if is_onset:
            self.t = 'Начало'
        else:
            self.t = 'Конец'
        self.ann = MyAnn(parent=self, text=f'{self.t}: {self.info[xaxis]} {self.units[xaxis]}', xy=xy, xytext=xy, color=self.peak.segment._color,
                         arrowprops=dict(arrowstyle="-", color=self.peak.segment._color, antialiased=False, lw=LW)
                         )
        super().__init__(xdata=xdata, ydata=ydata, lw=LW, *args, **kwargs)
        self.set_antialiased(False)
        self.peak.segment.plotter.ax.add_artist(self.ann)
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
    
    def remove(self, redraw=False, exclude_from_list=True) -> None:
        if exclude_from_list:
            self.peak.onset_lines.remove(self)
        self.peak.segment.plotter.items.remove(self)
        self.peak.segment.plotter.items.remove(self.ann)
        self.ann.remove()
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
        match self.parent:
            case OnsetLine():
                xb = self.parent.xb
            case Peak():
                xb = self.parent.df_baseline[xaxis].values[self.parent.anni]
            case _:
                raise RuntimeError(f"Не предусмотренный родительский класс {self.parent.__class__.__name__}")
        self.set(x=xb, y=self.get_position()[1])
        self.xy = (xb, self.xy[1])

    def set_color(self, color) -> None:
        self.arrow_patch.set_color(color)
        return super().set_color(color)