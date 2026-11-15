from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from pathlib import Path
from typing import Any, Final, NamedTuple

import numpy as np
import xlsxwriter
from fusion_common import (
    MeasurementRecord,
    get_appdata_path,
)
from loguru import logger as log
from pydantic import BaseModel, Field

from fusion_analysis.helpers import calculate_speed
from fusion_analysis.importers import load_measurement

TEXT_COLOR_BGR: Final[tuple[int, int, int]] = (0, 255, 255)
BG_COLOR_BGR: Final[tuple[int, int, int]] = (63, 63, 63)
BG_ALPHA: Final[float] = 0.8


def ensure_even(value: int) -> int:
    return value & ~1


def get_graph_size(frame_width: int, frame_height: int) -> tuple[int, int]:
    size = max(200, 3 * min(frame_width, frame_height) // 8)
    return size, size


class Alignment(Enum):
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()
    CENTER = auto()


class OverlapStatus(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class RectangleGeometry(NamedTuple):
    x: int
    y: int
    w: int
    h: int

    def safe_bound(self, max_width: int, max_height: int) -> RectangleGeometry:
        min_dim = 10
        x = ensure_even(max(0, min(self.x, max_width - min_dim)))
        y = ensure_even(max(0, min(self.y, max_height - min_dim)))
        w = ensure_even(max(min_dim, min(max_width - x, self.w)))
        h = ensure_even(max(min_dim, min(max_height - y, self.h)))
        return RectangleGeometry(x, y, w, h)


class GraphOverlaySettings(BaseModel):
    enabled: bool = True
    time_window: float = 30.0
    line_width: float = 1.5
    marker_size: int = 5
    speed_smoothing_window: int = 30
    temp_smoothing_window: int = 15


class TextOverlaySettings(BaseModel):
    main_size: int = 28
    additional_size: int = 20
    margin_x: int = 8
    margin_y: int = 8
    line_spacing: int = 8
    bg_padding: int = 5
    show_time: bool = True
    show_emf: bool = True
    show_temp: bool = True
    show_speed: bool = True
    show_operator: bool = True
    show_sample: bool = True


class VideoEncodingSettings(BaseModel):
    codec: str = "libx264"
    crf: int = 23
    preset: str = "medium"
    pix_fmt: str = "yuv420p"
    render_threads: int = Field(default_factory=lambda: max(2, os.cpu_count() or 4))


class OverlayConfig(BaseModel):
    logo_enabled: bool = False
    additional_text_enabled: bool = False
    additional_text: str = ""
    graph: GraphOverlaySettings = Field(default_factory=GraphOverlaySettings)
    text: TextOverlaySettings = Field(default_factory=TextOverlaySettings)
    video_encoding: VideoEncodingSettings = Field(default_factory=VideoEncodingSettings)

    @classmethod
    def load(cls) -> OverlayConfig:
        path = get_appdata_path("fusion-analysis") / "overlay_config.json"
        if path.exists():
            try:
                return cls.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                log.bind(error=str(exc)).warning("Using default overlay_config")
        cfg = cls()
        cfg.save()
        return cfg

    def save(self) -> None:
        path = get_appdata_path("fusion-analysis") / "overlay_config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")


overlay_config = OverlayConfig.load()


@dataclass
class VideoMeasurementData:
    """Данные измерения для наложения на видео и экспорта в .xlsx (без pandas)."""

    operator: str = ""
    sample: str = ""
    path: Path = field(default_factory=Path)
    time: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    emf: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    temp: np.ndarray | None = None

    @property
    def speed(self) -> np.ndarray | None:
        if self.temp is None:
            return None
        return calculate_speed(
            self.time,
            self.temp,
            temp_smoothing_window=overlay_config.graph.temp_smoothing_window,
            speed_smoothing_window=overlay_config.graph.speed_smoothing_window,
        )

    def to_excel(self, path: Path) -> None:
        """Экспортирует таблицу времени, ЭДС и температуры со встроенным графиком в .xlsx."""
        log.bind(path=str(path)).info("Exporting measurement to .xlsx")
        wb = xlsxwriter.Workbook(str(path))
        sheet_name = "Sheet1"
        ws = wb.add_worksheet(sheet_name)

        headers = ["Time, s", "EMF, mV"]
        if self.temp is not None:
            headers.append("Temperature, °C")
        ws.write_row(0, 0, headers)

        n_rows = len(self.time)
        t_rounded = np.round(self.time, 3).tolist()
        e_rounded = np.round(self.emf, 3).tolist()
        temp_rounded = (
            np.round(self.temp, 1).tolist() if self.temp is not None else None
        )

        for r_idx in range(n_rows):
            ws.write_number(r_idx + 1, 0, float(t_rounded[r_idx]))
            ws.write_number(r_idx + 1, 1, float(e_rounded[r_idx]))
            if temp_rounded is not None:
                ws.write_number(r_idx + 1, 2, float(temp_rounded[r_idx]))

        if n_rows > 0:
            chart: Any = wb.add_chart({"type": "scatter", "subtype": "straight"})
            y_col = 2 if self.temp is not None else 1
            y_title = "Temperature, °C" if self.temp is not None else "EMF, mV"
            chart.add_series(
                {
                    "categories": [sheet_name, 1, 0, n_rows, 0],
                    "values": [sheet_name, 1, y_col, n_rows, y_col],
                }
            )
            chart.set_legend({"position": "none"})
            chart.set_x_axis({"name": "Time, s"})
            chart.set_y_axis({"name": y_title})
            ws.insert_chart("E2", chart)
        wb.close()


@dataclass(slots=True)
class MeasurementSummaryInfo:
    source_format: str
    version: str
    path: Path
    sample: str
    operator: str
    points: int
    t_min_sec: float
    t_max_sec: float
    duration_sec: float
    emf_min: float | None
    emf_max: float | None
    temp_available: bool
    temp_min: float | None
    temp_max: float | None


@dataclass(slots=True)
class VideoInfo:
    path: Path
    input_width: int
    input_height: int
    fps_nominal: float
    real_fps: float | None = None
    total_frames: int = 0
    duration_sec: float = 0.0
    timestamps_source: str = ""
    timestamps_available: bool = False
    first_timestamp_sec: float | None = None
    last_timestamp_sec: float | None = None
    crop_rect: RectangleGeometry | None = None
    codec_name: str | None = None
    pix_fmt: str | None = None
    timestamps_sec: np.ndarray = field(
        repr=False, default_factory=lambda: np.array([], dtype=float)
    )
    used_start_sec: float | None = None
    used_end_sec: float | None = None
    kept_frames: int | None = None
    kept_duration_sec: float | None = None
    trimmed_start_frames: int = 0
    trimmed_end_frames: int = 0

    @property
    def output_width(self) -> int:
        return self.crop_rect.w if self.crop_rect else self.input_width

    @property
    def output_height(self) -> int:
        return self.crop_rect.h if self.crop_rect else self.input_height


@dataclass(slots=True)
class TimelineSelection:
    status: OverlapStatus
    overlap_start_sec: float
    overlap_end_sec: float
    overlap_duration_sec: float
    source_frame_indices: np.ndarray
    kept_timestamps_sec: np.ndarray
    kept_frames: int
    trimmed_start_frames: int
    trimmed_end_frames: int
    data_discarded_before_sec: float
    data_discarded_after_sec: float
    video_trimmed_at_start: bool
    video_trimmed_at_end: bool
    error_message: str | None = None


@dataclass(slots=True)
class AlignedInfo:
    points: int
    t_min_sec: float
    t_max_sec: float
    duration_sec: float
    interpolation: str
    normalized_timestamps: bool
    temp_available: bool
    speed_available: bool
    real_fps: float | None
    temp_smoothing_window: int
    speed_smoothing_window: int
    overlap_status: OverlapStatus
    trimmed_start_frames: int
    trimmed_end_frames: int
    data_discarded_before_sec: float
    data_discarded_after_sec: float
    video_trimmed_at_start: bool
    video_trimmed_at_end: bool
    error_message: str | None = None


@dataclass(slots=True)
class LoadedVideoMeasurement:
    data: VideoMeasurementData
    info: MeasurementSummaryInfo


@dataclass(slots=True)
class OverlaySessionState:
    measurement: LoadedVideoMeasurement | None = None
    video_info: VideoInfo | None = None
    timeline: TimelineSelection | None = None
    aligned_info: AlignedInfo | None = None


class ProcessProgress(NamedTuple):
    value: int
    frame: Any = None


class ProcessResult(NamedTuple):
    is_success: bool
    traceback_msg: str | None = None


def record_to_video_measurement(
    record: MeasurementRecord,
    fallback_path: Path | None = None,
) -> LoadedVideoMeasurement:
    """Преобразует MeasurementRecord (.fus, .vtaz, .tda, .fus-mdt) в данные для видео-оверлея."""
    path = record.source_path or fallback_path or Path("measurement.fus")
    time_arr = np.asarray(record.time_array, dtype=float)

    emf_col = next(
        (
            k
            for k in (
                "emf__smoothed",
                "emf_1__smoothed",
                "dta_smoothed",
                "emf",
                "emf_1",
                "dta",
                "EMF",
            )
            if k in record.data
        ),
        None,
    )
    if emf_col is None:
        raise ValueError(
            "В файле измерения отсутствует канал ЭДС или сигнала для видео-оверлея"
        )
    emf_arr = np.asarray(record.data[emf_col], dtype=float)

    temp_col = next(
        (
            k
            for k in (
                "temperature__smoothed",
                "temp_1__smoothed",
                "temperature",
                "temp_1",
                "Temp.",
            )
            if k in record.data
        ),
        None,
    )
    temp_arr = (
        np.asarray(record.data[temp_col], dtype=float) if temp_col is not None else None
    )

    v_data = VideoMeasurementData(
        operator=record.manifest.operator,
        sample=record.manifest.sample,
        path=path,
        time=time_arr,
        emf=emf_arr,
        temp=temp_arr,
    )
    t_min = float(time_arr.min()) if len(time_arr) else 0.0
    t_max = float(time_arr.max()) if len(time_arr) else 0.0
    v_info = MeasurementSummaryInfo(
        source_format=record.source_format,
        version=record.source_version,
        path=path,
        sample=record.manifest.sample,
        operator=record.manifest.operator,
        points=len(time_arr),
        t_min_sec=t_min,
        t_max_sec=t_max,
        duration_sec=max(0.0, t_max - t_min),
        emf_min=float(emf_arr.min()) if len(emf_arr) else None,
        emf_max=float(emf_arr.max()) if len(emf_arr) else None,
        temp_available=temp_arr is not None,
        temp_min=float(temp_arr.min())
        if (temp_arr is not None and len(temp_arr))
        else None,
        temp_max=float(temp_arr.max())
        if (temp_arr is not None and len(temp_arr))
        else None,
    )
    return LoadedVideoMeasurement(data=v_data, info=v_info)


def load_video_measurement(path: Path) -> LoadedVideoMeasurement:
    record = load_measurement(path)
    return record_to_video_measurement(record, fallback_path=path)
