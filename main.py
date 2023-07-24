import sys
from PySide6 import QtWidgets
from Gui import MainWindow

app = QtWidgets.QApplication(sys.argv)
form = MainWindow()
form.show()
sys.exit(app.exec())
