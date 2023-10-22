from PySide6 import QtWidgets, QtCore, QtGui, QtUiTools
from Plotter import Plotter, SegmentDTA, Peak, OnsetLine, MyAnn
from libn2f import n2f, TYPE_HEAT, TYPE_COOL, TYPE_ISOTHERMAL
from libs2f import s2f
from libc2a import c2a
from Config import read_config, write_config
from ConfigWindow import ConfigWindow
from CustomWidgets import MySpinBox, RemoveAction, PropertiesAction, SegmentItem, DTAItem, MassItem, update_child_items_state
from data_file.DataFile import pick_open_path
from helpers import warning_message, error_message

Ui_MainWindow = QtUiTools.loadUiType('ui/MainWindow.ui')[0]

class TreeWidgetHandler(QtCore.QObject):
    list_segments: list[SegmentItem]
    def __init__(self, widget: QtWidgets.QTreeWidget, plotter: Plotter):
        super().__init__(parent=None)
        self.plotter = plotter
        self.widget = widget

    def setSelectedItem(self, artist: SegmentDTA):
        for item in self.list_segments:
            item.setSelected(False)
        self.list_segments[artist.index].setSelected(True)

    def init(self, segments: list[SegmentDTA]):
        self.list_segments = []
        for segment in segments:
            parent_item = SegmentItem(self.widget, artist=segment)
            self.list_segments.append(parent_item)
            child_item_dta = DTAItem(parent_item)
            # child_item_mass = MassItem(parent_item)
    
    def on_split(self):
        self.widget.clear()
        self.init(self.plotter.segments_dta)        

def ask_mass():
    ok = False
    while not ok:
        mass, ok = QtWidgets.QInputDialog.getDouble(None, "Введите массу", "Масса, мг:", decimals=1)
    print(f"* Введенная масса: {mass}")
    return mass

