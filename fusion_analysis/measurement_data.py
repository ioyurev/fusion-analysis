from __future__ import annotations

from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

import numpy as np
from fusion_common import ChannelKey, MeasurementRecord

from fusion_analysis.helpers import (
    centered_moving_average,
    derivative_data,
    second_derivative_data,
)

if TYPE_CHECKING:
    from pathlib import Path


class AxisChannel(StrEnum):
    TIME = "Time"
    TEMP = "Temp."
    DTA = "DTA"
    EMF = "EMF"
    MASS = "Mass"


SegmentTable = dict[str, np.ndarray]

RAW_PREFIX = "__raw__"


def raw_key_for(channel: str) -> str:
    return f"{RAW_PREFIX}{channel}"


class ThermalType(Enum):
    COOL = 0
    HEAT = 1
    ISOTHERMAL = 2


def classify_segment_thermal_type(
    vals: np.ndarray,
    iso_tol: float = 2.0,
) -> tuple[ThermalType, str]:
    """Определяет тип термического сегмента (HEAT, COOL, ISOTHERMAL) и подпись диапазона."""
    if len(vals) == 0:
        return ThermalType.ISOTHERMAL, "—"
    first_v = float(vals[0])  # noqa: MI001
    last_v = float(vals[-1])  # noqa: MI001
    min_v = float(np.min(vals))
    max_v = float(np.max(vals))
    span = max_v - min_v
    t1, t2 = round(first_v), round(last_v)

    if span <= iso_tol:
        return ThermalType.ISOTHERMAL, f"Изотерма ~{round(float(np.mean(vals)))}"
    if abs(last_v - first_v) <= iso_tol:
        # Неразрезанный цикл нагрева и охлаждения
        peak_ext = (
            round(max_v) if (max_v - first_v) >= (first_v - min_v) else round(min_v)
        )
        t_type = ThermalType.HEAT if peak_ext >= t1 else ThermalType.COOL
        return t_type, f"{t1} → {peak_ext} → {t2}"
    if last_v > first_v:
        return ThermalType.HEAT, f"{t1} - {t2}"
    return ThermalType.COOL, f"{t1} - {t2}"


