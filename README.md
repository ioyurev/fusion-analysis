# Fusion Analysis

<p align="center">
  <img src="assets/icon.svg" width="128" alt="Fusion Analysis Icon">
</p>

Приложение для постобработки, анализа пиков и видео-синхронизации данных термического анализа (ВТА, ДТА, ДСК, ТГА).

## Возможности

- **Вкладка «Анализ кривых»:**
  - открытие файлов `.fus`, `.fusa`, `.vtaz` (v0/v1), `.tda`, `.fus-mdt`, `.fus-fmdt`, а также импорт текстовых выгрузок приборов `Netzsch` и `Setaram`;
  - независимое неразрушающее сглаживание любой кривой измерения (`DTA`, `Temp.`, `EMF`, `Mass`) и построение производной $\mathrm{d}Y/\mathrm{d}X$ для любого выбранного канала по времени или температуре;
  - разбиение термограмм на сегменты нагрева/охлаждения, выделение пиков с линейной или Безье-базовой линией, расчёт площадей и поиск характеристических точек начала и конца пиков (`Onset` / `End`);
  - сохранение всех сглаженных кривых и графической разметки в отдельный файл проекта анализа **`.fusa`** без изменения исходного файла сырого измерения.
- **Вкладка «Видео-оверлей ВТА»:**
  - нативная 1:1 синхронизация видеозаписей рабочей камеры ВТА с переменной частотой кадров (VFR) и термограмм;
  - интерактивное кадрирование, наложение телеметрии и скользящего графика скорости нагрева $\mathrm{d}T/\mathrm{d}t\,(^\circ\text{C/с})$ и многопоточный экспорт в `.mp4` (FFmpeg) и `.xlsx`.

## Требования и запуск

- Python >= 3.13, менеджер пакетов `uv`, установленный в `PATH` пакет `ffmpeg` / `ffprobe` (для видео-оверлея)
- Установка окружения:
  `uv sync`
- Запуск из исходников:
  `.\run.cmd`
- Сборка исполняемого дистрибутива PyInstaller:
  `.\build.cmd`

## Документация и теоретические основы

Подробное руководство пользователя и теоретическое описание методов доступно в каталоге [`fusion_analysis/docs/`](fusion_analysis/docs/01_overview_and_formats.md) и внутри самой программы по клавише `F1` (**Справка → Руководство пользователя (F1)**):
- [1. Обзор анализатора и архитектура разделения .fus и .fusa](fusion_analysis/docs/01_overview_and_formats.md)
- [2. Фильтрация сигналов и производные 1-го и 2-го порядка](fusion_analysis/docs/02_smoothing_and_derivatives.md)
- [3. Конструирование базовых линий и интегрирование пиков](fusion_analysis/docs/03_baselines_and_peaks.md)
- [4. Характеристические температуры фазовых переходов и фазовые диаграммы](fusion_analysis/docs/04_characteristic_temperatures.md)
- [5. Стеклование, степень превращения α(T, t) и профиль Фрейзера--Сузуки](fusion_analysis/docs/05_glass_transition_and_kinetics.md)
- [6. Синхронный термический анализ (ТГА-ДТА/ДСК)](fusion_analysis/docs/06_sta_and_tga.md)
- [7. Термомикроскопия ВТА и синхронизация видео](fusion_analysis/docs/07_video_overlay_vta.md)

## Цитирование

Если вы используете **Fusion Analysis** в научной работе, пожалуйста, процитируйте программу (метаданные приведены в файле [`CITATION.cff`](CITATION.cff)):

> *Yurev I. O.* Fusion Analysis: Post-processing, peak analysis, and video synchronization software for thermal analysis (VTA, DTA, DSC, TGA) [Computer software]. — 2026. — URL: <https://github.com/ioyurev/fusion-analysis>.

## Лицензия

Проект распространяется на условиях лицензии **GNU General Public License v3.0 or later (`GPL-3.0-or-later`)** (см. [LICENSE.md](LICENSE.md), [LICENSE.ru.md](LICENSE.ru.md); официальная страница лицензии GNU GPL v3.0: [gnu.org/licenses/gpl-3.0.ru.html](https://www.gnu.org/licenses/gpl-3.0.ru.html)).
