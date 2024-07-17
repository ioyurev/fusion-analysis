from pathlib import Path

from PySide6 import QtWidgets

from .about_window import show_about
from .analyzer import Analyzer
from .ui.MainWindow import Ui_MainWindow


def remove_widgets_in_layout(layout: QtWidgets.QLayout):
    while layout.count() > 0:
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()


def get_open_filename(filter: str):
    return QtWidgets.QFileDialog.getOpenFileName(
        None, "Открыть файл измерения", filter=filter
    )[0]


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, scale):
        super().__init__()
        self.setupUi(self)
        # self.showMaximized()

        self.action_open.triggered.connect(lambda: self.open_measurement(mode=0))
        self.action_netzsch.triggered.connect(lambda: self.open_measurement(mode=1))
        self.action_about.triggered.connect(lambda: show_about(parent=self))

    def resizeEvent(self, event):
        if hasattr(self, "analyzer"):
            self.analyzer.plotter.fig.tight_layout()
        super().resizeEvent(event)

    def open_measurement(self, mode: int):
        if mode == 0:
            filename = get_open_filename(filter="(*.fus-mdt)")
        elif mode == 1:
            filename = get_open_filename(filter="(*.txt)")
        if filename == "":
            return

        if mode == 0:
            self.analyzer = Analyzer.from_collection(Path(filename), parent=self)
        elif mode == 1:
            self.analyzer = Analyzer.from_netzsch(Path(filename), parent=self)

        remove_widgets_in_layout(self.segments_tree_layout)
        self.segments_tree_layout.addWidget(self.analyzer.segments_tree_widget)

        remove_widgets_in_layout(self.plot_layout)
        self.plot_layout.addWidget(self.analyzer.toolbar)
        self.plot_layout.addWidget(self.analyzer.button_box)
        self.plot_layout.addWidget(self.analyzer.plotter.canvas)
        self.plot_layout.addWidget(self.analyzer.plotter.toolbar)

        self.analyzer.plotter.tight_layout()
