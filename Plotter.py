from PySide6 import QtCore, QtWidgets
from Segment import SegmentDTA, Line2D, Peak, MyAnn, OnsetLine
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.backend_bases import MouseEvent
import itertools
import pandas as pd
from helpers import find_nearest, log_info

colors = itertools.cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])
def get_next_color():
    return next(colors)

class Selector(Line2D):
    def __init__(self, ax: Axes, x: float, spinbox: QtWidgets.QDoubleSpinBox, limit_x1: float, limit_x2: float, ymin=0, ymax=1, *args, **kwargs) -> None:
        self.ax = ax
        trans = self.ax.get_xaxis_transform(which='grid')
        self.spinbox = spinbox
        self.spinbox.selector = self
        super().__init__(xdata=[x, x], ydata=[ymin,ymax], transform=trans, lw=0.5, color='black', *args, **kwargs)
        self.ax.add_line(self)
        self.set_picker(5)
        self.set_antialiased(False)
        self.limit_x1 = limit_x1
        self.limit_x2 = limit_x2
        self.spinbox.setRange(self.limit_x1, self.limit_x2)
        self.spinbox.setValue(x, block_signal=True)

    def set_x(self, x: float, update_spinbox_value: bool = True):
        if self.limit_x1 <= x <= self.limit_x2:
            super().set_xdata([x, x])
            if update_spinbox_value:
                self.spinbox.setValue(x, block_signal=True)
            self.ax.figure.canvas.draw()

