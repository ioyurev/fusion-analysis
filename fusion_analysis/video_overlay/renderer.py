from __future__ import annotations

import subprocess
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

import numpy as np
from loguru import logger as log
from PySide6 import QtCore, QtGui

from fusion_analysis.video_overlay.ffmpeg_pipe import (
    TempDirManager,
    VideoContext,
    build_codec_args,
)
from fusion_analysis.video_overlay.models import (
    BG_ALPHA,
    Alignment,
    OverlapStatus,
    ProcessProgress,
    ProcessResult,
    RectangleGeometry,
    TimelineSelection,
    VideoMeasurementData,
    ensure_even,
    get_graph_size,
    overlay_config,
)
from fusion_analysis.video_overlay.timeline import (
    AlignedData,
    build_vfr_setpts_script_content,
)


class FrameSize(NamedTuple):
    width: int
    height: int


class CVFrame:
    """Кадр видео в формате BGR888 с отрисовкой плашек и текста через QPainter."""

    def __init__(self, image: np.ndarray) -> None:
        self.image = np.ascontiguousarray(image, dtype=np.uint8)
        self._update_size()

    def _update_size(self) -> None:
        h, w = self.image.shape[:2]  # noqa: PU001
        self.size = FrameSize(int(w), int(h))

    def to_pixmap(self) -> QtGui.QPixmap:
        h, w = self.image.shape[:2]  # noqa: PU001
        stride = int(self.image.strides[0])  # noqa: MI001
        q_img = QtGui.QImage(
            self.image.data,
            w,
            h,
            stride,
            QtGui.QImage.Format.Format_BGR888,
        )
        return QtGui.QPixmap.fromImage(q_img.copy())

    def crop(self, x: int, y: int, w: int, h: int) -> None:
        self.image = np.ascontiguousarray(
            self.image[y : y + h, x : x + w].copy(), dtype=np.uint8
        )
        self._update_size()

    def crop_by_rect(self, rect: RectangleGeometry) -> None:
        h, w = self.image.shape[:2]  # noqa: PU001
        x = ensure_even(max(0, min(rect.x, w - 2)))
        y = ensure_even(max(0, min(rect.y, h - 2)))
        crop_w = ensure_even(max(10, min(rect.w, w - x)))
        crop_h = ensure_even(max(10, min(rect.h, h - y)))
        self.crop(x, y, crop_w, crop_h)

    def put_img(
        self,
        overlay_img: np.ndarray,
        x: int,
        y: int,
        align: Alignment = Alignment.TOP_LEFT,
    ) -> np.ndarray:
        bg_h, bg_w = self.image.shape[:2]  # noqa: PU001
        img_h, img_w = overlay_img.shape[:2]  # noqa: PU001

        if align is Alignment.TOP_RIGHT:
            x -= img_w
        elif align is Alignment.BOTTOM_LEFT:
            y -= img_h
        elif align is Alignment.BOTTOM_RIGHT:
            x -= img_w
            y -= img_h

        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + img_w, bg_w), min(y + img_h, bg_h)
        if x1 >= x2 or y1 >= y2:
            return self.image

        ix1, iy1 = x1 - x, y1 - y
        ix2, iy2 = ix1 + (x2 - x1), iy1 + (y2 - y1)
        cropped = overlay_img[iy1:iy2, ix1:ix2]
        roi = self.image[y1:y2, x1:x2]

        if cropped.shape[2] == 4:  # noqa: MI001
            alpha = cropped[:, :, 3:4].astype(np.float32) / 255.0
            color = cropped[:, :, :3].astype(np.float32)
        else:
            alpha = np.ones_like(roi[:, :, 0:1], dtype=np.float32)
            color = cropped.astype(np.float32)

        blended = color * alpha + roi.astype(np.float32) * (1.0 - alpha)
        self.image[y1:y2, x1:x2] = blended.astype(np.uint8)
        return self.image

    def put_text(
        self,
        text: str,
        xy: tuple[int, int],
        align: Alignment,
        small: bool = False,
    ) -> tuple[int, int, int, int]:
        px_size = (
            overlay_config.text.additional_size
            if small
            else overlay_config.text.main_size
        )
        pad = overlay_config.text.bg_padding
        h, w = self.image.shape[:2]  # noqa: PU001
        stride = int(self.image.strides[0])  # noqa: MI001

        q_img = QtGui.QImage(
            self.image.data,
            w,
            h,
            stride,
            QtGui.QImage.Format.Format_BGR888,
        )
        painter = QtGui.QPainter(q_img)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)

        font = QtGui.QFont("Segoe UI")
        font.setPixelSize(max(10, int(px_size)))
        painter.setFont(font)
        fm = QtGui.QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        ascent = fm.ascent()
        descent = fm.descent()

        x, y = xy
        if align is Alignment.TOP_LEFT:
            org_x, org_y = x, y + ascent
        elif align is Alignment.TOP_RIGHT:
            org_x, org_y = x - tw, y + ascent
        elif align is Alignment.BOTTOM_LEFT:
            org_x, org_y = x, y - descent
        elif align is Alignment.BOTTOM_RIGHT:
            org_x, org_y = x - tw, y - descent
        else:
            org_x, org_y = x, y + ascent

        x1 = max(0, org_x - pad)
        y1 = max(0, org_y - ascent - pad)
        x2 = min(w, org_x + tw + pad)
        y2 = min(h, org_y + descent + pad)

        if x2 > x1 and y2 > y1:
            painter.fillRect(
                x1,
                y1,
                x2 - x1,
                y2 - y1,
                QtGui.QColor(63, 63, 63, int(255 * BG_ALPHA)),
            )
        painter.setPen(QtGui.QColor(255, 255, 0))
        painter.drawText(org_x, org_y, text)
        painter.end()
        return (x1, y1, x2, y2)


