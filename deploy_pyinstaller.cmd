py git_hash.py
if not exist pyinstaller mkdir pyinstaller
cd pyinstaller
rd /f dist
pyinstaller ../main.py -i ../assets/icon.png --splash ../assets/splash.png -n fusion-analysis
py ../version_file_gen.py
pyi-set_version version_text_file dist/fusion-analysis/fusion-analysis.exe
