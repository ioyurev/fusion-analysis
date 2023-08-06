from PySide6 import QtWidgets, QtCore, QtGui, QtUiTools
from Plotter import Plotter, Segment, Peak, OnsetLine
from libn2f import STAFile
from Config import read_config, write_config
from ConfigWindow import ConfigWindow
from CustomWidgets import MySpinBox, RemoveAction, PropertiesAction

Ui_MainWindow = QtUiTools.loadUiType('MainWindow.ui')[0]

def warning_message(message):
    print(f'* Предупреждение. {message}')
    QtWidgets.QMessageBox.warning(None, "Предупреждение", message)

def layoutSetVisible(layout: QtWidgets.QLayout, visible: bool):
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget is not None:
            widget.setVisible(visible)
            widget.show() if visible else widget.hide()

def layoutSetEnabled(layout: QtWidgets.QLayout, enabled: bool):
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget is not None:
            widget.setEnabled(enabled)

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    btn_peaktool : QtWidgets.QPushButton
    btn_peaktool_ok : QtWidgets.QPushButton
    btn_peaktool_cancel : QtWidgets.QPushButton
    spinbox_T1 : MySpinBox
    spinbox_T2 : MySpinBox
    spinbox_onsettool_T1: MySpinBox
    spinbox_onsettool_T2: MySpinBox
    combobox_xaxis: QtWidgets.QComboBox
    combobox_yaxis: QtWidgets.QComboBox
    checkbox_grid: QtWidgets.QCheckBox
    menu_file: QtWidgets.QMenu
    menu_editor: QtWidgets.QMenu
    action_open: QtGui.QAction
    action_close: QtGui.QAction
    action_config: QtGui.QAction
    list_segments : QtWidgets.QListWidget
    checkbox_autoscale: QtWidgets.QCheckBox
    leftpanel: QtWidgets.QGridLayout
    peaktoolLayout: QtWidgets.QGridLayout
    onsettoolLayout: QtWidgets.QGridLayout
    combobox_baselinetype: QtWidgets.QComboBox
    btn_onsettool: QtWidgets.QPushButton
    btn_endtool: QtWidgets.QPushButton
    btn_onsettool_ok: QtWidgets.QPushButton
    btn_onsettool_cancel: QtWidgets.QPushButton
    btn_shiftsegment: QtWidgets.QPushButton
    list_segments : QtWidgets.QListWidget
    plotLayout: QtWidgets.QVBoxLayout
    
    def __init__(self, dpi, scale):
        print('* загрузка интерфейса')
        super().__init__()
        self.setupUi(self)
        self.showMaximized()
        self.resizeEvent = self.on_resize

        self.config = read_config()

        # плоттер
        self.plotter = Plotter(self, dpi=dpi, scale=scale)
        self.plotter.config = self.config['Plotter']
        
        # добавляем холст и панель инструментов matplotlib
        self.plotLayout.addWidget(self.plotter.canvas)
        self.plotLayout.addWidget(self.plotter.toolbar)
        
        # обработчики меню
        self.action_open.triggered.connect(self.on_click_open)
        self.action_close.triggered.connect(self.on_click_close)
        self.action_config.triggered.connect(self.on_click_config)
        
        # контекстное меню
        self.cm = QtWidgets.QMenu(self)
        self.cm_name = QtGui.QAction()
        self.cm_name.setEnabled(False)
        self.cm.addAction(self.cm_name)
        self.cm_remove = RemoveAction(self)
        self.cm.addAction(self.cm_remove)
        self.cm_prop = PropertiesAction(self)
        self.cm_prop.signal_prop_applied.connect(self.plotter.canvas.draw)
        self.cm.addAction(self.cm_prop)

        # обработчики инструментов
        self.btn_peaktool.clicked.connect(self.on_click_peaktool_start)
        self.btn_peaktool_ok.clicked.connect(lambda: self.on_click_peaktool_done(apply=True))
        self.btn_peaktool_cancel.clicked.connect(lambda: self.on_click_peaktool_done(apply=False))
        self.btn_onsettool.clicked.connect(lambda: self.on_click_onsettool_start())
        self.btn_onsettool_ok.clicked.connect(lambda: self.on_click_onsettool_done(apply=True))
        self.btn_onsettool_cancel.clicked.connect(lambda: self.on_click_onsettool_done(apply=False))
        self.btn_endtool.clicked.connect(lambda: self.on_click_onsettool_start(is_onset=False))
        self.btn_shiftsegment.mousePressEvent = self.on_press_shiftsegment
        self.btn_shiftsegment.mouseMoveEvent = self.on_move_shiftsegment

        # обработчики левой панели
        self.checkbox_grid.stateChanged.connect(self.on_checkbox_grid_changed)
        self.checkbox_autoscale.stateChanged.connect(self.on_checkbox_autoscale_changed)
        self.combobox_xaxis.currentIndexChanged.connect(self.on_combobox_changed)
        self.combobox_yaxis.currentIndexChanged.connect(self.on_combobox_changed)
        # self.spinbox_T1.valueChanged.connect(self.on_spinbox_T1_changed)

        # скрытие панелей инструментов
        layoutSetVisible(self.peaktoolLayout, False)
        layoutSetVisible(self.onsettoolLayout, False)

        # список сегментов
        self.list_segments.itemChanged.connect(self.on_item_changed)
        self.list_segments.itemSelectionChanged.connect(self.on_item_selection_changed)
        self.list_segments.contextMenuEvent = self.on_cm_list_segments
        self.items: list[QtWidgets.QListWidgetItem] = []
        
        self.measurement_is_opened = False
        self.comboboxes_is_set = False
        self.peaktool_initialized = False
        self.button_pressed = False

    def on_cm_list_segments(self, event: QtGui.QContextMenuEvent):
        index = self.list_segments.indexAt(event.pos()).row()
        obj = self.plotter.segments[index]
        self.cm_popup(obj=obj, pos=event.globalPos())

    def on_resize(self, event):
        self.plotter.fig.tight_layout(pad=0)
        super().resizeEvent(event)

    def on_press_shiftsegment(self, event: QtGui.QMouseEvent):
        self.press_position = event.globalPos().y()

    def on_move_shiftsegment(self, event: QtGui.QMouseEvent):
        if self.plotter.pickedSegment is not None:
            y = event.globalPos().y()
            dy = y - self.press_position
            self.plotter.pickedSegment.shifty(dy)
            self.plotter.canvas.draw()
            self.press_position = y

    def cm_popup(self, obj: Segment | Peak | OnsetLine, pos: QtCore.QPoint):
        if isinstance(obj, Segment):
            name = f"Сегмент {obj.index}"
            self.cm_remove.setVisible(False)
        elif isinstance(obj, Peak):
            name = f"Пик {obj.area}"
            self.cm_remove.setVisible(True)
        elif isinstance(obj, OnsetLine):
            name = f"{obj.t}: {obj.info}"
            self.cm_remove.setVisible(True)
        self.cm_name.setText(name)
        self.cm_remove.obj = obj
        self.cm_prop.obj = obj
        self.cm.popup(pos)

    def on_click_onsettool_start(self, is_onset: bool = True):
        if self.onsettool_check_is_valid():
            self.plotter.onsettool_start(is_onset)
            layoutSetVisible(self.onsettoolLayout, True)
            layoutSetEnabled(self.leftpanel, False)
            self.onsettools_initialized = True

    def on_click_onsettool_done(self, apply: bool):
        self.plotter.onsettool_done(apply=apply)
        layoutSetVisible(self.onsettoolLayout, False)
        layoutSetEnabled(self.leftpanel, True)
        self.peaktool_initialized = False

    def on_checkbox_autoscale_changed(self, state):
        if state == QtCore.Qt.Checked:
            self.plotter.autoscale()

    def on_item_selection_changed(self):
        selected_items = self.list_segments.selectedItems()
        if len(selected_items) == 1 and selected_items[0].checkState():
            index = self.list_segments.row(selected_items[0])
            self.on_pick_segment(True)
            self.plotter.pickSegment(self.plotter.segments[index])
        else:
            self.plotter.pickSegment(None)
            self.on_pick_segment(False)

    def on_checkbox_grid_changed(self, state):
        if state == 2:
            self.plotter.gridSetVisible(True)
        elif state == 0:
            self.plotter.gridSetVisible(False)

    def on_combobox_changed(self, index):
        if self.comboboxes_is_set:
            self.plotter.updateAxes()

    def on_click_peaktool_done(self, apply: bool):
        self.plotter.peaktool_done(apply=apply)
        layoutSetVisible(self.peaktoolLayout, False)
        layoutSetEnabled(self.leftpanel, True)
        self.btn_shiftsegment.setEnabled(True)
        self.btn_peaktool.setEnabled(True)
        self.peaktool_initialized = False

    def on_click_peaktool_start(self):
        if self.peaktool_check_is_valid():
            self.plotter.peaktool_start()
            layoutSetVisible(self.peaktoolLayout, True)
            layoutSetEnabled(self.leftpanel, False)
            self.btn_shiftsegment.setEnabled(False)
            self.btn_peaktool.setEnabled(False)
            self.peaktool_initialized = True

    def onsettool_check_is_valid(self):
        if self.plotter.pickedPeak is None:
            warning_message("Пик не выбран.")
            return False
        if self.chech_xaxis() and self.check_yaxis():
            pass
        else:
            return False
        return True

    def peaktool_check_is_valid(self):
        if self.plotter.pickedSegment is None:
            warning_message("Cегмент не выбран.")
            return False
        if self.chech_xaxis() and self.check_yaxis():
            pass
        else:
            return False
        return True
    
    def check_yaxis(self):
        if self.combobox_yaxis.currentText() != 'DTA':
            warning_message('Неправильно выбрана ось ординат!\nДолжна быть DTA.')
            return False
        return True

    def chech_xaxis(self):
        if self.combobox_xaxis.currentText() in ('Time', 'Temp.'):
            return True
        else:
            warning_message('Неправильно выбрана ось абцисс!\nДолжна быть Time или Temp.')
            return False

    def addSegments(self, filepath):
        stafile = STAFile(filepath)
        for index, df in enumerate(stafile.segments):
            # пределы сегмента
            t1 = round(df["Temp."].values[0])
            t2 = round(df["Temp."].values[-1])
            # добавляем сегмент к плоттеру
            self.plotter.addSegment(df=df, index=index, Type=stafile.segments_type[index])
            # добавляем сегмент в список интерфейса
            self.items.append(QtWidgets.QListWidgetItem(f'{t1} - {t2}', self.list_segments))
            self.items[index].setFlags(self.items[index].flags() | QtCore.Qt.ItemIsUserCheckable)
            self.items[index].setCheckState(QtCore.Qt.Checked)
            if t2 - t1 > 0:
                self.items[index].setIcon(QtGui.QIcon('assets/icon_heat.png'))
            else:
                self.items[index].setIcon(QtGui.QIcon('assets/icon_cool.png'))
        self.plotter.units = stafile.units
        if '+' in stafile.info['EXO']:
            self.plotter.measurement_exo = 1
        elif '-' in stafile.info['EXO']:
            self.plotter.measurement_exo = 0
        else:
            raise RuntimeError(f'Значение EXO {stafile.info["EXO"]} не распознано.')
        del stafile

    def on_click_config(self):
        c = ConfigWindow(self.config, parent=self)
        result = c.exec()
        if result == QtWidgets.QDialog.Accepted and c.changes_are_made:
            self.config = c.config
            write_config(self.config)
        elif result == QtWidgets.QDialog.Rejected:
            pass

    def on_click_close(self):
        self.comboboxes_is_set = False
        self.action_open.setEnabled(True)
        self.action_close.setEnabled(False)
        self.list_segments.clear()
        self.items.clear()
        self.plotter.clear()
        self.plotter.remove_segments()
        self.measurement_is_opened = False
        layoutSetEnabled(self.leftpanel, False)
        self.plotter.set_visible(False)
        self.combobox_xaxis.clear()
        self.combobox_yaxis.clear()

    def on_click_open(self):
        # обработчик открытия измерения
        options = QtWidgets.QFileDialog.Options(0x10)
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
        for yaxis in ('Time', 'Temp.', 'dDTA/dTime', 'dDTA/dTemp'):
            yaxes.remove(yaxis)
        for header in xaxes:
            self.combobox_xaxis.addItem(header)
        for header in yaxes:
            self.combobox_yaxis.addItem(header)

        self.combobox_xaxis.setCurrentText('Time')
        self.combobox_yaxis.setCurrentText('DTA')
        self.comboboxes_is_set = True
        layoutSetEnabled(self.leftpanel, True)
        # рисуем график
        self.plotter.plot(
            self.combobox_xaxis.currentText(),
            self.combobox_yaxis.currentText(),
        )
        self.measurement_is_opened = True
        self.plotter.set_exo()
        self.plotter.set_visible(True)

    def on_item_changed(self, item: QtWidgets.QListWidgetItem):
        if self.measurement_is_opened:
            index = self.list_segments.row(item)
            state = item.checkState() == QtCore.Qt.Checked
            self.plotter.segmentVisible(index, state)
            if self.checkbox_autoscale.checkState() == QtCore.Qt.Checked:
                self.plotter.autoscale()
            else:
                self.plotter.canvas.draw()

    def on_pick_segment(self, state):
        self.btn_peaktool.setEnabled(state)
        self.btn_shiftsegment.setEnabled(state)

    def on_pick_peak(self, state):
        self.btn_onsettool.setEnabled(state)
        self.btn_endtool.setEnabled(state)
