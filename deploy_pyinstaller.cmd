python git_hash.py
if not exist pyinstaller mkdir pyinstaller
cd pyinstaller

python ../devtools/splash_gen.py
..\.venv\Scripts\pyinstaller.exe ../fusion_analysis/__main__.py -i ../assets/icon.png --splash splash.png -n fusion-analysis --noconfirm
python ../devtools/version_file_gen.py
pyi-set_version version_text_file dist/fusion-analysis/fusion-analysis.exe

xcopy ..\LICENSE .\dist\fusion-analysis\
xcopy ..\LICENSE_RU .\dist\fusion-analysis\
python ../devtools/zip_build.py
