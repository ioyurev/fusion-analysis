from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from .segment import Segment


class SegmentTableItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, segment: "Segment", parent=None):
        super().__init__(parent)
        self.segment = segment
        self.setCheckState(0, QtCore.Qt.CheckState.Checked)
        t1 = segment.data.min_temp
        t2 = segment.data.max_temp
        self.setText(0, f"{t1} - {t2}")

    def set_selected(self, b: bool):
        self.setSelected(b)
