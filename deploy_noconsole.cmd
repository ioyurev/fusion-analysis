python -m nuitka Gui.py --standalone --enable-plugin=pyside6 --disable-console
xcopy .\assets\ .\Gui.dist\assets\
xcopy .\MainWindow.ui .\Gui.dist\