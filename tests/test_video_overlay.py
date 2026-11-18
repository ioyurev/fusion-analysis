from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from fusion_analysis.video_overlay import (
    AlignedData,
    FrameRenderer,
    OverlapStatus,
    VideoInfo,
    VideoMeasurementData,
    build_aligned_info,
    build_timeline_selection,
    build_vfr_setpts_script_content,
    update_video_info_with_timeline,
)
from fusion_analysis.video_overlay.ffmpeg_pipe import VideoContext


def _make_data(t_start: float, t_end: float, n: int = 200) -> VideoMeasurementData:
    t = np.linspace(t_start, t_end, n)
    return VideoMeasurementData(
        operator="Tester",
        sample="SmS",
        time=t,
        emf=t * 0.5,
        temp=t * 10.0 + 25.0,
    )


def _make_video_info(timestamps: np.ndarray, fps: float = 25.0) -> VideoInfo:
    first_ts: float | None = None
    last_ts: float | None = None
    if len(timestamps) > 0:
        f_v, *_, l_v = timestamps
        first_ts = float(f_v)
        last_ts = float(l_v)
    dur = (
        (last_ts - first_ts) if (first_ts is not None and last_ts is not None) else 0.0
    )
    return VideoInfo(
        path=Path("test.mp4"),
        input_width=640,
        input_height=480,
        fps_nominal=fps,
        total_frames=len(timestamps),
        duration_sec=dur,
        timestamps_source="synthetic",
        timestamps_available=len(timestamps) > 0,
        first_timestamp_sec=first_ts,
        last_timestamp_sec=last_ts,
        timestamps_sec=timestamps,
    )


def test_aligned_data_interpolation_and_excel_export(tmp_path: Path) -> None:
    data = VideoMeasurementData(
        operator="Op",
        sample="Sample",
        time=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        emf=np.array([0.0, 10.0, 20.0, 30.0, 40.0]),
        temp=np.array([100.0, 200.0, 300.0, 400.0, 500.0]),
    )
    ts = np.array([0.5, 1.5, 2.5, 3.5])
    aligned = AlignedData.from_data(ts, data)
    assert aligned.temp is not None
    assert aligned.speed is not None
    assert np.allclose(aligned.emf, [5.0, 15.0, 25.0, 35.0])
    assert np.allclose(aligned.temp, [150.0, 250.0, 350.0, 450.0])

    xlsx_path = tmp_path / "export.xlsx"
    data.to_excel(xlsx_path)
    assert xlsx_path.exists()
    assert xlsx_path.stat().st_size > 1000


def test_timeline_overlap_modes_and_vfr_properties() -> None:
    data_full = _make_data(0.0, 100.0)
    video_full = _make_video_info(np.linspace(0.0, 100.0, 500))
    tl_full = build_timeline_selection(data_full, video_full)
    assert tl_full.status is OverlapStatus.FULL
    assert tl_full.kept_frames == 500

    data_part = _make_data(20.0, 80.0)
    tl_part = build_timeline_selection(data_part, video_full)
    assert tl_part.status is OverlapStatus.PARTIAL
    assert tl_part.video_trimmed_at_start
    assert tl_part.video_trimmed_at_end
    upd_v = update_video_info_with_timeline(video_full, tl_part)
    assert upd_v.used_start_sec == pytest.approx(20.0, abs=0.2)
    info_al = build_aligned_info(data_part, upd_v, tl_part)
    assert info_al.points == tl_part.kept_frames

    data_none = _make_data(200.0, 300.0)
    tl_none = build_timeline_selection(data_none, video_full)
    assert tl_none.status is OverlapStatus.NONE
    assert tl_none.kept_frames == 0

    for seed in range(100):
        rng = np.random.RandomState(seed)
        d_s = float(rng.uniform(-50.0, 100.0))
        d_e = d_s + float(rng.uniform(5.0, 100.0))
        v_s = float(rng.uniform(-50.0, 100.0))
        v_e = v_s + float(rng.uniform(5.0, 100.0))
        v_ts = np.sort(rng.uniform(v_s, v_e, 120))
        tl = build_timeline_selection(_make_data(d_s, d_e, 100), _make_video_info(v_ts))
        assert (
            tl.kept_frames
            == len(tl.source_frame_indices)
            == len(tl.kept_timestamps_sec)
        )
        if tl.kept_frames > 0:
            assert np.allclose(v_ts[tl.source_frame_indices], tl.kept_timestamps_sec)


def test_vfr_setpts_and_frame_renderer() -> None:
    _app = QApplication.instance() or QApplication(sys.argv)
    script = build_vfr_setpts_script_content(np.array([0.0, 0.5, 1.0, 2.5]))
    assert script.startswith("setpts=(")
    assert script.endswith(")/TB")

    data = _make_data(0.0, 4.0, 5)
    mock_ctx = MagicMock(spec=VideoContext)
    mock_ctx.fps = 1.0
    mock_ctx.total_frames = 5
    mock_ctx.width = 640
    mock_ctx.height = 480

    renderer = FrameRenderer(
        video_ctx=mock_ctx,
        data=data,
        timestamps=np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        graph_enabled=True,
    )
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    frame = renderer.render_overlay(img, 2)
    assert frame is not None
    assert frame.size.width == 640
    assert frame.size.height == 480


def test_main_window_contains_curves_and_video_overlay_tabs() -> None:
    from fusion_analysis.main_window import MainWindow

    _app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(scale=1.0)
    try:
        assert win.mode_tabs.count() == 2
        assert win.mode_tabs.tabText(0) == "Анализ кривых"
        assert win.mode_tabs.tabText(1) == "Видео-оверлей ВТА"
        vtab = win.video_overlay_tab
        assert vtab.btn_play.text() == "Пуск"
        assert not vtab.btn_play.icon().isNull()
        assert vtab.cb_play_speed.count() == 5
        assert vtab.sync_plot.cb_mode.count() == 3
        assert "Кадр:" in vtab.lbl_telemetry.text()
    finally:
        win.close()
