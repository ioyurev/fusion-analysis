# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'OnsetProperties.ui'
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
    QDialogButtonBox, QGridLayout, QLabel, QSizePolicy,
    QSpacerItem, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(256, 192)
        self.gridLayout = QGridLayout(Dialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.buttonBox = QDialogButtonBox(Dialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 6, 0, 1, 1)

        self.checkbox_temp = QCheckBox(Dialog)
        self.checkbox_temp.setObjectName(u"checkbox_temp")

        self.gridLayout.addWidget(self.checkbox_temp, 3, 0, 1, 1)

        self.checkbox_time = QCheckBox(Dialog)
        self.checkbox_time.setObjectName(u"checkbox_time")

        self.gridLayout.addWidget(self.checkbox_time, 2, 0, 1, 1)

        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setPointSize(12)
        self.label.setFont(font)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.checkbox_label = QCheckBox(Dialog)
        self.checkbox_label.setObjectName(u"checkbox_label")

        self.gridLayout.addWidget(self.checkbox_label, 1, 0, 1, 1)

        self.checkbox_dta = QCheckBox(Dialog)
        self.checkbox_dta.setObjectName(u"checkbox_dta")

        self.gridLayout.addWidget(self.checkbox_dta, 4, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 5, 0, 1, 1)


        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        self.checkbox_temp.setText(QCoreApplication.translate("Dialog", u"\u0422\u0435\u043c\u043f\u0435\u0440\u0430\u0442\u0443\u0440\u0430", None))
        self.checkbox_time.setText(QCoreApplication.translate("Dialog", u"\u0412\u0440\u0435\u043c\u044f", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"\u041e\u0442\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u0438", None))
        self.checkbox_label.setText(QCoreApplication.translate("Dialog", u"\u041f\u043e\u0434\u043f\u0438\u0441\u044c", None))
        self.checkbox_dta.setText(QCoreApplication.translate("Dialog", u"\u0414\u0422\u0410", None))
        pass
    # retranslateUi