class GraphOverlay:
    """Быстрый потокобезопасный рендерер скользящего графика скорости dT/dt на QPainter."""

    def __init__(
        self,
        data: np.ndarray,
        fps: float,
        width: int,
        height: int,
        time_window_sec: float = 30.0,
        timestamps: np.ndarray | None = None,
    ) -> None:
        self.data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
        self.fps = max(1.0, float(fps))
        self.time_window_sec = time_window_sec
        self.window_frames = int(time_window_sec * self.fps)
        self.width = width
        self.height = height

        if timestamps is not None and len(timestamps) > 0:
            first_ts, *_ = timestamps
            self.t_full = timestamps - float(first_ts)
        else:
            self.t_full = np.arange(len(data), dtype=float) / self.fps

    def get_frame_overlay(self, current_idx: int) -> np.ndarray:
        w, h = self.width, self.height
        img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(63, 63, 63, int(255 * BG_ALPHA)))

        painter = QtGui.QPainter(img)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)

        yellow = QtGui.QColor(255, 255, 0)
        font_px = max(10, int(overlay_config.text.additional_size * 0.55))
        font = QtGui.QFont("Segoe UI")
        font.setPixelSize(font_px)
        painter.setFont(font)

        left_m = int(w * 0.18)
        right_m = int(w * 0.95)
        top_m = int(h * 0.12)
        bot_m = int(h * 0.86)
        plot_w = max(10, right_m - left_m)
        plot_h = max(10, bot_m - top_m)

        painter.setPen(QtGui.QPen(yellow, 1.0))
        painter.drawRect(left_m, top_m, plot_w, plot_h)
        painter.drawText(left_m, max(font_px, top_m - 4), "dT/dt (°C/s)")
        painter.drawText(left_m + plot_w // 2 - 10, h - 4, "t(s)")

        cur_t = (
            float(self.t_full[current_idx])
            if current_idx < len(self.t_full)
            else current_idx / self.fps
        )
        x_min = 0.0 if cur_t <= self.time_window_sec else cur_t - self.time_window_sec
        x_max = max(cur_t, x_min + 0.1)

        start_idx = max(0, current_idx - self.window_frames)
        end_idx = min(len(self.data), current_idx + 1)
        vis_y = self.data[start_idx:end_idx]
        vis_t = self.t_full[start_idx:end_idx]
        if len(vis_y) > 0:
            y_min, y_max = float(vis_y.min()), float(vis_y.max())
            margin = (y_max - y_min) * 0.1 or 1.0
            y_min -= margin
            y_max += margin
        else:
            y_min, y_max = -1.0, 1.0

        painter.drawText(2, top_m + font_px, f"{y_max:.1f}")
        painter.drawText(2, bot_m, f"{y_min:.1f}")

        if len(vis_t) >= 2:
            xs = left_m + ((vis_t - x_min) / (x_max - x_min)) * plot_w
            ys = bot_m - ((vis_y - y_min) / (y_max - y_min)) * plot_h
            painter.setClipRect(left_m, top_m, plot_w, plot_h)
            painter.setPen(QtGui.QPen(yellow, float(overlay_config.graph.line_width)))
            poly = QtGui.QPolygonF(
                [QtCore.QPointF(float(px), float(py)) for px, py in zip(xs, ys)]
            )
            painter.drawPolyline(poly)
            painter.setClipping(False)

            last_x = float(xs[-1])  # noqa: MI001
            last_y = float(ys[-1])  # noqa: MI001
            r = max(3, int(overlay_config.graph.marker_size))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0)))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawEllipse(QtCore.QPointF(last_x, last_y), r, r)

        painter.end()
        ptr = img.constBits()
        return np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()


