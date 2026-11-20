from __future__ import annotations

from pathlib import Path
from typing import Any

from fusion_common import (
    ANALYSIS_ICON_BG,
    is_newer_version,
    resolve_ui_icon,
    show_fusion_about,
    show_fusion_docs,
    show_fusion_license,
    show_fusion_logs,
)
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets

from fusion_analysis.config import (
    APPDATA_PATH,
    DEFAULT_CONFIG_PATH,
    AnalysisConfig,
    read_config,
    write_config,
)
from fusion_analysis.config_window import ConfigWindow
from fusion_analysis.custom_widgets import (
    CurveItem,
    MySpinBox,
    OnsetItem,
    PeakItem,
    PropertiesAction,
    RemoveAction,
    SegmentItem,
    load_asset_icon,
    update_child_items_state,
)
from fusion_analysis.helpers import error_message, warning_message
from fusion_analysis.importers import (
    ImportSource,
    import_netzsch_txt,
    import_setaram_txt,
    load_fusion_measurement,
    pick_open_measurement_path,
    pick_save_fusa_path,
    save_measurement_analysis,
)
from fusion_analysis.measurement_data import (
    MeasurementData,
    classify_segment_thermal_type,
)
from fusion_analysis.plotter import Plotter, PlotterControls
from fusion_analysis.segment import (
    CurveSegment,
    MyAnn,
    OnsetLine,
    Peak,
    SegmentDTA,
)
from fusion_analysis.segment_properties_window import SummaryTableDialog
from fusion_analysis.version import VERSION
from fusion_analysis.video_overlay.tab import VideoOverlayTab


class TreeWidgetHandler(QtCore.QObject):
    list_segments: list[SegmentItem]
    curve_items: dict[tuple[int, str], CurveItem]
    has_massdata: bool

    def __init__(self, widget: QtWidgets.QTreeWidget, plotter: Plotter) -> None:
        super().__init__(parent=None)
        self.plotter = plotter
        self.widget = widget
        self.list_segments = []
        self.curve_items = {}
        self.has_massdata = False

    def select_curve_item(self, curve: CurveSegment) -> None:
        self.widget.blockSignals(True)
        self.widget.clearSelection()
        key = (curve.parent_segment.index, curve.channel_name)
        c_item = self.curve_items.get(key)
        if c_item is not None:
            c_item.setSelected(True)
        self.widget.blockSignals(False)

    def init(self, segments: list[SegmentDTA], has_massdata: bool) -> None:
        self.has_massdata = has_massdata
        self.list_segments = []
        self.curve_items = {}
        for segment in segments:
            seg_item = SegmentItem(self.widget, artist=segment)
            self.list_segments.append(seg_item)
            for ch_name, curve in segment.curves.items():
                c_item = CurveItem(seg_item, curve)
                self.curve_items[(segment.index, ch_name)] = c_item
                for peak in curve.peaks:
                    pk_item = PeakItem(c_item, peak)
                    for ol in peak.onset_lines:
                        OnsetItem(pk_item, ol)
                c_item.setExpanded(True)
            seg_item.setExpanded(True)

    def on_split(self) -> None:
        self.widget.blockSignals(True)
        self.widget.clear()
        self.init(segments=self.plotter.segments_dta, has_massdata=self.has_massdata)
        self.widget.blockSignals(False)


def ask_mass(parent: QtWidgets.QWidget | None = None) -> float | None:
    mass, ok = QtWidgets.QInputDialog.getDouble(  # noqa: PU001
        parent, "Введите массу", "Масса, мг:", 100.0, 0.01, 1e6, 1
    )
    return float(mass) if ok else None


def layoutSetEnabled(layout: QtWidgets.QLayout, enabled: bool) -> None:
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is not None:
            widget = item.widget()
            if widget is not None:
                widget.setEnabled(enabled)


