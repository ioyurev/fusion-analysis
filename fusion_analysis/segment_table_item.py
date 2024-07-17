from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from .segment import Segment


class SegmentTableItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, segment: "Segment"):
        super().__init__()
        self.segment = segment
        self.setCheckState(0, QtCore.Qt.CheckState.Checked)
        t1 = segment.data.temp[0]
        t2 = segment.data.temp[-1]
        self.setText(0, f"{t1} - {t2}")

    def set_selected(self, b: bool):
        self.setSelected(b)