def make_frame(
    img: np.ndarray,
    crop_rect: RectangleGeometry | None,
    time_sec: float,
    emf: float,
    temp: float | None,
    temp_speed: float | None,
    graph_img: np.ndarray | None,
    operator_name: str,
    sample_name: str,
    add_text: str | None,
) -> CVFrame:
    cvframe = CVFrame(image=img)
    if crop_rect is not None:
        cvframe.crop_by_rect(crop_rect)

    if graph_img is not None and graph_img.ndim == 3:
        gh, gw = graph_img.shape[:2]  # noqa: PU001
        fh, fw = cvframe.image.shape[:2]  # noqa: PU001
        x_off = fw - gw
        y_off = overlay_config.text.margin_y
        if x_off >= 0 and y_off >= 0 and y_off + gh <= fh:
            cvframe.put_img(graph_img, x_off, y_off, align=Alignment.TOP_LEFT)

    mx = overlay_config.text.margin_x
    my = overlay_config.text.margin_y
    ls = overlay_config.text.line_spacing
    top_y = my

    if overlay_config.text.show_time:
        mins, secs = divmod(max(0.0, time_sec), 60.0)  # noqa: PU001
        _, _, _, bottom_y = cvframe.put_text(  # noqa: PU001
            f"t: {mins:02.0f}:{secs:04.1f}", (mx, top_y), Alignment.TOP_LEFT
        )
        top_y = bottom_y + ls

    if overlay_config.text.show_emf:
        _, _, _, bottom_y = cvframe.put_text(  # noqa: PU001
            f"E(мВ): {emf:.2f}", (mx, top_y), Alignment.TOP_LEFT
        )
        top_y = bottom_y + ls

    if overlay_config.text.show_temp and temp is not None:
        _, _, _, bottom_y = cvframe.put_text(  # noqa: PU001
            f"T(°C): {temp:.0f}", (mx, top_y), Alignment.TOP_LEFT
        )
        top_y = bottom_y + ls

    if overlay_config.text.show_speed and temp_speed is not None:
        cvframe.put_text(
            f"dT/dt(°C/с): {temp_speed:.2f}", (mx, top_y), Alignment.TOP_LEFT
        )

    bot_y = cvframe.size.height - my
    if add_text and overlay_config.additional_text_enabled:
        _, top_b, _, _ = cvframe.put_text(  # noqa: PU001
            add_text, (mx, bot_y), Alignment.BOTTOM_LEFT, small=True
        )
        bot_y = top_b - ls

    if overlay_config.text.show_operator and operator_name:
        _, top_b, _, _ = cvframe.put_text(  # noqa: PU001
            operator_name, (mx, bot_y), Alignment.BOTTOM_LEFT, small=True
        )
        bot_y = top_b - ls

    if overlay_config.text.show_sample and sample_name:
        cvframe.put_text(sample_name, (mx, bot_y), Alignment.BOTTOM_LEFT)

    return cvframe


