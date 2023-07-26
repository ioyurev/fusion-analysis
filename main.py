import sys
from PySide6 import QtWidgets
from Gui import MainWindow
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message="The figure layout has changed to tight")

app = QtWidgets.QApplication(sys.argv)
form = MainWindow()
form.show()
sys.exit(app.exec())
