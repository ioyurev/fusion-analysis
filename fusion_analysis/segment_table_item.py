from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from .segment import Segment


class SegmentTableItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, segment: "Segment", parent=None):
        super().__init__(parent)
        self.segment = segment
        self.setCheckState(0, QtCore.Qt.CheckState.Checked)
        if segment.data.emf is not None:
            t1 = segment.data.emf[0]
            t2 = segment.data.emf[-1]
        if segment.data.temp is not None:
            t1 = int(round(segment.data.temp[0], 0))
            t2 = int(round(segment.data.temp[-1], 0))
        self.setText(0, f"{t1} - {t2}")

    def set_selected(self, b: bool):
        self.setSelected(b)
