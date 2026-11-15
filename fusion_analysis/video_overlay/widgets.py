from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from fusion_analysis.video_overlay.ffmpeg_pipe import (
    VideoContext,
    get_available_codecs,
)
from fusion_analysis.video_overlay.models import (
    AlignedInfo,
    MeasurementSummaryInfo,
    OverlapStatus,
    RectangleGeometry,
    TimelineSelection,
    VideoInfo,
    overlay_config,
)
from fusion_analysis.video_overlay.renderer import CVFrame
from fusion_analysis.video_overlay.timeline import AlignedData


class AspectRatioLabel(QtWidgets.QLabel):
    """Виджет предпросмотра кадра с сохранением пропорций видео."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._aspect_ratio: float = 16.0 / 9.0
        self._original_pixmap: QtGui.QPixmap | None = None
        self.setMinimumSize(200, 120)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

    def set_aspect_ratio(self, width: int, height: int) -> None:
        if height > 0:
            self._aspect_ratio = width / height
        self.updateGeometry()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        if self._aspect_ratio > 0:
            return int(width / self._aspect_ratio)
        return super().heightForWidth(width)

    def sizeHint(self) -> QtCore.QSize:
        w = self.width()
        return QtCore.QSize(w, self.heightForWidth(w))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def setPixmap(self, pixmap: QtGui.QPixmap | QtGui.QImage) -> None:  # type: ignore[override]
        if isinstance(pixmap, QtGui.QImage):
            pixmap = QtGui.QPixmap.fromImage(pixmap)
        self._original_pixmap = pixmap
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self) -> None:
        if self._original_pixmap is None:
            return
        scaled = self._original_pixmap.scaled(
            self.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        super().setPixmap(scaled)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)


class InfoPanel(QtWidgets.QGroupBox):
    def __init__(
        self,
        title: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.warning_label = QtWidgets.QLabel()
        self.warning_label.setStyleSheet("color: #cc7700; font-weight: bold;")
        self.warning_label.setWordWrap(True)
        self.warning_label.setMaximumHeight(80)
        self.warning_label.hide()
        layout.addWidget(self.warning_label)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self.content = QtWidgets.QWidget()
        self.form = QtWidgets.QFormLayout(self.content)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(3)
        scroll.setWidget(self.content)
        layout.addWidget(scroll)

    def set_warning(self, text: str | None) -> None:
        if text:
            self.warning_label.setText(f"⚠ {text}")
            self.warning_label.show()
        else:
            self.warning_label.hide()

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        for key, value in rows:
            val_label = QtWidgets.QLabel(value)
            val_label.setWordWrap(True)
            val_label.setTextInteractionFlags(
                QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.form.addRow(key, val_label)


class SessionInfoWidget(QtWidgets.QWidget):
    """Трёхпанельная сводка состояния сессии видео-оверлея."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.panel_measurement = InfoPanel("Данные измерения")
        self.panel_video = InfoPanel("Видеопоток")
        self.panel_aligned = InfoPanel("Синхронизация VFR")

        layout.addWidget(self.panel_measurement, 1)
        layout.addWidget(self.panel_video, 1)
        layout.addWidget(self.panel_aligned, 1)

    def set_measurement_info(self, info: MeasurementSummaryInfo | None) -> None:
        if info is None:
            self.panel_measurement.set_rows([("Статус", "Данные не загружены")])
            self.panel_measurement.set_warning(None)
            return
        self.panel_measurement.set_warning(None)
        self.panel_measurement.set_rows(
            [
                ("Формат", f"{info.source_format} (v{info.version})"),
                ("Файл", str(info.path.name)),
                ("Образец", info.sample or "—"),
                ("Оператор", info.operator or "—"),
                ("Точек", str(info.points)),
                (
                    "Диапазон t (мин)",
                    f"{info.t_min_sec / 60.0:.2f} — {info.t_max_sec / 60.0:.2f}",
                ),
                ("Длительность (мин)", f"{info.duration_sec / 60.0:.2f}"),
                (
                    "Диапазон ЭДС (мВ)",
                    "—"
                    if info.emf_min is None
                    else f"{info.emf_min:.3f} — {info.emf_max:.3f}",
                ),
                (
                    "Диапазон T (°C)",
                    "—"
                    if info.temp_min is None
                    else f"{info.temp_min:.1f} — {info.temp_max:.1f}",
                ),
            ]
        )

    def set_video_info(self, info: VideoInfo | None) -> None:
        if info is None:
            self.panel_video.set_rows([("Статус", "Видео не загружено")])
            self.panel_video.set_warning(None)
            return
        crop_str = (
            f"{info.crop_rect.x}, {info.crop_rect.y}, {info.crop_rect.w}×{info.crop_rect.h}"
            if info.crop_rect
            else "—"
        )
        real_fps = "—" if info.real_fps is None else f"{info.real_fps:.2f}"
        rows = [
            ("Файл", str(info.path.name)),
            ("Входной размер", f"{info.input_width} × {info.input_height}"),
            ("Выходной размер", f"{info.output_width} × {info.output_height}"),
            ("Кадрирование", crop_str),
            ("Номинальный FPS", f"{info.fps_nominal:.2f}"),
            ("Реальный FPS (VFR)", real_fps),
            ("Всего кадров", str(info.total_frames)),
            ("Длительность (с)", f"{info.duration_sec:.2f}"),
            ("Кодек", info.codec_name or "—"),
        ]
        if info.kept_frames is not None:
            rows.extend(
                [
                    ("Кадров в пересечении", str(info.kept_frames)),
                    ("Обрезано в начале", str(info.trimmed_start_frames)),
                    ("Обрезано в конце", str(info.trimmed_end_frames)),
                ]
            )
        self.panel_video.set_warning(None)
        self.panel_video.set_rows(rows)

    def set_aligned_info(self, info: AlignedInfo | None) -> None:
        if info is None:
            self.panel_aligned.set_rows([("Статус", "Ожидание данных и видео")])
            self.panel_aligned.set_warning(None)
            return
        if info.overlap_status is OverlapStatus.NONE:
            self.panel_aligned.set_warning(
                info.error_message or "Нет пересечения по времени!"
            )
        elif info.overlap_status is OverlapStatus.PARTIAL:
            parts: list[str] = []
            if info.video_trimmed_at_start:
                parts.append(
                    f"Обрезка видео в начале ({info.trimmed_start_frames} кадр.)"
                )
            if info.video_trimmed_at_end:
                parts.append(f"Обрезка видео в конце ({info.trimmed_end_frames} кадр.)")
            self.panel_aligned.set_warning("\n".join(parts) if parts else None)
        else:
            self.panel_aligned.set_warning(None)

        fps_str = "—" if info.real_fps is None else f"{info.real_fps:.2f}"
        self.panel_aligned.set_rows(
            [
                ("Пересечение", str(info.overlap_status)),
                ("Сопоставлено кадров", str(info.points)),
                ("Интервал (с)", f"{info.t_min_sec:.2f} — {info.t_max_sec:.2f}"),
                ("Реальный FPS", fps_str),
                ("Температура", "Да" if info.temp_available else "Нет"),
                ("Скорость dT/dt", "Да" if info.speed_available else "Нет"),
            ]
        )


