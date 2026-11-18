from __future__ import annotations

import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
from fusion_common import MeasurementRecord, resolve_ui_icon
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtMultimedia import QMediaPlayer

from fusion_analysis.importers import ALL_SUPPORTED_FILTER
from fusion_analysis.video_overlay.ffmpeg_pipe import (
    FFmpeg,
    TempDirManager,
    build_video_info,
    resolve_ffmpeg_binary,
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
    CropSelectionDialog,
    LiveSyncPlotWidget,
    OverlaySettingsDialog,
    SessionInfoWidget,
    VideoPlayerView,
)

QtCore.QLoggingCategory.setFilterRules("qt.multimedia.ffmpeg*=false")


class VideoOverlayTab(QtWidgets.QWidget):
    """Нативный видеоплеер термомикроскопии ВТА на QMediaPlayer с синхронным графиком и экспортом MP4."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = OverlaySessionState()
        self.aligned_data: AlignedData | None = None
        self.pipeline = VideoExportPipeline(self)
        self.current_fps: float = 25.0
        self.preview_total_frames: int = 0
        self.render_start_time: float | None = None
        self.current_render_fps: float = 0.0
        self._seek_on_load_pending: bool = False

        self.media_player = QMediaPlayer(self)
        self._build_ui()
        self.media_player.setVideoOutput(self.video_preview.video_item)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.positionChanged.connect(self._on_media_position_changed)
        self.media_player.errorOccurred.connect(self._on_media_error)

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

        self.video_preview = VideoPlayerView(self)
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
        self.cb_play_speed.currentIndexChanged.connect(self._on_play_speed_changed)

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
        info_dict = asdict(loaded.info)
        info_dict["path"] = str(loaded.info.path)
        log.bind(**info_dict).info("Loaded measurement data into Video Overlay tab")
        self._refresh_timeline_and_aligned()
        self._refresh_info_panel()
        self._update_telemetry_and_cursor(self.slider.value())

    def _pick_data_file(self) -> None:
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(  # noqa: PU001
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
            log.opt(exception=True).bind(path=fname, error=repr(exc)).error(
                "Failed to load measurement file in Video Overlay tab"
            )
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка чтения данных",
                f"Не удалось загрузить файл: {exc}",
            )

    def _pick_video_file(self) -> None:
        for bin_name in ("ffmpeg", "ffprobe"):
            try:
                resolve_ffmpeg_binary(bin_name)
            except FileNotFoundError as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    "FFmpeg не найден",
                    str(exc),
                )
                return

        fname, _ = QtWidgets.QFileDialog.getOpenFileName(  # noqa: PU001
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
            vinfo = build_video_info(v_path, crop_rect=None)
            self.session.video_info = vinfo
            log.bind(
                path=str(vinfo.path),
                input_width=vinfo.input_width,
                input_height=vinfo.input_height,
                fps_nominal=round(vinfo.fps_nominal, 3),
                real_fps=(
                    round(vinfo.real_fps, 3) if vinfo.real_fps is not None else None
                ),
                total_frames=vinfo.total_frames,
                duration_sec=round(vinfo.duration_sec, 3),
                codec_name=vinfo.codec_name,
                pix_fmt=vinfo.pix_fmt,
                timestamps_available=vinfo.timestamps_available,
                first_timestamp_sec=vinfo.first_timestamp_sec,
                last_timestamp_sec=vinfo.last_timestamp_sec,
            ).info("Loaded video stream in Video Overlay tab")
            self.video_preview.clear_export_pixmap()
            self.video_preview.set_video_geometry(w, h, crop_rect=None)
            self._refresh_timeline_and_aligned()
            self._refresh_info_panel()
            self._load_media_player_source(v_path)
        except Exception as exc:  # noqa: BLE001
            log.opt(exception=True).bind(path=str(v_path), error=repr(exc)).error(
                "Failed to open video file in Video Overlay tab"
            )
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка видеофайла",
                f"Не удалось открыть видео: {exc}",
            )

    def _load_media_player_source(self, video_path: Path) -> None:
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
        self._seek_on_load_pending = True
        self.media_player.setSource(
            QtCore.QUrl.fromLocalFile(str(video_path.resolve()))
        )
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._update_telemetry_and_cursor(0)

    def _active_timestamps_sec(self) -> np.ndarray | None:
        tl = self.pipeline.timeline
        if (
            tl is not None
            and tl.status is not OverlapStatus.NONE
            and len(tl.kept_timestamps_sec) > 0
        ):
            return tl.kept_timestamps_sec
        if (
            self.session.video_info is not None
            and len(self.session.video_info.timestamps_sec) > 0
        ):
            return self.session.video_info.timestamps_sec
        return None

    def _video_first_ts_sec(self) -> float:
        if (
            self.session.video_info is not None
            and self.session.video_info.first_timestamp_sec is not None
        ):
            return float(self.session.video_info.first_timestamp_sec)
        return 0.0

    def _frame_index_to_ms(self, frame_index: int) -> int:
        ts = self._active_timestamps_sec()
        if ts is not None and len(ts) > 0:
            clamped = max(0, min(len(ts) - 1, int(frame_index)))
            rel_s = max(0.0, float(ts[clamped]) - self._video_first_ts_sec())
            return round(rel_s * 1000.0)
        return round((max(0, frame_index) / max(1.0, self.current_fps)) * 1000.0)

    def _ms_to_frame_index(self, pos_ms: int) -> int:
        ts = self._active_timestamps_sec()
        if ts is not None and len(ts) > 0:
            abs_s = self._video_first_ts_sec() + (max(0, pos_ms) / 1000.0)
            idx = int(np.searchsorted(ts, abs_s, side="left"))
            return max(0, min(len(ts) - 1, idx))
        max_i = max(0, self.slider.maximum())
        idx = round((max(0, pos_ms) / 1000.0) * self.current_fps)
        return max(0, min(max_i, idx))

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if (
            status == QMediaPlayer.MediaStatus.LoadedMedia
            and self._seek_on_load_pending
        ):
            self._seek_on_load_pending = False
            self.media_player.pause()
            self.media_player.setPosition(self._frame_index_to_ms(0))
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.pause()

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setIcon(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.MediaPlaybackPause
                if is_playing
                else QtGui.QIcon.ThemeIcon.MediaPlaybackStart,
                QtWidgets.QStyle.StandardPixmap.SP_MediaPause
                if is_playing
                else QtWidgets.QStyle.StandardPixmap.SP_MediaPlay,
            )
        )
        self.btn_play.setText("Пауза" if is_playing else "Пуск")

    def _on_media_position_changed(self, pos_ms: int) -> None:
        if not self.slider.isEnabled():
            return
        ts = self._active_timestamps_sec()
        if (
            ts is not None
            and len(ts) > 0
            and self.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            max_ms = self._frame_index_to_ms(len(ts) - 1)
            if pos_ms >= max_ms:
                self.media_player.pause()
        idx = self._ms_to_frame_index(pos_ms)
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(idx)
            self.slider.blockSignals(False)
        self._update_telemetry_and_cursor(idx)

    def _on_media_error(self, error: QMediaPlayer.Error, error_str: str) -> None:
        log.bind(error=str(error), message=error_str).error(
            "QMediaPlayer playback error"
        )

    def _on_slider_changed(self, val: int) -> None:
        self.video_preview.clear_export_pixmap()
        self._update_telemetry_and_cursor(val)
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.pause()
        self.media_player.setPosition(self._frame_index_to_ms(val))

    def _step_frame(self, delta: int) -> None:
        self._stop_playback()
        if not self.slider.isEnabled():
            return
        new_idx = max(0, min(self.slider.maximum(), self.slider.value() + delta))
        self.slider.setValue(new_idx)

    def _toggle_playback(self) -> None:
        self.video_preview.clear_export_pixmap()
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            if self.slider.value() >= self.slider.maximum():
                self.slider.setValue(0)
            self._on_play_speed_changed()
            self.media_player.play()

    def _stop_playback(self) -> None:
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()

    def _on_play_speed_changed(self) -> None:
        mult = float(self.cb_play_speed.currentData() or 1.0)
        self.media_player.setPlaybackRate(mult)

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
        ts_arr = (
            self.session.video_info.timestamps_sec
            if self.session.video_info is not None
            else None
        )
        dlg = CropSelectionDialog(
            self.pipeline.video_path_input,
            initial_rect=self.pipeline.crop_rect,
            timestamps_sec=ts_arr,
            parent=self,
        )
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._apply_crop(dlg.get_crop_rect())

    def _apply_crop(self, rect: RectangleGeometry) -> None:
        self.pipeline.crop_rect = rect
        if self.session.video_info is not None:
            self.session.video_info = replace(self.session.video_info, crop_rect=rect)
            self._refresh_info_panel()
        self.video_preview.set_video_geometry(
            self.session.video_info.input_width if self.session.video_info else 1920,
            self.session.video_info.input_height if self.session.video_info else 1080,
            crop_rect=rect,
        )
        self.btn_reset_crop.setEnabled(True)
        if self.slider.isEnabled():
            self.media_player.setPosition(self._frame_index_to_ms(self.slider.value()))

    def _reset_crop(self) -> None:
        self.pipeline.crop_rect = None
        if self.session.video_info is not None:
            self.session.video_info = replace(self.session.video_info, crop_rect=None)
            self.video_preview.set_video_geometry(
                self.session.video_info.input_width,
                self.session.video_info.input_height,
                crop_rect=None,
            )
            self._refresh_info_panel()
        self.btn_reset_crop.setEnabled(False)
        if self.slider.isEnabled():
            self.media_player.setPosition(self._frame_index_to_ms(self.slider.value()))

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
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(  # noqa: PU001
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
            self.video_preview.show_export_pixmap(progress.frame.to_pixmap())

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
        self.video_preview.clear_export_pixmap()
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
        self.media_player.setSource(QtCore.QUrl())
        if self.pipeline.isRunning():
            self.pipeline.stop()
            self.pipeline.wait(5000)
        TempDirManager.cleanup()
