from loguru import logger as log
from PySide6 import QtWidgets

from .ui.MainWindow import Ui_MainWindow


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, scale):
        log.info("* загрузка интерфейса")
        super().__init__()
        self.setupUi(self)
        self.showMaximized()