class LiveSyncPlotWidget(QtWidgets.QWidget):
    """Встроенный график термограммы на PyQtGraph с бегущим маркером кадра."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.aligned: AlignedData | None = None
        self.current_idx: int = 0
        self._x_arr: np.ndarray = np.array([], dtype=float)
        self._y_arr: np.ndarray = np.array([], dtype=float)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(QtWidgets.QLabel("График синхронизации:"))
        self.cb_mode = QtWidgets.QComboBox()
        self.cb_mode.addItems(
            [
                "Температура T (°C)",
                "Скорость нагрева dT/dt (°C/с)",
                "Сигнал ЭДС (мВ)",
            ]
        )
        self.cb_mode.currentIndexChanged.connect(self._replot_curve)
        top_row.addWidget(self.cb_mode, 1)
        self.lbl_coords = QtWidgets.QLabel("t=—, y=—")
        self.lbl_coords.setStyleSheet("font-family: Consolas, monospace;")
        top_row.addWidget(self.lbl_coords)
        layout.addLayout(top_row)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumHeight(160)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel("bottom", "Время, мин")
        self.curve_line = self.plot_widget.plot(
            [], [], pen=pg.mkPen("#0284C7", width=1.8)
        )
        self.cursor_vline = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            pen=pg.mkPen("#EF4444", width=1.4, style=QtCore.Qt.PenStyle.DashLine),
        )
        self.plot_widget.addItem(self.cursor_vline)
        self.cursor_dot = pg.ScatterPlotItem(
            size=8, brush=pg.mkBrush("#EF4444"), pen=pg.mkPen(None)
        )
        self.plot_widget.addItem(self.cursor_dot)
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)
        layout.addWidget(self.plot_widget, 1)

        style_hints = QtGui.QGuiApplication.styleHints()
        style_hints.colorSchemeChanged.connect(self._apply_theme)
        self._apply_theme(style_hints.colorScheme())

    def _apply_theme(self, scheme: QtCore.Qt.ColorScheme) -> None:
        is_dark = scheme == QtCore.Qt.ColorScheme.Dark
        self.plot_widget.setBackground("#0F172A" if is_dark else "#FFFFFF")
        fg = "#CBD5E1" if is_dark else "#1E293B"
        p_item = self.plot_widget.getPlotItem()
        if p_item is not None:
            for ax_name in ("bottom", "left"):
                ax = p_item.getAxis(ax_name)
                ax.setPen(fg)
                ax.setTextPen(fg)

    def set_aligned_data(self, aligned: AlignedData | None) -> None:
        self.aligned = aligned
        self.current_idx = 0
        self._replot_curve()

    def _replot_curve(self) -> None:
        if self.aligned is None or len(self.aligned.timestamps) == 0:
            self._x_arr = np.array([], dtype=float)
            self._y_arr = np.array([], dtype=float)
            self.curve_line.setData([], [])
            self.cursor_dot.setData([], [])
            return

        self._x_arr = self.aligned.timestamps / 60.0
        mode_idx = self.cb_mode.currentIndex()
        if mode_idx == 0 and self.aligned.temp is not None:
            self._y_arr = self.aligned.temp
            ylabel = "T, °C"
        elif mode_idx == 1 and self.aligned.speed is not None:
            self._y_arr = self.aligned.speed
            ylabel = "dT/dt, °C/с"
        else:
            self._y_arr = self.aligned.emf
            ylabel = "ЭДС, мВ"

        self.plot_widget.setLabel("left", ylabel)
        self.curve_line.setData(self._x_arr, self._y_arr, skipFiniteCheck=True)
        self.plot_widget.enableAutoRange()
        self.set_cursor_index(self.current_idx)

    def set_cursor_index(self, idx: int) -> None:
        self.current_idx = idx
        if len(self._x_arr) == 0 or idx < 0 or idx >= len(self._x_arr):
            return
        cur_x = float(self._x_arr[idx])
        cur_y = float(self._y_arr[idx])
        self.cursor_vline.setPos(cur_x)
        self.cursor_dot.setData([cur_x], [cur_y])

    def _on_mouse_moved(self, scene_pos: QtCore.QPointF) -> None:
        p_item = self.plot_widget.getPlotItem()
        if p_item is not None and p_item.vb.sceneBoundingRect().contains(scene_pos):
            pt = p_item.vb.mapSceneToView(scene_pos)
            self.lbl_coords.setText(f"t={pt.x():.2f} мин, y={pt.y():.2f}")


class CropSelectionDialog(QtWidgets.QDialog):
    """Диалог выбора области кадрирования видео с предпросмотром через OpenCV."""

    def __init__(
        self,
        video_path: Path,
        initial_rect: RectangleGeometry | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Кадрирование видео")
        self.resize(760, 560)
        self.video_ctx = VideoContext.open(video_path)
        vw = max(20, self.video_ctx.width)
        vh = max(20, self.video_ctx.height)

        default_rect = initial_rect or RectangleGeometry(
            max(0, (vw - vh) // 2), 0, min(vw, vh), vh
        ).safe_bound(vw, vh)

        layout = QtWidgets.QVBoxLayout(self)
        self.preview_lbl = AspectRatioLabel()
        self.preview_lbl.set_aspect_ratio(vw, vh)
        layout.addWidget(self.preview_lbl, 1)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, max(0, self.video_ctx.total_frames - 1))
        self.slider.valueChanged.connect(self._render_preview)
        layout.addWidget(self.slider)

        spin_row = QtWidgets.QHBoxLayout()
        self.sb_x = QtWidgets.QSpinBox()
        self.sb_y = QtWidgets.QSpinBox()
        self.sb_w = QtWidgets.QSpinBox()
        self.sb_h = QtWidgets.QSpinBox()
        for sb, max_v, init_v, min_v in (
            (self.sb_x, vw - 10, default_rect.x, 0),
            (self.sb_y, vh - 10, default_rect.y, 0),
            (self.sb_w, vw, default_rect.w, 10),
            (self.sb_h, vh, default_rect.h, 10),
        ):
            sb.setRange(min_v, max(min_v, max_v))
            sb.setValue(init_v)
            sb.valueChanged.connect(self._render_preview)

        for lbl_txt, sb in (
            ("X:", self.sb_x),
            ("Y:", self.sb_y),
            ("Ширина W:", self.sb_w),
            ("Высота H:", self.sb_h),
        ):
            spin_row.addWidget(QtWidgets.QLabel(lbl_txt))
            spin_row.addWidget(sb)
        layout.addLayout(spin_row)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self._render_preview()

    def get_crop_rect(self) -> RectangleGeometry:
        return RectangleGeometry(
            int(self.sb_x.value()),
            int(self.sb_y.value()),
            int(self.sb_w.value()),
            int(self.sb_h.value()),
        ).safe_bound(self.video_ctx.width, self.video_ctx.height)

    def _render_preview(self) -> None:
        raw = self.video_ctx.read_frame(int(self.slider.value()))
        if raw is None:
            return
        vis = raw.copy()
        r = self.get_crop_rect()
        cv2.rectangle(vis, (r.x, r.y), (r.x + r.w, r.y + r.h), (0, 255, 0), 3)
        self.preview_lbl.setPixmap(CVFrame(vis).to_pixmap())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.video_ctx.close()
        super().closeEvent(event)


class OverlaySettingsDialog(QtWidgets.QDialog):
    """Окно настройки элементов видео-оверлея и параметров кодирования FFmpeg."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки видео-оверлея и кодирования")
        self.resize(400, 480)
        layout = QtWidgets.QVBoxLayout(self)

        gb_text = QtWidgets.QGroupBox("Отображаемые поля телеметрии")
        lt_text = QtWidgets.QVBoxLayout(gb_text)
        self.cb_time = QtWidgets.QCheckBox("Время t (с)")
        self.cb_time.setChecked(overlay_config.text.show_time)
        self.cb_emf = QtWidgets.QCheckBox("ЭДС термопары (мВ)")
        self.cb_emf.setChecked(overlay_config.text.show_emf)
        self.cb_temp = QtWidgets.QCheckBox("Температура T (°C)")
        self.cb_temp.setChecked(overlay_config.text.show_temp)
        self.cb_speed = QtWidgets.QCheckBox("Скорость нагрева dT/dt (°C/с)")
        self.cb_speed.setChecked(overlay_config.text.show_speed)
        self.cb_op = QtWidgets.QCheckBox("Имя оператора")
        self.cb_op.setChecked(overlay_config.text.show_operator)
        self.cb_smp = QtWidgets.QCheckBox("Название образца")
        self.cb_smp.setChecked(overlay_config.text.show_sample)
        self.cb_graph = QtWidgets.QCheckBox("Скользящий график скорости dT/dt")
        self.cb_graph.setChecked(overlay_config.graph.enabled)
        self.cb_add = QtWidgets.QCheckBox("Дополнительный текст:")
        self.cb_add.setChecked(overlay_config.additional_text_enabled)
        self.le_add = QtWidgets.QLineEdit(overlay_config.additional_text)

        for w in (
            self.cb_time,
            self.cb_emf,
            self.cb_temp,
            self.cb_speed,
            self.cb_op,
            self.cb_smp,
            self.cb_graph,
            self.cb_add,
            self.le_add,
        ):
            lt_text.addWidget(w)
        layout.addWidget(gb_text)

        gb_enc = QtWidgets.QGroupBox("Кодирование видео (FFmpeg)")
        form_enc = QtWidgets.QFormLayout(gb_enc)
        self.cb_codec = QtWidgets.QComboBox()
        for label, codec_id in get_available_codecs():
            self.cb_codec.addItem(label, codec_id)
        idx_c = self.cb_codec.findData(overlay_config.video_encoding.codec)
        if idx_c >= 0:
            self.cb_codec.setCurrentIndex(idx_c)

        self.sb_crf = QtWidgets.QSpinBox()
        self.sb_crf.setRange(0, 28)
        self.sb_crf.setValue(overlay_config.video_encoding.crf)

        self.cb_preset = QtWidgets.QComboBox()
        self.cb_preset.addItems(["fast", "medium", "slow"])
        self.cb_preset.setCurrentText(overlay_config.video_encoding.preset)

        self.sb_threads = QtWidgets.QSpinBox()
        self.sb_threads.setRange(1, max(4, (os.cpu_count() or 4) * 2))
        self.sb_threads.setValue(overlay_config.video_encoding.render_threads)

        form_enc.addRow("Кодек:", self.cb_codec)
        form_enc.addRow("Качество CRF (0..28):", self.sb_crf)
        form_enc.addRow("Пресет скорости:", self.cb_preset)
        form_enc.addRow("Потоков рендеринга:", self.sb_threads)
        layout.addWidget(gb_enc)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self) -> None:
        overlay_config.text.show_time = self.cb_time.isChecked()
        overlay_config.text.show_emf = self.cb_emf.isChecked()
        overlay_config.text.show_temp = self.cb_temp.isChecked()
        overlay_config.text.show_speed = self.cb_speed.isChecked()
        overlay_config.text.show_operator = self.cb_op.isChecked()
        overlay_config.text.show_sample = self.cb_smp.isChecked()
        overlay_config.graph.enabled = self.cb_graph.isChecked()
        overlay_config.additional_text_enabled = self.cb_add.isChecked()
        overlay_config.additional_text = self.le_add.text().strip()
        overlay_config.video_encoding.codec = str(
            self.cb_codec.currentData() or "libx264"
        )
        overlay_config.video_encoding.crf = int(self.sb_crf.value())
        overlay_config.video_encoding.preset = self.cb_preset.currentText()
        overlay_config.video_encoding.render_threads = int(self.sb_threads.value())
        overlay_config.save()
        self.accept()


