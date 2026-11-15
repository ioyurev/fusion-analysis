@echo off
chcp 65001 >nul
if not exist pyinstaller mkdir pyinstaller
cd pyinstaller
uv run fusion-splash --subtitle "Thermal Analysis Tool" --bg-color "#1E293B" --svg-out ../assets/icon.svg --icon-out icon.ico --version-from .. --out splash.png || exit /b 1
uv run pyinstaller ../fusion_analysis/__main__.py --noconsole -i icon.ico --splash splash.png --collect-data fusion_common --collect-data fusion_analysis -n fusion-analysis --noconfirm --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module scipy || exit /b 1
uv run fusion-packaging version-file --package fusion-analysis --product "Fusion Analysis" --description "Fusion Analysis" --version-from .. --out version_text_file || exit /b 1
uv run pyi-set_version version_text_file dist/fusion-analysis/fusion-analysis.exe || exit /b 1
uv run fusion-docs --package fusion_analysis --out-dir dist/fusion-analysis || exit /b 1
uv run fusion-packaging zip-dist --package fusion-analysis --version-from .. --dist-root dist || exit /b 1
uv run fusion-packaging installer --package fusion-analysis --product "Fusion Analysis" --version-from .. --dist-root dist --icon icon.ico || exit /b 1
pause