class Plotter(QtCore.QObject):
    measurement_exo: int
    units: dict
    picked_item: SegmentDTA | Peak | OnsetLine | MyAnn = None
    picked_segment: SegmentDTA = None
    picked_peak: Peak = None
    holding_item: SegmentDTA | Peak | OnsetLine | MyAnn | Selector = None
    config: dict = None
    signal_pick = QtCore.Signal(object)
    signal_cm = QtCore.Signal(tuple)
    signal_split = QtCore.Signal(tuple)
    spinbox_T1: QtWidgets.QDoubleSpinBox
    spinbox_T2: QtWidgets.QDoubleSpinBox
    spinbox_onsettool_T1: QtWidgets.QDoubleSpinBox
    spinbox_onsettool_T2: QtWidgets.QDoubleSpinBox

    def __init__(self, parent, dpi, scale) -> None:
        log_info("* инициализация плоттера")
        super().__init__(parent)
        self.fig = plt.figure(dpi=dpi)
        self.scale = scale
        self.ax = self.fig.add_subplot(111)
        self.ax_ddta = self.ax.twinx()
        self.ax_ddta.set_visible(False)
        self.ax_ddta.autoscale(enable=True, axis='y', tight=True)
        self.ax_mass = self.ax.twinx()
        self.ax_mass.set_visible(False)
        self.ax_temp = self.ax.twinx()
        # self.ax_temp.set_visible(False)
        self.ax_temp_visible_2 = True
        self.canvas = FigureCanvas(self.fig)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_move)
        self.canvas.mpl_connect('button_press_event', self.on_button_press)
        self.toolbar = NavigationToolbar(self.canvas, None)
        self.segments_dta: list[SegmentDTA] = []
        self.selectMode = None # 0 - peaktool, 1 - onsettool
        self.picked = False
        self.set_visible(False)
        self.items: list[SegmentDTA | Peak | OnsetLine | MyAnn] = []

    def on_close(self):
        self.clear()
        self.remove_segments()
        self.set_visible(False)

    def update_axes_spines_position(self):
        shift = 0
        if self.ax_temp.get_visible():
            self.ax_temp.spines['right'].set_position(('outward', shift))
            shift += 48
        if self.ax_ddta.get_visible():
            self.ax_ddta.spines['right'].set_position(('outward', shift))

    def on_checkbox_temp(self, checked: bool):
        state = checked and self.ax_temp_visible_2
        self.ax_temp.set_visible(state)
        self.update_axes_spines_position()
        self.fig.tight_layout()
        self.canvas.draw()

    def on_checkbox_ddta(self, checked: bool):
        self.ax_ddta.set_visible(checked)
        self.update_axes_spines_position()
        self.fig.tight_layout()
        self.canvas.draw()

    def on_button_press(self, event: MouseEvent):
        if not event.inaxes:
            return # вне графика
        picked = [item for item in self.items if item.contains(event)[0]]
        if not picked:
            return
        item = picked[0]
        self.on_pick(item, event)
        self.holding_item = item

    def set_exo(self):
        if self.measurement_exo:
            a = '↑'
        else:
            a = '↓'
        self.ax.text(0 + 5 / self.getWidth(), 1 - 5 / self.getHeight(), s=f'exo{a}', horizontalalignment='left',
                        verticalalignment='top', transform=self.ax.transAxes)

    def getHeight(self) -> int:
        return int(self.canvas.get_renderer().height)
    
    def getWidth(self) -> int:
        return int(self.canvas.get_renderer().width)

    def set_xlabel(self, xaxis: str):
        self.ax.set_xlabel(f'{xaxis}, {self.get_units(xaxis)}')#, {self.segments[0].df[xaxis].units.to_compact()}')

    def get_units(self, axis: str):
        unit = str(self.units[axis])
        # убрать пробелы перед и после / в unit
        if '/' in unit:
            unit = unit.replace(' ', '')
        return unit

    def set_visible(self, visible: bool):
        self.fig.set_visible(visible)
        if visible:
            self.fig.tight_layout()
        self.canvas.draw()

    def autoscale(self, redraw=True):
        self.autoscale_segments(0)
        if self.ax_ddta.get_visible():
            self.autoscale_segments(1)
        if self.ax_temp.get_visible() and self.ax_temp_visible_2:
            self.autoscale_segments(2)
        if redraw:
            self.canvas.draw()

    def autoscale_segments(self, segments_type: int):
        """
        segments_type: 0 - dta, 1 - ddta, 2 - temp
        """
        if segments_type == 0:
            visible_segments = [segment for segment in self.segments_dta if segment.get_visible()]
        elif segments_type == 1:
            visible_segments = [segment.dsegment for segment in self.segments_dta if segment.dsegment.get_visible()]
        elif segments_type == 2:
            visible_segments = [segment.temp_segment for segment in self.segments_dta if segment.temp_segment.get_visible()]
        if not visible_segments:
            return
        
        x_values = [segment.xmax for segment in visible_segments] + [segment.xmin for segment in visible_segments]
        y_values = [segment.ymax for segment in visible_segments] + [segment.ymin for segment in visible_segments]
        x_max = max(x_values)
        x_min = min(x_values)
        y_max = max(y_values)
        y_min = min(y_values)
        rx = x_max - x_min
        ry = y_max - y_min

        if segments_type == 0:
            self.ax.set_xlim(xmin=x_min-rx*0.05, xmax=x_max+rx*0.05)
            self.ax.set_ylim(ymin=y_min-ry*0.05, ymax=y_max+ry*0.05)
        elif segments_type == 1:
            self.ax_ddta.set_xlim(xmin=x_min-rx*0.05, xmax=x_max+rx*0.05)
            self.ax_ddta.set_ylim(ymin=y_min-ry*0.05, ymax=y_max+ry*0.05)
        elif segments_type == 2:
            self.ax_temp.set_xlim(xmin=x_min-rx*0.05, xmax=x_max+rx*0.05)
            self.ax_temp.set_ylim(ymin=y_min-ry*0.05, ymax=y_max+ry*0.05)

    def getCurrentXaxis(self) -> str:
        return self.parent().combobox_xaxis.currentText()

    def updateAxes(self):
        xaxis = self.getCurrentXaxis()
        self.ax_temp_visible_2 = xaxis == 'Time'
        if self.ax_temp_visible_2:
            self.ax.spines.bottom.set_color('black')
            self.ax.xaxis.set_tick_params(color='black')
            self.ax.xaxis.label.set_color('black')
        else:
            self.ax.spines.bottom.set_color('red')
            self.ax.xaxis.set_tick_params(color='red')
            self.ax.xaxis.label.set_color('red')
        self.on_checkbox_temp(self.parent().checkbox_temp.isChecked())
        self.update_axes_spines_position()
        yaxis = 'DTA'
        self.set_xlabel(xaxis)
        for segment in self.segments_dta:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            segment.peaksSetData(xaxis=xaxis)
        self.autoscale(redraw=False)
        self.fig.tight_layout()
        self.canvas.draw()

    def remove_segments(self):
        self.segments_dta.clear()

    def plot(self, xaxis: str, yaxis: str, has_massdata=True, has_tempdata=True):
        if has_tempdata:
            temp_axis = "Temp."
        else:
            temp_axis = 'EMF'
        self.clear()
        for segment in self.segments_dta:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            self.ax.add_line(segment)
            self.ax_ddta.add_line(segment.dsegment)
            self.ax_temp.add_line(segment.temp_segment)
        self.set_xlabel(xaxis)
        self.ax.set_ylabel(f'{"DTA"}, {self.get_units("DTA")}', color='blue')
        self.ax.yaxis.set_tick_params(color='blue')
        self.ax.spines.left.set_color('blue')
        if has_massdata:
            self.ax_mass.set_ylabel(f'{"Mass"}, {self.get_units("Mass")}')
        self.ax.autoscale_view()
        self.ax_ddta.set_ylabel('dDTA/dT')
        self.ax_ddta.yaxis.set_label_position('right')
        self.ax_ddta.autoscale_view()
        self.ax_temp.set_ylabel(f'{temp_axis}, {self.get_units(temp_axis)}', color='red')
        self.ax_temp.yaxis.set_label_position('right')
        self.ax_temp.yaxis.set_tick_params(color='red')
        self.ax_temp.spines['right'].set_color('red')
        self.ax_temp.autoscale_view()
        self.canvas.draw()

    def on_move(self, event: MouseEvent):
        if event.button == 1:
            if event.inaxes:
                match self.holding_item:
                    case Selector():
                        x = event.xdata
                        self.holding_item.set_x(x)
                    case MyAnn():
                        if event.inaxes == self.ax:
                            ydata = event.ydata
                        else:
                            trans = event.inaxes.transData + self.ax.transData.inverted()
                            ydata = trans.transform((event.xdata, event.ydata))[1]
                        self.holding_item.set_position((event.xdata, ydata))
                self.canvas.draw()
                
    def on_unpick(self):
        if isinstance(self.holding_item, Selector):
            self.picked_item = None
            self.picked = False

    def on_button_release(self, event: MouseEvent):
        self.on_unpick()
        self.holding_item = None

    def on_remove(self):
        self.picked_peak = None
        self.picked_segment = None
        self.picked = False
        self.signal_pick.emit(None)

    def on_pick(self, item: SegmentDTA | Peak | OnsetLine| MyAnn, event: MouseEvent):
        x = event.x / self.scale
        y = (self.getHeight()-event.y) / self.scale
        pos = self.canvas.mapToGlobal(QtCore.QPoint(x,y))
        if self.picked_peak is not None: self.picked_peak.setPickEffect(False)
        if self.picked_segment is not None: self.picked_segment.setPickEffect(False)
        self.picked = True
        match item:
            case MyAnn():
                pass
            case SegmentDTA():
                self.picked_segment = item            
                item.setPickEffect(True)
            case Peak():
                self.picked_peak = item
                item.setPickEffect(True)
        if event.button == 3:
            if isinstance(item, MyAnn):  
                self.signal_cm.emit((item.parent, pos))
            else:
                self.signal_cm.emit((item, pos))
        self.picked_item = item
        self.signal_pick.emit(item)
        self.canvas.draw()

    def addSegment(self, df: pd.DataFrame, index: int, Type: int, temp_axis: str):
        segment = SegmentDTA(df=df, plotter=self, index=index, Type=Type, color='blue', temp_axis=temp_axis)
        self.segments_dta.append(segment)
        self.items.append(segment)
        return segment

    def segmentsVisible(self, arrb: list[bool]):
        for i, segment in enumerate(self.segments_dta):
            segment.set_visible(arrb[i])

    def segmentVisible(self, index: int, visible: bool):
        self.segments_dta[index].set_visible(visible)

    def clear(self):
        self.ax.clear()
        self.ax_ddta.clear()
        self.ax_temp.clear()
        self.canvas.draw()

    def gridSetVisible(self, visible: bool):
        self.ax.grid(visible=visible)
        self.canvas.draw()

    def spawn_split_selector(self, t: float):
        selector = Selector(ax=self.ax, x=t,
                            limit_x1=self.picked_item.xmin,
                            limit_x2=self.picked_item.xmax,
                            spinbox=self.parent().spinbox_t)
        self.items.append(selector)
        return selector

    def splittool_start(self):
        segment = self.picked_segment
        xdata = segment.get_xdata()
        ax_t1, ax_t2 = self.ax.get_xlim()
        ax_i1 = find_nearest(xdata, ax_t1)
        ax_i2 = find_nearest(xdata, ax_t2)
        i = ax_i1 + len(xdata[ax_i1:ax_i2]) // 2
        self.selectMode = 1
        self.selector_split = self.spawn_split_selector(t=xdata[i])
        for segment in self.segments_dta:
            segment.set_picker(False)
        self.canvas.draw()

    def splittool_done(self, apply: bool):
        for segment in self.segments_dta:
            if segment.get_visible():
                segment.set_picker(5)
        self.parent().spinbox_t.selector = None
        self.selector_split.remove()
        self.items.remove(self.selector_split)
        del self.selector_split
        if apply:
            x = self.parent().spinbox_t.value()
            log_info(f"Разделение сегмента {self.picked_segment.index} на {x}")
            segment1, segment2 = self.picked_segment.split(x=x)
            start_i = self.picked_segment.index
            end_i = len(self.segments_dta)
            for i in range(start_i+1, end_i):
                self.segments_dta[i].index += 1
            self.items.append(segment1)
            self.items.append(segment2)
            self.items.remove(self.picked_segment)
            self.picked_segment.remove()
            self.ax.add_artist(segment1)
            self.ax.add_artist(segment2)
            self.ax_ddta.add_line(segment1.dsegment)
            self.ax_ddta.add_line(segment2.dsegment)
            self.ax_temp.add_line(segment1.temp_segment)
            self.ax_temp.add_line(segment2.temp_segment)
            self.segments_dta[start_i] = segment2
            self.segments_dta.insert(start_i, segment1)
            self.signal_split.emit((segment1, segment2, start_i))
            
        self.canvas.draw()

    def onsettool_done(self, apply: bool):
        for segment in self.segments_dta:
            if segment.get_visible():
                segment.set_picker(5)
        self.parent().spinbox_onsettool_T1.selector = None
        self.parent().spinbox_onsettool_T2.selector = None
        if apply:
            t1 = self.parent().spinbox_onsettool_T1.value()
            t2 = self.parent().spinbox_onsettool_T2.value()
            line = self.picked_peak.onset(t1=t1, t2=t2, is_onset=self.is_onset)
            self.items.append(line)
            self.items.append(line.ann)
        self.despawn_selectors()
        self.canvas.draw()

    def onsettool_start(self, is_onset: bool):
        self.is_onset = is_onset
        peak = self.picked_item
        peak_xdata = peak.df_baseline[self.getCurrentXaxis()].values
        x0 = float(peak_xdata.min())
        x1 = float(peak_xdata.max())
        ci = peak_xdata.size // 2
        xc = float(peak_xdata[ci])
        if is_onset:
            self.spawn_selectors(t1=x0, t2=xc, selectMode=1)
            self.spinbox_onsettool_T1.setValue(x0)
            self.spinbox_onsettool_T2.setValue(xc)
        else:
            self.spawn_selectors(t1=xc, t2=x1, selectMode=1)
            self.spinbox_onsettool_T1.setValue(xc)
            self.spinbox_onsettool_T2.setValue(x1)
        for segment in self.segments_dta:
            segment.set_picker(False)
        self.canvas.draw()

    def peaktool_start(self):
        x1 = self.picked_item.xmin
        x2 = self.picked_item.xmax
        ax_t1, ax_t2 = self.ax.get_xlim()
        if ax_t1 > x1:
            x1 = ax_t1
        if ax_t2 < x2:
            x2 = ax_t2
        r = x2 - x1
        t1 = round(x1 + r/3, 1)
        t2 = round(x1 + 2*r/3, 1)
        self.spawn_selectors(t1=t1, t2=t2, selectMode=0)
        self.spinbox_T1.setValue(t1)
        self.spinbox_T2.setValue(t2)
        for segment in self.segments_dta:
            segment.set_picker(False)
        self.canvas.draw()

    def spawn_selectors(self, t1:float, t2:float, selectMode:int):
        """
        selectMode: 0 - выделение пика, 1 - выделение начала пика
        """
        self.selectMode = selectMode
        if self.selectMode == 0:
            limit_x1 = self.picked_item.xmin
            limit_x2 = self.picked_item.xmax
            spinbox1 = self.spinbox_T1
            spinbox2 = self.spinbox_T2
        elif self.selectMode == 1:
            xaxis = self.getCurrentXaxis()
            limit_x1 = float(self.picked_item.df_baseline[xaxis].values[0])
            limit_x2 = float(self.picked_item.df_baseline[xaxis].values[-1])
            if limit_x1 > limit_x2:
                limit_x1, limit_x2 = limit_x2, limit_x1
            spinbox1 = self.spinbox_onsettool_T1
            spinbox2 = self.spinbox_onsettool_T2
        self.selector1 = Selector(ax=self.ax, x=t1, limit_x1=limit_x1, limit_x2=limit_x2, spinbox=spinbox1)
        self.selector2 = Selector(ax=self.ax, x=t2, limit_x1=limit_x1, limit_x2=limit_x2, spinbox=spinbox2)
        spinbox1.selector = self.selector1
        spinbox2.selector = self.selector2
        self.items.append(self.selector1)
        self.items.append(self.selector2)

    def despawn_selectors(self):
        self.selector1.remove()
        self.selector2.remove()
        self.items.remove(self.selector1)
        self.items.remove(self.selector2)
        del self.selector1
        del self.selector2

    def peaktool_done(self, apply: bool):
        for segment in self.segments_dta:
            if segment.get_visible():
                segment.set_picker(5)
        if apply:
            t1 = self.selector1.get_xdata()[0]
            t2 = self.selector2.get_xdata()[0]
            log_info(f"Выделяем пик между {t1} и {t2}")
            peak = self.picked_segment.addPeak(
                t1=t1,
                t2=t2,
                baseline_type=self.parent().combobox_baselinetype.currentIndex()
                )
            self.items.append(peak)
            self.items.append(peak.ann)
        self.spinbox_T1.selector = None
        self.spinbox_T2.selector = None
        self.despawn_selectors()
        self.canvas.draw()        
