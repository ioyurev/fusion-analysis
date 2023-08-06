import sys
from PySide6 import QtWidgets, QtGui
from Gui import MainWindow
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message="The figure layout has changed to tight")

app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')
scale = QtGui.QWindow().devicePixelRatio()
dpi = app.screens()[0].logicalDotsPerInch() * scale 
form = MainWindow(dpi=dpi, scale=scale)
form.show()
sys.exit(app.exec())
