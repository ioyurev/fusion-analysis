from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import ffmpeg  # type: ignore[import-untyped]
import numpy as np
from loguru import logger as log

from fusion_analysis.video_overlay.models import RectangleGeometry, VideoInfo
from fusion_analysis.video_overlay.timeline import compute_real_fps


@lru_cache(maxsize=4)
def resolve_ffmpeg_binary(name: str = "ffmpeg") -> str:
    """Ищет бинарник ffmpeg/ffprobe сначала рядом с программой, затем в системном PATH."""
    exe_name = f"{name}.exe" if sys.platform.startswith("win") else name
    exe_dir = Path(sys.executable).resolve().parent
    candidates = [
        exe_dir / exe_name,
        exe_dir / "ffmpeg" / exe_name,
        Path.cwd() / exe_name,
        Path.cwd() / "ffmpeg" / exe_name,
    ]
    for cand in candidates:
        if cand.is_file():
            log.bind(binary=name, path=str(cand), source="bundled").info(
                "Resolved bundled FFmpeg binary"
            )
            return str(cand)
    from_path = shutil.which(name)
    if from_path:
        log.bind(binary=name, path=from_path, source="PATH").info(
            "Resolved system FFmpeg binary"
        )
        return from_path
    raise FileNotFoundError(
        f"Исполняемый файл '{exe_name}' не найден ни в папке программы, ни в PATH."
    )


def build_codec_args(codec: str, crf: int, preset: str) -> list[str]:
    if codec == "libx265":
        if crf == 0:
            return ["-x265-params", "lossless=1"]
        return ["-crf", str(crf), "-preset", preset]
    if codec == "libx264":
        return ["-crf", str(crf), "-preset", preset]
    if codec in ("h264_amf", "hevc_amf"):
        return [
            "-usage",
            "transcoding",
            "-quality",
            "speed",
            "-rc",
            "cqp",
            "-qp",
            str(crf),
        ]
    if codec in ("h264_nvenc", "hevc_nvenc"):
        return ["-rc", "constqp", "-qp", str(crf)]
    if codec in ("h264_qsv", "hevc_qsv"):
        return ["-global_quality", str(crf)]
    if codec == "mpeg4":
        return ["-q:v", str(crf if crf > 0 else 1)]
    return []


def _extract_pts_ms(packets: list[dict[str, Any]]) -> list[int]:
    pts: list[int] = []
    for packet in packets:
        time_str = packet.get("pts_time") or packet.get("dts_time")
        if time_str is not None:
            try:
                pts.append(int(Decimal(str(time_str)) * 1000))
            except (ValueError, ArithmeticError):
                continue
    pts.sort()
    return pts


class FFmpeg:
    def get_video_stream_info(self, video_path: Path | str) -> dict[str, Any]:
        ffprobe_bin = resolve_ffmpeg_binary("ffprobe")
        probe = ffmpeg.probe(str(video_path), cmd=ffprobe_bin)
        streams: list[dict[str, Any]] = probe.get("streams", [])
        return next(s for s in streams if s.get("codec_type") == "video")

    def get_resolution(self, video_path: Path | str) -> tuple[int, int]:
        stream = self.get_video_stream_info(video_path)
        return int(stream["width"]), int(stream["height"])

    def get_timestamps(self, video_path: Path, index: int = 0) -> list[int]:
        resolved = video_path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Видеофайл не найден: {resolved}")

        ffprobe_bin = resolve_ffmpeg_binary("ffprobe")
        proc = subprocess.Popen(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-select_streams",
                str(index),
                "-show_entries",
                "packet=pts_time,dts_time",
                "-of",
                "json",
                str(resolved),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()  # noqa: PU001
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="replace"))
        probe: dict[str, Any] = json.loads(stdout.decode("utf-8"))
        return _extract_pts_ms(probe.get("packets", []))


def build_video_info(
    video_path: Path,
    crop_rect: RectangleGeometry | None = None,
) -> VideoInfo:
    ff = FFmpeg()
    timestamps = np.array(ff.get_timestamps(video_path), dtype=float) / 1000.0

    cap = cv2.VideoCapture(str(video_path))
    fps_nominal = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    opencv_total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    stream = ff.get_video_stream_info(video_path)
    width = int(stream["width"])
    height = int(stream["height"])

    if len(timestamps) > 0:
        first_ts, *_, last_ts = timestamps
        f_val: float | None = float(first_ts)
        l_val: float | None = float(last_ts)
        total_frames = len(timestamps)
        duration_sec = float(last_ts - first_ts) if len(timestamps) > 1 else 0.0
        real_fps = compute_real_fps(timestamps)
    else:
        f_val = None
        l_val = None
        total_frames = max(0, opencv_total_frames)
        duration_sec = total_frames / fps_nominal if fps_nominal > 0 else 0.0
        real_fps = None

    return VideoInfo(
        path=video_path,
        input_width=width,
        input_height=height,
        fps_nominal=fps_nominal,
        real_fps=real_fps,
        total_frames=total_frames,
        duration_sec=duration_sec,
        timestamps_source="ffprobe packet timestamps",
        timestamps_available=len(timestamps) > 0,
        first_timestamp_sec=f_val,
        last_timestamp_sec=l_val,
        crop_rect=crop_rect,
        codec_name=stream.get("codec_name"),
        pix_fmt=stream.get("pix_fmt"),
        timestamps_sec=timestamps,
    )


