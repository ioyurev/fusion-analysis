import sys
from PyQt5 import uic, QtWidgets, QtCore, QtGui
from Plotter import Plotter
from libn2f import STAFile

Ui_MainWindow, QMainWindow = uic.loadUiType('assets/MainWindow.ui')

def warning_message(message):
    print(f'* Предупреждение. {message}')
    error_dialog = QtWidgets.QMessageBox()
    error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
    error_dialog.setText(message)
    # error_dialog.setInformativeText(message)
    error_dialog.setWindowTitle("Предупреждение")
    error_dialog.exec_()

class MainWindow(QMainWindow, Ui_MainWindow):
    btn_peaktool : QtWidgets.QPushButton
    btn_ok : QtWidgets.QPushButton
    btn_cancel : QtWidgets.QPushButton
    spinbox_T1 : QtWidgets.QSpinBox
    spinbox_T2 : QtWidgets.QSpinBox
    combobox_xaxis: QtWidgets.QComboBox
    combobox_yaxis: QtWidgets.QComboBox
    checkbox_grid: QtWidgets.QCheckBox
    # checkox_derivative: QtWidgets.QCheckBox
    action_open: QtWidgets.QAction
    action_close: QtWidgets.QAction
    list_segments : QtWidgets.QListWidget

    def __init__(self):
        print('* загрузка интерфейса')
        super().__init__()
        self.setupUi(self)
        self.showMaximized()
        # плоттер
        # self: QtWidgets.QMainWindow
        self.plotter = Plotter(self)
        # self.statusBar = QtWidgets.QStatusBar()
        # self.setStatusBar(self.statusBar)
        # добавляем холст и панель инструментов matplotlib
        self.plotLayout.addWidget(self.plotter.canvas)
        self.plotLayout.addWidget(self.plotter.toolbar)
        # находим виджеты и добавляем им обработчики событий
        self.action_open = self.findChild(QtWidgets.QAction, 'action_open')
        self.action_open.triggered.connect(self.on_click_open)
        self.action_close = self.findChild(QtWidgets.QAction, 'action_close')
        self.action_close.triggered.connect(self.on_click_close)
        
        self.btn_peaktool.clicked.connect(self.on_click_peaktool_start)
        self.btn_ok.clicked.connect(lambda: self.on_click_peaktool_done(apply=True))
        self.btn_cancel.clicked.connect(lambda: self.on_click_peaktool_done(apply=False))
        self.checkbox_grid.stateChanged.connect(self.on_checkbox_grid_changed)
        # self.checkox_derivative.stateChanged.connect(self.on_checkbox_derivative_changed)
        self.combobox_xaxis.currentIndexChanged.connect(self.on_combobox_changed)
        self.combobox_yaxis.currentIndexChanged.connect(self.on_combobox_changed)

        # стили CSS!
        # with open('toolbar.css') as f:
        #     self.setStyleSheet("".join(f.readlines()))

        # список сегментов
        self.list_segments : QtWidgets.QListWidget = self.findChild(QtWidgets.QListWidget, 'listWidget')
        self.list_segments.itemChanged.connect(self.on_item_changed)
        self.list_segments.itemSelectionChanged.connect(self.on_item_selection_changed)
        # self.list_segments.clicked.connect(self.on_item_clicked)
        self.items: list[QtWidgets.QListWidgetItem] = []
        self.measurement_is_opened = False
        self.comboboxes_is_set = False
        # QtWidgets.QStatusBar
    
    # def on_item_clicked(self, event):
    #     # print(item)
    #     if not self.list_segments.indexAt(event.pos()).isValid():
    #         print("очистка")
    #         self.list_segments.clearSelection()

    def toolsSetEnabled(self, enabled):
        self.btn_peaktool.setEnabled(enabled)
        self.combobox_xaxis.setEnabled(enabled)
        self.combobox_yaxis.setEnabled(enabled)
        self.checkbox_grid.setEnabled(enabled)
        # self.checkox_derivative.setEnabled(enabled)

    def on_item_selection_changed(self):
        selected_items = self.list_segments.selectedItems()
        if len(selected_items) == 1:
            if selected_items[0].checkState():
                index = self.list_segments.row(selected_items[0])
                self.plotter.pickSegment(index)
            else:
                self.plotter.pickSegment(None)

    def on_checkbox_grid_changed(self, state):
        self.plotter.gridSetVisible(state)

    # def on_checkbox_derivative_changed(self, state):
    #     self.plotter.derivativeSetVisible(state)

    def on_combobox_changed(self, index):
        if self.comboboxes_is_set:
            self.plotter.updateAxes()
            arrb = []
            for i in range(self.list_segments.count()):
                arrb.append(self.list_segments.item(i).checkState())
            self.plotter.segmentsVisible(arrb)

    def on_click_peaktool_done(self, apply: bool):
        self.btn_peaktool.setEnabled(True)
        self.btn_ok.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.spinbox_T1.setEnabled(False)
        self.spinbox_T2.setEnabled(False)
        self.plotter.peaktool_done(apply=apply)
        print("* инструмент выделения пика применен")

    def on_click_peaktool_start(self):
        if self.peaktool_chech_is_valid():
            print("* инструмент выделения пика запущен")
            self.btn_peaktool.setEnabled(False)
            self.btn_ok.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            self.spinbox_T1.setEnabled(True)
            self.spinbox_T2.setEnabled(True)
            self.plotter.peaktool_start()

    def peaktool_chech_is_valid(self):
        if self.plotter.pickedSegment is None:
            warning_message("Cегмент не выбран.")
            return False
        if self.combobox_yaxis.currentText() != 'DTA':
            warning_message('Неправильно выбрана ось ординат!\nДолжна быть DTA.')
            return False
        xaxis = self.combobox_xaxis.currentText()
        if xaxis in ('Time', 'Temp.'):
            pass
        else:
            warning_message('Неправильно выбрана ось абцисс!\nДолжна быть Time или Temp.')
            return False
        return True
    
    def on_click_close(self):
        # обработчик закрытия измерения
        print("* нажата кнопка закрытия измерения")
        # переключаем кнопки
        self.action_open.setEnabled(True)
        self.action_close.setEnabled(False)
        # удаляем элементы из списка
        self.list_segments.clear()
        del self.items
        self.items = []
        self.plotter.clear()
        self.plotter.remove_segments()
        self.measurement_is_opened = False
        self.toolsSetEnabled(False)

    def addSegments(self, filepath):
        stafile = STAFile(filepath)
        for index, df in enumerate(stafile.segments):
            # пределы сегмента
            t1 = round(df["Temp."].values[0])
            t2 = round(df["Temp."].values[-1])
            # добавляем сегмент к плоттеру
            self.plotter.addSegment(df, index)
            # добавляем сегмент в список интерфейса
            self.items.append(QtWidgets.QListWidgetItem(f'{t1} - {t2}', self.list_segments))
            self.items[index].setFlags(self.items[index].flags() | QtCore.Qt.ItemIsUserCheckable)
            self.items[index].setCheckState(QtCore.Qt.Checked)
            if t2 - t1 > 0:
                self.items[index].setIcon(QtGui.QIcon('assets/icon_heat.png'))
            else:
                self.items[index].setIcon(QtGui.QIcon('assets/icon_cool.png'))
        # self.plotter.units = stafile.units
        del stafile
        
    def on_click_open(self):
        # обработчик открытия измерения
        print("* нажата кнопка открытия измерения")
        options = QtWidgets.QFileDialog.Options()
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '', 'All Files (*);;Text Files (*.txt)', options=options)
        if file_name == '':
            return
        print(f"* открыт файл {file_name}")
        # переключаем кнопки
        self.action_open.setEnabled(False)
        self.action_close.setEnabled(True)
        # создаем сегменты и добавляем их в список
        self.addSegments(file_name)
        # добавляем доступные параметры в комбобоксы
        xaxes = ('Time', 'Temp.')
        yaxes = list(self.plotter.segments[0].df.columns)
        yaxes.remove('Time')
        yaxes.remove('Temp.')

        for header in xaxes:
            self.combobox_xaxis.addItem(header)
        for header in yaxes:
            self.combobox_yaxis.addItem(header)

        self.combobox_xaxis.setCurrentText('Time')
        self.combobox_yaxis.setCurrentText('DTA')
        self.comboboxes_is_set = True
        self.toolsSetEnabled(True)
        # рисуем график
        self.plotter.plot(
            self.combobox_xaxis.currentText(),
            self.combobox_yaxis.currentText(),
        )
        self.measurement_is_opened = True

    def on_item_changed(self, item: QtWidgets.QListWidgetItem):
        if self.measurement_is_opened:
            index = self.list_segments.row(item)
            state = item.checkState()
            self.plotter.segmentVisible(index, state)
            self.plotter.canvas.draw()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    form = MainWindow()
    form.show()
    sys.exit(app.exec_())
