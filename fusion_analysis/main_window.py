from pathlib import Path

from PySide6 import QtWidgets

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

        self.action_netzsch.triggered.connect(self.open_netzsch)

    def resizeEvent(self, event):
        if hasattr(self, "analyzer"):
            self.analyzer.plotter.fig.tight_layout()
        super().resizeEvent(event)

    def open_netzsch(self):
        filename = get_open_filename(filter="(*.txt)")
        if filename == "":
            return
        self.analyzer = Analyzer.from_netzsch(Path(filename), parent=self)
        remove_widgets_in_layout(self.plot_layout)
        remove_widgets_in_layout(self.segments_tree_layout)
        self.segments_tree_layout.addWidget(self.analyzer.segments_tree)
        self.plot_layout.addWidget(self.analyzer.plotter.canvas)
        self.plot_layout.addWidget(self.analyzer.plotter.toolbar)
        self.analyzer.plotter.tight_layout()

        self.combobox_xaxis.currentIndexChanged.connect(self.analyzer.switch_xaxis)
        self.combobox_xaxis.setEnabled(True)
