if not exist fusion_analysis\ui mkdir fusion_analysis\ui
if not exist fusion_analysis\ui\__init__.py cd . > fusion_analysis\ui\__init__.py
python devtools/git_hash.py
pyside6-uic.exe assets/MainWindow.ui > fusion_analysis/ui/MainWindow.py
pyside6-uic.exe assets/Config.ui > fusion_analysis/ui/Config.py
pyside6-uic.exe assets/OnsetProperties.ui > fusion_analysis/ui/OnsetProperties.py
pyside6-uic.exe assets/PeakProperties.ui > fusion_analysis/ui/PeakProperties.py
pyside6-uic.exe assets/SegmentProperties.ui > fusion_analysis/ui/SegmentProperties.py
pyside6-uic.exe assets/DenoiseWindow.ui > fusion_analysis/ui/DenoiseWindow.py
pyside6-rcc.exe assets/resources.qrc > fusion_analysis/ui/resources_rc.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/MainWindow.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/Config.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/OnsetProperties.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/PeakProperties.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/SegmentProperties.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/DenoiseWindow.py
