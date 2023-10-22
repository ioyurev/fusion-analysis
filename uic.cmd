cd ui
pyside6-uic.exe src/MainWindow.ui > MainWindow.py 
pyside6-uic.exe src/Config.ui > Config.py 
pyside6-uic.exe src/OnsetProperties.ui > OnsetProperties.py
pyside6-uic.exe src/PeakProperties.ui > PeakProperties.py
pyside6-uic.exe src/SegmentProperties.ui > SegmentProperties.py
cd ..
pyside6-rcc.exe assets/resources.qrc > resources_rc.py