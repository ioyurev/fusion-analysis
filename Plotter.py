from Segment import Segment, Line2D, Annotation, Peak
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.backend_bases import MouseEvent, PickEvent
from PySide6 import QtCore

class Plotter:
    # headers: list[str] = None
    units: dict
    pickedSegment: int = None
    pickedSelector: Line2D = None
    pickedSelector_limit_x1: float
    pickedSelector_limit_x2: float
    pickedPeak: Peak = None

    def __init__(self, parent) -> None:
        print("* инициализация плоттера")
        self.parent = parent
        self.fig = plt.figure()
        # self.fig.tight_layout()
        gs = self.fig.add_gridspec(2, hspace=0, height_ratios=[3, 1])
        # self.ax, self.ax_ddta = self.fig.subplots(2, sharex=True, height_ratios=[3, 1])
        self.ax, self.ax_ddta = gs.subplots(sharex=True)
        self.ax: Axes
        self.ax_ddta: Axes
        self.ax_ddta.autoscale(enable=True, axis='y', tight=True)
        # self.ax_ddta = self.fig.gca()
        # self.ax = self.ax_ddta.twinx()
        self.canvas = FigureCanvas(self.fig)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_move)
        # self.canvas.mpl_connect('scroll_event', self.on_zoom)
        self.toolbar = NavigationToolbar(self.canvas, None)
        self.segments: list[Segment] = []
        # self.lines: list[Line2D] = None
        # self.lines_ddta: list[Line2D] = None
        self.segments_color = []
        self.segments_lw = []
        self.pickMode = 0 # 0 - сегменты, 1 - селекторы
        self.selectMode = None # 0 - peaktool, 1 - onsettool
        self.picked = False
        self.set_visible(False)

    def getHeight(self):
        return int(self.canvas.get_renderer().height)

    def set_xlabel(self, xaxis: str):
        self.ax_ddta.set_xlabel(f'{xaxis}, {self.get_units(xaxis)}')#, {self.segments[0].df[xaxis].units.to_compact()}')

    def set_ylabel(self, yaxis: str):
        self.ax.set_ylabel(f'{yaxis}, {self.get_units(yaxis)}')#, {self.segments[0].df[yaxis].units.to_compact()}')

    def get_units(self, axis: str):
        unit = str(self.units[axis])
        # убрать пробелы перед и после / в unit
        if '/' in unit:
            unit = unit.replace(' ', '')
        return unit

    def set_visible(self, visible: bool):
        self.ax.set_visible(visible)
        self.ax_ddta.set_visible(visible)
        self.canvas.draw()

    def autoscale(self):
        visible_segments = [segment for segment in self.segments if segment.get_visible()]
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
        self.canvas.draw()

    def axesIsValidForPeaks(self):
        return self.getCurrentYaxis() == "DTA" and (self.getCurrentXaxis() in ("Time", "Temp."))

    def getCurrentXaxis(self) -> str:
        return self.parent.combobox_xaxis.currentText()

    def getCurrentYaxis(self) -> str:
        return self.parent.combobox_yaxis.currentText()

    def updateAxes(self):
        xaxis = self.getCurrentXaxis()
        yaxis = self.getCurrentYaxis()
        self.set_xlabel(xaxis)
        self.set_ylabel(yaxis)
        peaks_visible = self.axesIsValidForPeaks()
        for segment in self.segments:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            if peaks_visible:
                segment.peaksSetData(xaxis=xaxis)
            segment.set_visible_peaks(peaks_visible)
        self.autoscale()

    def remove_segments(self):
        self.segments.clear()

    def plot(self, xaxis: str, yaxis: str):
        self.clear()
        print('* рисуем график')
        print(f"* ставим оси {xaxis} и {yaxis}")
        for segment in self.segments:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            self.ax.add_line(segment)
            self.ax_ddta.add_line(segment.dsegment)
        self.set_xlabel(xaxis)
        self.set_ylabel(yaxis)
        self.ax_ddta.set_ylabel(f'dDTA/dT')
        self.ax.autoscale_view()
        self.ax_ddta.autoscale_view()
        self.canvas.draw()
    
    def move_selector(self, x):
        if self.pickedSelector_limit_x1< x < self.pickedSelector_limit_x2:
            self.fig.canvas.draw_idle()
            if self.pickedSelector in (self.selector1, self.selector1_ddta):
                self.selector1.set_xdata(x)
                self.selector1_ddta.set_xdata(x)
                self.parent.spinbox_T1.setValue(x)
            elif self.pickedSelector in (self.selector2, self.selector2_ddta):
                self.selector2.set_xdata(x)
                self.selector2_ddta.set_xdata(x)
                self.parent.spinbox_T2.setValue(x)

    def on_move(self, event: MouseEvent):
        if self.pickMode == 1:
            self.on_move_selector(event)

    def on_move_selector(self, event):
        if self.pickedSelector != None:
            if event.inaxes:
                x = event.xdata
                self.move_selector(x)

    def on_unpick(self, event):
        if self.picked:
            if self.pickMode == 1:
                # print("* селектор отпущен")
                self.pickedSelector = None
            self.picked = False

    def on_button_release(self, event: MouseEvent):
        self.on_unpick(event)

    def on_pick(self, event: PickEvent):
        line = event.artist
        if isinstance(line, Annotation):
            return
        self.picked = True
        if self.pickMode == 0:
            if isinstance(line, Segment):
                self.parent.on_pick_segment(True)
                self.parent.on_pick_peak(False)
                self.pickSegment(line)
                if event.mouseevent.button == 3:
                    self.segmentContextMenu(event)
            elif isinstance(line, Peak):
                self.pickPeak(line)
                self.parent.on_pick_segment(False)
                self.parent.on_pick_peak(True)
                if event.mouseevent.button == 3:
                    self.peakContextMenu(event)
        elif self.pickMode == 1:
            self.pickSelector(line)

    def peakContextMenu(self, event: PickEvent):
        peak = event.artist
        self.parent.cm_peak.setTitle(f"Пик. {peak.area}")
        point = QtCore.QPoint(event.mouseevent.x, self.getHeight()-event.mouseevent.y)
        self.parent.cm_peak.popup(self.canvas.mapToGlobal(point))

    def removePeak(self):
        print("* удаляем пик")
        self.pickedPeak.remove()
        self.pickedPeak = None
        self.canvas.draw()

    def segmentContextMenu(self, event: PickEvent):
        # TODO: вызов контекстное меню сегмента
        pass

    def pickPeak(self, line: Peak):
        # print("* выбран пик")
        self.pickedSegment = None
        self.pickedSelector = None
        self.pickedPeak = line
        for segment in self.segments:
            segment.setPickEffect(False)
        line.setPickEffect(True)
        self.parent.list_segments.clearSelection()
        self.canvas.draw()

    def pickSelector(self, line):
        # print("* выбран селектор")
        self.pickedSelector = line
        if self.selectMode == 0:
            self.pickedSelector_limit_x1 = self.segments[self.pickedSegment].xmin
            self.pickedSelector_limit_x2 = self.segments[self.pickedSegment].xmax
        elif self.selectMode == 1:
            self.pickedSelector_limit_x1 = self.pickedPeak.baseline_data_t[0]
            self.pickedSelector_limit_x2 = self.pickedPeak.baseline_data_t[-1]

    def pickSegment(self, line: Segment):
        if line is None:
            self.pickedSegment = None
            return
        index = line.index
        self.parent.list_segments.setCurrentItem(self.parent.list_segments.item(index))
        self.pickedSegment = index
        for segment in self.segments:
            segment.setPickEffect(False)
        self.segments[index].setPickEffect(True)
        if self.pickedPeak:
            self.pickedPeak.setPickEffect(False)
        self.pickedPeak = None
        self.canvas.draw()
        # print(f'* выбрана линия с индексом {index}')

    def addSegment(self, df, index):
        # print(f"* добавляем сегмент {len(self.segments)}")
        self.segments.append(Segment(df=df, plotter=self, index=index))

    def segmentsVisible(self, arrb: list[bool]):
        segment: Segment
        for i, segment in enumerate(self.segments):
            segment.set_visible(arrb[i])

    def segmentVisible(self, index: int, visible: bool):
        self.segments[index].set_visible(visible)

    def clear(self):
        self.ax.clear()
        self.ax_ddta.clear()
        self.canvas.draw()

    def gridSetVisible(self, visible: bool):
        self.ax.grid(visible=visible)
        self.ax_ddta.grid(visible=visible)
        self.canvas.draw()

    def onsettool_done(self, apply: bool):
        self.pickMode = 0
        for line in (self.selector1, self.selector2, self.selector1_ddta, self.selector2_ddta):
            line.remove()
            del line
        for segment in self.segments:
            if segment.get_visible():
                segment.set_picker(5)
        if apply:
            self.pickedPeak.onset(t1=self.parent.spinbox_onsettool_T1.value(), t2=self.parent.spinbox_onsettool_T2.value())
            self.canvas.draw()

    def onsettool_start(self):
        self.pickMode = 1
        peak = self.pickedPeak
        x0 = min(peak.baseline_data_t)
        x1 = max(peak.baseline_data_t)
        ci = len(peak.baseline_data_t) // 2
        xc = peak.baseline_data_t[ci]
        self.parent.spinbox_onsettool_T1.setRange(x0, x1)
        self.parent.spinbox_onsettool_T2.setRange(x0, x1)

        self.spawn_selectors(t1=x0, t2=xc, selectMode=1)

        self.parent.spinbox_onsettool_T1.setValue(x0)
        self.parent.spinbox_onsettool_T2.setValue(xc)

        for segment in self.segments:
            segment.set_picker(False)
        for selector in [self.selector1, self.selector2, self.selector1_ddta, self.selector2_ddta]:
            selector.set_picker(5)
            selector.set_antialiased(False)
        self.canvas.draw()

    def peaktool_start(self):
        self.pickMode = 1
        segment = self.segments[self.pickedSegment]
        x0 = segment.xmin
        x1 = segment.xmax
        self.parent.spinbox_T1.setRange(x0, x1)
        self.parent.spinbox_T2.setRange(x0, x1)
        r = x1 - x0
        t1 = round(x0 + r/3, 1)
        t2 = round(x0 + 2*r/3, 1)
        self.spawn_selectors(t1=t1, t2=t2, selectMode=0)
        self.parent.spinbox_T1.setValue(t1)
        self.parent.spinbox_T2.setValue(t2)
        for segment in self.segments:
            segment.set_picker(False)
        for selector in [self.selector1, self.selector2, self.selector1_ddta, self.selector2_ddta]:
            selector.set_picker(5)
            selector.set_antialiased(False)
        self.canvas.draw()

    def spawn_selectors(self, t1, t2, selectMode):
        self.selectMode = selectMode
        self.selector1 = self.ax.axvline(t1, lw=0.5, color='black')
        self.selector2 = self.ax.axvline(t2, lw=0.5, color='black')
        self.selector1_ddta = self.ax_ddta.axvline(t1, lw=0.5, color='black')
        self.selector2_ddta = self.ax_ddta.axvline(t2, lw=0.5, color='black')

    def peaktool_done(self, apply: bool):
        self.pickMode = 0
        for line in (self.selector1, self.selector2, self.selector1_ddta, self.selector2_ddta):
            line.remove()
            del line
        for segment in self.segments:
            if segment.get_visible():
                segment.set_picker(5)
        if apply:
            self.segments[self.pickedSegment].addPeak(
                self.parent.spinbox_T1.value(),
                self.parent.spinbox_T2.value()
                )
        self.canvas.draw()
