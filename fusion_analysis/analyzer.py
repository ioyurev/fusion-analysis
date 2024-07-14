from pathlib import Path

from loguru import logger as log
from PySide6 import QtCore, QtWidgets

from .converters import n2f
from .plotter import Plotter
from .segment import Segment
from .segment_table_item import SegmentTableItem


class Analyzer(QtCore.QObject):
    selection_includes_treewidget = True

    def __init__(self, segments: list[Segment], parent):
        super().__init__(parent)
        self.segments = segments
        self.plotter = Plotter(parent=parent, segments=segments)
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
    def from_netzsch(path: Path, parent):
        log.debug(f"Импорт измерения Netzsch {path}")
        netzsch_segments = n2f(path)
        segments: list[Segment] = list()
        for ns in netzsch_segments:
            segment = Segment.from_netzsch(ns)
            segments.append(segment)
        return Analyzer(segments=segments, parent=parent)

    @QtCore.Slot()
    def treewidget_item_changed(self, item: SegmentTableItem):
        enabled = item.checkState(0) == QtCore.Qt.CheckState.Checked
        item.segment.set_enabled(enabled)
        if item.segment.is_selected and not enabled:
            self.select_segment(-1)
        self.plotter.update_all_axes_limits()
        self.plotter.tight_layout()

    @QtCore.Slot()
    def treewidget_item_selection_changed(self):
        if self.selection_includes_treewidget:
            selected = self.segments_tree.selectedItems()
            if len(selected) > 0:
                item: SegmentTableItem = selected[0]
                # if item.segment
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
        self.selection_includes_treewidget = True
        self.plotter.canvas.draw()

    def switch_xaxis(self, xaxis_index: int):
        if xaxis_index > 1:
            raise Exception("Не реализованный вариант оси X")
        self.plotter.set_xaxis(xaxis_index)
        self.plotter.tight_layout()
