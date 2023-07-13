import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from helpers import find_nearest, make_peakbaseline, np, get_next_color
import pandas as pd

class Segment:
    line: Line2D
    index: int

    def __init__(self, df: pd.DataFrame, plotter, index) -> None:
        self.index = index
        self.plotter = plotter
        self.df = df    
        self.color = get_next_color()
        self.lw = 1.5
        self.peaks = []
    
    def add_peak(self, t1, t2):
        print("* добавляем пик")
        self.peaks.append(Peak(self, t1, t2))
    
    def draw(self):
        print("* отрисовка сегмента")
        xaxis = self.plotter.headers[self.plotter.parent.combobox_xaxis.currentIndex()]
        yaxis = self.plotter.headers[self.plotter.parent.combobox_yaxis.currentIndex()]
        self.line, = self.plotter._ax.plot(self.df[xaxis], self.df[yaxis], color=self.color, lw=self.lw)
        # if len(self.peaks) > 0:
        peak: Peak
        for peak in self.peaks:
            peak.update_xdata_to_draw()
            peak.draw()

class Plotter:
    headers: list[str] = None
    units: list[str] = None
    lines: list[Line2D] = None
    segments: list[Segment] = []
    pickedSegment: int = None
    selectedSelector: Line2D = None
    selectedSelector_limit_x1: float
    selectedSelector_limit_x2: float

    def __init__(self, parent) -> None:
        print("* инициализация плоттера")
        self.parent = parent
        self._fig = plt.figure()
        self._fig.tight_layout()
        self._ax = self._fig.gca()
        self.canvas = FigureCanvas(self._fig)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('button_release_event', self.on_unpick)
        self.canvas.mpl_connect('motion_notify_event', self.on_move)
        self.toolbar = NavigationToolbar(self.canvas, None)
        self.segments: list[Segment] = []
        self.lines = []
        self.segments_color = []
        self.segments_lw = []
        self.pickMode = 0 # 0 - сегменты, 1 - селекторы
        self.picked = False

    def remove_segments(self):
        del self.segments
        self.segments = []

    def replot(self, xaxis: str, yaxis: str):
        self.clear()
        print('* перерисовываем график')
        print(f"* ставим оси {xaxis} и {yaxis}")
        del self.lines
        self.lines = []
        peak: Peak
        for segment in self.segments:
            segment.draw()
            # segment.line, = self._ax.plot(segment.df[xaxis], segment.df[yaxis], color=segment.color, lw=segment.lw)
            xi = self.parent.combobox_xaxis.currentIndex()
            yi = self.parent.combobox_yaxis.currentIndex()
            self._ax.set_xlabel(f'{self.headers[xi]}/{self.units[xi]}')
            self._ax.set_ylabel(f'{self.headers[yi]}/{self.units[yi]}')
            segment.line.set_picker(True)
            segment.line.set_pickradius(5)
            self.lines.append(segment.line)
        self._ax.grid(visible=self.parent.checkbox_grid.checkState())
        if self.pickedSegment != None:
            self.on_pick_segment(self.segments[self.pickedSegment].line)
        self.canvas.draw()
    
    def move_selector(self, x):
        if self.selectedSelector_limit_x1< x < self.selectedSelector_limit_x2:
            self.selectedSelector.set_xdata(x)
            self._fig.canvas.draw_idle()
            if self.selectedSelector is self.selector1:
                self.parent.spinbox_T1.setValue(x)
            elif self.selectedSelector is self.selector2:
                self.parent.spinbox_T2.setValue(x)

    def on_move(self, event):
        if self.pickMode == 1:
            self.on_move_selector(event)

    def on_move_selector(self, event):
        if self.selectedSelector != None:
            if event.inaxes:
                x = event.xdata
                self.move_selector(x)

    def on_unpick(self, event):
        if self.picked:
            if self.pickMode == 1:
                # print("* селектор отпущен")
                self.selectedSelector = None
            self.picked = False

    def on_pick(self, event):
        line: Line2D = event.artist
        self.picked = True
        if self.pickMode == 0:
            self.on_pick_segment(line)
        elif self.pickMode == 1:
            self.on_pick_selector(line)

    def on_pick_selector(self, line):
        # print("* выбран селектор")
        self.selectedSelector = line
        # print(line)
        self.selectedSelector_limit_x1 = self.lines[self.pickedSegment].get_xdata()[0]
        self.selectedSelector_limit_x2 = self.lines[self.pickedSegment].get_xdata()[-1]

    def on_pick_segment(self, line):
        # устанавливаем цвета всех линий, которые были ранее
        for index, segment in enumerate(self.segments):
            segment.line.set_color(self.segments_color[index])
            segment.line.set_linewidth(self.segments_lw[index])
        # устанавливаем цвет выбранной линии
        line.set_color('black')
        line.set_linewidth(2)
        self.pickedSegment = self.lines.index(line)
        # self.parent.statusBar.showMessage(f'* выбрана линия с индексом {self.selectedSegment}')
        print(f'* выбрана линия с индексом {self.pickedSegment}')
        self.canvas.draw()

    def rememberLinesProperties(self):
        print("* запоминаем исходные свойства линий")
        for segment in self.segments:
            self.segments_color.append(segment.color)
            self.segments_lw.append(segment.lw)
        # print(self.lines_lw)

    def addSegment(self, df, index):
        print(f"* добавляем сегмент {len(self.segments)}")
        self.segments.append(Segment(df, self, index))

    def segmentVisible(self, index, visible):
        print(f"* меняем видиимость сегмента {index}")
        # print(self.segments)
        self.segments[index].line.set_visible(visible)

    def clear(self):
        print("* очищаем график")
        self._ax.clear()
        # del self.segments
        # self.segments: list[Segment] = []
        self.canvas.draw()

    def gridSetVisible(self, visible):
        print("* меняем видимость сетки")
        self._ax.grid(visible=visible)
        self.canvas.draw()

    def peaktool_start(self):
        self.pickMode = 1
        segment = self.segments[self.pickedSegment]
        xdata = segment.df[self.parent.combobox_xaxis.currentText()].to_list()
        # ydata = segment.df[self.parent.combobox_yaxis.currentText()].to_list()
        x0 = xdata[0]
        x1 = xdata[-1]
        self.parent.spinbox_T1.setRange(x0, x1)
        self.parent.spinbox_T2.setRange(x0, x1)
        # print("* ограничение селекторов")
        # print(x0, x1)
        r = x1 - x0
        t1 = round(x0 + r/3, 1)
        t2 = round(x0 + 2*r/3, 1)
        # print("* координаты селекторов")
        self.selector1 = self._ax.axvline(t1, lw=0.5, color='black')
        self.selector2 = self._ax.axvline(t2, lw=0.5, color='black')
        # print("* созданые новые селекторы")
        # print(self.selector1, self.selector2)
        self.selector1.set_antialiased(False)
        self.selector2.set_antialiased(False)
        self.parent.spinbox_T1.setValue(t1)
        self.parent.spinbox_T2.setValue(t2)
        for line in self.lines:
            line.set_picker(False)
        self.selector1.set_picker(True)
        self.selector2.set_picker(True)
        self.selector1.set_pickradius(5)
        self.selector2.set_pickradius(5)
        self.canvas.draw()

    def peaktool_done(self):
        self.pickMode = 0
        self.selector1.remove()
        self.selector2.remove()
        del self.selector1
        del self.selector2
        for line in self.lines:
            line.set_picker(True)
            line.set_pickradius(5)
        self.segments[self.pickedSegment].add_peak(
            self.parent.spinbox_T1.value(),
            self.parent.spinbox_T2.value()
            )
        self.canvas.draw()