class FrameRenderer:
    """Единый рендерер кадров для интерактивного превью и пакетного экспорта."""

    def __init__(
        self,
        video_ctx: VideoContext,
        data: VideoMeasurementData,
        timestamps: np.ndarray | None = None,
        crop_rect: RectangleGeometry | None = None,
        graph_enabled: bool = True,
    ) -> None:
        self.video_ctx = video_ctx
        self.data = data
        self.crop_rect = crop_rect

        if timestamps is None:
            duration = video_ctx.total_frames / max(1.0, video_ctx.fps)
            timestamps = np.linspace(0.0, duration, max(1, video_ctx.total_frames))

        self.aligned = AlignedData.from_data(timestamps, data)
        self.graph_renderer: GraphOverlay | None = None
        if graph_enabled and self.aligned.speed is not None:
            fw = crop_rect.w if crop_rect else video_ctx.width
            fh = crop_rect.h if crop_rect else video_ctx.height
            gw, gh = get_graph_size(fw, fh)  # noqa: PU001
            self.graph_renderer = GraphOverlay(
                data=self.aligned.speed,
                fps=video_ctx.fps,
                width=gw,
                height=gh,
                time_window_sec=overlay_config.graph.time_window,
                timestamps=self.aligned.timestamps,
            )

    def render_overlay(
        self, img: np.ndarray | None, frame_index: int
    ) -> CVFrame | None:
        if img is None:
            return None
        tel = self.aligned.at_index(frame_index)
        graph_img = (
            self.graph_renderer.get_frame_overlay(frame_index)
            if (self.graph_renderer and overlay_config.graph.enabled)
            else None
        )
        op_label = f"Оператор: {self.data.operator}" if self.data.operator else ""
        smp_label = f"Образец: {self.data.sample}" if self.data.sample else ""
        add_txt = (
            overlay_config.additional_text
            if overlay_config.additional_text_enabled
            else None
        )
        return make_frame(
            img=img,
            crop_rect=self.crop_rect,
            time_sec=float(self.aligned.timestamps[frame_index]),
            emf=tel.emf,
            temp=tel.temp,
            temp_speed=tel.speed,
            graph_img=graph_img,
            operator_name=op_label,
            sample_name=smp_label,
            add_text=add_txt,
        )


