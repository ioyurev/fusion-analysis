from Segment import Segment, Line2D
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)


class Plotter:
    # headers: list[str] = None
    # units: list[str] = None
    pickedSegment: int = None
    pickedSelector: Line2D = None
    pickedSelector_limit_x1: float
    pickedSelector_limit_x2: float

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
        self.picked = False

    def axesIsValidForPeaks(self):
        return self.getCurrentYaxis() == "DTA" and (self.getCurrentXaxis() in ("Time", "Temp."))

    def getCurrentXaxis(self) -> str:
        return self.parent.combobox_xaxis.currentText()

    def getCurrentYaxis(self) -> str:
        return self.parent.combobox_yaxis.currentText()

    def updateAxes(self):
        xaxis = self.getCurrentXaxis()
        yaxis = self.getCurrentYaxis()
        self.ax_ddta.set_xlabel(f'{xaxis}')#/{self.units[xi]}')
        self.ax.set_ylabel(f'{yaxis}')#/{self.units[yi]}')
        xmax = []
        xmin = []
        ymax = []
        ymin = []
        peaks_visible = self.axesIsValidForPeaks()
        for segment in self.segments:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            if peaks_visible:
                segment.peaksSetData(xaxis=xaxis)
            segment.set_visible_peaks(peaks_visible)
            xmax.append(segment.xmax)
            xmin.append(segment.xmin)
            ymax.append(segment.ymax)
            ymin.append(segment.ymin)
        x_max = max(xmax)
        x_min = min(xmin)
        y_max = max(ymax)
        y_min = min(ymin)
        rx = x_max - x_min
        ry = y_max - y_min
        self.ax.set_xlim(xmin=x_min-rx*0.05, xmax=x_max+rx*0.05)
        self.ax.set_ylim(ymin=y_min-ry*0.05, ymax=y_max+ry*0.05)
        self.canvas.draw()

    def remove_segments(self):
        del self.segments
        self.segments = []

    def plot(self, xaxis: str, yaxis: str):
        self.clear()
        print('* рисуем график')
        print(f"* ставим оси {xaxis} и {yaxis}")
        for segment in self.segments:
            segment.set_axes(xaxis=xaxis, yaxis=yaxis)
            self.ax.add_line(segment)
            self.ax_ddta.add_line(segment.dsegment)
            # segment.line, = self.ax.plot(segment.df[xaxis], segment.df[yaxis], color=segment.color, lw=segment.lw)
            # xi = self.parent.combobox_xaxis.currentIndex()
            # yi = self.parent.combobox_yaxis.currentIndex()
            self.ax_ddta.set_xlabel(f'{xaxis}')#/{self.units[xi]}')
            self.ax.set_ylabel(f'{yaxis}')#/{self.units[yi]}')
            self.ax_ddta.set_ylabel(f'dDTA/dT')
            # segment.set_picker(True)
            # segment.set_pickradius(5)
            # self.lines.append(segment.line)
            # self.lines_ddta.append(segment.line_ddta)
        self.ax.autoscale_view()
        self.ax_ddta.autoscale_view()
        self.ax.grid(visible=self.parent.checkbox_grid.checkState())
        self.pickSegment(self.pickedSegment)
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

    def on_move(self, event):
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

    def on_button_release(self, event):
        self.on_unpick(event)

    def on_pick(self, event):
        line: Segment = event.artist
        self.picked = True
        if self.pickMode == 0:
            index = line.index
            self.parent.list_segments.setCurrentItem(self.parent.list_segments.item(index))
            self.pickSegment(index)
        elif self.pickMode == 1:
            self.pickSelector(line)

    def pickSelector(self, line):
        # print("* выбран селектор")
        self.pickedSelector = line
        self.pickedSelector_limit_x1 = self.segments[self.pickedSegment].xmin
        self.pickedSelector_limit_x2 = self.segments[self.pickedSegment].xmax

    def pickSegment(self, index):
        self.pickedSegment = index
        if index is None:
            return
        for segment in self.segments:
            segment.setPickEffect(False)
        self.segments[index].setPickEffect(True)
        self.canvas.draw()
        # print(f'* выбрана линия с индексом {index}')

    def addSegment(self, df, index):
        print(f"* добавляем сегмент {len(self.segments)}")
        self.segments.append(Segment(df=df, plotter=self, index=index))

    def segmentsVisible(self, arrb: list[bool]):
        segment: Segment
        for i, segment in enumerate(self.segments):
            segment.set_visible(arrb[i])

    def segmentVisible(self, index, visible):
        self.segments[index].set_visible(visible)

    def clear(self):
        print("* очищаем график")
        self.ax.clear()
        self.ax_ddta.clear()
        self.canvas.draw()

    def gridSetVisible(self, visible):
        print("* меняем видимость сетки")
        self.ax.grid(visible=visible)
        self.ax_ddta.grid(visible=visible)
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
        self.selector1 = self.ax.axvline(t1, lw=0.5, color='black')
        self.selector2 = self.ax.axvline(t2, lw=0.5, color='black')
        self.selector1_ddta = self.ax_ddta.axvline(t1, lw=0.5, color='black')
        self.selector2_ddta = self.ax_ddta.axvline(t2, lw=0.5, color='black')
        self.selector1.set_antialiased(False)
        self.selector2.set_antialiased(False)
        self.selector1_ddta.set_antialiased(False)
        self.selector2_ddta.set_antialiased(False)
        self.parent.spinbox_T1.setValue(t1)
        self.parent.spinbox_T2.setValue(t2)
        for segment in self.segments:
            segment.set_picker(False)
        self.selector1.set_picker(True)
        self.selector2.set_picker(True)
        self.selector1_ddta.set_picker(True)
        self.selector2_ddta.set_picker(True)
        self.selector1.set_pickradius(5)
        self.selector2.set_pickradius(5)
        self.selector1_ddta.set_pickradius(5)
        self.selector2_ddta.set_pickradius(5)
        self.canvas.draw()

    def peaktool_done(self, apply: bool):
        self.pickMode = 0
        for line in (self.selector1, self.selector2, self.selector1_ddta, self.selector2_ddta):
            line.remove()
            del line
        for segment in self.segments:
            if segment.get_visible():
                segment.make_pickable(True)
        if apply:
            self.segments[self.pickedSegment].addPeak(
                self.parent.spinbox_T1.value(),
                self.parent.spinbox_T2.value()
                )
        self.canvas.draw()