class MainWindow(QtWidgets.QMainWindow):
    measurement_data: MeasurementData
    press_position: int = 0

    plotter: Plotter
    video_overlay_tab: VideoOverlayTab

    def _build_ui(self) -> None:
        self.setWindowTitle("Fusion Analysis")
        self.resize(1024, 768)
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        root_grid = QtWidgets.QGridLayout(central)

        self.leftpanel = QtWidgets.QGridLayout()
        self.leftpanel.addWidget(
            QtWidgets.QLabel("<b>Настройки отображения графика</b>"), 0, 0, 1, 2
        )
        self.leftpanel.addWidget(QtWidgets.QLabel("Ось абсцисс (X):"), 1, 0)
        self.combobox_xaxis = QtWidgets.QComboBox()
        self.combobox_xaxis.setEnabled(False)
        self.leftpanel.addWidget(self.combobox_xaxis, 1, 1)

        self.checkbox_grid = QtWidgets.QCheckBox("Включить сетку")
        self.checkbox_grid.setEnabled(False)
        self.leftpanel.addWidget(self.checkbox_grid, 2, 0, 1, 2)

        self.leftpanel.addWidget(
            QtWidgets.QLabel("<b>Список сегментов</b>"), 10, 0, 1, 2
        )
        self.treewidget_segments = QtWidgets.QTreeWidget()
        self.treewidget_segments.setHeaderHidden(True)
        self.leftpanel.addWidget(self.treewidget_segments, 11, 0, 1, 2)
        root_grid.addLayout(self.leftpanel, 0, 0)

        self.rightpanel = QtWidgets.QGridLayout()
        self.toolbar = QtWidgets.QHBoxLayout()
        self.btn_shiftsegment = QtWidgets.QPushButton(
            load_asset_icon("shift.svg"), "Сдвиг"
        )
        self.btn_shiftsegment.setToolTip("Перемещение сегмента по оси Y")
        self.btn_split = QtWidgets.QPushButton(
            load_asset_icon("split.svg"), "Разделить"
        )
        self.btn_split.setToolTip("Разделить сегмент на два")
        self.btn_peaktool = QtWidgets.QPushButton(load_asset_icon("peak.svg"), "Пик")
        self.btn_peaktool.setToolTip("Выделение пика")
        self.btn_onsettool = QtWidgets.QPushButton(
            load_asset_icon("onset.svg"), "Начало"
        )
        self.btn_onsettool.setToolTip("Найти начало пика")
        self.btn_endtool = QtWidgets.QPushButton(load_asset_icon("end.svg"), "Конец")
        self.btn_endtool.setToolTip("Найти конец пика")
        self.btn_smoothtool = QtWidgets.QPushButton(
            load_asset_icon("smooth.svg"), "Сглаживание"
        )
        self.btn_smoothtool.setToolTip(
            "Сглаживание кривых с предпросмотром на основном графике"
        )
        self.btn_derivtool = QtWidgets.QPushButton(
            load_asset_icon("derivative.svg"), "Производная"
        )
        self.btn_derivtool.setToolTip(
            "Настройка и построение 1-й и 2-й производной выбранной кривой"
        )
        for btn in (
            self.btn_shiftsegment,
            self.btn_split,
            self.btn_peaktool,
            self.btn_onsettool,
            self.btn_endtool,
            self.btn_smoothtool,
            self.btn_derivtool,
        ):
            btn.setEnabled(False)
            btn.setIconSize(QtCore.QSize(24, 24))
            btn.setMinimumHeight(36)
            self.toolbar.addWidget(btn)
        self.toolbar.addStretch()
        self.rightpanel.addLayout(self.toolbar, 0, 0)

        self.tab_widget = QtWidgets.QTabWidget()
        tab_peak = QtWidgets.QWidget()
        g_peak = QtWidgets.QGridLayout(tab_peak)
        self.label_T1 = QtWidgets.QLabel("t₁, мин")
        self.label_T2 = QtWidgets.QLabel("t₂, мин")
        self.spinbox_T1 = MySpinBox()
        self.spinbox_T2 = MySpinBox()
        for sb in (self.spinbox_T1, self.spinbox_T2):
            sb.setDecimals(5)
            sb.setMaximum(20000.0)
            sb.setSingleStep(0.1)
        self.combobox_baselinetype = QtWidgets.QComboBox()
        self.combobox_baselinetype.addItems(
            ["Линейная", "Безье", "Сигмоидальная", "Ступенчатая"]
        )
        self.buttonbox_peak = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        g_peak.addWidget(self.label_T1, 0, 0)
        g_peak.addWidget(self.label_T2, 0, 1)
        g_peak.addWidget(QtWidgets.QLabel("Вид базовой линии"), 0, 2)
        g_peak.addWidget(self.spinbox_T1, 1, 0)
        g_peak.addWidget(self.spinbox_T2, 1, 1)
        g_peak.addWidget(self.combobox_baselinetype, 1, 2)
        g_peak.setColumnStretch(3, 1)
        g_peak.addWidget(self.buttonbox_peak, 2, 0, 1, 4)
        self.tab_widget.addTab(tab_peak, "Peak")

        tab_onset = QtWidgets.QWidget()
        g_onset = QtWidgets.QGridLayout(tab_onset)
        self.lbl_onset_x1 = QtWidgets.QLabel("t₁, мин")
        self.lbl_onset_x2 = QtWidgets.QLabel("t₂, мин")
        self.spinbox_onsettool_T1 = MySpinBox()
        self.spinbox_onsettool_T2 = MySpinBox()
        for sb in (self.spinbox_onsettool_T1, self.spinbox_onsettool_T2):
            sb.setDecimals(5)
            sb.setMaximum(20000.0)
            sb.setSingleStep(0.1)
        self.buttonbox_onset = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        g_onset.addWidget(self.lbl_onset_x1, 0, 0)
        g_onset.addWidget(self.lbl_onset_x2, 0, 1)
        g_onset.addWidget(self.spinbox_onsettool_T1, 1, 0)
        g_onset.addWidget(self.spinbox_onsettool_T2, 1, 1)
        g_onset.setColumnStretch(2, 1)
        g_onset.addWidget(self.buttonbox_onset, 2, 0, 1, 3)
        self.tab_widget.addTab(tab_onset, "Onset")

        tab_split = QtWidgets.QWidget()
        g_split = QtWidgets.QGridLayout(tab_split)
        self.lbl_split_x = QtWidgets.QLabel("t, мин")
        self.spinbox_t = MySpinBox()
        self.spinbox_t.setDecimals(5)
        self.spinbox_t.setMaximum(20000.0)
        self.buttonbox_split = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        g_split.addWidget(self.lbl_split_x, 0, 0)
        g_split.addWidget(self.spinbox_t, 1, 0)
        g_split.setColumnStretch(1, 1)
        g_split.addWidget(self.buttonbox_split, 2, 0, 1, 2)
        self.tab_widget.addTab(tab_split, "Split")

        tab_smooth = QtWidgets.QWidget()
        g_smooth = QtWidgets.QGridLayout(tab_smooth)
        self.lbl_smooth_target = QtWidgets.QLabel("Кривая: —")
        self.spinbox_smooth_win = QtWidgets.QSpinBox()
        self.spinbox_smooth_win.setRange(1, 500)
        self.spinbox_smooth_win.setValue(1)
        self.btn_smooth_reset = QtWidgets.QPushButton(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.EditClear,
                QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton,
            ),
            "Сбросить (1)",
        )
        self.buttonbox_smooth = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        g_smooth.addWidget(self.lbl_smooth_target, 0, 0)
        g_smooth.addWidget(QtWidgets.QLabel("Окно сглаживания:"), 0, 1)
        g_smooth.addWidget(self.spinbox_smooth_win, 1, 1)
        g_smooth.addWidget(self.btn_smooth_reset, 1, 2)
        g_smooth.setColumnStretch(3, 1)
        g_smooth.addWidget(self.buttonbox_smooth, 2, 0, 1, 4)
        self.tab_widget.addTab(tab_smooth, "Smooth")

        tab_deriv = QtWidgets.QWidget()
        g_deriv = QtWidgets.QGridLayout(tab_deriv)
        self.lbl_deriv_target = QtWidgets.QLabel("Исходная кривая: —")
        self.combobox_derivative_order = QtWidgets.QComboBox()
        self.combobox_derivative_order.addItems(["1-я (dY/dX)", "2-я (d²Y/dX²)"])
        self.buttonbox_deriv = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        g_deriv.addWidget(self.lbl_deriv_target, 0, 0)
        g_deriv.addWidget(QtWidgets.QLabel("Порядок производной:"), 0, 1)
        g_deriv.addWidget(self.combobox_derivative_order, 1, 1)
        g_deriv.setColumnStretch(2, 1)
        g_deriv.addWidget(self.buttonbox_deriv, 2, 0, 1, 3)
        self.tab_widget.addTab(tab_deriv, "Derivative")
        self.rightpanel.addWidget(self.tab_widget, 3, 0)

        self.plotLayout = QtWidgets.QVBoxLayout()
        self.rightpanel.addLayout(self.plotLayout, 4, 0)
        self.rightpanel.setRowStretch(4, 1)
        root_grid.addLayout(self.rightpanel, 0, 1)
        root_grid.setColumnStretch(1, 1)

        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        menubar = self.menuBar()
        menubar.clear()
        self.menu_file = menubar.addMenu("Файл")
        self.action_open = QtGui.QAction(
            resolve_ui_icon(ti.DocumentOpen, st.SP_DialogOpenButton),
            "Открыть",
            self,
        )
        self.menu_import = QtWidgets.QMenu("Импорт", self)
        self.menu_import.setIcon(resolve_ui_icon(ti.FolderOpen, st.SP_DirOpenIcon))
        self.action_netzsch = QtGui.QAction(
            resolve_ui_icon(ti.DocumentNew, st.SP_FileIcon),
            "Netzsch ANSI TXT",
            self,
        )
        self.action_setaram = QtGui.QAction(
            resolve_ui_icon(ti.DocumentNew, st.SP_FileIcon),
            "Setaram ANSI TXT",
            self,
        )
        self.menu_import.addAction(self.action_netzsch)
        self.menu_import.addAction(self.action_setaram)
        self.action_close = QtGui.QAction(
            resolve_ui_icon(ti.WindowClose, st.SP_DialogCloseButton),
            "Закрыть",
            self,
        )
        self.action_close.setEnabled(False)
        self.menu_file.addAction(self.action_open)
        self.menu_file.addMenu(self.menu_import)
        self.menu_file.addAction(self.action_close)

        self.menu_tools = menubar.addMenu("Инструменты")

        self.menu_settings = menubar.addMenu("Настройки")
        self.action_config = QtGui.QAction(
            resolve_ui_icon(ti.DocumentPageSetup, st.SP_FileDialogDetailedView),
            "Параметры отображения",
            self,
        )
        self.menu_settings.addAction(self.action_config)

        self.menu_help = menubar.addMenu("Справка")
        self.action_docs = QtGui.QAction(
            resolve_ui_icon(ti.HelpFaq, st.SP_DialogHelpButton),
            "Руководство пользователя (F1)",
            self,
        )
        self.action_docs.setShortcut(QtGui.QKeySequence("F1"))
        self.action_docs.triggered.connect(
            lambda: show_fusion_docs(
                app_title="Fusion Analysis",
                package_name="fusion_analysis",
                icon_bg_color=ANALYSIS_ICON_BG,
                parent=self,
            )
        )
        self.action_license = QtGui.QAction(
            resolve_ui_icon(ti.DialogInformation, st.SP_MessageBoxInformation),
            "Лицензия GNU GPL v3.0",
            self,
        )
        self.action_license.triggered.connect(
            lambda: show_fusion_license(
                app_title="Fusion Analysis",
                icon_bg_color=ANALYSIS_ICON_BG,
                parent=self,
            )
        )
        self.action_logs = QtGui.QAction(
            resolve_ui_icon(ti.EditFind, st.SP_FileDialogInfoView),
            "Журнал работы (логи) (F12)",
            self,
        )
        self.action_logs.setShortcut(QtGui.QKeySequence("F12"))
        self.action_logs.triggered.connect(
            lambda: show_fusion_logs(
                app_title="Fusion Analysis",
                appdata_path=APPDATA_PATH,
                icon_bg_color=ANALYSIS_ICON_BG,
                parent=self,
            )
        )
        self.action_about = QtGui.QAction(
            resolve_ui_icon(ti.HelpAbout, st.SP_MessageBoxInformation),
            "О программе",
            self,
        )
        self.menu_help.addAction(self.action_docs)
        self.menu_help.addAction(self.action_license)
        self.menu_help.addAction(self.action_logs)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.action_about)

    def __init__(self, scale: float) -> None:
        self.list_segments: list[SegmentItem] = []
        super().__init__()
        self._build_ui()

        self.config: AnalysisConfig = read_config()
        log.bind(
            version=VERSION,
            scale=scale,
            config_path=str(DEFAULT_CONFIG_PATH),
            **self.config.model_dump(mode="json"),
        ).info("Fusion Analysis MainWindow initialized")
        controls = PlotterControls(
            spinbox_t=self.spinbox_t,
            spinbox_T1=self.spinbox_T1,
            spinbox_T2=self.spinbox_T2,
            spinbox_onsettool_T1=self.spinbox_onsettool_T1,
            spinbox_onsettool_T2=self.spinbox_onsettool_T2,
            combobox_xaxis=self.combobox_xaxis,
            combobox_baselinetype=self.combobox_baselinetype,
        )
        self.plotter = Plotter(self, scale=scale, controls=controls)
        self.plotter.config = self.config.Plotter
        self.showMaximized()
        self.plotter.signal_pick.connect(self.on_pick)
        self.plotter.signal_cm.connect(self.cm_popup)
        self.plotter.signal_split.connect(self.on_split_done)

        self.plotLayout.addWidget(self.plotter.canvas)
        self.plotLayout.addWidget(self.plotter.toolbar)

        self.action_about.triggered.connect(
            lambda: show_fusion_about(
                app_title="Fusion Analysis",
                version_str=VERSION,
                description=(
                    "Программа для обработки, анализа пиков и видео-синхронизации "
                    "данных термического анализа (ВТА, ДТА, ДСК, ТГА)."
                ),
                repo_slug="fusion-analysis",
                icon_bg_color=ANALYSIS_ICON_BG,
                zenodo_doi="10.5281/zenodo.24275025",
                parent=self,
            )
        )
        self.action_config.triggered.connect(self.on_click_config)
        self.action_open.triggered.connect(
            lambda: self.on_click_open(source=ImportSource.FUSION)
        )
        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        self.action_save_analysis = QtGui.QAction(
            resolve_ui_icon(ti.DocumentSaveAs, st.SP_DialogSaveButton),
            "Сохранить анализ как (.fusa)",
            self,
        )
        self.action_save_analysis.setEnabled(False)
        self.action_save_analysis.triggered.connect(self.on_click_save_analysis)
        self.menu_file.insertAction(self.action_close, self.action_save_analysis)

        self.action_netzsch.triggered.connect(
            lambda: self.on_click_open(source=ImportSource.NETZSCH)
        )
        self.action_setaram.triggered.connect(
            lambda: self.on_click_open(source=ImportSource.SETARAM)
        )
        self.action_summary_table = QtGui.QAction(
            resolve_ui_icon(ti.DocumentProperties, st.SP_FileDialogListView),
            "Сводная таблица пиков и переходов",
            self,
        )
        self.action_summary_table.setEnabled(False)
        self.action_summary_table.triggered.connect(self._open_summary_table)
        self.menu_tools.addAction(self.action_summary_table)

        self.action_close.triggered.connect(self.on_click_close)

        # контекстное меню
        self.cm = QtWidgets.QMenu(self)
        self.cm_name = QtGui.QAction()
        self.cm_name.setEnabled(False)
        self.cm.addAction(self.cm_name)
        self.cm_remove = RemoveAction(self)
        self.cm_remove.signal_removed.connect(self._refresh_segments_tree)
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

        self._smooth_backup: dict[str, int] = {}
        self._active_smooth_ch: str = ""
        self.btn_smoothtool.clicked.connect(self.on_click_smoothtool_start)
        self.spinbox_smooth_win.valueChanged.connect(self._on_smooth_win_changed)
        self.btn_smooth_reset.clicked.connect(
            lambda: self.spinbox_smooth_win.setValue(1)
        )
        self.buttonbox_smooth.accepted.connect(
            lambda: self.on_click_smoothtool_done(apply=True)
        )
        self.buttonbox_smooth.rejected.connect(
            lambda: self.on_click_smoothtool_done(apply=False)
        )

        self.btn_shiftsegment.mousePressEvent = self.on_press_shiftsegment  # type: ignore[method-assign]
        self.btn_shiftsegment.mouseMoveEvent = self.on_move_shiftsegment  # type: ignore[method-assign]

        self._active_deriv_ch: str = ""
        self._preview_deriv_col: str = ""
        self._preexisting_derivs: set[str] = set()
        self.btn_derivtool.clicked.connect(self.on_click_derivtool_start)
        self.combobox_derivative_order.currentIndexChanged.connect(
            self._on_deriv_order_preview_changed
        )
        self.buttonbox_deriv.accepted.connect(
            lambda: self.on_click_derivtool_done(apply=True)
        )
        self.buttonbox_deriv.rejected.connect(
            lambda: self.on_click_derivtool_done(apply=False)
        )

        self.lbl_split_x.setText("t, мин")

        self.checkbox_exo_up = QtWidgets.QCheckBox("Экзоэффект вверх (exo↑)", self)
        self.checkbox_exo_up.setChecked(True)
        self.checkbox_exo_up.setEnabled(False)
        self.checkbox_exo_up.toggled.connect(self._on_exo_direction_toggled)
        self.leftpanel.addWidget(self.checkbox_exo_up, 3, 0, 1, 2)

        self.lbl_passport = QtWidgets.QLabel("Паспорт: файл не открыт")
        self.lbl_passport.setWordWrap(True)
        self.lbl_passport.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.lbl_passport.setContentsMargins(6, 4, 6, 4)
        self.leftpanel.addWidget(self.lbl_passport, 4, 0, 1, 2)

        # обработчики левой панели
        self.checkbox_grid.stateChanged.connect(self.on_checkbox_grid_changed)
        self.combobox_xaxis.currentIndexChanged.connect(self.on_combobox_changed)

        # скрытие панелей инструментов
        tab_bar = self.tab_widget.tabBar()
        if tab_bar is not None:
            tab_bar.setVisible(False)
        self.tab_widget.setVisible(False)

        analysis_page = self.takeCentralWidget()
        if analysis_page is None:
            raise RuntimeError("Central widget is missing")
        self.mode_tabs = QtWidgets.QTabWidget(self)
        self.video_overlay_tab = VideoOverlayTab(parent=self)
        self.mode_tabs.addTab(
            analysis_page,
            load_asset_icon("peak.svg"),
            "Анализ кривых",
        )
        QtGui.QGuiApplication.styleHints().colorSchemeChanged.connect(
            self._refresh_theme_icons
        )
        self.mode_tabs.addTab(
            self.video_overlay_tab,
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.CameraVideo,
                QtWidgets.QStyle.StandardPixmap.SP_MediaPlay,
            ),
            "Видео-оверлей ВТА",
        )
        self.setCentralWidget(self.mode_tabs)

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

    def on_click_smoothtool_start(self) -> None:
        curve = self.plotter.picked_curve or self.plotter.picked_segment
        if not self.measurement_is_opened or curve is None:
            warning_message("Выделите кривую на графике или в списке сегментов.")
            return
        self._active_smooth_ch = curve.channel_name
        self.lbl_smooth_target.setText(f"<b>Кривая:</b> {self._active_smooth_ch}")
        self._smooth_backup = dict(self.measurement_data.smoothing_windows)
        init_win = int(
            self.measurement_data.smoothing_windows.get(self._active_smooth_ch, 1)
        )
        self.spinbox_smooth_win.blockSignals(True)
        self.spinbox_smooth_win.setValue(max(1, init_win))
        self.spinbox_smooth_win.blockSignals(False)
        self.plotter.show_smoothing_ghost(self._active_smooth_ch)

        self.tab_widget.setVisible(True)
        self.tab_widget.setCurrentIndex(3)
        layoutSetEnabled(self.leftpanel, False)
        self.btn_smoothtool.setEnabled(False)
        self.btn_derivtool.setEnabled(False)

    def _on_smooth_win_changed(self, win_val: int) -> None:
        if not self.measurement_is_opened or not self._active_smooth_ch:
            return
        ch = self._active_smooth_ch
        self.measurement_data.apply_channel_smoothing(ch, int(win_val))
        self.plotter.apply_live_smoothing(ch, int(win_val))

    def on_click_smoothtool_done(self, apply: bool) -> None:
        if not apply and self._active_smooth_ch:
            ch = self._active_smooth_ch
            prev_w = int(self._smooth_backup.get(ch, 1))
            self.measurement_data.apply_channel_smoothing(ch, prev_w)
            self.plotter.apply_live_smoothing(ch, prev_w)
        elif apply:
            self._sync_smoothed_to_record()
            log.bind(
                channel=self._active_smooth_ch,
                window=int(self.spinbox_smooth_win.value()),
                smoothing_windows=dict(self.measurement_data.smoothing_windows),
            ).info("Applied channel smoothing")
        self.plotter.clear_smoothing_ghost()
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        has_curve = self.plotter.picked_curve is not None
        self.btn_smoothtool.setEnabled(has_curve)
        self.btn_derivtool.setEnabled(has_curve)

    def _update_deriv_preview(self) -> None:
        if not self.measurement_is_opened or not self._active_deriv_ch:
            return
        if (
            self._preview_deriv_col
            and self._preview_deriv_col not in self._preexisting_derivs
        ):
            self.plotter.remove_derivative_channel(self._preview_deriv_col)
            self._preview_deriv_col = ""
        order = 2 if self.combobox_derivative_order.currentIndex() == 1 else 1
        self._preview_deriv_col = self.plotter.add_derivative_for_channel(
            self._active_deriv_ch, order=order
        )

    def _on_deriv_order_preview_changed(self, _index: int = 0) -> None:
        if self.tab_widget.isVisible() and self.tab_widget.currentIndex() == 4:
            self._update_deriv_preview()

    def on_click_derivtool_start(self) -> None:
        curve = self.plotter.picked_curve or self.plotter.picked_segment
        if not self.measurement_is_opened or curve is None:
            warning_message("Выделите исходную кривую для расчёта производной.")
            return
        self._active_deriv_ch = curve.channel_name
        self._preexisting_derivs = (
            set(self.plotter.segments_dta[0].curves.keys())  # noqa: MI001
            if self.plotter.segments_dta
            else set()
        )
        self._preview_deriv_col = ""
        self.lbl_deriv_target.setText(
            f"<b>Исходная кривая:</b> {self._active_deriv_ch}"
        )
        self.tab_widget.setVisible(True)
        self.tab_widget.setCurrentIndex(4)
        layoutSetEnabled(self.leftpanel, False)
        self.btn_smoothtool.setEnabled(False)
        self.btn_derivtool.setEnabled(False)
        self._update_deriv_preview()

    def on_click_derivtool_done(self, apply: bool) -> None:
        if apply and self._active_deriv_ch:
            x_col = self.combobox_xaxis.currentText() or "Time"
            order = 2 if self.combobox_derivative_order.currentIndex() == 1 else 1
            d_col = self.measurement_data.compute_derivative_channel(
                y_col=self._active_deriv_ch, x_col=x_col, order=order
            )
            self.plotter.add_derivative_for_channel(self._active_deriv_ch, order=order)
            self._refresh_segments_tree()
            log.bind(
                source_channel=self._active_deriv_ch,
                x_axis=x_col,
                order=order,
                derivative_channel=d_col,
            ).info("Added derivative channel")
        elif (
            self._preview_deriv_col
            and self._preview_deriv_col not in self._preexisting_derivs
        ):
            self.plotter.remove_derivative_channel(self._preview_deriv_col)
        self._preview_deriv_col = ""
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        has_curve = self.plotter.picked_curve is not None
        self.btn_smoothtool.setEnabled(has_curve)
        self.btn_derivtool.setEnabled(has_curve)

    def _sync_smoothed_to_record(self) -> None:
        self.measurement_data.sync_smoothed_to_record()
        if self.measurement_data.record is not None:
            self.video_overlay_tab.set_loaded_record(self.measurement_data.record)

    def on_click_save_analysis(self) -> None:
        if not self.measurement_is_opened:
            return
        self.measurement_data.analysis_state.update(
            self.plotter.export_analysis_state()
        )
        target = pick_save_fusa_path(
            source_path=self.measurement_data.source_path,
            parent=self,
        )
        if target is None:
            return
        try:
            saved = save_measurement_analysis(self.measurement_data, target)
            log.bind(
                target_path=str(saved),
                source_path=(
                    str(self.measurement_data.source_path)
                    if self.measurement_data.source_path is not None
                    else None
                ),
                segments=len(self.plotter.segments_dta),
                smoothing_windows=dict(self.measurement_data.smoothing_windows),
            ).info("Saved analysis project (.fusa)")
            self.statusBar().showMessage(
                f"Проект анализа сохранён в {saved.name}", 5000
            )
        except Exception as exc:  # noqa: BLE001
            error_message(f"Не удалось сохранить анализ (.fusa): {exc}")
            log.opt(exception=True).bind(
                target_path=str(target), error=repr(exc)
            ).error("Failed to save .fusa")

    def _on_exo_direction_toggled(self, checked: bool) -> None:
        if not self.measurement_is_opened:
            return
        self.measurement_data.exo = 1 if checked else 0
        self.plotter.measurement_exo = self.measurement_data.exo
        self.plotter.set_exo()
        self.plotter.canvas.draw()

    def on_treewidget_selection_changed(self) -> None:
        if self.plotter is None or self.treewidget_paused:
            return
        selected = self.treewidget_segments.selectedItems()
        if not selected:
            self.plotter.clear_selection()
            return
        first_item, *_ = selected
        is_checked = first_item.checkState(0) == QtCore.Qt.CheckState.Checked
        if not is_checked:
            self.plotter.clear_selection()
            return
        if isinstance(first_item, (CurveItem, SegmentItem)):
            self.plotter.select_curve_directly(first_item.artist)
            self.on_pick_segment(True)
            self.on_pick_peak(False)
        elif isinstance(first_item, PeakItem):
            self.plotter.select_peak_directly(first_item.artist)
            self.on_pick_segment(False)
            self.on_pick_peak(True)
        else:
            self.plotter.clear_selection()
        self.plotter.canvas.draw()

    def on_treewidget_changed(
        self,
        item: QtWidgets.QTreeWidgetItem,
        _col: int = 0,
    ) -> None:
        if self.measurement_is_opened and not self.treewidget_paused:
            self.treewidget_paused = True
            state = item.checkState(0) == QtCore.Qt.CheckState.Checked
            if isinstance(item, SegmentItem):
                item.artist.set_visible_all(state)
                update_child_items_state(item)
            elif isinstance(item, CurveItem):
                item.artist.set_visible(state)
                update_child_items_state(item)
                self.plotter.sync_aux_axes_visibility()
            elif isinstance(item, (PeakItem, OnsetItem)):
                item.artist.set_visible(state)
            self.plotter.sync_aux_axes_visibility()
            self.plotter.autoscale(redraw=False)
            self.treewidget_paused = False
            self.plotter.canvas.draw()

    def on_press_shiftsegment(self, event: QtGui.QMouseEvent) -> None:
        self.press_position = int(event.globalPosition().y())

    def on_move_shiftsegment(self, event: QtGui.QMouseEvent) -> None:
        target = self.plotter.picked_curve or self.plotter.picked_segment
        if target is not None:
            y = int(event.globalPosition().y())
            dy = y - self.press_position
            target.shifty(dy)
            self.plotter.canvas.draw()
            self.press_position = y

    def cm_popup(self, tpl: tuple[Any, QtCore.QPoint]) -> None:
        obj, pos = tpl
        match obj:
            case CurveSegment():
                name = f"Кривая {obj.channel_name} (Сегмент {obj.parent_segment.index})"
                self.cm_remove.setVisible(bool(obj.is_derivative))
            case Peak():
                name = f"Пик {obj.area}"
                self.cm_remove.setVisible(True)
            case OnsetLine():
                name = f"{obj.t}: {obj.info}"
                self.cm_remove.setVisible(True)
            case _:
                return
        self.cm_name.setText(name)
        self.cm_remove.obj = obj
        self.cm_prop.obj = obj
        self.cm.popup(pos)

    def on_click_splittool_done(self, apply: bool) -> None:
        self.treewidget_paused = True
        self.plotter.splittool_done(apply=apply)
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        self.treewidget_paused = False

    def splittool_check_is_valid(self) -> bool:
        if self.plotter.picked_segment is None:
            warning_message("Cегмент не выбран.")
            return False
        if self.combobox_xaxis.currentText() in ("Time"):
            pass
        else:
            warning_message("Неправильно выбрана ось абцисс!\nДолжна быть Time.")
            return False
        return True

    def on_click_splittool_start(self) -> None:
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

    def on_click_onsettool_start(self, is_onset: bool = True) -> None:
        if self.onsettool_check_is_valid():
            self.plotter.onsettool_start(is_onset)
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(1)
            layoutSetEnabled(self.leftpanel, False)
            self.btn_onsettool.setEnabled(False)
            self.btn_endtool.setEnabled(False)

    def _refresh_segments_tree(self) -> None:
        self.treewidget_paused = True
        self.treewidget_handler.on_split()
        self.treewidget_paused = False

    def _open_summary_table(self) -> None:
        if not self.measurement_is_opened:
            return
        SummaryTableDialog(self.plotter.segments_dta, parent=self).exec()

    def on_click_onsettool_done(self, apply: bool) -> None:
        self.plotter.onsettool_done(apply=apply)
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        if apply:
            self._refresh_segments_tree()

    def on_checkbox_grid_changed(self, state: int) -> None:
        self.plotter.gridSetVisible(state == 2)

    def _update_selector_labels(self, xaxis: str) -> None:
        if xaxis == "Time":
            l1, l2 = "t₁, мин", "t₂, мин"
        elif xaxis == "Temp.":
            l1, l2 = "T₁, °C", "T₂, °C"
        else:
            l1, l2 = "E₁, мВ", "E₂, мВ"
        self.label_T1.setText(l1)
        self.label_T2.setText(l2)
        self.lbl_onset_x1.setText(l1)
        self.lbl_onset_x2.setText(l2)

    def on_combobox_changed(self, _index: int) -> None:
        if self.comboboxes_is_set:
            self._update_selector_labels(self.combobox_xaxis.currentText())
            self.plotter.updateAxes()

    def on_click_peaktool_done(self, apply: bool) -> None:
        self.plotter.peaktool_done(apply=apply)
        self.tab_widget.setVisible(False)
        layoutSetEnabled(self.leftpanel, True)
        if apply:
            self._refresh_segments_tree()

    def on_click_peaktool_start(self) -> None:
        if self.peaktool_check_is_valid():
            self.plotter.peaktool_start()
            self.tab_widget.setVisible(True)
            self.tab_widget.setCurrentIndex(0)
            layoutSetEnabled(self.leftpanel, False)
            self.btn_shiftsegment.setEnabled(False)
            self.btn_peaktool.setEnabled(False)
            self.btn_split.setEnabled(False)

    def onsettool_check_is_valid(self) -> bool:
        if not isinstance(self.plotter.picked_item, Peak):
            warning_message("Пик не выбран.")
            return False
        return self._has_valid_xaxis()

    def peaktool_check_is_valid(self) -> bool:
        if self.plotter.picked_curve is None and self.plotter.picked_segment is None:
            warning_message("Кривая не выбрана.")
            return False
        return self._has_valid_xaxis()

    def _has_valid_xaxis(self) -> bool:
        return bool(self.combobox_xaxis.currentText())

    def on_click_config(self) -> None:
        c = ConfigWindow(self.config, parent=self)
        result = c.exec()
        if result == QtWidgets.QDialog.DialogCode.Accepted and c.changes_are_made:
            self.config = c.config
            self.plotter.config = self.config.Plotter
            self.plotter.apply_antialias(self.config.Plotter.antialias)
            write_config(self.config)
            log.bind(
                config_path=str(DEFAULT_CONFIG_PATH),
                **self.config.model_dump(mode="json"),
            ).info("Updated analysis configuration from Settings dialog")

    def on_click_close(self) -> None:
        closed_path = (
            str(self.measurement_data.source_path)
            if self.measurement_is_opened
            and self.measurement_data.source_path is not None
            else None
        )
        self.comboboxes_is_set = False
        self.action_open.setEnabled(True)
        self.action_save_analysis.setEnabled(False)
        self.action_summary_table.setEnabled(False)
        self.action_close.setEnabled(False)
        self.on_pick_segment(False)
        self.on_pick_peak(False)
        self.list_segments.clear()
        self.menu_import.setEnabled(True)
        self.treewidget_segments.clear()
        self.measurement_is_opened = False
        layoutSetEnabled(self.leftpanel, False)
        self.combobox_xaxis.clear()
        self.plotter.on_close()
        self.checkbox_exo_up.setVisible(False)
        log.bind(path=closed_path).info("Closed measurement")

    def on_click_open(
        self,
        source: ImportSource = ImportSource.FUSION,
    ) -> None:
        path: Path | None = None
        if source is ImportSource.FUSION:
            path = pick_open_measurement_path(self)
        else:
            file_name, _ = QtWidgets.QFileDialog.getOpenFileName(  # noqa: PU001
                self,
                "Open file",
                "",
                "Text Files (*.txt);;All Files (*)",
            )
            if file_name:
                path = Path(file_name)

        if path is None or not path.exists():
            return
        try:
            if source is ImportSource.FUSION:
                self.measurement_data = load_fusion_measurement(path)
            elif source is ImportSource.NETZSCH:
                self.measurement_data = import_netzsch_txt(path)
            else:
                mass_val = ask_mass(self)
                if mass_val is None:
                    return
                self.measurement_data = import_setaram_txt(path, startmass=mass_val)
        except Exception as exc:  # noqa: BLE001
            error_message(f"Не удалось открыть измерение: {exc}")
            log.opt(exception=True).bind(
                path=str(path), source=str(source), error=repr(exc)
            ).error("Failed to open measurement")
            return
        log.bind(path=str(path), source=str(source)).info("Measurement opened")
        try:
            self.init_measurement()
        except Exception as exc:  # noqa: BLE001
            self.on_click_close()
            error_message(f"Не удалось отобразить измерение: {exc}")
            log.opt(exception=True).bind(
                path=str(path), source=str(source), error=repr(exc)
            ).error("Failed to initialize measurement UI")

    def init_measurement(self) -> None:
        string = "Temp." if self.measurement_data.has_tempdata else "EMF"
        xaxes = ["Time", *self.measurement_data.available_channels]
        seen_x: set[str] = set()
        for header in xaxes:
            if header not in seen_x:
                seen_x.add(header)
                self.combobox_xaxis.addItem(header)

        primary_y = (
            "DTA"
            if "DTA" in self.measurement_data.available_channels
            else self.measurement_data.available_channels[0]  # noqa: MI001
        )
        self.combobox_xaxis.setCurrentText("Time")
        self.combobox_derivative_order.setEnabled(True)
        self._update_selector_labels("Time")
        info = self.measurement_data.info
        smp = info.get("sample") or "—"
        op = info.get("operator") or "—"
        inst = info.get("instrument") or "—"
        mass = info.get("sample_mass_mg")
        mass_s = f"{mass} мг" if mass else "—"
        cruc = info.get("crucible") or "—"
        atm = info.get("atmosphere") or "—"
        self.lbl_passport.setText(
            f"<b>Образец:</b> {smp} | <b>Прибор:</b> {inst} | <b>Масса:</b> {mass_s}<br>"
            f"<b>Тигель:</b> {cruc} | <b>Атмосфера:</b> {atm} | <b>Оператор:</b> {op}"
        )
        points_total = sum(
            len(seg.get("Time", [])) for seg in self.measurement_data.segments
        )
        log.bind(
            path=(
                str(self.measurement_data.source_path)
                if self.measurement_data.source_path is not None
                else None
            ),
            source_format=(
                self.measurement_data.record.source_format
                if self.measurement_data.record is not None
                else None
            ),
            sample=smp,
            operator=op,
            instrument=inst,
            sample_mass_mg=mass,
            crucible=cruc,
            atmosphere=atm,
            exo=self.measurement_data.exo,
            has_massdata=self.measurement_data.has_massdata,
            has_tempdata=self.measurement_data.has_tempdata,
            channels=list(self.measurement_data.available_channels),
            units=dict(self.measurement_data.units),
            segments=len(self.measurement_data.segments),
            points_total=points_total,
            smoothing_windows=dict(self.measurement_data.smoothing_windows),
        ).info("Initialized measurement in curve analysis tab")
        self.setWindowTitle(f"Fusion Analysis — {smp}")
        self.plotter.deriv_channel = str(
            self.measurement_data.analysis_state.get("deriv_channel", primary_y)
        )

        self.comboboxes_is_set = True
        layoutSetEnabled(self.leftpanel, True)

        artists = []
        for index, df in enumerate(self.measurement_data.segments):
            thermal_type, _ = classify_segment_thermal_type(df[string])  # noqa: PU001
            artist = self.plotter.addSegment(
                df=df, index=index, thermal_type=thermal_type, temp_axis=string
            )
            artists.append(artist)
        self.treewidget_handler.init(
            artists, has_massdata=self.measurement_data.has_massdata
        )

        has_dta = "DTA" in self.measurement_data.available_channels
        # рисуем график
        self.plotter.units = self.measurement_data.units
        self.plotter.measurement_exo = self.measurement_data.exo
        self.plotter.sample_mass_mg = self.measurement_data.info.get("sample_mass_mg")
        self.checkbox_exo_up.setVisible(has_dta)
        self.checkbox_exo_up.blockSignals(True)
        self.checkbox_exo_up.setChecked(self.measurement_data.exo == 1)
        self.checkbox_exo_up.blockSignals(False)
        self.plotter.plot(
            self.combobox_xaxis.currentText(),
            primary_y,
            has_massdata=self.measurement_data.has_massdata,
            has_tempdata=self.measurement_data.has_tempdata,
        )
        if has_dta:
            self.plotter.set_exo()
        self.plotter.set_visible(True)
        self.measurement_is_opened = True

        # переключаем кнопки
        is_fusa_project = bool(self.measurement_data.analysis_state) or (
            self.measurement_data.source_path is not None
            and self.measurement_data.source_path.suffix.lower() == ".fusa"
        )
        file_sw = str(self.measurement_data.info.get("software_version") or "").strip()
        is_newer_fusa = bool(
            is_fusa_project and file_sw and is_newer_version(file_sw, VERSION)
        )
        if self.measurement_data.analysis_state:
            restore_warnings = self.plotter.restore_analysis_state(
                self.measurement_data.analysis_state
            )
            self._refresh_segments_tree()
            if restore_warnings:
                if is_newer_fusa:
                    header = (
                        f"Файл анализа создан в более новой версии Fusion Analysis "
                        f"(v{file_sw.lstrip('v')}; текущая версия v{VERSION}). "
                        "Часть разметки не удалось восстановить — обновите программу до последней версии:"
                    )
                else:
                    header = "Часть разметки анализа не удалось восстановить:"
                    details = "\n".join(f"• {msg}" for msg in restore_warnings[:10])
                log.bind(
                    file_software_version=file_sw,
                    current_version=VERSION,
                    warnings_count=len(restore_warnings),
                ).warning("Partial restore of .fusa analysis_state")
                warning_message(f"{header}\n\n{details}")
            elif is_newer_fusa:
                log.bind(
                    file_software_version=file_sw,
                    current_version=VERSION,
                ).warning("Opened .fusa created by a newer Fusion Analysis version")
        elif is_newer_fusa:
            log.bind(
                file_software_version=file_sw,
                current_version=VERSION,
            ).warning("Opened .fusa created by a newer Fusion Analysis version")

        self.action_open.setEnabled(False)
        self.action_save_analysis.setEnabled(True)
        self.action_summary_table.setEnabled(True)
        self.action_close.setEnabled(True)
        self.on_pick_segment(False)
        self.on_pick_peak(False)
        self.menu_import.setEnabled(False)
        if self.measurement_data.record is not None:
            self.video_overlay_tab.set_loaded_record(self.measurement_data.record)

    def _refresh_theme_icons(
        self, _scheme: QtCore.Qt.ColorScheme | None = None
    ) -> None:
        for btn, icon_name in (
            (self.btn_shiftsegment, "shift.svg"),
            (self.btn_split, "split.svg"),
            (self.btn_peaktool, "peak.svg"),
            (self.btn_onsettool, "onset.svg"),
            (self.btn_endtool, "end.svg"),
            (self.btn_smoothtool, "smooth.svg"),
            (self.btn_derivtool, "derivative.svg"),
        ):
            btn.setIcon(load_asset_icon(icon_name))
        self.mode_tabs.setTabIcon(0, load_asset_icon("peak.svg"))
        it = QtWidgets.QTreeWidgetItemIterator(self.treewidget_segments)
        while it.value() is not None:
            node = it.value()
            if isinstance(node, (SegmentItem, CurveItem, PeakItem, OnsetItem)):
                node.refresh_icon()
            it += 1

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.video_overlay_tab is not None:
            self.video_overlay_tab.shutdown()
        super().closeEvent(event)

    def on_pick_segment(self, state: bool) -> None:
        self.btn_peaktool.setEnabled(state)
        self.btn_shiftsegment.setEnabled(state)
        self.btn_split.setEnabled(state)
        self.btn_smoothtool.setEnabled(state)
        self.btn_derivtool.setEnabled(state)

    def on_pick_peak(self, state: bool) -> None:
        self.btn_onsettool.setEnabled(state)
        self.btn_endtool.setEnabled(state)

    def on_pick(
        self,
        item: CurveSegment | Peak | OnsetLine | MyAnn | None,
    ) -> None:
        match item:
            case CurveSegment():
                self.on_pick_segment(True)
                self.on_pick_peak(False)
                self.treewidget_handler.select_curve_item(item)
            case Peak():
                self.on_pick_segment(False)
                self.on_pick_peak(True)
                self.treewidget_segments.blockSignals(True)
                self.treewidget_segments.clearSelection()
                self.treewidget_segments.blockSignals(False)
            case None:
                self.on_pick_segment(False)
                self.on_pick_peak(False)
                self.treewidget_segments.blockSignals(True)
                self.treewidget_segments.clearSelection()
                self.treewidget_segments.blockSignals(False)

    def on_split_done(self, _tpl: tuple[SegmentDTA, SegmentDTA, int]) -> None:
        self.treewidget_handler.on_split()
