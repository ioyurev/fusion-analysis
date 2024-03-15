from PySide6 import QtWidgets, QtCore, QtGui
from fusion_analysis.Plotter import Plotter, SegmentDTA, Peak, OnsetLine, MyAnn
from fusion_analysis.libfusiondata import ThermalType
from fusion_analysis.libn2f import n2f
from fusion_analysis.libs2f import s2f
from fusion_analysis.libc2a import c2a

# from ConfigHandler import read_config, write_config
from fusion_analysis.ConfigWindow import ConfigWindow
from fusion_analysis.CustomWidgets import (
    RemoveAction,
    PropertiesAction,
    SegmentItem,
    DTAItem,
    MassItem,
    TempItem,
    update_child_items_state,
)
from fusion_analysis.DataFile import pick_open_path
from fusion_analysis.helpers import warning_message, error_message, log_info
from ui.MainWindow import Ui_MainWindow
from fusion_analysis.AboutWindow import show_about


class TreeWidgetHandler(QtCore.QObject):
    list_segments: list[SegmentItem]
    has_massdata: bool

    def __init__(self, widget: QtWidgets.QTreeWidget, plotter: Plotter):
        super().__init__(parent=None)
        self.plotter = plotter
        self.widget = widget

    def setSelectedItem(self, artist: SegmentDTA):
        for item in self.list_segments:
            item.setSelected(False)
        self.list_segments[artist.index].setSelected(True)

    def init(self, segments: list[SegmentDTA], has_massdata: bool):
        self.has_massdata = has_massdata
        self.list_segments = []
        for segment in segments:
            parent_item = SegmentItem(self.widget, artist=segment)
            self.list_segments.append(parent_item)
            # child_item_dta =
            DTAItem(parent_item)
            # child_item_temp =
            TempItem(parent_item)
            if self.has_massdata:
                # child_item_mass =
                MassItem(parent_item)

    def on_split(self):
        self.widget.clear()
        self.init(segments=self.plotter.segments_dta, has_massdata=self.has_massdata)


def ask_mass():
    ok = False
    while not ok:
        mass, ok = QtWidgets.QInputDialog.getDouble(
            None, "Введите массу", "Масса, мг:", decimals=1
        )
    log_info(f"* Введенная масса: {mass}")
    return mass


