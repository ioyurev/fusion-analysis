from PySide6 import QtCore
from Segment import SegmentDTA, Line2D, Peak, MyAnn, OnsetLine
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.backend_bases import MouseEvent
import itertools
from libn2f import TYPE_COOL, TYPE_HEAT
import pandas as pd

colors = itertools.cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])
def get_next_color():
    return next(colors)

class Selector(Line2D):
    def __init__(self, ax: Axes, x: float, spinbox, ymin=0, ymax=1, *args, **kwargs) -> None:
        self.ax = ax
        trans = self.ax.get_xaxis_transform(which='grid')
        self.spinbox = spinbox
        super().__init__(xdata=[x, x], ydata=[ymin,ymax], transform=trans, lw=0.5, color='black', *args, **kwargs)
        self.ax.add_line(self)
        self.set_picker(5)
        self.set_antialiased(False)

    def set_x(self, x: float, update_spinbox_value: bool = True):
        if update_spinbox_value: self.spinbox.setValue(x, block_signal=True)
        super().set_xdata([x, x])

class Plotter(QtCore.QObject):
    measurement_exo: int
    units: dict
    picked_selector_limit_x1: float
    picked_selector_limit_x2: float
    picked_item: SegmentDTA | Peak | OnsetLine | MyAnn = None
    picked_segment: SegmentDTA = None
    picked_peak: Peak = None
    holding_item: SegmentDTA | Peak | OnsetLine | MyAnn = None
    config: dict = None
    signal_pick = QtCore.Signal(object)
    signal_cm = QtCore.Signal(tuple)

    def __init__(self, parent, dpi, scale) -> None:
        print("* инициализация плоттера")
        super().__init__(parent)
        self.fig = plt.figure(dpi=dpi)
        self.scale = scale
        gs = self.fig.add_gridspec(2, hspace=0, height_ratios=[3, 1])
        self.ax, self.ax_ddta = gs.subplots(sharex=True)
        self.ax: Axes
        self.ax2 = self.ax.twinx()
        self.ax2.set_visible(False)
        self.ax_ddta: Axes
        self.ax_ddta.autoscale(enable=True, axis='y', tight=True)
        self.canvas = FigureCanvas(self.fig)
        # self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_move)
        self.canvas.mpl_connect('button_press_event', self.on_button_press)
        self.toolbar = NavigationToolbar(self.canvas, None)
        self.segments_dta: list[SegmentDTA] = []
        self.selectMode = None # 0 - peaktool, 1 - onsettool
        self.picked = False
        self.set_visible(False)
        self.items: list[SegmentDTA | Peak | OnsetLine | MyAnn] = []

    def on_button_press(self, event: MouseEvent):
        if not event.inaxes:
            return # вне графика
        picked = [item for item in self.items if item.contains(event)[0]]
        if not picked:
            return
        item = picked[0]
        # item.pick()
        self.on_pick(item, event)
        self.holding_item = item
        # self.on_pick(PickEvent("pick_event", self.canvas, event, item))
        # self.pick(item=picked[0], event=event)

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
        self.ax_ddta.set_xlabel(f'{xaxis}, {self.get_units(xaxis)}')#, {self.segments[0].df[xaxis].units.to_compact()}')

    def get_units(self, axis: str):
        unit = str(self.units[axis])
        # убрать пробелы перед и после / в unit
        if '/' in unit:
            unit = unit.replace(' ', '')
        return unit

    def set_visible(self, visible: bool):
        self.ax.set_visible(visible)
        self.ax_ddta.set_visible(visible)
        if visible:
            self.fig.tight_layout(pad=0)
        self.canvas.draw()

    def autoscale(self, redraw=True):
        visible_segments = [segment for segment in self.segments_dta if segment.get_visible()]
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
        
        self.ax.set_xlim(xmin=x_min-rx*0.05, xmax=x_max+rx*0.05)
        self.ax.set_ylim(ymin=y_min-ry*0.05, ymax=y_max+ry*0.05)
        if redraw:
            self.canvas.draw()

    def axesIsValidForPeaks(self):
        return self.getCurrentXaxis() in ("Time", "Temp.")

    def getCurrentXaxis(self) -> str:
        return self.parent().combobox_xaxis.currentText()

    def updateAxes(self):
        xaxis = self.getCurrentXaxis()
        yaxis = 'DTA'
        self.set_xlabel(xaxis)
        peaks_visible = self.axesIsValidForPeaks()
        for segment in self.segments_dta:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            if peaks_visible:
                segment.peaksSetData(xaxis=xaxis)
            segment.set_visible_peaks(peaks_visible)
        self.autoscale(redraw=False)
        self.fig.tight_layout(pad=0)
        self.canvas.draw()

    def remove_segments(self):
        self.segments_dta.clear()

    def plot(self, xaxis: str, yaxis: str, has_massdata=True):
        self.clear()
        for segment in self.segments_dta:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            self.ax.add_line(segment)
            self.ax_ddta.add_line(segment.dsegment)
        self.set_xlabel(xaxis)
        self.ax.set_ylabel(f'{"DTA"}, {self.get_units("DTA")}')
        if has_massdata:
            self.ax2.set_ylabel(f'{"Mass"}, {self.get_units("Mass")}')
        self.ax_ddta.set_ylabel('dDTA/dT')
        self.ax.autoscale_view()
        self.ax_ddta.autoscale_view()
        self.canvas.draw()

    def move_selector(self, selector: Selector, x: float, update_spinbox_value: bool = True):
        if self.picked_selector_limit_x1< x < self.picked_selector_limit_x2:
            if selector in (self.selector1, self.selector1_ddta):
                self.selector1.set_x(x=x, update_spinbox_value=update_spinbox_value)
                self.selector1_ddta.set_x(x=x, update_spinbox_value=update_spinbox_value)
            elif selector in (self.selector2, self.selector2_ddta):
                self.selector2.set_x(x=x, update_spinbox_value=update_spinbox_value)
                self.selector2_ddta.set_x(x=x, update_spinbox_value=update_spinbox_value)

    def on_move(self, event: MouseEvent):
        if event.button == 1:
            if event.inaxes:
                match self.holding_item:
                    case Selector():
                        x = event.xdata
                        self.move_selector(selector=self.holding_item, x=x)
                    case MyAnn():
                        if event.inaxes == self.ax:
                            ydata = event.ydata
                        elif event.inaxes == self.ax2:
                            trans = self.ax2.transAxes + self.ax.transData.inverted()
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

    def addSegment(self, df: pd.DataFrame, index: int, Type: int):
        if self.config['autocolor']:
            color = get_next_color()
        else:
            if Type == TYPE_COOL:
                color = self.config['default_cool_color']
            elif Type == TYPE_HEAT:
                color = self.config['default_heat_color']
        segment = SegmentDTA(df=df, plotter=self, index=index, Type=Type, color=color)
        self.segments_dta.append(segment)
        self.items.append(segment)

    def segmentsVisible(self, arrb: list[bool]):
        for i, segment in enumerate(self.segments_dta):
            segment.set_visible(arrb[i])

    def segmentVisible(self, index: int, visible: bool):
        self.segments_dta[index].set_visible(visible)

    def clear(self):
        self.ax.clear()
        self.ax_ddta.clear()
        self.canvas.draw()

    def gridSetVisible(self, visible: bool):
        self.ax.grid(visible=visible)
        self.ax_ddta.grid(visible=visible)
        self.canvas.draw()

    def onsettool_done(self, apply: bool):
        for segment in self.segments_dta:
            if segment.get_visible():
                segment.set_picker(5)
        self.parent().spinbox_onsettool_T1.selectors = []
        self.parent().spinbox_onsettool_T2.selectors = []
        if apply:
            line = self.picked_peak.onset(t1=self.parent().spinbox_onsettool_T1.value(), t2=self.parent().spinbox_onsettool_T2.value(), is_onset=self.is_onset)
            self.items.append(line)
            self.items.append(line.ann)
        self.despawn_selectors()
        self.canvas.draw()

    def onsettool_start(self, is_onset: bool):
        self.is_onset = is_onset
        peak = self.picked_item
        peak_xdata = peak.df_baseline[self.getCurrentXaxis()]
        x0 = min(peak_xdata)
        x1 = max(peak_xdata)
        ci = len(peak_xdata) // 2
        xc = peak_xdata[ci]
        self.parent().spinbox_onsettool_T1.setRange(x0, x1)
        self.parent().spinbox_onsettool_T2.setRange(x0, x1)
        if is_onset:
            self.spawn_selectors(t1=x0, t2=xc, selectMode=1)
            self.parent().spinbox_onsettool_T1.setValue(x0)
            self.parent().spinbox_onsettool_T2.setValue(xc)
        else:
            self.spawn_selectors(t1=xc, t2=x1, selectMode=1)
            self.parent().spinbox_onsettool_T1.setValue(xc)
            self.parent().spinbox_onsettool_T2.setValue(x1)
        for segment in self.segments_dta:
            segment.set_picker(False)
        for selector in [self.selector1, self.selector2, self.selector1_ddta, self.selector2_ddta]:
            selector.set_picker(5)
            selector.set_antialiased(False)
        self.canvas.draw()

    def peaktool_start(self):
        x0 = self.picked_item.xmin
        x1 = self.picked_item.xmax
        self.parent().spinbox_T1.setRange(x0, x1)
        self.parent().spinbox_T2.setRange(x0, x1)
        r = x1 - x0
        t1 = round(x0 + r/3, 1)
        t2 = round(x0 + 2*r/3, 1)
        self.spawn_selectors(t1=t1, t2=t2, selectMode=0)
        self.parent().spinbox_T1.setValue(t1)
        self.parent().spinbox_T2.setValue(t2)
        for segment in self.segments_dta:
            segment.set_picker(False)
        for selector in [self.selector1, self.selector2, self.selector1_ddta, self.selector2_ddta]:
            selector.set_picker(5)
            selector.set_antialiased(False)
        self.canvas.draw()

    def spawn_selectors(self, t1, t2, selectMode):
        self.selectMode = selectMode
        if self.selectMode == 0:
            self.picked_selector_limit_x1 = self.picked_item.xmin
            self.picked_selector_limit_x2 = self.picked_item.xmax
            self.selector1 = Selector(ax=self.ax, x=t1, spinbox=self.parent().spinbox_T1)
            self.selector2 = Selector(ax=self.ax, x=t2, spinbox=self.parent().spinbox_T2)
            self.selector1_ddta = Selector(ax=self.ax_ddta, x=t1, spinbox=self.parent().spinbox_T1)
            self.selector2_ddta = Selector(ax=self.ax_ddta, x=t2, spinbox=self.parent().spinbox_T2)
            self.parent().spinbox_T1.selectors = [self.selector1, self.selector1_ddta]
            self.parent().spinbox_T2.selectors = [self.selector2, self.selector2_ddta]
        elif self.selectMode == 1:
            xaxis = self.getCurrentXaxis()
            self.picked_selector_limit_x1 = self.picked_item.df_baseline[xaxis].values[0]
            self.picked_selector_limit_x2 = self.picked_item.df_baseline[xaxis].values[-1]
            if self.picked_selector_limit_x1 > self.picked_selector_limit_x2:
                self.picked_selector_limit_x1, self.picked_selector_limit_x2 = self.picked_selector_limit_x2, self.picked_selector_limit_x1
            self.selector1 = Selector(ax=self.ax, x=t1, spinbox=self.parent().spinbox_onsettool_T1)
            self.selector2 = Selector(ax=self.ax, x=t2, spinbox=self.parent().spinbox_onsettool_T2)
            self.selector1_ddta = Selector(ax=self.ax_ddta, x=t1, spinbox=self.parent().spinbox_onsettool_T1)
            self.selector2_ddta = Selector(ax=self.ax_ddta, x=t2, spinbox=self.parent().spinbox_onsettool_T2)
            self.parent().spinbox_onsettool_T1.selectors = [self.selector1, self.selector1_ddta]
            self.parent().spinbox_onsettool_T2.selectors = [self.selector2, self.selector2_ddta]
        self.items.append(self.selector1)
        self.items.append(self.selector2)
        self.items.append(self.selector1_ddta)
        self.items.append(self.selector2_ddta)

    def despawn_selectors(self):
        self.selector1.remove()
        self.selector2.remove()
        self.selector1_ddta.remove()
        self.selector2_ddta.remove()
        self.items.remove(self.selector1)
        self.items.remove(self.selector2)
        self.items.remove(self.selector1_ddta)
        self.items.remove(self.selector2_ddta)
        del self.selector1
        del self.selector2
        del self.selector1_ddta
        del self.selector2_ddta

    def peaktool_done(self, apply: bool):
        for segment in self.segments_dta:
            if segment.get_visible():
                segment.set_picker(5)
        if apply:
            peak = self.picked_segment.addPeak(
                t1=self.selector1.get_xdata()[0],
                t2=self.selector2.get_xdata()[0],
                baseline_type=self.parent().combobox_baselinetype.currentIndex()
                )
            self.items.append(peak)
            self.items.append(peak.ann)
        self.parent().spinbox_T1.selectors = []
        self.parent().spinbox_T2.selectors = []
        self.despawn_selectors()
        self.canvas.draw()        