@dataclass
class VideoContext:
    """Контекст чтения кадров из видеофайла с кэшированием и быстрым seek в ОЗУ для .asf."""

    cap: cv2.VideoCapture
    fps: float
    total_frames: int
    width: int
    height: int
    path: Path = field(default_factory=Path)
    timestamps_sec: np.ndarray | None = None
    _last_index: int = field(default=-1, init=False)
    _last_img: np.ndarray | None = field(default=None, init=False)

    @classmethod
    def open(
        cls,
        path: str | Path,
        timestamps_sec: np.ndarray | None = None,
    ) -> VideoContext:
        p = Path(path)
        cap = cv2.VideoCapture(str(p))
        if not cap.isOpened():
            raise RuntimeError(f"Не удалось открыть видеофайл: {p}")
        fps_val = float(cap.get(cv2.CAP_PROP_FPS))
        return cls(
            cap=cap,
            fps=fps_val if fps_val > 0 else 30.0,
            total_frames=max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))),
            width=max(0, int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))),
            height=max(0, int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))),
            path=p,
            timestamps_sec=timestamps_sec,
        )

    def _seek_frame_in_ram_pipe(self, index: int) -> np.ndarray | None:
        """Декодирует одиночный кадр по времени напрямую в ОЗУ через пайп ffmpeg без создания файлов на диске."""
        if self.timestamps_sec is not None and 0 <= index < len(self.timestamps_sec):
            t0 = float(self.timestamps_sec[0])  # noqa: MI001
            t_sec = max(0.0, float(self.timestamps_sec[index]) - t0)
        else:
            t_sec = max(0.0, index / max(1.0, self.fps))
        expected_bytes = self.width * self.height * 3
        if expected_bytes <= 0 or not self.path.is_file():
            return None
        try:
            ffmpeg_bin = resolve_ffmpeg_binary("ffmpeg")
            proc = subprocess.run(
                [
                    ffmpeg_bin,
                    "-v",
                    "error",
                    "-ss",
                    f"{t_sec:.3f}",
                    "-i",
                    str(self.path),
                    "-frames:v",
                    "1",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "bgr24",
                    "pipe:1",
                ],
                capture_output=True,
                check=False,
            )
            if len(proc.stdout) == expected_bytes:
                frame = (
                    np.frombuffer(proc.stdout, dtype=np.uint8)
                    .reshape((self.height, self.width, 3))
                    .copy()
                )
                self._last_index = index
                self._last_img = frame
                return frame
        except (OSError, subprocess.SubprocessError) as exc:
            log.bind(index=index, error=repr(exc)).warning(
                "RAM pipe frame seek failed, falling back to OpenCV"
            )
        return None

    def read_frame(self, index: int) -> np.ndarray | None:
        if index == self._last_index and self._last_img is not None:
            return self._last_img

        diff = index - self._last_index
        if 0 < diff <= 45:
            img = None
            for _ in range(diff):
                ret, frame = self.cap.read()  # noqa: PU001
                if not ret:
                    self._last_index = -1
                    self._last_img = None
                    return None
                img = frame
            if img is not None:
                self._last_index = index
                self._last_img = img
                return img

        if index > 0 and self.path.suffix.lower() in (".asf", ".wmv"):
            piped = self._seek_frame_in_ram_pipe(index)
            if piped is not None:
                return piped

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ret, img = self.cap.read()  # noqa: PU001
        if ret and img is not None:
            self._last_index = index
            self._last_img = img
            return img
        return None

    def close(self) -> None:
        if self.cap:
            self.cap.release()
            self._last_img = None


@lru_cache(maxsize=32)
def is_codec_working(codec_name: str) -> bool:
    try:
        ffmpeg_bin = resolve_ffmpeg_binary("ffmpeg")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            "640x480",
            "-pix_fmt",
            "bgr24",
            "-r",
            "10",
            "-i",
            "-",
            "-c:v",
            codec_name,
            *build_codec_args(codec_name, 23, "medium"),
            "-pix_fmt",
            "yuv420p",
            "-f",
            "null",
            "-",
        ]
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        raw_frame = b"\x00" * (640 * 480 * 3)
        p.communicate(input=raw_frame * 5, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return False
    else:
        return p.returncode == 0


@lru_cache(maxsize=1)
def get_available_codecs() -> list[tuple[str, str]]:
    all_codecs = [
        ("H.264 / AVC (libx264) - CPU", "libx264"),
        ("H.265 / HEVC (libx265) - CPU", "libx265"),
        ("NVIDIA NVENC H.264 - GPU", "h264_nvenc"),
        ("NVIDIA NVENC HEVC - GPU", "hevc_nvenc"),
        ("Intel QuickSync H.264 - GPU", "h264_qsv"),
        ("Intel QuickSync HEVC - GPU", "hevc_qsv"),
        ("AMD AMF H.264 - GPU", "h264_amf"),
        ("AMD AMF HEVC - GPU", "hevc_amf"),
        ("MPEG-4 (mpeg4)", "mpeg4"),
    ]
    working = [(label, c) for label, c in all_codecs if is_codec_working(c)]
    return working or [("H.264 (libx264)", "libx264")]


class TempDirManager:
    _temp_dir: Path | None = None
    _lock = threading.Lock()

    @classmethod
    def get_temp_dir(cls) -> Path:
        with cls._lock:
            if cls._temp_dir is None:
                cls._temp_dir = Path(tempfile.mkdtemp())
            return cls._temp_dir

    @classmethod
    def cleanup(cls) -> None:
        with cls._lock:
            if cls._temp_dir is not None and cls._temp_dir.exists():
                shutil.rmtree(cls._temp_dir, ignore_errors=True)
            cls._temp_dir = None
