python -m nuitka Gui.py --standalone --enable-plugin=pyside6
xcopy .\assets\ .\Gui.dist\assets\
xcopy .\MainWindow.ui .\Gui.dist\