class PreviewWorker(QtCore.QObject):
    """Быстрый фоновый декодер чистых видеокадров для нативного плеера (без выжигания оверлея)."""

    frame_ready = QtCore.Signal(object, int, float)

    def __init__(self, video_path: str) -> None:
        super().__init__()
        self.video_path = video_path
        self.video_ctx: VideoContext | None = None
        self.latest_requested_index: int = -1

    @QtCore.Slot()
    def init_video(self) -> None:
        self.video_ctx = VideoContext.open(self.video_path)

    @QtCore.Slot(int, object, object)
    def request_frame(
        self,
        frame_index: int,
        crop_rect: RectangleGeometry | None,
        timeline: TimelineSelection | None,
    ) -> None:
        self.latest_requested_index = frame_index
        if self.video_ctx is None:
            return

        if timeline is not None and timeline.status is not OverlapStatus.NONE:
            if frame_index < 0 or frame_index >= len(timeline.source_frame_indices):
                return
            source_idx = int(timeline.source_frame_indices[frame_index])
            time_sec = float(timeline.kept_timestamps_sec[frame_index])
        else:
            if frame_index < 0 or frame_index >= self.video_ctx.total_frames:
                return
            source_idx = frame_index
            time_sec = frame_index / max(1.0, self.video_ctx.fps)

        img = self.video_ctx.read_frame(source_idx)
        if img is None:
            return
        cv_frame = CVFrame(img)
        if crop_rect is not None:
            cv_frame.crop_by_rect(crop_rect)
        if frame_index == self.latest_requested_index:
            self.frame_ready.emit(cv_frame.to_pixmap(), frame_index, time_sec)

    @QtCore.Slot()
    def cleanup(self) -> None:
        if self.video_ctx is not None:
            self.video_ctx.close()
