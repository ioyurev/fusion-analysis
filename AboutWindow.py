from PySide6 import QtWidgets

TEXT = """
Fussion Analysis
Программа для анализа измерений термического анализа
Автор: Юрьев И.О
i.o.yurev@yandex.ru
Тюмень, 2023 г.

Melt icon created by Vitaly Gorbachev - Flaticon
https://www.flaticon.com/free-icons/melt
"""

class AboutWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(TEXT)
        layout.addWidget(label)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())

def show_about():
    AboutWindow().exec()

if __name__ == '__main__':
    app = QtWidgets.QApplication()
    show_about()
    app.exec()
