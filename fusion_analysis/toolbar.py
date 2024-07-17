from PySide6 import QtGui, QtWidgets


class Toolbar(QtWidgets.QToolBar):
    def __init__(self, parent):
        super().__init__(parent)
        # self.setContentsMargins(0, 0, 0, 0)
        self.action_xswitch = QtGui.QAction("Смена оси X", self)
        self.action_xswitch.setIcon(QtGui.QIcon(":/xswitch.png"))
        self.addAction(self.action_xswitch)

        self.addSeparator()

        self.action_filter = QtGui.QAction("Фильтрация", self)
        self.action_filter.setIcon(QtGui.QIcon(":/filter.png"))
        self.addAction(self.action_filter)

        self.action_split = QtGui.QAction("Разделить", self)
        self.action_split.setIcon(QtGui.QIcon(":/split.png"))
        self.addAction(self.action_split)

        self.addSeparator()

        self.action_peak = QtGui.QAction("Пик", self)
        self.action_peak.setIcon(QtGui.QIcon(":/peak.png"))
        self.addAction(self.action_peak)

        self.action_onset = QtGui.QAction("Начало", self)
        self.action_onset.setIcon(QtGui.QIcon(":/onset.png"))
        self.addAction(self.action_onset)

        self.action_end = QtGui.QAction("Конец", self)
        self.action_end.setIcon(QtGui.QIcon(":/end.png"))
        self.addAction(self.action_end)

        self.none_selected()

    def segment_selected(self):
        self.action_filter.setEnabled(True)
        self.action_split.setEnabled(True)
        self.action_peak.setEnabled(True)
        self.action_onset.setEnabled(False)
        self.action_end.setEnabled(False)

    def peak_selected(self):
        self.action_filter.setEnabled(False)
        self.action_split.setEnabled(False)
        self.action_peak.setEnabled(False)
        self.action_onset.setEnabled(True)
        self.action_end.setEnabled(True)

    def none_selected(self):
        self.action_filter.setEnabled(False)
        self.action_split.setEnabled(False)
        self.action_peak.setEnabled(False)
        self.action_onset.setEnabled(False)
        self.action_end.setEnabled(False)
