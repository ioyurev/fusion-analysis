if not exist fusion_analysis\ui mkdir fusion_analysis\ui
if not exist fusion_analysis\ui\__init__.py cd . > fusion_analysis\ui\__init__.py

.venv\Scripts\pyside6-uic.exe assets/MainWindow.ui > fusion_analysis/ui/MainWindow.py
.venv\Scripts\pyside6-uic.exe assets/Config.ui > fusion_analysis/ui/Config.py
.venv\Scripts\pyside6-uic.exe assets/OnsetProperties.ui > fusion_analysis/ui/OnsetProperties.py
.venv\Scripts\pyside6-uic.exe assets/PeakProperties.ui > fusion_analysis/ui/PeakProperties.py
.venv\Scripts\pyside6-uic.exe assets/SegmentProperties.ui > fusion_analysis/ui/SegmentProperties.py
.venv\Scripts\pyside6-uic.exe assets/FilterWindow.ui > fusion_analysis/ui/FilterWindow.py

.venv\Scripts\pyside6-rcc.exe assets/resources.qrc > fusion_analysis/ui/resources_rc.py

.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_analysis/ui/MainWindow.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_analysis/ui/Config.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_analysis/ui/OnsetProperties.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_analysis/ui/PeakProperties.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_analysis/ui/SegmentProperties.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_analysis/ui/FilterWindow.py