def layoutSetEnabled(layout: QtWidgets.QLayout, enabled: bool):
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget is not None:
            widget.setEnabled(enabled)

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    tab_widget: QtWidgets.QTabWidget
    btn_peaktool : QtWidgets.QPushButton
    spinbox_T1 : MySpinBox
    spinbox_T2 : MySpinBox
    spinbox_onsettool_T1: MySpinBox
    spinbox_onsettool_T2: MySpinBox
    combobox_xaxis: QtWidgets.QComboBox
    checkbox_grid: QtWidgets.QCheckBox
    menu_file: QtWidgets.QMenu
    menu_editor: QtWidgets.QMenu
    menu_import: QtWidgets.QMenu
    action_open: QtGui.QAction
    action_netzsch: QtGui.QAction
    action_setaram: QtGui.QAction
    action_close: QtGui.QAction
    action_config: QtGui.QAction
    checkbox_autoscale: QtWidgets.QCheckBox
    checkbox_derivative: QtWidgets.QCheckBox
    leftpanel: QtWidgets.QGridLayout
    combobox_baselinetype: QtWidgets.QComboBox
    btn_onsettool: QtWidgets.QPushButton
    btn_endtool: QtWidgets.QPushButton
    btn_shiftsegment: QtWidgets.QPushButton
    btn_split: QtWidgets.QPushButton
    plotLayout: QtWidgets.QVBoxLayout
    treewidget_segments: QtWidgets.QTreeWidget
    buttonbox_peak: QtWidgets.QDialogButtonBox
    buttonbox_onset: QtWidgets.QDialogButtonBox
    buttonbox_split: QtWidgets.QDialogButtonBox
    
    def __init__(self, dpi, scale):
        self.list_segments: list[SegmentItem] = []
        print('* загрузка интерфейса')
        super().__init__()
        self.setupUi(self)
        self.showMaximized()
        self.resizeEvent = self.on_resize

        self.config = read_config()

        # плоттер
        self.plotter = Plotter(self, dpi=dpi, scale=scale)
        self.plotter.config = self.config['Plotter']
        self.plotter.signal_pick.connect(self.on_pick)
        self.plotter.signal_cm.connect(self.cm_popup)
        self.plotter.signal_split.connect(self.on_split_done)

        # добавляем холст и панель инструментов matplotlib
        self.plotLayout.addWidget(self.plotter.canvas)
        self.plotLayout.addWidget(self.plotter.toolbar)
        
        # обработчики меню
        self.action_open.triggered.connect(lambda: self.on_click_open(mode=0))
        self.action_netzsch.triggered.connect(lambda: self.on_click_open(mode=1))
        self.action_setaram.triggered.connect(lambda: self.on_click_open(mode=2))
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
        self.buttonbox_peak.accepted.connect(lambda: self.on_click_peaktool_done(apply=True))
        self.buttonbox_peak.rejected.connect(lambda: self.on_click_peaktool_done(apply=False))

        self.btn_onsettool.clicked.connect(lambda: self.on_click_onsettool_start())
        self.btn_endtool.clicked.connect(lambda: self.on_click_onsettool_start(is_onset=False))
        self.buttonbox_onset.accepted.connect(lambda: self.on_click_onsettool_done(apply=True))
        self.buttonbox_onset.rejected.connect(lambda: self.on_click_onsettool_done(apply=False))

        self.btn_split.clicked.connect(self.on_click_splittool_start)
        self.buttonbox_split.accepted.connect(lambda: self.on_click_splittool_done(apply=True))
        self.buttonbox_split.rejected.connect(lambda: self.on_click_splittool_done(apply=False))

        self.btn_shiftsegment.mousePressEvent = self.on_press_shiftsegment
        self.btn_shiftsegment.mouseMoveEvent = self.on_move_shiftsegment

        # обработчики левой панели
        self.checkbox_grid.stateChanged.connect(self.on_checkbox_grid_changed)
        self.checkbox_autoscale.stateChanged.connect(self.on_checkbox_autoscale_changed)
        self.combobox_xaxis.currentIndexChanged.connect(self.on_combobox_changed)
        self.checkbox_derivative.stateChanged.connect(self.on_checkbox_derivative_changed)

        # скрытие панелей инструментов
        self.tab_widget.tabBar().setVisible(False)
        self.tab_widget.setVisible(False)

        # дерево сегментов
        self.treewidget_handler = TreeWidgetHandler(self.treewidget_segments, self.plotter)
        self.treewidget_segments.itemChanged.connect(self.on_treewidget_changed)
        self.treewidget_segments.itemSelectionChanged.connect(self.on_treewidget_selection_changed)
        
        self.measurement_is_opened = False
        self.comboboxes_is_set = False
        self.peaktool_initialized = False
        self.button_pressed = False

    def on_checkbox_derivative_changed(self, state):
        if state == 2:
            derivative = True
        else:
            derivative = False
        self.plotter.ax_ddta.set_visible(derivative)
        self.plotter.canvas.draw()

    def on_treewidget_selection_changed(self):
        selected = self.treewidget_segments.selectedItems()
        if selected:
            item = selected[0]
            item: SegmentItem
            if self.plotter.picked_item is not None:
                self.plotter.picked_item.setPickEffect(False)
            if item.checkState(0) == QtCore.Qt.Checked:
                self.on_pick_segment(True)
                self.plotter.picked_item = item.artist
                self.plotter.picked_item.setPickEffect(True)
            else:
                self.plotter.picked_item = None
                self.on_pick_segment(False)
            self.plotter.canvas.draw()

    def on_treewidget_changed(self, item: SegmentItem | DTAItem | MassItem):
        if self.measurement_is_opened:
            match item:
                case SegmentItem():
                    update_child_items_state(item)
                case DTAItem():
                    index = item.parent().index
                    state = item.checkState(0) == QtCore.Qt.Checked
                    self.plotter.segmentVisible(index, state)
                    if self.checkbox_autoscale.checkState() == QtCore.Qt.Checked:
                        self.plotter.autoscale()
                    else:
                        self.plotter.canvas.draw()
                case MassItem():
                    pass   

    def on_cm_list_segments(self, event: QtGui.QContextMenuEvent):
        index = self.list_segments.indexAt(event.pos()).row()
        obj = self.plotter.segments_dta[index]
        self.cm_popup(obj=obj, pos=event.globalPos())

    def on_resize(self, event):
        self.plotter.fig.tight_layout()
        super().resizeEvent(event)

    def on_press_shiftsegment(self, event: QtGui.QMouseEvent):
        self.press_position = event.globalPos().y()

    def on_move_shiftsegment(self, event: QtGui.QMouseEvent):
        if self.plotter.picked_segment is not None:
            y = event.globalPos().y()
            dy = y - self.press_position
            self.plotter.picked_segment.shifty(dy)
            self.plotter.canvas.draw()
            self.press_position = y

    def cm_popup(self, tpl: tuple[SegmentDTA | Peak | OnsetLine, QtCore.QPoint]):
        obj = tpl[0]
        pos = tpl[1]
        match obj:
            case SegmentDTA():
                name = f"Сегмент {obj.index}"
                self.cm_remove.setVisible(False)
            case Peak():
                name = f"Пик {obj.area}"
                self.cm_remove.setVisible(True)
            case OnsetLine():
                name = f"{obj.t}: {obj.info}"
                self.cm_remove.setVisible(True)
        self.cm_name.setText(name)
        self.cm_remove.obj = obj
        self.cm_prop.obj = obj
        self.cm.popup(pos)

    def on_click_splittool_done(self, apply: bool):
        self.plotter.splittool_done(apply=apply)
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        self.splittool_initialized = False

    def splittool_check_is_valid(self):
        if not isinstance(self.plotter.picked_item, SegmentDTA):
            warning_message("Cегмент не выбран.")
            return False
        if self.combobox_xaxis.currentText() in ('Time'):
            pass
        else:
            warning_message('Неправильно выбрана ось абцисс!\nДолжна быть Time.')
            return False
        return True

    def on_click_splittool_start(self):
        if self.splittool_check_is_valid():
            self.plotter.splittool_start()
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(2)
            layoutSetEnabled(self.leftpanel, False)

    def on_click_onsettool_start(self, is_onset: bool = True):
        if self.onsettool_check_is_valid():
            self.plotter.onsettool_start(is_onset)
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(1)
            layoutSetEnabled(self.leftpanel, False)
            self.onsettools_initialized = True

    def on_click_onsettool_done(self, apply: bool):
        self.plotter.onsettool_done(apply=apply)
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        self.peaktool_initialized = False

    def on_checkbox_autoscale_changed(self, state):
        if state == QtCore.Qt.Checked:
            self.plotter.autoscale()

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
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        self.btn_shiftsegment.setEnabled(True)
        self.btn_peaktool.setEnabled(True)
        self.peaktool_initialized = False

    def on_click_peaktool_start(self):
        if self.peaktool_check_is_valid():
            self.plotter.peaktool_start()
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(0)
            layoutSetEnabled(self.leftpanel, False)
            self.btn_shiftsegment.setEnabled(False)
            self.btn_peaktool.setEnabled(False)
            self.peaktool_initialized = True

    def onsettool_check_is_valid(self):
        if not isinstance(self.plotter.picked_item, Peak):
            warning_message("Пик не выбран.")
            return False
        if self.chech_xaxis():
            pass
        else:
            return False
        return True

    def peaktool_check_is_valid(self):
        if not isinstance(self.plotter.picked_item, SegmentDTA):
            warning_message("Cегмент не выбран.")
            return False
        if self.chech_xaxis():
            pass
        else:
            return False
        return True

    def chech_xaxis(self):
        if self.combobox_xaxis.currentText() in ('Time', 'Temp.'):
            return True
        else:
            warning_message('Неправильно выбрана ось абцисс!\nДолжна быть Time или Temp.')
            return False

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
        self.menu_import.setEnabled(True)
        self.treewidget_segments.clear()
        self.plotter.clear()
        self.plotter.remove_segments()
        self.measurement_is_opened = False
        layoutSetEnabled(self.leftpanel, False)
        self.plotter.set_visible(False)
        self.combobox_xaxis.clear()

    def on_click_open(self, mode: int):
        """
        Parameters:
            mode (int): 0 - измерение Fusion Collection, 1 - измерение Netzsch, 2 - измерение Setaram
        """
        options = QtWidgets.QFileDialog.Options(0x10)
        file_name = ''
        
        if mode == 0:
            file_name = pick_open_path()
            print('* импорт измерения Fusion Collection')
        elif mode in (1, 2):
            file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '', 'All Files (*);;Text Files (*.txt)', options=options)
            if mode == 1:
                print('* импорт измерения Netzsch')
            else:
                print('* импорт измерения Setaram')
        
        if file_name == '':
            return
        
        try:
            if mode == 0:
                self.measurement_data = c2a(file_name)
            elif mode == 1:
                self.measurement_data = n2f(file_name)
            elif mode == 2:
                self.measurement_data = s2f(file_name, startmass=ask_mass())
        except:
            error_message('Не удалось открыть измерение')
            return
        
        print(f"* открыт файл {file_name}")
        
        self.init_measurement(has_massdata=False)

    def init_measurement(self, has_massdata=True):
        # добавляем доступные параметры в комбобоксы
        xaxes = ('Time', 'Temp.')
        yaxes = list(self.measurement_data.units.keys())
        for yaxis in xaxes:
            yaxes.remove(yaxis)
        for header in xaxes:
            self.combobox_xaxis.addItem(header)

        self.combobox_xaxis.setCurrentText('Time')
        self.comboboxes_is_set = True
        layoutSetEnabled(self.leftpanel, True)

        # добавляем сегменты
        artists = []
        for index, df in enumerate(self.measurement_data.segments):
            t1 = round(df["Temp."].values[0])
            t2 = round(df["Temp."].values[-1])
            if t2 > t1:
                Type = TYPE_HEAT
            elif t2 < t1:
                Type = TYPE_COOL
            elif t2 == t1:
                Type = TYPE_ISOTHERMAL
            artist = self.plotter.addSegment(df=df, index=index, Type=Type)
            artists.append(artist)
        self.treewidget_handler.init(artists)

        # рисуем график
        self.plotter.units = self.measurement_data.units
        self.plotter.measurement_exo = self.measurement_data.exo
        self.plotter.plot(
            self.combobox_xaxis.currentText(),
            "DTA",
            has_massdata=has_massdata
        )
        self.plotter.set_exo()
        self.plotter.set_visible(True)
        self.measurement_is_opened = True

        # переключаем кнопки
        self.action_open.setEnabled(False)
        self.action_close.setEnabled(True)
        self.menu_import.setEnabled(False)

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
        self.btn_split.setEnabled(state)

    def on_pick_peak(self, state):
        self.btn_onsettool.setEnabled(state)
        self.btn_endtool.setEnabled(state)

    def on_pick(self, item: SegmentDTA | Peak | OnsetLine | MyAnn):
        print(f'* выбран {item.__class__.__name__}')
        match item:
            case SegmentDTA():
                self.on_pick_segment(True)
                self.on_pick_peak(False)
                self.treewidget_handler.setSelectedItem(item)
            case Peak():
                self.on_pick_segment(False)
                self.on_pick_peak(True)
                self.treewidget_segments.clearSelection()

    def on_split_done(self, tpl: tuple[SegmentDTA, SegmentDTA, int]):
        self.treewidget_handler.on_split()
        