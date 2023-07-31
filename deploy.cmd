cd deployment
python -m nuitka --standalone --enable-plugin=pyside6 ../main.py
@REM xcopy .\MainWindow.ui .\deployment\main.dist\
@REM xcopy .\assets\ .\deployment\main.dist\assets /s /e