class CVProcessor(QtCore.QObject):
    progress_signal = QtCore.Signal(object)
    fps_signal = QtCore.Signal(float)

    def __init__(
        self,
        video_path: Path,
        data: VideoMeasurementData,
        path_output: Path,
        timeline: TimelineSelection,
        crop_rect: RectangleGeometry | None = None,
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.data = data
        self.path_output = path_output
        self.timeline = timeline
        self.crop_rect = crop_rect
        self.is_interrupted = False

    def stop(self) -> None:
        self.is_interrupted = True

    def run(self) -> None:
        video_ctx = VideoContext.open(self.video_path)
        renderer = FrameRenderer(
            video_ctx=video_ctx,
            data=self.data,
            timestamps=self.timeline.kept_timestamps_sec,
            crop_rect=self.crop_rect,
            graph_enabled=overlay_config.graph.enabled,
        )
        out_w = ensure_even(self.crop_rect.w if self.crop_rect else video_ctx.width)
        out_h = ensure_even(self.crop_rect.h if self.crop_rect else video_ctx.height)

        script_text = build_vfr_setpts_script_content(self.timeline.kept_timestamps_sec)
        script_file = (
            TempDirManager.get_temp_dir() / f"vfr_setpts_{uuid.uuid4().hex}.txt"
        )
        script_file.parent.mkdir(parents=True, exist_ok=True)
        script_file.write_text(script_text, encoding="utf-8")

        enc = overlay_config.video_encoding
        cmd = [
            "ffmpeg",
            "-y",
            "-threads",
            "1",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            f"{out_w}x{out_h}",
            "-pix_fmt",
            "bgr24",
            "-r",
            "1000",
            "-i",
            "-",
            "-filter_script:v",
            str(script_file),
            "-c:v",
            enc.codec,
            *build_codec_args(enc.codec, enc.crf, enc.preset),
            "-pix_fmt",
            enc.pix_fmt,
            "-fps_mode",
            "vfr",
            str(self.path_output),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        num_threads = max(1, enc.render_threads)
        batch_size = max(4, num_threads * 2)
        source_indices = self.timeline.source_frame_indices
        max_frames = len(source_indices)

        def _worker(pair: tuple[int, np.ndarray]) -> tuple[int, CVFrame | None]:
            idx, raw_frame = pair
            return idx, renderer.render_overlay(raw_frame, idx)

        try:
            with ThreadPoolExecutor(max_workers=num_threads) as pool:
                for b_start in range(0, max_frames, batch_size):
                    if self.is_interrupted:
                        break
                    b_end = min(b_start + batch_size, max_frames)
                    t0 = time.perf_counter()
                    raw_items: list[tuple[int, np.ndarray]] = []
                    for kept_i in range(b_start, b_end):
                        src_idx = int(source_indices[kept_i])
                        raw = video_ctx.read_frame(src_idx)
                        if raw is not None:
                            raw_items.append((kept_i, raw.copy()))
                    if not raw_items:
                        continue

                    results = sorted(
                        pool.map(_worker, raw_items),
                        key=lambda item: item[0],  # noqa: MI001
                    )
                    dt = time.perf_counter() - t0
                    if dt > 0:
                        self.fps_signal.emit(len(results) / dt)

                    for idx, frame in results:
                        if self.is_interrupted:
                            break
                        if frame is not None and proc.stdin is not None:
                            proc.stdin.write(frame.image.tobytes())
                            self.progress_signal.emit(
                                ProcessProgress(value=idx, frame=frame)
                            )
        finally:
            if proc.stdin is not None:
                proc.stdin.close()
            if self.is_interrupted:
                proc.terminate()
            proc.wait()
            script_file.unlink(missing_ok=True)
            video_ctx.close()


class VideoExportPipeline(QtCore.QThread):
    stage_progress = QtCore.Signal(object)
    stage_finished = QtCore.Signal(tuple)
    work_finished = QtCore.Signal(object)
    fps_updated = QtCore.Signal(float)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.data: VideoMeasurementData | None = None
        self.video_path_input: Path | None = None
        self.video_path_output: Path | None = None
        self.crop_rect: RectangleGeometry | None = None
        self.timeline: TimelineSelection | None = None
        self.cv_agent: CVProcessor | None = None

    def stop(self) -> None:
        self.requestInterruption()
        if self.cv_agent is not None:
            self.cv_agent.stop()

    def run(self) -> None:
        try:
            if (
                self.video_path_input is None
                or self.video_path_output is None
                or self.data is None
                or self.timeline is None
                or self.timeline.status is OverlapStatus.NONE
            ):
                raise ValueError(
                    "Не заданы входные данные или отсутствует пересечение шкал."
                )
            self.stage_finished.emit(
                (max(1, self.timeline.kept_frames - 1), "1/1", "frame")
            )
            self.cv_agent = CVProcessor(
                video_path=self.video_path_input,
                data=self.data,
                path_output=self.video_path_output,
                timeline=self.timeline,
                crop_rect=self.crop_rect,
            )
            self.cv_agent.progress_signal.connect(self.stage_progress.emit)
            self.cv_agent.fps_signal.connect(self.fps_updated.emit)
            self.cv_agent.run()
            self.work_finished.emit(ProcessResult(is_success=True))
        except Exception as exc:  # noqa: BLE001
            log.bind(error=str(exc)).error("Video export pipeline failed")
            self.work_finished.emit(
                ProcessResult(is_success=False, traceback_msg=traceback.format_exc())
            )
