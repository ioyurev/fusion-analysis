from __future__ import annotations

import shutil
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from fusion_common import MeasurementRecord, resolve_ui_icon
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets

from fusion_analysis.importers import ALL_SUPPORTED_FILTER
from fusion_analysis.video_overlay.ffmpeg_pipe import (
    FFmpeg,
    TempDirManager,
    build_video_info,
)
from fusion_analysis.video_overlay.models import (
    LoadedVideoMeasurement,
    OverlapStatus,
    OverlaySessionState,
    ProcessProgress,
    ProcessResult,
    RectangleGeometry,
    load_video_measurement,
    record_to_video_measurement,
)
from fusion_analysis.video_overlay.renderer import VideoExportPipeline
from fusion_analysis.video_overlay.timeline import (
    AlignedData,
    build_aligned_info,
    build_timeline_selection,
    update_video_info_with_timeline,
)
from fusion_analysis.video_overlay.widgets import (
    AspectRatioLabel,
    CropSelectionDialog,
    LiveSyncPlotWidget,
    OverlaySettingsDialog,
    PreviewWorker,
    SessionInfoWidget,
)


class VideoOverlayTab(QtWidgets.QWidget):
    """Нативный видеоплеер термомикроскопии ВТА с синхронным графиком и экспортом MP4 с оверлеем."""

    worker_request_signal = QtCore.Signal(int, object, object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = OverlaySessionState()
        self.aligned_data: AlignedData | None = None
        self.pipeline = VideoExportPipeline(self)
        self.preview_thread: QtCore.QThread | None = None
        self.worker: PreviewWorker | None = None
        self.current_fps: float = 25.0
        self.preview_total_frames: int = 0
        self.render_start_time: float | None = None
        self.current_render_fps: float = 0.0

        self.play_timer = QtCore.QTimer(self)
        self.play_timer.timeout.connect(self._on_play_tick)

        self._build_ui()
        self.pipeline.stage_progress.connect(self._on_stage_progress)
        self.pipeline.stage_finished.connect(self._on_stage_finished)
        self.pipeline.fps_updated.connect(self._on_fps_updated)
        self.pipeline.work_finished.connect(self._on_work_finished)

    def _build_ui(self) -> None:
        main_grid = QtWidgets.QGridLayout(self)
        main_grid.setContentsMargins(6, 6, 6, 6)
        main_grid.setSpacing(8)

        ctrl_box = QtWidgets.QWidget()
        ctrl_layout = QtWidgets.QVBoxLayout(ctrl_box)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)

        data_row = QtWidgets.QHBoxLayout()
        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        self.btn_data = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentOpen, st.SP_DialogOpenButton),
            "Выбрать файл измерения",
        )
        self.edit_data = QtWidgets.QLineEdit()
        self.edit_data.setReadOnly(True)
        self.btn_data.clicked.connect(self._pick_data_file)
        data_row.addWidget(self.btn_data)
        data_row.addWidget(self.edit_data, 1)
        ctrl_layout.addLayout(data_row)

        vid_row = QtWidgets.QHBoxLayout()
        self.btn_video = QtWidgets.QPushButton(
            resolve_ui_icon(ti.CameraVideo, st.SP_DirOpenIcon),
            "Выбрать видеофайл",
        )
        self.edit_video = QtWidgets.QLineEdit()
        self.edit_video.setReadOnly(True)
        self.btn_video.clicked.connect(self._pick_video_file)
        vid_row.addWidget(self.btn_video)
        vid_row.addWidget(self.edit_video, 1)
        ctrl_layout.addLayout(vid_row)

        tools_row = QtWidgets.QHBoxLayout()
        self.btn_crop = QtWidgets.QPushButton(
            resolve_ui_icon(ti.InsertImage, st.SP_FileDialogContentsView),
            "Кадрировать",
        )
        self.btn_crop.setEnabled(False)
        self.btn_reset_crop = QtWidgets.QPushButton(
            resolve_ui_icon(ti.ViewRestore, st.SP_DialogResetButton),
            "Сбросить кадрирование",
        )
        self.btn_reset_crop.setEnabled(False)
        self.btn_settings = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentProperties, st.SP_FileDialogDetailedView),
            "Настройки экспорта оверлея",
        )
        self.btn_crop.clicked.connect(self._open_crop_dialog)
        self.btn_reset_crop.clicked.connect(self._reset_crop)
        self.btn_settings.clicked.connect(self._open_overlay_settings)
        for b in (self.btn_crop, self.btn_reset_crop, self.btn_settings):
            tools_row.addWidget(b)
        ctrl_layout.addLayout(tools_row)

        self.cb_excel = QtWidgets.QCheckBox(
            "Экспортировать таблицу данных со встроенным графиком в .xlsx"
        )
        self.cb_excel.setChecked(True)
        ctrl_layout.addWidget(self.cb_excel)

        self.btn_export = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentSaveAs, st.SP_DialogSaveButton),
            "Экспорт видео с наложенным оверлеем (.mp4)",
        )
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._start_export)
        ctrl_layout.addWidget(self.btn_export)

        self.sync_plot = LiveSyncPlotWidget(self)
        ctrl_layout.addWidget(self.sync_plot, 1)

        self.lbl_eta = QtWidgets.QLabel("Готово к работе")
        ctrl_layout.addWidget(self.lbl_eta)
        self.progressbar = QtWidgets.QProgressBar()
        self.progressbar.setValue(0)
        ctrl_layout.addWidget(self.progressbar)
        main_grid.addWidget(ctrl_box, 0, 0)

        preview_box = QtWidgets.QWidget()
        preview_layout = QtWidgets.QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)

        self.lbl_telemetry = QtWidgets.QLabel(
            "Кадр: — | t: 0.00 мин | T: — °C | E: — мВ | dT/dt: — °C/с"
        )
        self.lbl_telemetry.setStyleSheet(
            "background-color: #1e272e; color: #f1c40f; font-family: Consolas; "
            "font-size: 13px; font-weight: bold; padding: 6px; border-radius: 4px;"
        )
        self.lbl_telemetry.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        preview_layout.addWidget(self.lbl_telemetry)

        self.video_preview = AspectRatioLabel()
        self.video_preview.setStyleSheet("background-color: rgb(0, 0, 0);")
        preview_layout.addWidget(self.video_preview, 1)

        transport_row = QtWidgets.QHBoxLayout()
        self.btn_prev_frame = QtWidgets.QPushButton(
            resolve_ui_icon(ti.MediaSkipBackward, st.SP_MediaSkipBackward),
            "-1",
        )
        self.btn_prev_frame.setFixedWidth(58)
        self.btn_prev_frame.setEnabled(False)
        self.btn_play = QtWidgets.QPushButton(
            resolve_ui_icon(ti.MediaPlaybackStart, st.SP_MediaPlay),
            "Пуск",
        )
        self.btn_play.setFixedWidth(88)
        self.btn_play.setEnabled(False)
        self.btn_next_frame = QtWidgets.QPushButton(
            resolve_ui_icon(ti.MediaSkipForward, st.SP_MediaSkipForward),
            "+1",
        )
        self.btn_next_frame.setFixedWidth(58)
        self.btn_next_frame.setEnabled(False)

        self.cb_play_speed = QtWidgets.QComboBox()
        for spd_label, spd_mult in (
            ("0.5x", 0.5),
            ("1.0x", 1.0),
            ("2.0x", 2.0),
            ("5.0x", 5.0),
            ("10.0x", 10.0),
        ):
            self.cb_play_speed.addItem(spd_label, spd_mult)
        self.cb_play_speed.setCurrentIndex(1)
        self.cb_play_speed.currentIndexChanged.connect(self._update_timer_interval)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setEnabled(False)

        self.btn_prev_frame.clicked.connect(lambda: self._step_frame(-1))
        self.btn_next_frame.clicked.connect(lambda: self._step_frame(1))
        self.btn_play.clicked.connect(self._toggle_playback)
        self.slider.valueChanged.connect(self._on_slider_changed)

        transport_row.addWidget(self.btn_prev_frame)
        transport_row.addWidget(self.btn_play)
        transport_row.addWidget(self.btn_next_frame)
        transport_row.addWidget(self.cb_play_speed)
        transport_row.addWidget(self.slider, 1)
        preview_layout.addLayout(transport_row)
        main_grid.addWidget(preview_box, 0, 1)

        self.session_info = SessionInfoWidget()
        self.session_info.setMinimumHeight(175)
        main_grid.addWidget(self.session_info, 1, 0, 1, 2)

        main_grid.setRowStretch(0, 3)
        main_grid.setRowStretch(1, 1)
        main_grid.setColumnStretch(0, 1)
        main_grid.setColumnStretch(1, 1)

    def set_loaded_record(self, record: MeasurementRecord) -> None:
        loaded = record_to_video_measurement(record)
        self._apply_loaded_measurement(loaded)

    def _apply_loaded_measurement(self, loaded: LoadedVideoMeasurement) -> None:
        self.session.measurement = loaded
        self.pipeline.data = loaded.data
        self.edit_data.setText(str(loaded.data.path))
        self._refresh_timeline_and_aligned()
        self._refresh_info_panel()
        self._update_telemetry_and_cursor(self.slider.value())

    def _pick_data_file(self) -> None:
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(  # noqa: PU001 — Qt QFileDialog tuple
            self,
            "Открыть файл измерения для видео-оверлея",
            "",
            ALL_SUPPORTED_FILTER,
        )
        if not fname:
            return
        try:
            loaded = load_video_measurement(Path(fname))
            self._apply_loaded_measurement(loaded)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self, "Ошибка чтения данных", f"Не удалось загрузить файл: {exc}"
            )

    def _pick_video_file(self) -> None:
        for bin_name in ("ffmpeg", "ffprobe"):
            if shutil.which(bin_name) is None:
                QtWidgets.QMessageBox.critical(
                    self,
                    "FFmpeg не найден",
                    f"Утилита '{bin_name}' не найдена в PATH.",
                )
                return

        fname, _ = QtWidgets.QFileDialog.getOpenFileName(  # noqa: PU001 — Qt QFileDialog tuple
            self,
            "Выбрать видеофайл ВТА",
            "",
            "Видео (*.asf *.mp4 *.avi *.mkv);;Все файлы (*.*)",
        )
        if not fname:
            return
        v_path = Path(fname)
        try:
            self._stop_playback()
            w, h = FFmpeg().get_resolution(v_path)  # noqa: PU001
            self.pipeline.video_path_input = v_path
            self.pipeline.crop_rect = None
            self.btn_crop.setEnabled(True)
            self.btn_reset_crop.setEnabled(False)
            self.edit_video.setText(str(v_path))
            if h > 0:
                self.video_preview.set_aspect_ratio(w, h)
            self.session.video_info = build_video_info(v_path, crop_rect=None)
            self._refresh_timeline_and_aligned()
            self._refresh_info_panel()
            self._start_preview_worker(str(v_path))
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self, "Ошибка видеофайла", f"Не удалось открыть видео: {exc}"
            )

    def _start_preview_worker(self, video_path: str) -> None:
        self._stop_preview_worker()
        self.preview_thread = QtCore.QThread(self)
        self.worker = PreviewWorker(video_path)
        self.worker.moveToThread(self.preview_thread)
        self.preview_thread.started.connect(self.worker.init_video)
        self.worker_request_signal.connect(self.worker.request_frame)
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.preview_thread.start()

        if self.session.video_info is not None:
            self.preview_total_frames = max(0, self.session.video_info.total_frames)
            self.current_fps = max(
                1.0,
                float(
                    self.session.video_info.real_fps
                    or self.session.video_info.fps_nominal
                ),
            )
        self._refresh_slider_range()
        self.slider.setValue(0)
        self._request_preview_update(0)

    def _stop_preview_worker(self) -> None:
        self._stop_playback()
        if self.preview_thread is not None and self.preview_thread.isRunning():
            if self.worker is not None:
                self.worker.cleanup()
            self.preview_thread.quit()
            self.preview_thread.wait(2000)
        self.preview_thread = None
        self.worker = None

    def _request_preview_update(self, frame_index: int) -> None:
        self._update_telemetry_and_cursor(frame_index)
        if self.worker is None:
            return
        self.worker_request_signal.emit(
            frame_index,
            self.pipeline.crop_rect,
            self.pipeline.timeline,
        )

    @QtCore.Slot(object, int, float)
    def _on_frame_ready(
        self,
        pixmap: QtGui.QPixmap,
        _frame_idx: int,
        _time_sec: float,
    ) -> None:
        self.video_preview.setPixmap(pixmap)

    def _on_slider_changed(self, val: int) -> None:
        self._request_preview_update(val)

    def _step_frame(self, delta: int) -> None:
        self._stop_playback()
        if not self.slider.isEnabled():
            return
        new_idx = max(0, min(self.slider.maximum(), self.slider.value() + delta))
        self.slider.setValue(new_idx)

    def _toggle_playback(self) -> None:
        if self.play_timer.isActive():
            self._stop_playback()
        else:
            if self.slider.value() >= self.slider.maximum():
                self.slider.setValue(0)
            self._update_timer_interval()
            self.play_timer.start()
            self.btn_play.setIcon(
                resolve_ui_icon(
                    QtGui.QIcon.ThemeIcon.MediaPlaybackPause,
                    QtWidgets.QStyle.StandardPixmap.SP_MediaPause,
                )
            )
            self.btn_play.setText("Пауза")

    def _stop_playback(self) -> None:
        if self.play_timer.isActive():
            self.play_timer.stop()
        self.btn_play.setIcon(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.MediaPlaybackStart,
                QtWidgets.QStyle.StandardPixmap.SP_MediaPlay,
            )
        )
        self.btn_play.setText("Пуск")

    def _update_timer_interval(self) -> None:
        mult = float(self.cb_play_speed.currentData() or 1.0)
        eff_fps = max(1.0, self.current_fps * mult)
        interval_ms = max(15, int(1000.0 / eff_fps))
        self.play_timer.setInterval(interval_ms)

    def _on_play_tick(self) -> None:
        if not self.slider.isEnabled():
            self._stop_playback()
            return
        nxt = self.slider.value() + 1
        if nxt > self.slider.maximum():
            self._stop_playback()
            return
        self.slider.setValue(nxt)

    def _update_telemetry_and_cursor(self, idx: int) -> None:
        self.sync_plot.set_cursor_index(idx)
        total = self.slider.maximum() + 1 if self.slider.isEnabled() else 0
        if self.aligned_data is not None and 0 <= idx < len(
            self.aligned_data.timestamps
        ):
            t_s = float(self.aligned_data.timestamps[idx])
            tel = self.aligned_data.at_index(idx)
            mins, secs = divmod(max(0.0, t_s), 60.0)  # noqa: PU001
            t_str = f"{mins:02.0f}:{secs:04.1f} ({t_s / 60.0:.2f} мин)"
            temp_str = f"{tel.temp:.1f} °C" if tel.temp is not None else "— °C"
            emf_str = f"{tel.emf:.3f} мВ"
            spd_str = f"{tel.speed:.2f} °C/с" if tel.speed is not None else "— °C/с"
            self.lbl_telemetry.setText(
                f"Кадр: {idx + 1}/{total} | t: {t_str} | T: {temp_str} | E: {emf_str} | dT/dt: {spd_str}"
            )
        else:
            t_s = idx / max(1.0, self.current_fps)
            self.lbl_telemetry.setText(
                f"Кадр: {idx + 1}/{total} | t: {t_s / 60.0:.2f} мин | T: — °C | E: — мВ | dT/dt: — °C/с"
            )

    def _refresh_slider_range(self) -> None:
        tl = self.pipeline.timeline
        if tl is not None and tl.status is not OverlapStatus.NONE:
            max_i = max(0, tl.kept_frames - 1)
            enabled = tl.kept_frames > 0
        elif self.preview_total_frames > 0:
            max_i = max(0, self.preview_total_frames - 1)
            enabled = True
        else:
            max_i = 0
            enabled = False
        self.slider.setRange(0, max_i)
        for w in (
            self.slider,
            self.btn_play,
            self.btn_prev_frame,
            self.btn_next_frame,
        ):
            w.setEnabled(enabled)

    def _refresh_timeline_and_aligned(self) -> None:
        if self.session.measurement is not None and self.session.video_info is None:
            # Если загружены только данные измерения без видео — строим график по самим данным
            d = self.session.measurement.data
            self.aligned_data = AlignedData(
                timestamps=d.time,
                emf=d.emf,
                temp=d.temp,
                speed=d.speed,
            )
            self.sync_plot.set_aligned_data(self.aligned_data)
            self.session.timeline = None
            self.session.aligned_info = None
            self.btn_export.setEnabled(False)
            return

        if self.session.measurement is None or self.session.video_info is None:
            self.aligned_data = None
            self.sync_plot.set_aligned_data(None)
            self.session.timeline = None
            self.session.aligned_info = None
            self.btn_export.setEnabled(False)
            return

        tl = build_timeline_selection(
            data=self.session.measurement.data,
            video_info=self.session.video_info,
        )
        self.session.timeline = tl
        self.session.video_info = update_video_info_with_timeline(
            self.session.video_info, tl
        )
        self.session.aligned_info = build_aligned_info(
            self.session.measurement.data, self.session.video_info, tl
        )
        self.pipeline.timeline = tl
        if tl.status is not OverlapStatus.NONE and len(tl.kept_timestamps_sec) > 0:
            self.aligned_data = AlignedData.from_data(
                tl.kept_timestamps_sec, self.session.measurement.data
            )
        else:
            self.aligned_data = AlignedData(
                timestamps=np.array([], dtype=float),
                emf=np.array([], dtype=float),
                temp=None,
                speed=None,
            )
        self.sync_plot.set_aligned_data(self.aligned_data)
        self.btn_export.setEnabled(tl.status is not OverlapStatus.NONE)
        self._refresh_slider_range()

    def _refresh_info_panel(self) -> None:
        self.session_info.set_measurement_info(
            self.session.measurement.info if self.session.measurement else None
        )
        self.session_info.set_video_info(self.session.video_info)
        self.session_info.set_aligned_info(self.session.aligned_info)

    def _open_crop_dialog(self) -> None:
        if self.pipeline.video_path_input is None:
            return
        self._stop_playback()
        dlg = CropSelectionDialog(
            self.pipeline.video_path_input,
            initial_rect=self.pipeline.crop_rect,
            parent=self,
        )
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._apply_crop(dlg.get_crop_rect())

    def _apply_crop(self, rect: RectangleGeometry) -> None:
        self.pipeline.crop_rect = rect
        if rect.h > 0:
            self.video_preview.set_aspect_ratio(rect.w, rect.h)
        if self.session.video_info is not None:
            self.session.video_info = replace(self.session.video_info, crop_rect=rect)
            self._refresh_info_panel()
        self.btn_reset_crop.setEnabled(True)
        if self.slider.isEnabled():
            self._request_preview_update(self.slider.value())

    def _reset_crop(self) -> None:
        self.pipeline.crop_rect = None
        if self.session.video_info is not None:
            self.session.video_info = replace(self.session.video_info, crop_rect=None)
            self.video_preview.set_aspect_ratio(
                self.session.video_info.input_width,
                self.session.video_info.input_height,
            )
            self._refresh_info_panel()
        self.btn_reset_crop.setEnabled(False)
        if self.slider.isEnabled():
            self._request_preview_update(self.slider.value())

    def _open_overlay_settings(self) -> None:
        OverlaySettingsDialog(parent=self).exec()

    def _set_controls_enabled(self, enabled: bool) -> None:
        for w in (
            self.btn_data,
            self.btn_video,
            self.btn_crop,
            self.btn_settings,
            self.cb_excel,
            self.slider,
            self.btn_play,
            self.btn_prev_frame,
            self.btn_next_frame,
        ):
            w.setEnabled(enabled)
        self.btn_reset_crop.setEnabled(enabled and self.pipeline.crop_rect is not None)
        tl = self.pipeline.timeline
        self.btn_export.setEnabled(
            enabled and tl is not None and tl.status is not OverlapStatus.NONE
        )

    def _start_export(self) -> None:
        self._stop_playback()
        if self.pipeline.data is None or self.pipeline.timeline is None:
            return
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(  # noqa: PU001 — Qt QFileDialog tuple
            self, "Сохранить видео с оверлеем", "", "Видео MP4 (*.mp4)"
        )
        if not fname:
            return
        out_path = Path(fname)
        if out_path.suffix.lower() != ".mp4":
            out_path = out_path.with_suffix(".mp4")

        self._set_controls_enabled(False)
        self.render_start_time = time.perf_counter()
        self.current_render_fps = 0.0
        self.pipeline.video_path_output = out_path
        if self.cb_excel.isChecked():
            try:
                self.pipeline.data.to_excel(out_path.with_suffix(".xlsx"))
            except Exception as exc:  # noqa: BLE001
                log.bind(error=str(exc)).warning("Excel export failed")
        self.pipeline.start()

    def _on_stage_finished(self, tpl: tuple[int, str, str]) -> None:
        total, _, _ = tpl
        self.progressbar.setValue(0)
        self.progressbar.setMaximum(max(1, int(total)))

    def _on_fps_updated(self, fps: float) -> None:
        self.current_render_fps = fps
        self._update_eta_label()

    def _on_stage_progress(self, progress: ProcessProgress) -> None:
        self.progressbar.setValue(progress.value)
        self._update_eta_label()
        if progress.frame is not None:
            self.video_preview.setPixmap(progress.frame.to_pixmap())

    def _update_eta_label(self) -> None:
        if self.render_start_time is None:
            return
        elapsed = time.perf_counter() - self.render_start_time
        el_s = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        rem = max(0, self.progressbar.maximum() - self.progressbar.value())
        eta_s = (
            f"{int((rem / self.current_render_fps) // 60):02d}:{int((rem / self.current_render_fps) % 60):02d}"
            if self.current_render_fps > 0 and rem > 0
            else "--:--"
        )
        self.lbl_eta.setText(
            f"FPS: {self.current_render_fps:.1f} | Прошло: {el_s} | Осталось: {eta_s}"
        )

    def _on_work_finished(self, res: ProcessResult) -> None:
        self.render_start_time = None
        TempDirManager.cleanup()
        self._set_controls_enabled(True)
        self.progressbar.setValue(0)
        if res.is_success:
            self.lbl_eta.setText("Экспорт видео успешно завершён")
            QtWidgets.QMessageBox.information(
                self, "Готово", "Обработка и экспорт видео завершены."
            )
        else:
            self.lbl_eta.setText("Ошибка при обработке видео")
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка экспорта",
                f"Не удалось завершить обработку видео:\n{res.traceback_msg}",
            )

    def shutdown(self) -> None:
        self._stop_playback()
        if self.pipeline.isRunning():
            self.pipeline.stop()
            self.pipeline.wait(5000)
        self._stop_preview_worker()
        TempDirManager.cleanup()
