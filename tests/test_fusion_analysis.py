from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fusion_analysis.config import read_config, write_config
from fusion_analysis.helpers import (
    BEZIER_TYPE,
    LINEAR_TYPE,
    SIGMOIDAL_TYPE,
    STEPPED_TYPE,
    calc_peakonset,
    centered_moving_average,
    derivative_data,
    make_peakbaseline,
)
from fusion_analysis.importers import (
    load_fusion_measurement,
    save_measurement_analysis,
)
from fusion_common import (
    ChannelDescriptor,
    MeasurementManifest,
    MeasurementRecord,
    save_fus,
)


def test_config_roundtrip_fixes_color_slice_bug(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    cfg = read_config(cfg_file)
    assert cfg.Plotter.default_heat_color == [1.0, 0.0, 0.0]
    assert cfg.Plotter.default_cool_color == [0.0, 0.0, 1.0]

    cfg.Plotter.default_heat_color = [0.5, 0.25, 0.75]
    write_config(cfg, path=cfg_file)
    reloaded = read_config(cfg_file)
    assert reloaded.Plotter.default_heat_color == [0.5, 0.25, 0.75]


def test_any_channel_smoothing_and_separate_fusa_file(tmp_path: Path) -> None:
    t_arr = np.linspace(0.0, 10.0, 41)
    temp_arr = np.linspace(25.0, 500.0, 41) + np.sin(t_arr * 3.0)
    dta_arr = np.sin(t_arr)

    dta_rec = MeasurementRecord(
        manifest=MeasurementManifest(
            sample="Sm2S3",
            operator="Tester",
            channels=[
                ChannelDescriptor(column="time", label="Время", unit="s"),
                ChannelDescriptor(column="temperature", label="Температура", unit="°C"),
                ChannelDescriptor(
                    column="dta",
                    label="ДТА",
                    unit="mV",
                    metadata={"exo_up": True},
                ),
            ],
        ),
        data={"time": t_arr, "temperature": temp_arr, "dta": dta_arr},
    )
    raw_fus_path = tmp_path / "sample_raw.fus"
    save_fus(dta_rec, raw_fus_path)
    raw_bytes_before = raw_fus_path.read_bytes()

    m_data = load_fusion_measurement(raw_fus_path)
    assert "DTA" in m_data.available_channels
    assert "Temp." in m_data.available_channels

    # Сглаживаем и кривую DTA, и кривую температуры Temp.
    m_data.apply_channel_smoothing("DTA", 2)
    m_data.apply_channel_smoothing("Temp.", 3)
    m_data.analysis_state["deriv_channel"] = "Temp."
    m_data.analysis_state["split_times"] = [5.0]

    fusa_path = tmp_path / "sample_analyzed.fusa"
    saved_path = save_measurement_analysis(m_data, fusa_path)
    assert saved_path == fusa_path

    # Сырой файл .fus остался побитово неизменным
    assert raw_fus_path.read_bytes() == raw_bytes_before

    # Из отдельного файла .fusa восстанавливаются все сглаженные каналы и состояние анализа
    reloaded = load_fusion_measurement(fusa_path)
    first_seg, *_ = m_data.segments
    rel_seg, *_ = reloaded.segments
    assert np.allclose(rel_seg["DTA"], first_seg["DTA"])
    assert np.allclose(rel_seg["Temp."], first_seg["Temp."])
    assert reloaded.smoothing_windows.get("DTA") == 2
    assert reloaded.smoothing_windows.get("Temp.") == 3
    assert reloaded.analysis_state.get("deriv_channel") == "Temp."
    assert reloaded.analysis_state.get("split_times") == [5.0]


def test_peak_baseline_and_arbitrary_derivative_math() -> None:
    x = np.linspace(0.0, 100.0, 201)
    y = np.exp(-((x - 50.0) ** 2) / 50.0)
    dy = derivative_data(x, y)

    temp_curve = 25.0 + 10.0 * x
    dtemp_dt = derivative_data(x, temp_curve)
    assert np.allclose(dtemp_dt[1:], 10.0, atol=1e-6)

    lin_curve = make_peakbaseline(LINEAR_TYPE, 20, 180, x.tolist(), y.tolist())
    assert len(lin_curve.values) == 161

    bez_curve = make_peakbaseline(BEZIER_TYPE, 20, 180, x.tolist(), y.tolist())
    assert len(bez_curve.values) == 161

    # Пик со ступенькой базовой линии (скачок теплоёмкости Delta Cp по ур. 71 Haines et al.)
    step_bg = np.where(x < 50.0, 0.0, 0.5)
    y_step = step_bg + np.exp(-((x - 50.0) ** 2) / 30.0)
    sig_curve = make_peakbaseline(SIGMOIDAL_TYPE, 20, 180, x.tolist(), y_step.tolist())
    assert len(sig_curve.values) == 161
    first_b, *_, last_b = sig_curve.values
    assert float(first_b) == pytest.approx(0.0, abs=0.05)
    assert float(last_b) == pytest.approx(0.5, abs=0.05)

    stepped_curve = make_peakbaseline(
        STEPPED_TYPE, 20, 180, x.tolist(), y_step.tolist()
    )
    assert len(stepped_curve.values) == 161
    s_first, *_, s_last = stepped_curve.values
    assert float(s_first) == pytest.approx(0.0, abs=0.05)
    assert float(s_last) == pytest.approx(0.5, abs=0.05)

    onset = calc_peakonset(
        t1=30.0,
        t2=50.0,
        data_t=x,
        data_dta=y,
        data_ddta=dy,
        expr_baseline=lin_curve.expr,
        is_onset=True,
        peak_exo=1,
    )
    assert 0 <= onset.baseline_idx <= onset.tangent_idx < len(x)

    # Кривая охлаждения: температура убывает от 1000 °C до 800 °C вдоль времени
    temp_cool = np.linspace(1000.0, 800.0, 201)
    dta_cool = np.exp(-((temp_cool - 900.0) ** 2) / 50.0)
    ddta_dtemp_cool = derivative_data(temp_cool, dta_cool)
    cool_onset = calc_peakonset(
        t1=900.0,
        t2=950.0,
        data_t=temp_cool,
        data_dta=dta_cool,
        data_ddta=ddta_dtemp_cool,
        expr_baseline=lambda t_val: np.zeros_like(t_val, dtype=float),
        is_onset=True,
        peak_exo=1,
    )
    # Ликвидус (начало кристаллизации при охлаждении) лежит выше 900 °C (индекс <= 100)
    assert 0 < cool_onset.baseline_idx <= cool_onset.tangent_idx < 100

    assert len(centered_moving_average(x, 5)) == len(x)


def test_ictac_segment_thermal_type_classification() -> None:
    from fusion_analysis.measurement_data import (
        ThermalType,
        classify_segment_thermal_type,
    )

    # Полный цикл нагрев 25 -> 1200 -> охлаждение 25 не должен считаться изотермой
    cycle = np.concatenate(
        (np.linspace(25.0, 1200.0, 50), np.linspace(1200.0, 25.0, 50))
    )
    t_type, label = classify_segment_thermal_type(cycle)  # noqa: PU001
    assert t_type is ThermalType.HEAT
    assert "1200" in label

    iso = np.array([500.0, 500.3, 499.8, 500.1])
    iso_type, iso_label = classify_segment_thermal_type(iso)  # noqa: PU001
    assert iso_type is ThermalType.ISOTHERMAL
    assert "Изотерма" in iso_label


def test_first_and_second_derivatives_in_any_axes_and_smoothing(
    tmp_path: Path,
) -> None:
    t_s = np.linspace(0.0, 600.0, 101)  # 0..10 мин
    temp_c = 25.0 + 3.0 * (t_s / 60.0) ** 2  # T(t) = 25 + 3*t_min^2
    dta_mv = np.sin(t_s / 60.0)

    rec = MeasurementRecord(
        manifest=MeasurementManifest(
            sample="Al-Si",
            channels=[
                ChannelDescriptor(column="time", label="Время", unit="s"),
                ChannelDescriptor(column="temperature", label="Температура", unit="°C"),
                ChannelDescriptor(column="dta", label="ДТА", unit="mV"),
            ],
        ),
        data={"time": t_s, "temperature": temp_c, "dta": dta_mv},
    )
    fus_p = tmp_path / "ca_cca.fus"
    save_fus(rec, fus_p)

    m = load_fusion_measurement(fus_p)
    # 1-я производная температуры по времени: d(Temp.)/d(Time) = 6 * t_min
    ch_d1 = m.compute_derivative_channel("Temp.", "Time", order=1)
    assert ch_d1 == "d(Temp.)/d(Time)"
    assert ch_d1 in m.available_channels

    # 2-я производная температуры по времени: d²(Temp.)/d(Time)² ≈ 6.0
    ch_d2 = m.compute_derivative_channel("Temp.", "Time", order=2)
    assert ch_d2 == "d²(Temp.)/d(Time)²"
    seg0, *_ = m.segments
    assert np.allclose(seg0[ch_d2][3:], 6.0, atol=0.2)

    # Производная в других осях: d(DTA)/d(Temp.) и её сглаживание как обычного 1D-массива
    ch_dt = m.compute_derivative_channel("DTA", "Temp.", order=1)
    assert ch_dt == "d(DTA)/d(Temp.)"
    m.apply_channel_smoothing(ch_dt, 2)
    assert m.smoothing_windows[ch_dt] == 2


def test_chalcogenide_glass_transition_and_fraser_suzuki_math() -> None:
    from fusion_analysis.helpers import (
        compute_glass_transition_metrics,
        estimate_fraser_suzuki_asymmetry,
        fraser_suzuki_curve,
    )

    t_grid = np.linspace(100.0, 300.0, 401)
    # Асимметричный пик кристаллизации ЖМА (a3 = -0.25) при Tp = 200 °C, FWHM = 20 °C
    fs_peak = fraser_suzuki_curve(
        t_grid, height=5.0, center=200.0, fwhm=20.0, asymmetry=-0.25
    )
    peak_i = int(np.argmax(fs_peak))
    assert float(t_grid[peak_i]) == pytest.approx(200.0, abs=0.5)
    a3_est = estimate_fraser_suzuki_asymmetry(t_grid, fs_peak, peak_i)
    assert a3_est == pytest.approx(-0.25, abs=0.05)

    # Ступень стеклования при Tg = 180 °C со скачком Delta Y = 1.0
    y_glass_step = 0.5 * (1.0 + np.tanh((t_grid - 180.0) / 4.0))
    metrics = compute_glass_transition_metrics(t_grid, y_glass_step, 40, 360)
    assert metrics.tg_mid == pytest.approx(180.0, abs=1.0)
    assert metrics.t_inflection == pytest.approx(180.0, abs=1.0)
    assert metrics.t_fictive == pytest.approx(180.0, abs=1.0)
    assert metrics.delta_y_step == pytest.approx(1.0, abs=0.05)


def test_setaram_import_preserves_sample_mass_mg(tmp_path: Path) -> None:
    from fusion_analysis.importers import import_setaram_txt

    txt = tmp_path / "setaram.txt"
    txt.write_text(
        "Header\nTime\tSample temperature\tHeatFlow\tTG\n"
        "Units\ts\tC\tmW\tmg\n"
        "0.0\t25.0\t0.1\t0.0\n"
        "60.0\t125.0\t0.5\t-5.0\n",
        encoding="cp1251",
    )
    m = import_setaram_txt(txt, startmass=50.0)
    assert m.info.get("sample_mass_mg") == pytest.approx(50.0)
    seg0, *_ = m.segments
    assert float(seg0["Mass"][-1]) == pytest.approx(90.0)  # noqa: MI001


def test_hildal_perepezko_nonuniform_melting_and_tau_metrics() -> None:
    from fusion_analysis.helpers import compute_melting_range_and_tau_metrics

    # Неравномерный нагрев: T(t) ускоряется со временем
    t_min = np.linspace(0.0, 10.0, 1001)
    temp_c = 500.0 + 20.0 * t_min + 2.0 * (t_min**2)
    # Пик начинается при t = 3.0 мин, достигает максимума при t = 5.0 мин
    # и релаксирует по экспоненте с постоянной времени tau = 12 с (0.2 мин)
    dev = np.zeros_like(t_min)
    rising = (t_min >= 3.0) & (t_min <= 5.0)
    dev[rising] = ((t_min[rising] - 3.0) / 2.0) ** 2
    falling = t_min > 5.0
    dev[falling] = np.exp(-(t_min[falling] - 5.0) / 0.2)

    pk_idx = int(np.argmax(dev))
    mm = compute_melting_range_and_tau_metrics(t_min, temp_c, dev, pk_idx)
    expected_t_init = float(np.interp(3.0 + 2.0 * np.sqrt(0.02), t_min, temp_c))
    expected_t_corr = float(np.interp(5.0 - 0.2, t_min, temp_c))
    assert mm.t_init_dev == pytest.approx(expected_t_init, abs=1.5)
    assert mm.tau_relax_sec == pytest.approx(12.0, abs=0.5)
    assert mm.temp_lag_corrected == pytest.approx(expected_t_corr, abs=1.0)

    from fusion_analysis.segment_properties_window import (
        SUMMARY_TABLE_HEADERS,
        build_peaks_summary_rows,
    )

    assert len(SUMMARY_TABLE_HEADERS) == 12
    assert build_peaks_summary_rows([]) == []

    from fusion_analysis.helpers import format_peak_quantity

    q_mv = format_peak_quantity(1.5, "mV", 1)
    assert q_mv.units == "мВ·с"
    q_mw = format_peak_quantity(1.0, "mW", -1, mass_mg=10.0)
    assert q_mw.units == "Дж/г"
    assert q_mw.magnitude == pytest.approx(-6.0)


def test_segment_add_peak_and_onset_Creation() -> None:
    import sys

    from fusion_analysis.measurement_data import ThermalType
    from fusion_analysis.plotter import Plotter
    from PySide6.QtWidgets import QApplication, QWidget

    _app = QApplication.instance() or QApplication(sys.argv)
    host = QWidget()
    plotter = Plotter(host, scale=1.0)
    plotter.units = {"Time": "min", "Temp.": "°C", "DTA": "mV"}
    t_min = np.linspace(0.0, 10.0, 201)
    temp_c = 100.0 + 50.0 * t_min
    dta_mv = np.exp(-((t_min - 5.0) ** 2) / 0.5)
    seg = plotter.addSegment(
        df={"Time": t_min, "Temp.": temp_c, "DTA": dta_mv},
        index=0,
        thermal_type=ThermalType.HEAT,
        temp_axis="Temp.",
    )
    peak = seg.addPeak(t1=2.0, t2=8.0, baseline_type=0)
    assert peak.ann is not None
    onset_line = peak.onset(t1=3.0, t2=5.0, is_onset=True)
    assert onset_line.ann is not None
