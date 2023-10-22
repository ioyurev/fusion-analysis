# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'MainWindow.ui'
##
## Created by: Qt User Interface Compiler version 6.5.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLayout, QMainWindow,
    QMenu, QMenuBar, QPushButton, QSizePolicy,
    QSpacerItem, QStatusBar, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)

from CustomWidgets import MySpinBox
import resources_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1024, 768)
        self.action_open = QAction(MainWindow)
        self.action_open.setObjectName(u"action_open")
        self.action_close = QAction(MainWindow)
        self.action_close.setObjectName(u"action_close")
        self.action_close.setEnabled(False)
        self.action_config = QAction(MainWindow)
        self.action_config.setObjectName(u"action_config")
        self.action_netzsch = QAction(MainWindow)
        self.action_netzsch.setObjectName(u"action_netzsch")
        self.action_setaram = QAction(MainWindow)
        self.action_setaram.setObjectName(u"action_setaram")
        self.action_about = QAction(MainWindow)
        self.action_about.setObjectName(u"action_about")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_2 = QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.leftpanel = QGridLayout()
        self.leftpanel.setObjectName(u"leftpanel")
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setPointSize(10)
        self.label.setFont(font)

        self.leftpanel.addWidget(self.label, 7, 0, 1, 1)

        self.checkbox_autoscale = QCheckBox(self.centralwidget)
        self.checkbox_autoscale.setObjectName(u"checkbox_autoscale")
        self.checkbox_autoscale.setEnabled(False)
        self.checkbox_autoscale.setChecked(True)

        self.leftpanel.addWidget(self.checkbox_autoscale, 2, 0, 1, 2)

        self.treewidget_segments = QTreeWidget(self.centralwidget)
        __qtreewidgetitem = QTreeWidgetItem()
        __qtreewidgetitem.setText(0, u"1");
        self.treewidget_segments.setHeaderItem(__qtreewidgetitem)
        self.treewidget_segments.setObjectName(u"treewidget_segments")
        self.treewidget_segments.setHeaderHidden(True)

        self.leftpanel.addWidget(self.treewidget_segments, 8, 0, 1, 2)

        self.combobox_xaxis = QComboBox(self.centralwidget)
        self.combobox_xaxis.setObjectName(u"combobox_xaxis")
        self.combobox_xaxis.setEnabled(False)

        self.leftpanel.addWidget(self.combobox_xaxis, 1, 1, 1, 1)

        self.label_xaxis = QLabel(self.centralwidget)
        self.label_xaxis.setObjectName(u"label_xaxis")

        self.leftpanel.addWidget(self.label_xaxis, 1, 0, 1, 1)

        self.checkbox_grid = QCheckBox(self.centralwidget)
        self.checkbox_grid.setObjectName(u"checkbox_grid")
        self.checkbox_grid.setEnabled(False)

        self.leftpanel.addWidget(self.checkbox_grid, 4, 0, 1, 2)

        self.label_4 = QLabel(self.centralwidget)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setFont(font)

        self.leftpanel.addWidget(self.label_4, 0, 0, 1, 2)

        self.line_3 = QFrame(self.centralwidget)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.HLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.leftpanel.addWidget(self.line_3, 6, 0, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.leftpanel.addItem(self.verticalSpacer, 9, 0, 1, 1)

        self.checkbox_derivative = QCheckBox(self.centralwidget)
        self.checkbox_derivative.setObjectName(u"checkbox_derivative")
        self.checkbox_derivative.setEnabled(False)

        self.leftpanel.addWidget(self.checkbox_derivative, 3, 0, 1, 2)


        self.gridLayout_2.addLayout(self.leftpanel, 0, 0, 1, 1)

        self.line_2 = QFrame(self.centralwidget)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.VLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.gridLayout_2.addWidget(self.line_2, 0, 1, 1, 1)

        self.rightpanel = QGridLayout()
        self.rightpanel.setObjectName(u"rightpanel")
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(6)
        self.toolbar.setObjectName(u"toolbar")
        self.toolbar.setSizeConstraint(QLayout.SetMinimumSize)
        self.toolbar.setContentsMargins(-1, -1, -1, 0)
        self.btn_shiftsegment = QPushButton(self.centralwidget)
        self.btn_shiftsegment.setObjectName(u"btn_shiftsegment")
        self.btn_shiftsegment.setEnabled(False)
        icon = QIcon()
        icon.addFile(u":/shift.png", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_shiftsegment.setIcon(icon)
        self.btn_shiftsegment.setIconSize(QSize(32, 32))

        self.toolbar.addWidget(self.btn_shiftsegment)

        self.btn_split = QPushButton(self.centralwidget)
        self.btn_split.setObjectName(u"btn_split")
        self.btn_split.setEnabled(False)
        icon1 = QIcon()
        icon1.addFile(u":/split.png", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_split.setIcon(icon1)
        self.btn_split.setIconSize(QSize(32, 32))

        self.toolbar.addWidget(self.btn_split)

        self.btn_peaktool = QPushButton(self.centralwidget)
        self.btn_peaktool.setObjectName(u"btn_peaktool")
        self.btn_peaktool.setEnabled(False)
        icon2 = QIcon()
        icon2.addFile(u":/peak.png", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_peaktool.setIcon(icon2)
        self.btn_peaktool.setIconSize(QSize(32, 32))
        self.btn_peaktool.setFlat(False)

        self.toolbar.addWidget(self.btn_peaktool)

        self.btn_onsettool = QPushButton(self.centralwidget)
        self.btn_onsettool.setObjectName(u"btn_onsettool")
        self.btn_onsettool.setEnabled(False)
        icon3 = QIcon()
        icon3.addFile(u":/onset.png", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_onsettool.setIcon(icon3)
        self.btn_onsettool.setIconSize(QSize(32, 32))

        self.toolbar.addWidget(self.btn_onsettool)

        self.btn_endtool = QPushButton(self.centralwidget)
        self.btn_endtool.setObjectName(u"btn_endtool")
        self.btn_endtool.setEnabled(False)
        icon4 = QIcon()
        icon4.addFile(u":/end.png", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_endtool.setIcon(icon4)
        self.btn_endtool.setIconSize(QSize(32, 32))

        self.toolbar.addWidget(self.btn_endtool)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.toolbar.addItem(self.horizontalSpacer)


        self.rightpanel.addLayout(self.toolbar, 0, 0, 1, 1)

        self.plotLayout = QVBoxLayout()
        self.plotLayout.setObjectName(u"plotLayout")

        self.rightpanel.addLayout(self.plotLayout, 4, 0, 1, 1)

        self.onsettoolLayout = QGridLayout()
        self.onsettoolLayout.setObjectName(u"onsettoolLayout")
        self.onsettoolLayout.setSizeConstraint(QLayout.SetMinimumSize)
        self.line_4 = QFrame(self.centralwidget)
        self.line_4.setObjectName(u"line_4")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.line_4.sizePolicy().hasHeightForWidth())
        self.line_4.setSizePolicy(sizePolicy)
        self.line_4.setFrameShape(QFrame.HLine)
        self.line_4.setFrameShadow(QFrame.Sunken)

        self.onsettoolLayout.addWidget(self.line_4, 0, 0, 1, 4)

        self.tab_widget = QTabWidget(self.centralwidget)
        self.tab_widget.setObjectName(u"tab_widget")
        self.tab_widget.setTabBarAutoHide(True)
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.gridLayout = QGridLayout(self.tab)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label_T2 = QLabel(self.tab)
        self.label_T2.setObjectName(u"label_T2")
        self.label_T2.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)

        self.gridLayout.addWidget(self.label_T2, 0, 1, 1, 1)

        self.combobox_baselinetype = QComboBox(self.tab)
        self.combobox_baselinetype.addItem("")
        self.combobox_baselinetype.addItem("")
        self.combobox_baselinetype.setObjectName(u"combobox_baselinetype")
        sizePolicy.setHeightForWidth(self.combobox_baselinetype.sizePolicy().hasHeightForWidth())
        self.combobox_baselinetype.setSizePolicy(sizePolicy)

        self.gridLayout.addWidget(self.combobox_baselinetype, 1, 2, 1, 1)

        self.label_T1 = QLabel(self.tab)
        self.label_T1.setObjectName(u"label_T1")
        sizePolicy.setHeightForWidth(self.label_T1.sizePolicy().hasHeightForWidth())
        self.label_T1.setSizePolicy(sizePolicy)
        self.label_T1.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)

        self.gridLayout.addWidget(self.label_T1, 0, 0, 1, 1)

        self.label_2 = QLabel(self.tab)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 0, 2, 1, 1)

        self.spinbox_T2 = MySpinBox(self.tab)
        self.spinbox_T2.setObjectName(u"spinbox_T2")
        sizePolicy.setHeightForWidth(self.spinbox_T2.sizePolicy().hasHeightForWidth())
        self.spinbox_T2.setSizePolicy(sizePolicy)
        self.spinbox_T2.setDecimals(5)
        self.spinbox_T2.setMaximum(2000.000000000000000)
        self.spinbox_T2.setSingleStep(0.100000000000000)

        self.gridLayout.addWidget(self.spinbox_T2, 1, 1, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_2, 1, 3, 1, 1)

        self.spinbox_T1 = MySpinBox(self.tab)
        self.spinbox_T1.setObjectName(u"spinbox_T1")
        sizePolicy.setHeightForWidth(self.spinbox_T1.sizePolicy().hasHeightForWidth())
        self.spinbox_T1.setSizePolicy(sizePolicy)
        self.spinbox_T1.setDecimals(5)
        self.spinbox_T1.setMaximum(2000.000000000000000)
        self.spinbox_T1.setSingleStep(0.100000000000000)

        self.gridLayout.addWidget(self.spinbox_T1, 1, 0, 1, 1)

        self.buttonbox_peak = QDialogButtonBox(self.tab)
        self.buttonbox_peak.setObjectName(u"buttonbox_peak")
        self.buttonbox_peak.setLayoutDirection(Qt.LeftToRight)
        self.buttonbox_peak.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonbox_peak, 2, 0, 1, 4)

        self.tab_widget.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.gridLayout_3 = QGridLayout(self.tab_2)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.buttonbox_onset = QDialogButtonBox(self.tab_2)
        self.buttonbox_onset.setObjectName(u"buttonbox_onset")
        self.buttonbox_onset.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout_3.addWidget(self.buttonbox_onset, 2, 0, 1, 3)

        self.label_3 = QLabel(self.tab_2)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)

        self.gridLayout_3.addWidget(self.label_3, 0, 0, 1, 1)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout_3.addItem(self.horizontalSpacer_3, 1, 2, 1, 1)

        self.label_5 = QLabel(self.tab_2)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)

        self.gridLayout_3.addWidget(self.label_5, 0, 1, 1, 1)

        self.spinbox_onsettool_T1 = MySpinBox(self.tab_2)
        self.spinbox_onsettool_T1.setObjectName(u"spinbox_onsettool_T1")
        sizePolicy.setHeightForWidth(self.spinbox_onsettool_T1.sizePolicy().hasHeightForWidth())
        self.spinbox_onsettool_T1.setSizePolicy(sizePolicy)
        self.spinbox_onsettool_T1.setDecimals(5)
        self.spinbox_onsettool_T1.setMaximum(2000.000000000000000)
        self.spinbox_onsettool_T1.setSingleStep(0.100000000000000)

        self.gridLayout_3.addWidget(self.spinbox_onsettool_T1, 1, 0, 1, 1)

        self.spinbox_onsettool_T2 = MySpinBox(self.tab_2)
        self.spinbox_onsettool_T2.setObjectName(u"spinbox_onsettool_T2")
        sizePolicy.setHeightForWidth(self.spinbox_onsettool_T2.sizePolicy().hasHeightForWidth())
        self.spinbox_onsettool_T2.setSizePolicy(sizePolicy)
        self.spinbox_onsettool_T2.setDecimals(5)
        self.spinbox_onsettool_T2.setMaximum(2000.000000000000000)
        self.spinbox_onsettool_T2.setSingleStep(0.100000000000000)

        self.gridLayout_3.addWidget(self.spinbox_onsettool_T2, 1, 1, 1, 1)

        self.tab_widget.addTab(self.tab_2, "")
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.gridLayout_4 = QGridLayout(self.tab_3)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.buttonbox_split = QDialogButtonBox(self.tab_3)
        self.buttonbox_split.setObjectName(u"buttonbox_split")
        self.buttonbox_split.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout_4.addWidget(self.buttonbox_split, 2, 0, 1, 2)

        self.spinbox_t = MySpinBox(self.tab_3)
        self.spinbox_t.setObjectName(u"spinbox_t")
        self.spinbox_t.setDecimals(5)
        self.spinbox_t.setMaximum(2000.000000000000000)

        self.gridLayout_4.addWidget(self.spinbox_t, 1, 0, 1, 1)

        self.label_7 = QLabel(self.tab_3)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setAlignment(Qt.AlignCenter)

        self.gridLayout_4.addWidget(self.label_7, 0, 0, 1, 1)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout_4.addItem(self.horizontalSpacer_4, 1, 1, 1, 1)

        self.tab_widget.addTab(self.tab_3, "")

        self.onsettoolLayout.addWidget(self.tab_widget, 1, 0, 1, 4)


        self.rightpanel.addLayout(self.onsettoolLayout, 3, 0, 1, 1)

        self.rightpanel.setRowStretch(4, 1)

        self.gridLayout_2.addLayout(self.rightpanel, 0, 2, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1024, 22))
        self.menu_file = QMenu(self.menubar)
        self.menu_file.setObjectName(u"menu_file")
        self.menu_import = QMenu(self.menu_file)
        self.menu_import.setObjectName(u"menu_import")
        self.menu_editor = QMenu(self.menubar)
        self.menu_editor.setObjectName(u"menu_editor")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menu_file.menuAction())
        self.menubar.addAction(self.menu_editor.menuAction())
        self.menu_file.addAction(self.action_open)
        self.menu_file.addAction(self.menu_import.menuAction())
        self.menu_file.addAction(self.action_close)
        self.menu_file.addAction(self.action_about)
        self.menu_import.addAction(self.action_netzsch)
        self.menu_import.addAction(self.action_setaram)
        self.menu_editor.addAction(self.action_config)

        self.retranslateUi(MainWindow)

        self.tab_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Fusion Analysis", None))
        self.action_open.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c", None))
        self.action_close.setText(QCoreApplication.translate("MainWindow", u"\u0417\u0430\u043a\u0440\u044b\u0442\u044c", None))
        self.action_config.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", None))
        self.action_netzsch.setText(QCoreApplication.translate("MainWindow", u"Netzsch ANSI TXT", None))
        self.action_setaram.setText(QCoreApplication.translate("MainWindow", u"Setaram ANSI TXT", None))
        self.action_about.setText(QCoreApplication.translate("MainWindow", u"\u041e \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0435", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u0421\u043f\u0438\u0441\u043e\u043a \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u043e\u0432", None))
        self.checkbox_autoscale.setText(QCoreApplication.translate("MainWindow", u"\u0410\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u043c\u0430\u0441\u0448\u0442\u0430\u0431 \u043e\u0441\u0435\u0439", None))
        self.label_xaxis.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0441\u044c \u0430\u0431\u0446\u0438\u0441\u0441:", None))
        self.checkbox_grid.setText(QCoreApplication.translate("MainWindow", u"\u0412\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u0441\u0435\u0442\u043a\u0443", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u043e\u0442\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f \u0433\u0440\u0430\u0444\u0438\u043a\u0430", None))
        self.checkbox_derivative.setText(QCoreApplication.translate("MainWindow", u"\u0412\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u043d\u0443\u044e", None))
#if QT_CONFIG(tooltip)
        self.btn_shiftsegment.setToolTip(QCoreApplication.translate("MainWindow", u"\u041f\u0435\u0440\u0435\u043c\u0435\u0449\u0435\u043d\u0438\u0435 \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u0430 \u043f\u043e \u043e\u0441\u0438 y.", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.btn_split.setToolTip(QCoreApplication.translate("MainWindow", u"\u0420\u0430\u0437\u0434\u0435\u043b\u0438\u0442\u044c \u0441\u0435\u0433\u043c\u0435\u043d\u0442 \u043d\u0430 \u0434\u0432\u0430.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_split.setText("")
#if QT_CONFIG(tooltip)
        self.btn_peaktool.setToolTip(QCoreApplication.translate("MainWindow", u"\u0412\u044b\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u043f\u0438\u043a\u0430.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_peaktool.setText("")
#if QT_CONFIG(tooltip)
        self.btn_onsettool.setToolTip(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0439\u0442\u0438 \u043d\u0430\u0447\u0430\u043b\u043e \u043f\u0438\u043a\u0430.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_onsettool.setText("")
#if QT_CONFIG(tooltip)
        self.btn_endtool.setToolTip(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0439\u0442\u0438 \u043a\u043e\u043d\u0435\u0446 \u043f\u0438\u043a\u0430.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_endtool.setText("")
        self.label_T2.setText(QCoreApplication.translate("MainWindow", u"T2", None))
        self.combobox_baselinetype.setItemText(0, QCoreApplication.translate("MainWindow", u"\u041b\u0438\u043d\u0435\u0439\u043d\u0430\u044f", None))
        self.combobox_baselinetype.setItemText(1, QCoreApplication.translate("MainWindow", u"\u0411\u0435\u0437\u044c\u0435", None))

        self.label_T1.setText(QCoreApplication.translate("MainWindow", u"T1", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"\u0412\u0438\u0434 \u0431\u0430\u0437\u043e\u0432\u043e\u0439 \u043b\u0438\u043d\u0438\u0438", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.tab), QCoreApplication.translate("MainWindow", u"Peak", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"T1", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"T2", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.tab_2), QCoreApplication.translate("MainWindow", u"Onset", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"T", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.tab_3), QCoreApplication.translate("MainWindow", u"Split", None))
        self.menu_file.setTitle(QCoreApplication.translate("MainWindow", u"\u0424\u0430\u0439\u043b", None))
        self.menu_import.setTitle(QCoreApplication.translate("MainWindow", u"\u0418\u043c\u043f\u043e\u0440\u0442", None))
        self.menu_editor.setTitle(QCoreApplication.translate("MainWindow", u"\u0420\u0435\u0434\u0430\u043a\u0442\u043e\u0440", None))
    # retranslateUi

