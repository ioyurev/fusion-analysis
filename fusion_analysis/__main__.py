import sys

from loguru import logger as log
from PySide6 import QtGui, QtWidgets

import fusion_analysis.ui.resources_rc  # noqa: F401
from fusion_analysis.main_window import MainWindow


def close_splash():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            import pyi_splash

            pyi_splash.close()
        except ModuleNotFoundError as e:
            log.exception(e)


def main():
    app = QtWidgets.QApplication(sys.argv)
    scale = QtGui.QWindow().devicePixelRatio()
    form = MainWindow(scale=scale)
    form.show()
    close_splash()
    sys.exit(app.exec())


if __name__ == "__main__":
    log.add("logs/{time}.log")
    main()
