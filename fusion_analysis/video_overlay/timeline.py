from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from fusion_analysis.helpers import calculate_speed
from fusion_analysis.video_overlay.models import (
    AlignedInfo,
    OverlapStatus,
    TimelineSelection,
    VideoInfo,
    VideoMeasurementData,
    overlay_config,
)

TIMELINE_TOLERANCE_SEC = 0.1


def compute_real_fps(timestamps_sec: np.ndarray) -> float | None:
    if len(timestamps_sec) < 2:
        return None
    first_ts, *_, last_ts = timestamps_sec
    duration = float(last_ts - first_ts)
    if duration <= 0.0:
        return None
    return (len(timestamps_sec) - 1) / duration


def build_vfr_setpts_script_content(timestamps_sec: np.ndarray) -> str:
    """Генерирует скрипт фильтра setpts для FFmpeg с сохранением точных VFR PTS меток."""
    n_frames = len(timestamps_sec)
    if n_frames <= 1:
        return "setpts=N/TB"

    step = max(1, n_frames // 2500)
    seg_list = list(range(0, n_frames, step))
    *_, last_seg = seg_list
    if last_seg != n_frames - 1:
        seg_list.append(n_frames - 1)
    seg_indices = np.array(seg_list, dtype=int)

    parts: list[str] = []
    for i in range(len(seg_indices) - 1):
        n0 = int(seg_indices[i])
        n1 = int(seg_indices[i + 1])
        t0_val = float(timestamps_sec[n0])
        t1_val = float(timestamps_sec[n1])
        slope = (t1_val - t0_val) / (n1 - n0)
        parts.append(f"gte(N\\,{n0})*lt(N\\,{n1})*({t0_val:.4f}+(N-{n0})*{slope:.6f})")
    *_, final_ts = timestamps_sec
    parts.append(f"gte(N\\,{n_frames - 1})*{float(final_ts):.4f}")
    return f"setpts=({'+'.join(parts)})/TB"


@dataclass(frozen=True)
class FrameTelemetry:
    """Значения ЭДС, температуры и скорости нагрева для одного кадра видео."""

    emf: float
    temp: float | None
    speed: float | None


@dataclass
class AlignedData:
    """Данные термограммы, интерполированные на временную сетку кадров видео."""

    timestamps: np.ndarray
    emf: np.ndarray
    temp: np.ndarray | None
    speed: np.ndarray | None

    @classmethod
    def from_data(
        cls,
        timestamps: np.ndarray,
        data: VideoMeasurementData,
    ) -> AlignedData:
        if len(timestamps) > 0:
            first_ts, *_ = timestamps
            normalized_ts = timestamps - float(first_ts)
        else:
            normalized_ts = timestamps

        emf = np.asarray(np.interp(timestamps, data.time, data.emf), dtype=float)
        if data.temp is not None:
            temp: np.ndarray | None = np.asarray(
                np.interp(timestamps, data.time, data.temp), dtype=float
            )
            speed = calculate_speed(
                normalized_ts,
                temp,
                temp_smoothing_window=overlay_config.graph.temp_smoothing_window,
                speed_smoothing_window=overlay_config.graph.speed_smoothing_window,
            )
        else:
            temp = None
            speed = None

        return cls(timestamps=timestamps, emf=emf, temp=temp, speed=speed)

    def at_index(self, idx: int) -> FrameTelemetry:
        temp_val = float(self.temp[idx]) if self.temp is not None else None
        speed_val = float(self.speed[idx]) if self.speed is not None else None
        return FrameTelemetry(
            emf=float(self.emf[idx]),
            temp=temp_val,
            speed=speed_val,
        )


def build_timeline_selection(
    data: VideoMeasurementData,
    video_info: VideoInfo,
) -> TimelineSelection:
    """Вычисляет пересечение временных интервалов видео и термограммы (нативное VFR 1:1)."""
    video_ts = video_info.timestamps_sec
    data_time = data.time

    if len(video_ts) == 0 or len(data_time) == 0:
        return TimelineSelection(
            status=OverlapStatus.NONE,
            overlap_start_sec=0.0,
            overlap_end_sec=0.0,
            overlap_duration_sec=0.0,
            source_frame_indices=np.array([], dtype=int),
            kept_timestamps_sec=np.array([], dtype=float),
            kept_frames=0,
            trimmed_start_frames=0,
            trimmed_end_frames=0,
            data_discarded_before_sec=0.0,
            data_discarded_after_sec=0.0,
            video_trimmed_at_start=False,
            video_trimmed_at_end=False,
            error_message="Отсутствуют временные метки видео или данные измерения.",
        )

    v_first, *_, v_last = video_ts
    d_first, *_, d_last = data_time
    video_start = float(v_first)
    video_end = float(v_last)
    data_start = float(d_first)
    data_end = float(d_last)

    tol = TIMELINE_TOLERANCE_SEC
    overlap_start = video_start if data_start <= video_start + tol else data_start
    overlap_end = video_end if data_end >= video_end - tol else data_end

    if overlap_start >= overlap_end:
        return TimelineSelection(
            status=OverlapStatus.NONE,
            overlap_start_sec=overlap_start,
            overlap_end_sec=overlap_end,
            overlap_duration_sec=0.0,
            source_frame_indices=np.array([], dtype=int),
            kept_timestamps_sec=np.array([], dtype=float),
            kept_frames=0,
            trimmed_start_frames=int(np.sum(video_ts < overlap_start)),
            trimmed_end_frames=int(np.sum(video_ts > overlap_end)),
            data_discarded_before_sec=max(0.0, video_start - data_start),
            data_discarded_after_sec=max(0.0, data_end - video_end),
            video_trimmed_at_start=data_start > video_start + tol,
            video_trimmed_at_end=data_end < video_end - tol,
            error_message="Временные интервалы видео и измерения не пересекаются.",
        )

    overlap_duration = overlap_end - overlap_start
    mask = (video_ts >= overlap_start - 1e-5) & (video_ts <= overlap_end + 1e-5)
    (kept_indices,) = np.where(mask)  # noqa: PU001
    kept_ts = video_ts[mask]

    trimmed_start = int(np.sum(video_ts < overlap_start - 1e-5))
    trimmed_end = int(np.sum(video_ts > overlap_end + 1e-5))
    data_before = (
        max(0.0, video_start - data_start) if data_start < video_start - 1e-5 else 0.0
    )
    data_after = max(0.0, data_end - video_end) if data_end > video_end + 1e-5 else 0.0
    is_full = trimmed_start == 0 and trimmed_end == 0

    return TimelineSelection(
        status=OverlapStatus.FULL if is_full else OverlapStatus.PARTIAL,
        overlap_start_sec=float(overlap_start),
        overlap_end_sec=float(overlap_end),
        overlap_duration_sec=float(overlap_duration),
        source_frame_indices=kept_indices,
        kept_timestamps_sec=kept_ts,
        kept_frames=len(kept_indices),
        trimmed_start_frames=trimmed_start,
        trimmed_end_frames=trimmed_end,
        data_discarded_before_sec=data_before,
        data_discarded_after_sec=data_after,
        video_trimmed_at_start=trimmed_start > 0,
        video_trimmed_at_end=trimmed_end > 0,
    )


def update_video_info_with_timeline(
    video_info: VideoInfo,
    timeline: TimelineSelection,
) -> VideoInfo:
    has_overlap = timeline.status is not OverlapStatus.NONE
    return replace(
        video_info,
        used_start_sec=timeline.overlap_start_sec if has_overlap else None,
        used_end_sec=timeline.overlap_end_sec if has_overlap else None,
        kept_frames=timeline.kept_frames,
        kept_duration_sec=timeline.overlap_duration_sec if has_overlap else None,
        trimmed_start_frames=timeline.trimmed_start_frames,
        trimmed_end_frames=timeline.trimmed_end_frames,
    )


def build_aligned_info(
    data: VideoMeasurementData,
    _video_info: VideoInfo,
    timeline: TimelineSelection,
) -> AlignedInfo:
    if timeline.status is OverlapStatus.NONE or len(timeline.kept_timestamps_sec) == 0:
        return AlignedInfo(
            points=0,
            t_min_sec=0.0,
            t_max_sec=0.0,
            duration_sec=0.0,
            interpolation="np.interp",
            normalized_timestamps=True,
            temp_available=False,
            speed_available=False,
            real_fps=None,
            temp_smoothing_window=overlay_config.graph.temp_smoothing_window,
            speed_smoothing_window=overlay_config.graph.speed_smoothing_window,
            overlap_status=OverlapStatus.NONE,
            trimmed_start_frames=timeline.trimmed_start_frames,
            trimmed_end_frames=timeline.trimmed_end_frames,
            data_discarded_before_sec=timeline.data_discarded_before_sec,
            data_discarded_after_sec=timeline.data_discarded_after_sec,
            video_trimmed_at_start=timeline.video_trimmed_at_start,
            video_trimmed_at_end=timeline.video_trimmed_at_end,
            error_message=timeline.error_message,
        )

    kept_ts = timeline.kept_timestamps_sec
    aligned = AlignedData.from_data(kept_ts, data)
    first_k, *_, last_k = kept_ts
    t_min = float(first_k)
    t_max = float(last_k)
    return AlignedInfo(
        points=len(kept_ts),
        t_min_sec=t_min,
        t_max_sec=t_max,
        duration_sec=t_max - t_min,
        interpolation="np.interp",
        normalized_timestamps=True,
        temp_available=aligned.temp is not None,
        speed_available=aligned.speed is not None,
        real_fps=compute_real_fps(kept_ts),
        temp_smoothing_window=overlay_config.graph.temp_smoothing_window,
        speed_smoothing_window=overlay_config.graph.speed_smoothing_window,
        overlap_status=timeline.status,
        trimmed_start_frames=timeline.trimmed_start_frames,
        trimmed_end_frames=timeline.trimmed_end_frames,
        data_discarded_before_sec=timeline.data_discarded_before_sec,
        data_discarded_after_sec=timeline.data_discarded_after_sec,
        video_trimmed_at_start=timeline.video_trimmed_at_start,
        video_trimmed_at_end=timeline.video_trimmed_at_end,
    )