class MeasurementData:
    def __init__(
        self,
        segments: list[SegmentTable],
        info: dict[str, Any],
        units: dict[str, Any],
        hasMassData: bool,
        record: MeasurementRecord | None = None,
        source_path: Path | None = None,
        available_channels: list[str] | None = None,
        smoothing_windows: dict[str, int] | None = None,
        analysis_state: dict[str, Any] | None = None,
    ) -> None:
        self.segments = segments
        for seg in self.segments:
            for col in list(seg.keys()):
                if col != "Time" and not col.startswith(RAW_PREFIX):
                    rk = raw_key_for(col)
                    if rk not in seg:
                        seg[rk] = seg[col].copy()

        self.info = info
        self.units = units
        self.has_massdata = hasMassData
        self.has_tempdata = "Temp." in self.units
        self.record = record
        self.source_path = source_path

        if available_channels is not None:
            self.available_channels = list(available_channels)
        elif self.segments:
            first_s, *_ = self.segments
            self.available_channels = [
                k
                for k in first_s
                if k != "Time"
                and not k.startswith(RAW_PREFIX)
                and not k.startswith("d")
            ]
        else:
            self.available_channels = ["DTA"]

        self.smoothing_windows: dict[str, int] = (
            dict(smoothing_windows) if smoothing_windows else {}
        )
        self.analysis_state: dict[str, Any] = (
            dict(analysis_state) if analysis_state else {}
        )

        exo_str = str(self.info.get("EXO", "+"))
        if "+" in exo_str:
            self.exo = 1
        elif "-" in exo_str:
            self.exo = 0
        else:
            raise RuntimeError(f"Значение EXO {exo_str!r} не распознано.")

    def apply_channel_smoothing(self, channel: str, window_spin: int) -> None:
        """Неразрушающе пересчитывает сглаживание выбранного канала по его исходному ряду."""
        win_pts = max(1, 10 * int(window_spin)) if window_spin > 1 else 1
        self.smoothing_windows[channel] = int(window_spin)
        rk = raw_key_for(channel)
        for seg in self.segments:
            if rk in seg:
                raw_arr = seg[rk]
            elif channel in seg:
                raw_arr = seg[channel].copy()
                seg[rk] = raw_arr
            else:
                continue
            seg[channel] = (
                centered_moving_average(raw_arr, win_pts)
                if win_pts > 1
                else raw_arr.copy()
            )
        for d_spec in list(self.analysis_state.get("computed_derivatives", [])):
            y_c = str(d_spec.get("y_col", ""))
            x_c = str(d_spec.get("x_col", ""))
            ord_v = int(d_spec.get("order", 1))
            if channel in (y_c, x_c) and y_c and x_c:
                self.compute_derivative_channel(y_c, x_c, order=ord_v)

    def compute_derivative_channel(
        self,
        y_col: str,
        x_col: str,
        order: int = 1,
    ) -> str:
        """Вычисляет 1-ю или 2-ю производную dY/dX (или d²Y/dX²) для любой пары каналов и добавляет её как 1D-канал оси Y."""
        if order not in (1, 2):
            raise ValueError("Порядок производной должен быть 1 или 2")
        col_name = (
            f"d({y_col})/d({x_col})" if order == 1 else f"d²({y_col})/d({x_col})²"
        )
        rk = raw_key_for(col_name)
        for seg in self.segments:
            if y_col not in seg or x_col not in seg:
                raise KeyError(f"Каналы '{y_col}' или '{x_col}' отсутствуют в сегменте")
            x_arr = np.asarray(seg[x_col], dtype=float)
            y_arr = np.asarray(seg[y_col], dtype=float)
            d_arr = (
                derivative_data(x_arr, y_arr)
                if order == 1
                else second_derivative_data(x_arr, y_arr)
            )
            seg[rk] = d_arr.copy()
            win_spin = self.smoothing_windows.get(col_name, 1)
            win_pts = max(1, 10 * int(win_spin)) if win_spin > 1 else 1
            seg[col_name] = (
                centered_moving_average(d_arr, win_pts) if win_pts > 1 else d_arr.copy()
            )

        u_y = str(self.units.get(y_col, "")).strip() or "1"
        u_x = str(self.units.get(x_col, "")).strip() or "1"
        self.units[col_name] = f"{u_y}/{u_x}" if order == 1 else f"{u_y}/{u_x}²"
        if col_name not in self.available_channels:
            self.available_channels.append(col_name)

        deriv_specs: list[dict[str, Any]] = list(
            self.analysis_state.get("computed_derivatives", [])
        )
        spec_entry = {"y_col": y_col, "x_col": x_col, "order": order}
        if spec_entry not in deriv_specs:
            deriv_specs.append(spec_entry)
        self.analysis_state["computed_derivatives"] = deriv_specs
        return col_name

    def sync_smoothed_to_record(self) -> None:
        """Синхронизирует сглаженные каналы в MeasurementRecord (единый SSOT)."""
        if self.record is None or not self.segments:
            return
        first_seg, *_ = self.segments
        col_map: dict[str, str] = {
            AxisChannel.DTA: str(self.info.get("raw_dta_column", ChannelKey.DTA)),
            AxisChannel.TEMP: (
                ChannelKey.TEMPERATURE
                if ChannelKey.TEMPERATURE in self.record.data
                else "temp_1"
            ),
            AxisChannel.EMF: (
                ChannelKey.EMF_1 if ChannelKey.EMF_1 in self.record.data else "emf"
            ),
            AxisChannel.MASS: ChannelKey.MASS,
        }
        for ui_ch, win_spin in self.smoothing_windows.items():
            if ui_ch in first_seg and win_spin > 1:
                src_col = col_map.get(ui_ch, ui_ch.lower())
                self.record.set_smoothed_channel(
                    source_column=src_col,
                    smoothed_values=first_seg[ui_ch],
                    smoothing_window=win_spin,
                    label=f"{ui_ch} (сглаж.)",
                )
