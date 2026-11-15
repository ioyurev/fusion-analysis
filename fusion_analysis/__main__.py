from __future__ import annotations

import sys

from fusion_common.splash import (
    ANALYSIS_ICON_BG,
    finish_startup_splash,
    show_startup_splash,
)
from PySide6 import QtGui, QtWidgets

from fusion_analysis.version import VERSION


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    splash = show_startup_splash(
        app=app,
        subtitle="Thermal Analysis Tool",
        version_str=VERSION,
        icon_bg_color=ANALYSIS_ICON_BG,
    )

    from fusion_common.splash import setup_fusion_logging

    from fusion_analysis.config import APPDATA_PATH
    from fusion_analysis.main_window import MainWindow

    setup_fusion_logging(APPDATA_PATH)
    scale = QtGui.QWindow().devicePixelRatio()
    form = MainWindow(scale=scale)
    form.show()
    finish_startup_splash(splash, form)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
