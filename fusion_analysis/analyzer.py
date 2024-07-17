from pathlib import Path

from loguru import logger as log
from PySide6 import QtCore, QtWidgets

from .converters import c2a, n2f
from .filter_window import FilterWindow
from .plotter.plotter import Plotter
from .segment import Segment
from .segment_table_item import SegmentTableItem
from .toolbar import Toolbar


class Analyzer(QtCore.QObject):
    selection_includes_treewidget = True

    def __init__(self, segments: list[Segment], parent):
        super().__init__(parent)
        self.has_mass = segments[0].has_mass
        self.segments = segments

        self.toolbar = Toolbar(parent=parent)
        self.toolbar.action_xswitch.triggered.connect(self.switch_xaxis)
        self.toolbar.action_filter.triggered.connect(self.start_filter_dialog)

        self.plotter = Plotter(parent=parent, segments=segments, has_mass=self.has_mass)
        self.plotter.selection_changed.connect(self.plotter_selection_changed)

        self.segments_tree = QtWidgets.QTreeWidget(parent=parent)
        self.segments_tree.setHeaderHidden(True)
        self.segments_tree.itemSelectionChanged.connect(
            self.treewidget_item_selection_changed
        )
        self.segments_tree.itemChanged.connect(self.treewidget_item_changed)
        for segment in segments:
            self.segments_tree.addTopLevelItem(segment.table_item)

    @staticmethod
    def from_collection(path: Path, parent):
        log.debug(f"Открытие измерения Fusion Collection: {path}")
        data = c2a(path)
        segment = Segment.from_collection(data)
        analyzer = Analyzer(segments=[segment], parent=parent)
        return analyzer

    @staticmethod
    def from_netzsch(path: Path, parent):
        log.debug(f"Импорт измерения Netzsch: {path}")
        netzsch_segments = n2f(path)
        segments: list[Segment] = list()
        for ns in netzsch_segments:
            segment = Segment.from_netzsch(ns)
            segments.append(segment)
        return Analyzer(segments=segments, parent=parent)

    def start_filter_dialog(self):
        fw = FilterWindow(segment=self.plotter.picked_segment, parent=self.parent())
        fw.show()
        fw.accepted.connect(
            lambda: self.plotter.picked_segment.set_filtered_data(
                temp=fw.line_temp_filtered.get_ydata(),
                dta=fw.line_dta_filtered.get_ydata(),
                window=fw.avg_window,
            )
        )

    @QtCore.Slot()
    def treewidget_item_changed(self, item: SegmentTableItem):
        enabled = item.checkState(0) == QtCore.Qt.CheckState.Checked
        if item.segment.is_selected and not enabled:
            self.select_segment(-1)
        item.segment.set_enabled(enabled)
        self.plotter.update_all_axes_limits()
        self.plotter.tight_layout()

    @QtCore.Slot()
    def treewidget_item_selection_changed(self):
        if self.selection_includes_treewidget:
            selected = self.segments_tree.selectedItems()
            if len(selected) > 0:
                item: SegmentTableItem = selected[0]
                index = item.segment.index
                self.select_segment(index)

    def plotter_selection_changed(self, index: int):
        self.select_segment(index=index)

    @QtCore.Slot(int)
    def select_segment(self, index: int):
        self.selection_includes_treewidget = False
        for segment in self.segments:
            segment.set_selected(False)
        if index > -1:
            self.segments[index].set_selected(True)
            self.toolbar.segment_selected()
        else:
            log.debug("Выделение снято")
            self.toolbar.none_selected()
        self.selection_includes_treewidget = True
        self.plotter.canvas.draw()

    def switch_xaxis(self, _):
        self.plotter.switch_xaxis()
        self.plotter.tight_layout()