class Peak:
    def __init__(self, segment: Segment, t1, t2) -> None:
        self.segment = segment
        xdata = self.segment.df['Time'].to_list()
        ydata = self.segment.df['DTA'].to_list()
        # print(type(xdata))
        self.i1 = find_nearest(xdata, t1)
        self.i2 = find_nearest(xdata, t2)
        self.update_xdata_to_draw()
        baseline, self.baseline_expr = make_peakbaseline(
            baselinetype=0,
            i1=self.i1, i2=self.i2,
            xdata=xdata,
            ydata=ydata
        )
        self.curve_ydata = ydata[self.i1:self.i2]
        self.baseline_ydata = list(reversed(baseline))
        self.draw()

    def update_xdata_to_draw(self):
        header = self.segment.plotter.headers[self.segment.plotter.parent.combobox_xaxis.currentIndex()]
        self.curve_xdata = self.segment.df[header][self.i1:self.i2].to_list()
        self.baseline_xdata = list(reversed(self.curve_xdata))

    def draw(self):
        xaxis_header = self.segment.plotter.headers[self.segment.plotter.parent.combobox_xaxis.currentIndex()]
        yaxis_header = self.segment.plotter.headers[self.segment.plotter.parent.combobox_yaxis.currentIndex()]
        if yaxis_header == "DTA" and ((xaxis_header == "Time") or (xaxis_header == "Temp.")):
            print("* отрисовка пика")
            xdata = self.curve_xdata + self.baseline_xdata
            ydata = self.curve_ydata + self.baseline_ydata
            # print(xdata[0], ydata[0])
            self.segment.plotter._ax.fill(
                    xdata,
                    ydata,
                    hatch = '//',
                    edgecolor=self.segment.color, facecolor='none',
                    lw=1
                )
