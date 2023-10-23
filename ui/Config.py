# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Config.ui'
##
## Created by: Qt User Interface Compiler version 6.6.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QGridLayout, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(442, 205)
        self.gridLayout = QGridLayout(Dialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 2, 0, 1, 1)

        self.buttonBox = QDialogButtonBox(Dialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 6, 0, 1, 4)

        self.checkbox_autocolor = QCheckBox(Dialog)
        self.checkbox_autocolor.setObjectName(u"checkbox_autocolor")

        self.gridLayout.addWidget(self.checkbox_autocolor, 1, 0, 1, 4)

        self.w_color_heat = QWidget(Dialog)
        self.w_color_heat.setObjectName(u"w_color_heat")
        self.w_color_heat.setMinimumSize(QSize(24, 24))

        self.gridLayout.addWidget(self.w_color_heat, 2, 1, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 2, 3, 1, 1)

        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setPointSize(12)
        self.label.setFont(font)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 4)

        self.btn_color_heat = QPushButton(Dialog)
        self.btn_color_heat.setObjectName(u"btn_color_heat")

        self.gridLayout.addWidget(self.btn_color_heat, 2, 2, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 4, 3, 1, 1)

        self.label_3 = QLabel(Dialog)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 3, 0, 1, 1)

        self.w_color_cool = QWidget(Dialog)
        self.w_color_cool.setObjectName(u"w_color_cool")
        self.w_color_cool.setMinimumSize(QSize(24, 24))

        self.gridLayout.addWidget(self.w_color_cool, 3, 1, 1, 1)

        self.btn_color_cool = QPushButton(Dialog)
        self.btn_color_cool.setObjectName(u"btn_color_cool")

        self.gridLayout.addWidget(self.btn_color_cool, 3, 2, 1, 1)

        self.gridLayout.setColumnStretch(3, 1)

        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"\u0426\u0432\u0435\u0442 \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u0430 \u043d\u0430\u0433\u0440\u0435\u0432\u0430", None))
        self.checkbox_autocolor.setText(QCoreApplication.translate("Dialog", u"\u0418\u043d\u0434\u0438\u0432\u0438\u0432\u0438\u0434\u0443\u0430\u043b\u044c\u043d\u044b\u0439 \u0446\u0432\u0435\u0442 \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u043e\u0432 \u043f\u0440\u0438 \u043e\u0442\u043a\u0440\u044b\u0442\u0438\u0438 \u043d\u043e\u0432\u043e\u0433\u043e \u0438\u0437\u043c\u0435\u0440\u0435\u043d\u0438\u044f", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"\u041a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u044f \u043f\u043e \u0443\u043c\u043e\u043b\u0447\u0430\u043d\u0438\u044e", None))
        self.btn_color_heat.setText(QCoreApplication.translate("Dialog", u"\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"\u0426\u0432\u0435\u0442 \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u0430 \u043e\u0445\u043b\u0430\u0436\u0434\u0435\u043d\u0438\u044f", None))
        self.btn_color_cool.setText(QCoreApplication.translate("Dialog", u"\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c", None))
    # retranslateUi