def layoutSetEnabled(layout: QtWidgets.QLayout, enabled: bool):
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget is not None:
            widget.setEnabled(enabled)


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, dpi: float, scale: float):
        self.list_segments: list[SegmentItem] = []
        log_info("* загрузка интерфейса")
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(":/icon.png"))
        self.showMaximized()

        # self.config = read_config()

        # плоттер
        self.plotter = Plotter(self, dpi=dpi, scale=scale)
        self.plotter.spinbox_t = self.spinbox_t
        self.plotter.spinbox_T1 = self.spinbox_T1
        self.plotter.spinbox_T2 = self.spinbox_T2
        self.plotter.spinbox_onsettool_T1 = self.spinbox_onsettool_T1
        self.plotter.spinbox_onsettool_T2 = self.spinbox_onsettool_T2
        self.plotter.combobox_xaxis = self.combobox_xaxis
        self.plotter.combobox_baselinetype = self.combobox_baselinetype
        # self.plotter.config = self.config['Plotter']
        self.plotter.signal_pick.connect(self.on_pick)
        self.plotter.signal_cm.connect(self.cm_popup)
        self.plotter.signal_split.connect(self.on_split_done)

        # добавляем холст и панель инструментов matplotlib
        self.plotLayout.addWidget(self.plotter.canvas)
        self.plotLayout.addWidget(self.plotter.toolbar)

        # обработчики меню
        self.action_about.triggered.connect(show_about)
        self.action_open.triggered.connect(lambda: self.on_click_open(mode=0))
        self.action_netzsch.triggered.connect(lambda: self.on_click_open(mode=1))
        self.action_setaram.triggered.connect(lambda: self.on_click_open(mode=2))
        self.action_close.triggered.connect(self.on_click_close)
        # self.action_config.triggered.connect(self.on_click_config)

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
        self.buttonbox_peak.accepted.connect(
            lambda: self.on_click_peaktool_done(apply=True)
        )
        self.buttonbox_peak.rejected.connect(
            lambda: self.on_click_peaktool_done(apply=False)
        )

        self.btn_onsettool.clicked.connect(lambda: self.on_click_onsettool_start())
        self.btn_endtool.clicked.connect(
            lambda: self.on_click_onsettool_start(is_onset=False)
        )
        self.buttonbox_onset.accepted.connect(
            lambda: self.on_click_onsettool_done(apply=True)
        )
        self.buttonbox_onset.rejected.connect(
            lambda: self.on_click_onsettool_done(apply=False)
        )

        self.btn_split.clicked.connect(self.on_click_splittool_start)
        self.buttonbox_split.accepted.connect(
            lambda: self.on_click_splittool_done(apply=True)
        )
        self.buttonbox_split.rejected.connect(
            lambda: self.on_click_splittool_done(apply=False)
        )

        self.btn_shiftsegment.mousePressEvent = self.on_press_shiftsegment
        self.btn_shiftsegment.mouseMoveEvent = self.on_move_shiftsegment

        # обработчики левой панели
        self.checkbox_grid.stateChanged.connect(self.on_checkbox_grid_changed)
        self.checkbox_autoscale.stateChanged.connect(self.on_checkbox_autoscale_changed)
        self.combobox_xaxis.currentIndexChanged.connect(self.on_combobox_changed)
        self.checkbox_derivative.stateChanged.connect(
            self.on_checkbox_derivative_changed
        )
        self.checkbox_temp.stateChanged.connect(self.on_checkbox_temp_changed)
        self.checkbox_tg.stateChanged.connect(self.on_checkbox_tg_changed)

        # скрытие панелей инструментов
        self.tab_widget.tabBar().setVisible(False)
        self.tab_widget.setVisible(False)

        # дерево сегментов
        self.treewidget_handler = TreeWidgetHandler(
            self.treewidget_segments, self.plotter
        )
        self.treewidget_paused = False
        self.treewidget_segments.itemChanged.connect(self.on_treewidget_changed)
        self.treewidget_segments.itemSelectionChanged.connect(
            self.on_treewidget_selection_changed
        )

        self.measurement_is_opened = False
        self.comboboxes_is_set = False
        self.peaktool_initialized = False
        self.button_pressed = False

    def on_checkbox_temp_changed(self, state: int):
        self.plotter.on_checkbox_temp(state == 2)

    def on_checkbox_tg_changed(self, state: int):
        self.plotter.on_checkbox_tg(state == 2)

    def on_checkbox_derivative_changed(self, state):
        if state == 2:
            derivative = True
        else:
            derivative = False
        self.plotter.on_checkbox_ddta(derivative)

    def on_treewidget_selection_changed(self):
        selected = self.treewidget_segments.selectedItems()
        if selected:
            item = selected[0]
            if self.plotter.picked_item is not None:
                self.plotter.picked_item.setPickEffect(False)
            if item.checkState(0) == QtCore.Qt.Checked:
                if isinstance(item.artist, SegmentDTA):
                    self.on_pick_segment(True)
                    self.plotter.picked_item = item.artist
                    self.plotter.picked_item.setPickEffect(True)
            else:
                self.plotter.picked_item = None
                self.on_pick_segment(False)
            self.plotter.canvas.draw()

    def on_treewidget_changed(self, item: SegmentItem | DTAItem | MassItem | TempItem):
        if self.measurement_is_opened and (not self.treewidget_paused):
            state = item.checkState(0) == QtCore.Qt.CheckState.Checked
            if isinstance(item, SegmentItem):
                update_child_items_state(item)
                if self.checkbox_autoscale.checkState() == QtCore.Qt.CheckState.Checked:
                    self.plotter.autoscale(redraw=False)
            else:
                item.artist.set_visible(state)
            self.plotter.canvas.draw()

    def resizeEvent(self, event):
        if hasattr(self, "plotter"):
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

    def cm_popup(self, tpl):
        obj: SegmentDTA | Peak | OnsetLine = tpl[0]
        pos: QtCore.QPoint = tpl[1]
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
        self.treewidget_paused = True
        self.plotter.splittool_done(apply=apply)
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        self.splittool_initialized = False
        self.treewidget_paused = False

    def splittool_check_is_valid(self):
        if not isinstance(self.plotter.picked_item, SegmentDTA):
            warning_message("Cегмент не выбран.")
            return False
        if self.combobox_xaxis.currentText() in ("Time"):
            pass
        else:
            warning_message("Неправильно выбрана ось абцисс!\nДолжна быть Time.")
            return False
        return True

    def on_click_splittool_start(self):
        if self.splittool_check_is_valid():
            self.plotter.splittool_start()
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(2)
            layoutSetEnabled(self.leftpanel, False)
            self.btn_endtool.setEnabled(False)
            self.btn_onsettool.setEnabled(False)
            self.btn_peaktool.setEnabled(False)
            self.btn_shiftsegment.setEnabled(False)
            self.btn_split.setEnabled(False)

    def on_click_onsettool_start(self, is_onset: bool = True):
        if self.onsettool_check_is_valid():
            self.plotter.onsettool_start(is_onset)
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(1)
            layoutSetEnabled(self.leftpanel, False)
            self.btn_onsettool.setEnabled(False)
            self.btn_endtool.setEnabled(False)
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
        self.peaktool_initialized = False

    def on_click_peaktool_start(self):
        if self.peaktool_check_is_valid():
            self.plotter.peaktool_start()
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(0)
            layoutSetEnabled(self.leftpanel, False)
            self.btn_shiftsegment.setEnabled(False)
            self.btn_peaktool.setEnabled(False)
            self.btn_split.setEnabled(False)
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
        if self.combobox_xaxis.currentText() in ("Time", "Temp.", "EMF"):
            return True
        else:
            warning_message(
                "Неправильно выбрана ось абцисс!\nДолжна быть Time, Temp. или EMF."
            )
            return False

    def on_click_config(self):
        c = ConfigWindow(self.config, parent=self)
        result = c.exec()
        if result == QtWidgets.QDialog.Accepted and c.changes_are_made:
            self.config = c.config
            # write_config(self.config)
        elif result == QtWidgets.QDialog.Rejected:
            pass

    def on_click_close(self):
        self.comboboxes_is_set = False
        self.action_open.setEnabled(True)
        self.action_close.setEnabled(False)
        self.list_segments.clear()
        self.menu_import.setEnabled(True)
        self.treewidget_segments.clear()
        self.measurement_is_opened = False
        layoutSetEnabled(self.leftpanel, False)
        self.combobox_xaxis.clear()
        self.plotter.on_close()
        self.checkbox_temp.setChecked(False)
        self.checkbox_derivative.setChecked(False)

    def on_click_open(self, mode: int):
        """
        Parameters:
            mode (int): 0 - измерение Fusion Collection, 1 - измерение Netzsch, 2 - измерение Setaram
        """
        options = QtWidgets.QFileDialog.Option(0x10)
        file_name = ""

        if mode == 0:
            file_name = pick_open_path()
            log_info("* импорт измерения Fusion Collection")
        elif mode in (1, 2):
            file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Open file",
                "",
                "All Files (*);;Text Files (*.txt)",
                options=options,
            )
            if mode == 1:
                log_info("* импорт измерения Netzsch")
            else:
                log_info("* импорт измерения Setaram")

        if file_name == "":
            return

        try:
            if mode == 0:
                self.measurement_data = c2a(file_name)
            elif mode == 1:
                self.measurement_data = n2f(file_name)
            elif mode == 2:
                self.measurement_data = s2f(file_name, startmass=ask_mass())
        except Exception as e:
            error_message("Не удалось открыть измерение")
            raise e
        log_info(f"* открыт файл {file_name}")
        self.init_measurement()

    def init_measurement(self):
        if self.measurement_data.has_tempdata:
            string = "Temp."
        else:
            string = "EMF"
        xaxes = ("Time", string)

        # добавляем доступные параметры в комбобоксы
        for header in xaxes:
            self.combobox_xaxis.addItem(header)

        self.combobox_xaxis.setCurrentText("Time")
        self.comboboxes_is_set = True
        layoutSetEnabled(self.leftpanel, True)

        # добавляем сегменты
        artists = []
        for index, df in enumerate(self.measurement_data.segments):
            t1 = round(df[string].values[0])
            t2 = round(df[string].values[-1])
            if t2 > t1:
                thermal_type = ThermalType.HEAT
            elif t2 < t1:
                thermal_type = ThermalType.COOL
            elif t2 == t1:
                thermal_type = ThermalType.ISOTHERMAL
            artist = self.plotter.addSegment(
                df=df, index=index, thermal_type=thermal_type, temp_axis=string
            )
            artists.append(artist)
        self.treewidget_handler.init(
            artists, has_massdata=self.measurement_data.has_massdata
        )

        # рисуем график
        self.plotter.units = self.measurement_data.units
        self.plotter.measurement_exo = self.measurement_data.exo
        self.plotter.plot(
            self.combobox_xaxis.currentText(),
            "DTA",
            has_massdata=self.measurement_data.has_massdata,
            has_tempdata=self.measurement_data.has_tempdata,
        )
        self.plotter.set_exo()
        self.plotter.set_visible(True)
        self.measurement_is_opened = True

        # переключаем кнопки
        self.action_open.setEnabled(False)
        self.action_close.setEnabled(True)
        self.menu_import.setEnabled(False)

    def on_pick_segment(self, state):
        self.btn_peaktool.setEnabled(state)
        self.btn_shiftsegment.setEnabled(state)
        self.btn_split.setEnabled(state)

    def on_pick_peak(self, state):
        self.btn_onsettool.setEnabled(state)
        self.btn_endtool.setEnabled(state)

    def on_pick(self, item: SegmentDTA | Peak | OnsetLine | MyAnn):
        # log_info(f'* выбран {item.__class__.__name__}')
        match item:
            case SegmentDTA():
                self.on_pick_segment(True)
                self.on_pick_peak(False)
                self.treewidget_handler.setSelectedItem(item)
            case Peak():
                self.on_pick_segment(False)
                self.on_pick_peak(True)
                self.treewidget_segments.clearSelection()
            case None:
                self.on_pick_segment(False)
                self.on_pick_peak(False)

    def on_split_done(self, tpl: tuple[SegmentDTA, SegmentDTA, int]):
        self.treewidget_handler.on_split()
