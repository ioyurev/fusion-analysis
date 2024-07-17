from PySide6 import QtCore, QtWidgets

from .segment import Segment
from .segment_table_item import SegmentTableItem


class TreeWidgetHandler(QtCore.QObject):
    item_selection_changed = QtCore.Signal(int)
    item_changed = QtCore.Signal(SegmentTableItem)
    items: list[SegmentTableItem] = []

    def __init__(self, widget: QtWidgets.QTreeWidget, segments: list[Segment]):
        super().__init__()
        self.widget = widget
        self.widget.setHeaderHidden(True)
        self.widget.itemSelectionChanged.connect(self.emit_selected_index)
        self.widget.itemChanged.connect(self.emit_item_changed)
        for segment in segments:
            self.items.append(segment.table_item)
            self.widget.addTopLevelItem(segment.table_item)

    def split_segment(self, s1: Segment, s2: Segment):
        for item in self.items:
            self.widget.invisibleRootItem().removeChild(item)
        i = s1.index
        self.items[i] = s2.table_item
        self.items.insert(i, s1.table_item)
        for item in self.items:
            self.widget.addTopLevelItem(item)

    @QtCore.Slot()
    def emit_selected_index(self):
        selected = self.widget.selectedItems()
        if len(selected) > 0:
            item: SegmentTableItem = selected[0]
            index = item.segment.index
        else:
            index = -1
        self.item_selection_changed.emit(index)

    @QtCore.Slot(SegmentTableItem)
    def emit_item_changed(self, item: SegmentTableItem):
        self.item_changed.emit(item)
