import sys
import warnings

from loguru import logger as log
from PySide6 import QtWidgets

import fusion_analysis.ui.resources_rc  # noqa: F401
from fusion_analysis.main_window import MainWindow


def main():
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
    app = QtWidgets.QApplication(sys.argv)
    form = MainWindow()
    form.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    log.add("logs/{time}.log")
    main()
