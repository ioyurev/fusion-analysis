from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from PySide6 import QtWidgets

LINEAR_TYPE = 0
BEZIER_TYPE = 1
SIGMOIDAL_TYPE = 2
STEPPED_TYPE = 3


@dataclass(frozen=True)
class BaselineCurve:
    """Результат расчёта базовой линии пика."""

    values: np.ndarray
    expr: Callable[[float | np.ndarray], float | np.ndarray]


@dataclass(frozen=True)
class OnsetIndices:
    """Индексы точки касания и точки пересечения с базовой линией."""

    tangent_idx: int
    baseline_idx: int


@dataclass(frozen=True)
class GlassTransitionMetrics:
    """Характеристики ступени стеклования по Svoboda & Malek (2018), ур. (12.3) и (12.7)."""

    tg_mid: float
    t_inflection: float
    t_fictive: float
    delta_y_step: float


@dataclass(frozen=True)
class MeltingRangeMetrics:
    """Метрики интервала плавления и тепловой релаксации по Hildal & Perepezko (2018)."""

    t_init_dev: float
    t_return_dev: float
    tau_relax_sec: float
    temp_lag_corrected: float


def np_min_wo_infnan(array: np.ndarray) -> float:
    return float(np.nanmin(array[array != -np.inf]))


def error_message(message: str) -> None:
    QtWidgets.QMessageBox.critical(None, "Ошибка", message)


def warning_message(message: str) -> None:
    QtWidgets.QMessageBox.warning(None, "Предупреждение", message)


def baseline_temp(
    data_temp: Sequence[float] | np.ndarray,
    data_dta: Sequence[float] | np.ndarray,
) -> Callable[[float | np.ndarray], float | np.ndarray]:
    t_arr = np.asarray(data_temp, dtype=float)
    y_arr = np.asarray(data_dta, dtype=float)
    if len(t_arr) < 2:
        const_v = float(y_arr[0]) if len(y_arr) else 0.0  # noqa: MI001
        return lambda x: (
            np.full_like(x, const_v, dtype=float)
            if isinstance(x, np.ndarray)
            else const_v
        )
    order = np.argsort(t_arr)
    t_sorted = t_arr[order]
    y_sorted = y_arr[order]
    return lambda x: np.interp(x, t_sorted, y_sorted)


