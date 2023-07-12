import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from helpers import find_nearest, make_peakbaseline, np, get_next_color
import pandas as pd

class Plotter:
    def __init__(self, parent) -> None:
        print("* инициализация плоттера")
        self.parent = parent
        self.headers: list[str]
        self._fig = plt.figure()
        self._fig.tight_layout()
        self._ax = self._fig.gca()
        # self._ax.grid(visible=False)
        # self._ax.tick_params(axis='x', direction='in', length=0, width=1)
        # self._ax.tick_params(axis='y', direction='in', length=0, width=1)
        self.canvas = FigureCanvas(self._fig)
        # self.canvas.mpl_connect('pick_event', self.on_pick)
        # self.canvas.mpl_connect('button_release_event', self.on_unpick)
        # self.canvas.mpl_connect('motion_notify_event', self.on_move)
        self.previous_picked_line : Line2D = None
        self.toolbar = NavigationToolbar(self.canvas, None)
        self.segments: list[Segment] = []
        # self.lines: list[Line2D] = []
        self.segments_color = []
        self.segments_lw = []
        self.selectedSegment: int = None
        self.pickMode = 0 # 0 - сегменты, 1 - селекторы
        self.picked = False
        self.selectedSelector: Line2D = None
        self.selectedSelector_limit_x1: float
        self.selectedSelector_limit_x2: float
        self.units: list[str] = []
    
    def remove_segments(self):
        del self.segments
        self.segments = []

    def replot(self, xaxis: str, yaxis: str):
        self.clear()
        print('* перерисовываем график')
        print(f"* ставим оси {xaxis} и {yaxis}")
        for segment in self.segments:
            segment.line, = self._ax.plot(segment.df[xaxis], segment.df[yaxis], color=segment.color, lw=segment.lw)
            xi = self.parent.combobox_xaxis.currentIndex()
            yi = self.parent.combobox_yaxis.currentIndex()
            self._ax.set_xlabel(f'{self.headers[xi]}/{self.units[xi]}')
            self._ax.set_ylabel(f'{self.headers[yi]}/{self.units[yi]}')
            segment.line.set_picker(True)
            segment.line.set_pickradius(5)
        self._ax.grid(visible=self.parent.checkbox_grid.checkState())
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
                x = round(event.xdata, 1)
                self.move_selector(x)

    def on_unpick(self, event):
        if self.picked:
            if self.pickMode == 1:
                print("* селектор отпущен")
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
        print("* выбран селектор")
        self.selectedSelector = line
        # print(line)
        self.selectedSelector_limit_x1 = self.lines[self.selectedSegment].get_xdata()[0]
        self.selectedSelector_limit_x2 = self.lines[self.selectedSegment].get_xdata()[-1]

    def on_pick_segment(self, line):
        # устанавливаем цвета всех линий, которые были ранее
        for index, segment in enumerate(self.segments):
            segment.line.set_color(self.segments_color[index])
            segment.line.set_linewidth(self.segments_lw[index])
        # устанавливаем цвет выбранной линии
        line.set_color('black')
        line.set_linewidth(2)
        self.selectedSegment = self.lines.index(line)
        # self.parent.statusBar.showMessage(f'* выбрана линия с индексом {self.selectedSegment}')
        print(f'* выбрана линия с индексом {self.selectedSegment}')
        self.canvas.draw()

    def rememberLinesProperties(self):
        print("* запоминаем исходные свойства линий")
        for segment in self.segments:
            self.segments_color.append(segment.color)
            self.segments_lw.append(segment.lw)
        # print(self.lines_lw)

    def addSegment(self, df):
        print(f"* добавляем сегмент {len(self.segments)}")
        self.segments.append(Segment(df, self._ax, self))

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
        xdata = self.segments[self.selectedSegment].line.get_xdata()
        x0 = xdata[0]
        x1 = xdata[-1]
        self.parent.spinbox_T1.setRange(x0, x1)
        self.parent.spinbox_T2.setRange(x0, x1)
        print("* ограничение селекторов")
        print(x0, x1)
        r = x1 - x0
        t1 = round(x0 + r/3, 1)
        t2 = round(x0 + 2*r/3, 1)
        print("* координаты селекторов")
        self.selector1 = self._ax.axvline(t1, lw=0.5, color='black')
        self.selector2 = self._ax.axvline(t2, lw=0.5, color='black')
        print("* созданые новые селекторы")
        print(self.selector1, self.selector2)
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
        self.segments[self.selectedSegment].add_peak(
            self.parent.spinbox_T1.value(),
            self.parent.spinbox_T2.value()
            )
        self.canvas.draw()

class Segment:
    def __init__(self, df: pd.DataFrame, ax: Axes, plotter: Plotter) -> None:
        self.plotter = plotter
        self.df = df
        self.line: Line2D
        self.color = get_next_color()
        self.lw = 1.5
        # self.line.set_picker(True)
        # self.line.set_pickradius(5)
        self.peaks = []
        # self.plotter.lines.append(self.line)
    
    def add_peak(self, t1, t2):
        self.peaks.append(Peak(self, t1, t2))

class Peak:
    def __init__(self, segment: Segment, t1, t2) -> None:
        self.segment = segment
        xdata = list(segment.line.get_xdata())
        ydata = list(segment.line.get_ydata())
        # print(type(xdata))
        i1 = find_nearest(xdata, t1)
        i2 = find_nearest(xdata, t2)
        baseline, self.baseline_expr = make_peakbaseline(
            baselinetype=0,
            i1=i1, i2=i2,
            xdata=xdata,
            ydata=ydata
        )
        self.segment.plotter._ax.fill(
                xdata[i1:i2] + list(reversed(xdata[i1:i2])),
                ydata[i1:i2] + list(reversed(baseline)),
                hatch = '//',
                edgecolor=self.segment.color, facecolor='none',
                lw=1
            )
