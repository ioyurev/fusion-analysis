from pathlib import Path

from loguru import logger as log
from PySide6 import QtCore, QtWidgets

from .converters import c2a, n2f
from .filter_window import FilterWindow
from .plotter.plotter import Plotter
from .segment import Segment
from .segment_table_item import SegmentTableItem
from .segments_tree import TreeWidgetHandler
from .toolbar import Toolbar


class Analyzer(QtCore.QObject):
    selection_includes_treewidget = True
    fw: FilterWindow

    def __init__(self, segments: list[Segment], parent):
        super().__init__(parent)
        self.has_mass = segments[0].has_mass
        self.segments = segments

        self.toolbar = Toolbar(parent=parent)
        self.toolbar.action_xswitch.triggered.connect(self.switch_xaxis)
        self.toolbar.action_filter.triggered.connect(self.start_filter_tool)
        self.toolbar.action_split.triggered.connect(self.start_split_tool)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=parent,
        )
        self.button_box.hide()

        self.plotter = Plotter(parent=parent, segments=segments, has_mass=self.has_mass)
        self.plotter.selection_changed.connect(self.plotter_selection_changed)

        self.segments_tree_widget = QtWidgets.QTreeWidget(parent=parent)
        self.segments_tree_handler = TreeWidgetHandler(
            self.segments_tree_widget, segments=self.segments
        )
        self.segments_tree_handler.item_selection_changed.connect(
            self.treewidget_item_selection_changed
        )
        self.segments_tree_handler.item_changed.connect(self.treewidget_item_changed)

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

    @QtCore.Slot()
    def start_filter_tool(self):
        self.fw = FilterWindow(
            segment=self.plotter.picked_segment, parent=self.parent()
        )
        self.fw.show()
        self.fw.accepted.connect(self.apply_filter)

    def apply_filter(self):
        if self.fw.avg_window == 1:
            if self.plotter.picked_segment.filtered_data is not None:
                self.plotter.picked_segment.unfilter()
            return
        self.plotter.picked_segment.set_filtered_data(
            temp=self.fw.line_temp_filtered.get_ydata(),
            dta=self.fw.line_dta_filtered.get_ydata(),
            window=self.fw.avg_window,
        )
        del self.fw

    @QtCore.Slot()
    def start_split_tool(self):
        log.debug("Запущен инструмент разделения сегментов")
        self.toolbar.setEnabled(False)
        self.button_box.accepted.connect(lambda: self.stop_split_tool(accepted=True))
        self.button_box.rejected.connect(lambda: self.stop_split_tool(accepted=False))
        self.plotter.start_split_tool()
        self.button_box.show()

    def stop_split_tool(self, accepted: bool):
        log.debug("Остановлен инструмент разделения сегментов")
        self.button_box.hide()
        self.toolbar.setEnabled(True)
        x = self.plotter.stop_split_tool()
        if x is None:
            return
        if accepted:
            target_segment = self.plotter.segment_to_split
            target_index = target_segment.index
            log.debug(f"Разделение сегмента {target_index} в точке {x}")
            s1, s2 = target_segment.split(x)
            start_i = target_segment.index
            end_i = len(self.segments)
            for i in range(start_i + 1, end_i):
                self.segments[i].set_index(self.segments[i].index + 1)
            self.plotter.remove_segment(s=target_segment)
            self.plotter.add_segment(s=s1)
            self.plotter.add_segment(s=s2)
            self.segments[start_i] = s2
            self.segments.insert(start_i, s1)
            self.segments_tree_handler.split_segment(s1=s1, s2=s2)
            self.plotter.canvas.draw()

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
            selected = self.segments_tree_widget.selectedItems()
            if len(selected) > 0:
                item: SegmentTableItem = selected[0]
                index = item.segment.index
                self.select_segment(index)

    @QtCore.Slot()
    def plotter_selection_changed(self, index: int):
        self.select_segment(index=index)

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

    @QtCore.Slot()
    def switch_xaxis(self, _):
        self.plotter.switch_xaxis()
        self.plotter.tight_layout()