def centered_moving_average(y: np.ndarray, window: int) -> np.ndarray:
    """Гладкая фильтрация окном Ханна постоянной полуширины с касательным продолжением краёв (без колена у границ)."""
    arr = np.asarray(y, dtype=float)
    n = len(arr)
    w = max(1, int(window))
    if n <= 2 or w <= 1:
        return arr.copy()
    half = min(w // 2, max(1, n - 1))
    fit_pts = min(n, max(4, half // 2 + 2))

    x_l = np.arange(fit_pts, dtype=float)
    slope_l, _ = np.polyfit(x_l, arr[:fit_pts], 1)  # noqa: PU001
    left_pad = float(arr[0]) + slope_l * np.arange(-half, 0, dtype=float)  # noqa: MI001

    x_r = np.arange(fit_pts, dtype=float)
    slope_r, _ = np.polyfit(x_r, arr[n - fit_pts :], 1)  # noqa: PU001
    right_pad = float(arr[-1]) + slope_r * np.arange(1, half + 1, dtype=float)  # noqa: MI001

    padded = np.concatenate((left_pad, arr, right_pad))
    grid = np.arange(-half, half + 1, dtype=float)
    kernel = 0.5 * (1.0 + np.cos(np.pi * grid / (half + 1.0)))
    kernel /= float(np.sum(kernel))
    return np.asarray(np.convolve(padded, kernel, mode="valid"), dtype=float)


def calculate_speed(
    x: np.ndarray,
    y: np.ndarray | None,
    temp_smoothing_window: int = 15,
    speed_smoothing_window: int = 30,
) -> np.ndarray | None:
    """Рассчитывает сглаженную производную dy/dx (скорость нагрева dT/dt)."""
    if y is None:
        return None
    if len(x) < 2:
        return np.zeros_like(y, dtype=float)
    smooth_y = centered_moving_average(y, max(1, temp_smoothing_window))
    raw_speed = np.asarray(np.gradient(smooth_y, x), dtype=float)
    return centered_moving_average(raw_speed, max(1, speed_smoothing_window))


def find_nearest(array: Sequence[float] | np.ndarray, value: float) -> int:
    arr = np.asarray(array, dtype=float)
    return int(np.abs(arr - value).argmin())


def derivative_data(xdata: np.ndarray, ydata: np.ndarray) -> np.ndarray:
    """Вычисляет первую производную dy/dx без скрытого сглаживания."""
    x_arr = np.asarray(xdata, dtype=float)
    y_arr = np.asarray(ydata, dtype=float)
    if len(x_arr) < 2:
        return np.zeros_like(y_arr, dtype=float)
    dx = np.diff(x_arr)
    dy = np.diff(y_arr)
    span = float(np.ptp(x_arr))
    min_dx = max(1e-9, span / (len(x_arr) * 500.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(np.abs(dx) >= min_dx, dy / dx, 0.0)
    return np.insert(ratio, 0, 0.0, axis=0)


def second_derivative_data(xdata: np.ndarray, ydata: np.ndarray) -> np.ndarray:
    """Вычисляет вторую производную d²y/dx² = d(dy/dx)/dx без скрытого сглаживания."""
    first_deriv = derivative_data(xdata, ydata)
    return derivative_data(xdata, first_deriv)


def round_significant(x: float, n: int) -> float:
    if x == 0.0:
        return 0.0
    return round(x, -math.floor(math.log10(abs(x))) + (n - 1))


@dataclass(frozen=True)
class PeakQuantity:
    """Численная величина интегрального эффекта пика с единицей измерения (без pint)."""

    magnitude: float
    units: str

    def __str__(self) -> str:
        return f"{self.magnitude:g} {self.units}".strip()


_CANONICAL_UNIT_MAP: dict[str, str] = {
    "mv": "мВ",
    "V": "В",
    "v": "В",
    "mw": "мВт",
    "W": "Вт",
    "w": "Вт",
    "mw/mg": "мВт/мг",
    "j": "Дж",
    "mj": "мДж",
    "j/g": "Дж/г",
}


def normalize_unit_symbol(unit_raw: str) -> str:
    """Приводит строковое обозначение единицы к каноническому виду СИ (В, мВ, Вт, мВт, Дж, мДж, Дж/г)."""
    cleaned = str(unit_raw).strip().replace(" ", "")
    if cleaned in _CANONICAL_UNIT_MAP:
        return _CANONICAL_UNIT_MAP[cleaned]
    return _CANONICAL_UNIT_MAP.get(cleaned.lower(), cleaned)


def format_peak_quantity(
    raw_integral_min: float,
    y_unit_raw: str,
    sign_factor: int,
    mass_mg: float | None = None,
) -> PeakQuantity:
    """Переводит интеграл по времени из минут в секунды и формирует физическую единицу площади."""
    area_sec = abs(float(raw_integral_min)) * 60.0
    u_norm = normalize_unit_symbol(y_unit_raw)

    if u_norm == "мВт/мг":
        val = round_significant(area_sec, 3) * sign_factor
        return PeakQuantity(magnitude=val, units="Дж/г")

    if u_norm == "мВт":
        if mass_mg is not None and mass_mg > 0.0:
            val = round_significant(area_sec / float(mass_mg), 3) * sign_factor
            return PeakQuantity(magnitude=val, units="Дж/г")
        val = round_significant(area_sec, 3) * sign_factor
        return PeakQuantity(magnitude=val, units="мДж")

    if u_norm == "Вт":
        if mass_mg is not None and mass_mg > 0.0:
            val = (
                round_significant((area_sec * 1000.0) / float(mass_mg), 3) * sign_factor
            )
            return PeakQuantity(magnitude=val, units="Дж/г")
        val = round_significant(area_sec, 3) * sign_factor
        return PeakQuantity(magnitude=val, units="Дж")

    base_u = f"{u_norm}·с" if u_norm else "с"
    if mass_mg is not None and mass_mg > 0.0:
        val = round_significant(area_sec / float(mass_mg), 3) * sign_factor
        return PeakQuantity(magnitude=val, units=f"{base_u}/мг")

    val = round_significant(area_sec, 3) * sign_factor
    return PeakQuantity(magnitude=val, units=base_u)


def compute_padded_limits(
    arrays: Sequence[np.ndarray],
    pad_fraction: float = 0.05,
) -> tuple[float, float] | None:
    """Вычисляет пределы оси (vmin, vmax) с отступом и защитой от вырожденного диапазона."""
    finite_chunks: list[np.ndarray] = []
    for arr in arrays:
        a = np.asarray(arr, dtype=float)
        if a.size > 0:
            fin = a[np.isfinite(a)]
            if fin.size > 0:
                finite_chunks.append(fin)
    if not finite_chunks:
        return None
    vmin = float(min(float(np.min(c)) for c in finite_chunks))
    vmax = float(max(float(np.max(c)) for c in finite_chunks))
    span = vmax - vmin
    if span < 1e-9:
        delta = max(1.0, abs(vmin) * pad_fraction)
        return (vmin - delta, vmax + delta)
    margin = span * pad_fraction
    return (vmin - margin, vmax + margin)


def _estimate_wing_slope(
    x_arr: np.ndarray,
    y_arr: np.ndarray,
    idx: int,
    is_left: bool,
    wing_pts: int = 10,
) -> float:
    """Оценивает наклон базовой линии на крыле пика линейной регрессией по окну точек."""
    if is_left:
        lo = max(0, idx - wing_pts)
        hi = min(len(x_arr), idx + 2)
    else:
        lo = max(0, idx - 1)
        hi = min(len(x_arr), idx + wing_pts + 1)
    xs = x_arr[lo:hi]
    ys = y_arr[lo:hi]
    if len(xs) < 2 or float(np.ptp(xs)) < 1e-12:
        return 0.0
    slope, _ = np.polyfit(xs, ys, 1)  # noqa: PU001 — np.polyfit degree 1 returns (slope, intercept)
    return float(slope)


def make_peakbaseline(
    baselinetype: int,
    i1: int,
    i2: int,
    xdata: Sequence[float],
    ydata: Sequence[float],
) -> BaselineCurve:
    x_arr = np.asarray(xdata, dtype=float)
    y_arr = np.asarray(ydata, dtype=float)
    x_seg = x_arr[i1 : i2 + 1]
    y_seg = y_arr[i1 : i2 + 1]
    x1, x3 = float(x_arr[i1]), float(x_arr[i2])
    y1, y3 = float(y_arr[i1]), float(y_arr[i2])

    if baselinetype == LINEAR_TYPE:
        slope = (y3 - y1) / (x3 - x1) if abs(x3 - x1) > 1e-12 else 0.0
        intercept = y1 - x1 * slope

        def y_expr_lin(x: float | np.ndarray) -> float | np.ndarray:
            return intercept + slope * x

        return BaselineCurve(
            values=np.asarray(y_expr_lin(x_seg), dtype=float),
            expr=y_expr_lin,
        )

    b1 = _estimate_wing_slope(x_arr, y_arr, i1, is_left=True)
    b3 = _estimate_wing_slope(x_arr, y_arr, i2, is_left=False)

    if baselinetype == BEZIER_TYPE:
        a1 = y1 - x1 * b1
        a3 = y3 - x3 * b3
        if abs(b1 - b3) > 1e-6:
            x2_ctrl = float(np.clip((a3 - a1) / (b1 - b3), min(x1, x3), max(x1, x3)))
            y2_ctrl = a1 + b1 * x2_ctrl
        else:
            x2_ctrl = 0.5 * (x1 + x3)
            y2_ctrl = 0.5 * (y1 + y3)

        a_c = x1 - 2.0 * x2_ctrl + x3
        b_c = 2.0 * (x2_ctrl - x1)

        def t_expr(x: float | np.ndarray) -> float | np.ndarray:
            if abs(a_c) < 1e-12:
                return (x - x1) / (x3 - x1) if abs(x3 - x1) > 1e-12 else 0.0
            disc = np.maximum(0.0, b_c**2 - 4.0 * a_c * (x1 - x))
            return (-b_c + np.sqrt(disc)) / (2.0 * a_c)

        def y_expr_bez(x: float | np.ndarray) -> float | np.ndarray:
            t_val = np.clip(t_expr(x), 0.0, 1.0)
            return (
                (1.0 - t_val) ** 2 * y1
                + 2.0 * (1.0 - t_val) * t_val * y2_ctrl
                + t_val**2 * y3
            )

        return BaselineCurve(
            values=np.asarray(y_expr_bez(x_seg), dtype=float),
            expr=y_expr_bez,
        )

    if baselinetype == SIGMOIDAL_TYPE:
        # Уравнение (71) Haines et al. (1998): y_base = (1 - alpha)*y_pre + alpha*y_post
        y_pre = y1 + b1 * (x_seg - x1)
        y_post = y3 + b3 * (x_seg - x3)
        span_x = x3 - x1
        alpha = (
            np.clip((x_seg - x1) / span_x, 0.0, 1.0)
            if abs(span_x) > 1e-12
            else np.zeros_like(x_seg)
        )
        y_base = (1.0 - alpha) * y_pre + alpha * y_post
        for _ in range(3):
            diff = np.abs(y_seg - y_base)
            dx_steps = np.diff(x_seg)
            trap_steps = 0.5 * (diff[:-1] + diff[1:]) * np.abs(dx_steps)
            cum_area = np.concatenate((np.array([0.0]), np.cumsum(trap_steps)))
            total = float(cum_area[-1]) if len(cum_area) else 0.0  # noqa: MI001
            if total > 1e-12:
                alpha = np.clip(cum_area / total, 0.0, 1.0)
            y_base = (1.0 - alpha) * y_pre + alpha * y_post

        return BaselineCurve(
            values=np.asarray(y_base, dtype=float),
            expr=baseline_temp(x_seg, y_base),
        )

    if baselinetype == STEPPED_TYPE:
        # Уравнение (5a) и рис. 8 Richardson & Charsley (1998): ступенчатая экстраполяция ABCD
        y_pre = y1 + b1 * (x_seg - x1)
        y_post = y3 + b3 * (x_seg - x3)
        slope_chord = (y3 - y1) / (x3 - x1) if abs(x3 - x1) > 1e-12 else 0.0
        y_chord = y1 + slope_chord * (x_seg - x1)
        step_idx = int(np.argmax(np.abs(y_seg - y_chord))) if len(x_seg) > 0 else 0
        x_step = float(x_seg[step_idx]) if len(x_seg) > 0 else 0.5 * (x1 + x3)
        y_step_base = np.where(x_seg <= x_step, y_pre, y_post)
        return BaselineCurve(
            values=np.asarray(y_step_base, dtype=float),
            expr=baseline_temp(x_seg, y_step_base),
        )

    raise ValueError(f"Неизвестный тип базовой линии: {baselinetype}")


def calc_peakonset(
    t1: float,
    t2: float,
    data_t: np.ndarray,
    data_dta: np.ndarray,
    data_ddta: np.ndarray,
    expr_baseline: Callable[[float | np.ndarray], float | np.ndarray],
    is_onset: bool,
    peak_exo: int,
) -> OnsetIndices:
    i1 = find_nearest(data_t, t1)
    i2 = find_nearest(data_t, t2)
    if i1 > i2:
        i1, i2 = i2, i1
    if i1 == i2:
        i2 = min(len(data_t), i1 + 1)

    slice_ddta = data_ddta[i1:i2]
    x_increasing = (
        float(data_t[-1]) >= float(data_t[0])  # noqa: MI001
        if len(data_t) >= 2
        else True
    )
    same_sign = (
        (bool(is_onset) == bool(peak_exo))
        if x_increasing
        else (bool(is_onset) != bool(peak_exo))
    )
    bt = float(slice_ddta.max()) if same_sign else np_min_wo_infnan(slice_ddta)
    rel_idx = int(np.argmin(np.abs(slice_ddta - bt)))
    ci = i1 + rel_idx
    xt = float(data_t[ci])
    yt = float(data_dta[ci])
    at = yt - bt * xt

    tangent_vals = at + bt * data_t
    base_vals = np.asarray(expr_baseline(data_t), dtype=float)
    bi = int(np.argmin(np.abs(tangent_vals - base_vals)))
    return OnsetIndices(tangent_idx=ci, baseline_idx=bi)


def fraser_suzuki_curve(
    x: np.ndarray,
    height: float,
    center: float,
    fwhm: float,
    asymmetry: float,
) -> np.ndarray:
    """Асимметричный профиль пика Фрейзера-Сузуки по ур. (12.20) Svoboda & Malek (2018)."""
    x_arr = np.asarray(x, dtype=float)
    w = max(1e-9, abs(float(fwhm)))
    u = (x_arr - float(center)) / w
    a3 = float(asymmetry)
    if abs(a3) < 1e-5:
        return float(height) * np.exp(-4.0 * math.log(2.0) * (u**2))

    arg = 1.0 + 2.0 * a3 * u
    out = np.zeros_like(x_arr, dtype=float)
    valid = arg > 1e-12
    log_term = np.log(arg[valid])
    out[valid] = float(height) * np.exp(-(math.log(2.0) / (a3**2)) * (log_term**2))
    return out


def estimate_fraser_suzuki_asymmetry(
    x_arr: np.ndarray,
    dev_arr: np.ndarray,
    peak_idx: int,
) -> float:
    """Оценивает параметр асимметрии Фрейзера-Сузуки a3 = ln(w_right / w_left) на полувысоте пика."""
    if len(x_arr) < 3 or peak_idx <= 0 or peak_idx >= len(x_arr) - 1:
        return 0.0
    half_h = 0.5 * float(dev_arr[peak_idx])
    if half_h <= 1e-12:
        return 0.0
    above = np.where(dev_arr >= half_h)[0]  # noqa: MI001
    if len(above) < 2:
        return 0.0
    x_left = float(x_arr[int(above[0])])  # noqa: MI001
    x_right = float(x_arr[int(above[-1])])  # noqa: MI001
    x_peak = float(x_arr[peak_idx])
    w_left = abs(x_peak - x_left)
    w_right = abs(x_right - x_peak)
    if w_left <= 1e-9 or w_right <= 1e-9:
        return 0.0
    return float(np.clip(math.log(w_right / w_left), -1.5, 1.5))


def compute_glass_transition_metrics(
    temp_full: np.ndarray,
    y_full: np.ndarray,
    i1: int,
    i2: int,
) -> GlassTransitionMetrics:
    """Вычисляет Tg_mid (ур. 12.3), T_infl и фиктивную температуру Tf Мойнхана (ур. 12.7)."""
    t_arr = np.asarray(temp_full, dtype=float)
    y_arr = np.asarray(y_full, dtype=float)
    t_seg = t_arr[i1 : i2 + 1]
    y_seg = y_arr[i1 : i2 + 1]
    if len(t_seg) < 2:
        val_t = float(t_seg[0]) if len(t_seg) else 0.0  # noqa: MI001
        return GlassTransitionMetrics(
            tg_mid=val_t, t_inflection=val_t, t_fictive=val_t, delta_y_step=0.0
        )

    b_g = _estimate_wing_slope(t_arr, y_arr, i1, is_left=True)
    b_l = _estimate_wing_slope(t_arr, y_arr, i2, is_left=False)
    t1, t2 = float(t_arr[i1]), float(t_arr[i2])
    y1, y2 = float(y_arr[i1]), float(y_arr[i2])

    y_g = y1 + b_g * (t_seg - t1)
    y_l = y2 + b_l * (t_seg - t2)
    denom = y_l - y_g
    safe_denom = np.where(np.abs(denom) > 1e-9, denom, 1.0)
    cp_red = np.where(np.abs(denom) > 1e-9, (y_seg - y_g) / safe_denom, 0.5)

    mid_i = int(np.argmin(np.abs(cp_red - 0.5)))
    tg_mid = float(t_seg[mid_i])
    delta_step = float(denom[mid_i])

    dydt = np.abs(derivative_data(t_seg, y_seg))
    infl_i = int(np.argmax(dydt))
    t_infl = float(t_seg[infl_i])

    # Интеграл равных площадей Мойнхана (ур. 12.7 Svoboda & Malek, 2018)
    order = np.argsort(t_seg)
    t_sorted = t_seg[order]
    cp_sorted = np.clip(cp_red[order], -2.0, 5.0)
    t_star = float(t_sorted[-1])  # noqa: MI001
    t_zero = float(t_sorted[0])  # noqa: MI001
    integral_cp = float(np.trapezoid(cp_sorted, t_sorted))
    t_fictive = float(np.clip(t_star - integral_cp, t_zero, t_star))

    return GlassTransitionMetrics(
        tg_mid=tg_mid,
        t_inflection=t_infl,
        t_fictive=t_fictive,
        delta_y_step=delta_step,
    )


def compute_melting_range_and_tau_metrics(
    time_min: np.ndarray,
    temp_arr: np.ndarray,
    dev_arr: np.ndarray,
    peak_idx: int,
) -> MeltingRangeMetrics:
    """Вычисляет T_init, T_return, постоянную спада tau (с) и T(tp - tau) по реальному ходу T(t)."""
    t_m = np.asarray(time_min, dtype=float)
    temp_v = np.asarray(temp_arr, dtype=float)
    dev_v = np.asarray(dev_arr, dtype=float)
    if len(t_m) < 2 or len(temp_v) < 2:
        v0 = float(temp_v[0]) if len(temp_v) else 0.0  # noqa: MI001
        return MeltingRangeMetrics(
            t_init_dev=v0,
            t_return_dev=v0,
            tau_relax_sec=0.0,
            temp_lag_corrected=v0,
        )

    max_dev = float(dev_v[peak_idx]) if 0 <= peak_idx < len(dev_v) else 0.0
    threshold = max(1e-9, 0.02 * max_dev)
    active_indices = np.where(dev_v >= threshold)[0]  # noqa: MI001
    if len(active_indices) >= 2:
        init_i = int(active_indices[0])  # noqa: MI001
        ret_i = int(active_indices[-1])  # noqa: MI001
    else:
        init_i = 0
        ret_i = len(temp_v) - 1

    t_init = float(temp_v[init_i])
    t_return = float(temp_v[ret_i])

    # Оценка постоянной времени экспоненциальной релаксации спада (после вершины пика)
    tail_dev = dev_v[peak_idx:]
    tail_time_min = t_m[peak_idx:]
    tau_sec = 0.0
    if len(tail_dev) >= 3 and max_dev > 1e-9:
        mask_80 = np.where(tail_dev <= 0.8 * max_dev)[0]  # noqa: MI001
        mask_20 = np.where(tail_dev <= 0.2 * max_dev)[0]  # noqa: MI001
        if len(mask_80) > 0 and len(mask_20) > 0:
            i80 = int(mask_80[0])  # noqa: MI001
            i20 = int(mask_20[0])  # noqa: MI001
            dt_min = float(tail_time_min[i20] - tail_time_min[i80])
            if dt_min > 0.0:
                tau_sec = (dt_min * 60.0) / math.log(0.8 / 0.2)

    t_peak_min = float(t_m[peak_idx])
    tau_min = tau_sec / 60.0
    t_corr_min = max(float(t_m[0]), t_peak_min - tau_min)  # noqa: MI001
    temp_corr = float(np.interp(t_corr_min, t_m, temp_v))

    return MeltingRangeMetrics(
        t_init_dev=t_init,
        t_return_dev=t_return,
        tau_relax_sec=tau_sec,
        temp_lag_corrected=temp_corr,
    )
