import os
import sys
from PySide6 import QtWidgets, QtGui
from app.Gui import MainWindow
import warnings
import logging
import datetime


def run():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            import pyi_splash

            pyi_splash.update_text("UI Loaded ...")
            pyi_splash.close()
        except ModuleNotFoundError as e:
            print(e)

    warnings.filterwarnings(
        "ignore", category=UserWarning, message="The figure layout has changed to tight"
    )

    log_file = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log")
    logs_folder = f"{os.path.dirname(sys.argv[0])}\\logs"
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
    logging.basicConfig(
        level=logging.INFO,
        filename=f"{logs_folder}\\{log_file}",
        filemode="w",
        format="%(asctime)s %(levelname)s %(message)s",
    )

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    scale = QtGui.QWindow().devicePixelRatio()
    dpi = app.screens()[0].logicalDotsPerInch() * scale
    form = MainWindow(dpi=dpi, scale=scale)
    form.show()
    sys.exit(app.exec())
