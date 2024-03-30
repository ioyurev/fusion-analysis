if [ ! -d "fusion_analysis/ui" ]; then
    mkdir fusion_analysis/ui
fi 
python devtools/git_hash.py
pyside6-uic assets/MainWindow.ui > fusion_analysis/ui/MainWindow.py
pyside6-uic assets/Config.ui > fusion_analysis/ui/Config.py
pyside6-uic assets/OnsetProperties.ui > fusion_analysis/ui/OnsetProperties.py
pyside6-uic assets/PeakProperties.ui > fusion_analysis/ui/PeakProperties.py
pyside6-uic assets/SegmentProperties.ui > fusion_analysis/ui/SegmentProperties.py
pyside6-rcc assets/resources.qrc > fusion_analysis/ui/resources_rc.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/MainWindow.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/Config.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/OnsetProperties.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/PeakProperties.py
autoflake -i --remove-all-unused-imports fusion_analysis/ui/SegmentProperties.py
