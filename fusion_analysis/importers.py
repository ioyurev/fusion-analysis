from __future__ import annotations

import contextlib
import csv
import io
import json
from collections.abc import Callable
from enum import StrEnum
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Literal
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from fusion_common import (
    AdditivePolynomialCalibration,
    ChannelDescriptor,
    CjcData,
    DirectPolynomialCalibration,
    MeasurementManifest,
    MeasurementRecord,
    PolynomialSensorModel,
    Standard,
    evaluate_channel_temperature,
    load_fus,
    parse_csv_columns,
    save_fus,
)
from fusion_common import (
    __version__ as common_version,
)
from loguru import logger as log
from PySide6 import QtWidgets

from fusion_analysis.measurement_data import (
    MeasurementData,
    SegmentTable,
    raw_key_for,
)
from fusion_analysis.version import VERSION

FUSA_EXT_FILTER = "Файлы анализа Fusion (*.fusa)"
ALL_SUPPORTED_FILTER = (
    "Все поддерживаемые файлы (*.fus *.fusa *.vtaz *.tda *.fus-mdt *.fus-fmdt)"
)


def save_fusa(record: MeasurementRecord, path: Path) -> Path:
    """Сохраняет результаты анализа в отдельный файл .fusa без перезаписи сырого файла."""
    target = path if path.suffix.lower() == ".fusa" else path.with_suffix(".fusa")
    save_fus(record, target)
    return target


def _read_vtaz_csv(text_stream: io.TextIOBase) -> tuple[np.ndarray, np.ndarray]:
    content = text_stream.read()
    lines = [
        line.removesuffix(";") for line in content.strip().splitlines() if line.strip()
    ]
    reader = csv.reader(lines)
    next(reader, None)
    x_list: list[float] = []
    y_list: list[float] = []
    for row in reader:
        if len(row) >= 2:
            x_val, y_val, *_ = row
            x_list.append(float(x_val))
            y_list.append(float(y_val))
    return np.array(x_list, dtype=float), np.array(y_list, dtype=float)


def load_vtaz(path: Path) -> MeasurementRecord:
    """Читает архивные файлы .vtaz версий 0.0 и 1.0+."""
    with ZipFile(path, "r", ZIP_DEFLATED) as zipf:
        names = set(zipf.namelist())
        if "manifest.json" in names:
            return load_fus(path)
        meta = json.loads(zipf.read("metadata.json").decode("utf-8"))
        vtaz_ver = str(meta.get("vtaz_version", "0.0"))
        ver_parts = vtaz_ver.split(".")
        first_two = ver_parts[:2]
        ver_num = float(".".join(first_two) if len(first_two) == 2 else vtaz_ver)

        with zipf.open("data_input.csv", "r") as bf:
            text_f = TextIOWrapper(bf, encoding="utf-8")
            time_arr, emf_arr = _read_vtaz_csv(text_f)  # noqa: PU001

        channels: list[ChannelDescriptor] = [
            ChannelDescriptor(column="time", label="Время", unit="s"),
            ChannelDescriptor(column="emf", label="ЭДС", unit="mV"),
        ]
        data_map: dict[str, np.ndarray] = {"time": time_arr, "emf": emf_arr}

        if ver_num >= 1.0:
            cal_raw = json.loads(zipf.read("calibration.json").decode("utf-8"))
            cal_type_raw = cal_raw.get("calibration_type", "linear")
            cal_type: Literal["offset", "linear", "quadratic", "piecewise"] = (
                cal_type_raw
                if cal_type_raw in ("offset", "linear", "quadratic", "piecewise")
                else "linear"
            )
            standards = [
                Standard.model_validate(s) for s in cal_raw.get("standards", [])
            ]
            cal_spec = AdditivePolynomialCalibration(
                name=str(cal_raw.get("name", "")),
                description=str(cal_raw.get("description", "")),
                calibration_type=cal_type,
                coefficients=list(cal_raw.get("coefficients", [0.0, 0.0, 0.0])),
                standards=standards,
            )
            tc_raw = json.loads(zipf.read("thermocouple.json").decode("utf-8"))
            tc_spec = PolynomialSensorModel(
                name="VTA Thermocouple",
                coefficients=list(tc_raw["thermocouple_coefficients"]),
            )
            cjc_raw = json.loads(zipf.read("cjc.json").decode("utf-8"))
            cjc_spec = CjcData(
                temperature=float(cjc_raw.get("temperature", 25.0)),
                e_cold=float(cjc_raw.get("e_cold", 0.0)),
            )
            temp_arr = np.asarray(
                evaluate_channel_temperature(emf_arr, tc_spec, cjc_spec, cal_spec),
                dtype=float,
            )
            data_map["temperature"] = temp_arr
            channels.append(
                ChannelDescriptor(
                    column="temperature",
                    label="Температура",
                    unit="°C",
                    source_columns=["emf"],
                    sensor=tc_spec,
                    cjc=cjc_spec,
                    calibration=cal_spec,
                )
            )
        elif "calibration.json" in names:
            cal0 = json.loads(zipf.read("calibration.json").decode("utf-8"))
            coeffs_desc = [
                float(cal0["c3"]),
                float(cal0["c2"]),
                float(cal0["c1"]),
                float(cal0["c0"]),
            ]
            direct_cal = DirectPolynomialCalibration(coefficients_desc=coeffs_desc)
            temp_arr = np.asarray(direct_cal.apply(emf_arr), dtype=float)
            data_map["temperature"] = temp_arr
            channels.append(
                ChannelDescriptor(
                    column="temperature",
                    label="Температура",
                    unit="°C",
                    source_columns=["emf"],
                    calibration=direct_cal,
                )
            )

    manifest = MeasurementManifest(
        sample=str(meta.get("sample", "")),
        operator=str(meta.get("operator", "")),
        channels=channels,
    )
    return MeasurementRecord(
        manifest=manifest,
        data=data_map,
        source_path=path,
        source_format="VTAZ",
        source_version=vtaz_ver,
    )


def load_tda(path: Path) -> MeasurementRecord:
    """Читает архивные файлы VPTAnalyzer (.tda в кодировке cp1251)."""
    lines_raw = path.read_text(encoding="cp1251").splitlines(keepends=True)
    sample_name = ""
    operator = ""
    coeff_strs: list[str] = []
    start_idx = len(lines_raw)

    for idx, line in enumerate(lines_raw):
        stripped = line.rstrip("\n\r")
        if not stripped:
            continue
        if stripped.startswith("<"):
            if stripped.startswith("<NAME>"):
                sample_name = stripped[7:]
            elif stripped.startswith("<AUTOR>"):
                operator = stripped[8:]
            elif stripped.startswith("<FORMULE>"):
                coeff_strs = stripped[12:].split()
        else:
            start_idx = idx
            break

    lines_data = lines_raw[start_idx:-1] if start_idx < len(lines_raw) else []
    emf_list: list[float] = []
    time_days_list: list[float] = []
    for row_line in lines_data:
        tokens = row_line.strip().split()
        if len(tokens) >= 2:
            e_tok, t_tok, *_ = tokens
            emf_list.append(float(e_tok.replace(",", ".")))
            time_days_list.append(float(t_tok.replace(",", ".")))

    time_arr = np.array(time_days_list, dtype=float) * 86400.0
    emf_arr = np.array(emf_list, dtype=float)

    channels: list[ChannelDescriptor] = [
        ChannelDescriptor(column="time", label="Время", unit="s"),
        ChannelDescriptor(column="emf", label="ЭДС", unit="mV"),
    ]
    data_map: dict[str, np.ndarray] = {"time": time_arr, "emf": emf_arr}

    if coeff_strs:
        try:
            coeffs_desc = [float(item.replace(",", ".")) for item in coeff_strs]
            direct_cal = DirectPolynomialCalibration(coefficients_desc=coeffs_desc)
            temp_arr = np.asarray(direct_cal.apply(emf_arr), dtype=float)
            data_map["temperature"] = temp_arr
            channels.append(
                ChannelDescriptor(
                    column="temperature",
                    label="Температура",
                    unit="°C",
                    source_columns=["emf"],
                    calibration=direct_cal,
                )
            )
        except ValueError as exc:
            log.bind(path=str(path), error=str(exc)).warning(
                "Failed to parse <FORMULE> coefficients in .tda file"
            )

    return MeasurementRecord(
        manifest=MeasurementManifest(
            sample=sample_name,
            operator=operator,
            channels=channels,
        ),
        data=data_map,
        source_path=path,
        source_format="TDA",
        source_version="legacy",
    )


def load_fus_mdt(path: Path) -> MeasurementRecord:
    """Читает архивные файлы ДТА .fus-mdt (v1.0)."""
    with ZipFile(path, "r", ZIP_DEFLATED) as zipf:
        names = set(zipf.namelist())
        if "manifest.json" in names:
            return load_fus(path)
        version_str = zipf.read("VERSION").decode("utf-8").strip()
        with zipf.open("data.csv", "r") as bf:
            text_f = TextIOWrapper(bf, encoding="utf-8")
            cols = parse_csv_columns(text_f)

        info_dict: dict[str, str] = {}
        if "info.json" in names:
            try:
                info_dict = json.loads(zipf.read("info.json").decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                info_dict = {}

        cal_temp_coeffs: list[float] | None = None
        if "calibration.fus-cal" in names:
            cal_bytes = io.BytesIO(zipf.read("calibration.fus-cal"))
            with ZipFile(cal_bytes, "r") as cal_zip:
                if "coeff_temp.csv" in cal_zip.namelist():
                    arr = np.loadtxt(cal_zip.open("coeff_temp.csv"), dtype=float)
                    cal_temp_coeffs = [float(v) for v in np.atleast_1d(arr).tolist()]

    time_arr = cols["Time/s"]
    t1_arr = cols["T1/mV"]
    t2_arr = cols["T2/mV"]
    dta_arr = t1_arr - t2_arr

    channels: list[ChannelDescriptor] = [
        ChannelDescriptor(column="time", label="Время", unit="s"),
        ChannelDescriptor(column="emf_1", label="Термопара 1", unit="mV"),
        ChannelDescriptor(column="emf_2", label="Термопара 2", unit="mV"),
        ChannelDescriptor(
            column="dta",
            label="ДТА",
            unit="mV",
            source_columns=["emf_1", "emf_2"],
            metadata={"exo_up": True},
        ),
    ]
    data_map: dict[str, np.ndarray] = {
        "time": time_arr,
        "emf_1": t1_arr,
        "emf_2": t2_arr,
        "dta": dta_arr,
    }

    if cal_temp_coeffs:
        direct_cal = DirectPolynomialCalibration(coefficients_desc=cal_temp_coeffs)
        temp_arr = np.asarray(direct_cal.apply(t1_arr), dtype=float)
        data_map["temperature"] = temp_arr
        channels.append(
            ChannelDescriptor(
                column="temperature",
                label="Температура",
                unit="°C",
                source_columns=["emf_1"],
                calibration=direct_cal,
            )
        )

    return MeasurementRecord(
        manifest=MeasurementManifest(
            sample=str(info_dict.get("sample", "")),
            operator=str(info_dict.get("operator", "")),
            comment=str(info_dict.get("comment", "")),
            channels=channels,
        ),
        data=data_map,
        source_path=path,
        source_format="FUS-MDT",
        source_version=version_str,
    )


def load_fus_fmdt(path: Path) -> MeasurementRecord:
    """Читает архивные отфильтрованные файлы .fus-fmdt (v1.0)."""
    with ZipFile(path, "r", ZIP_DEFLATED) as zipf:
        if "manifest.json" in zipf.namelist():
            return load_fus(path)
        version_str = zipf.read("VERSION").decode("utf-8").strip()
        with zipf.open("data.csv", "r") as bf:
            text_f = TextIOWrapper(bf, encoding="utf-8")
            cols = parse_csv_columns(text_f)

    channels: list[ChannelDescriptor] = []
    data_map: dict[str, np.ndarray] = {}
    for col_str, arr in cols.items():
        if "/" in col_str:
            name_part, unit_part = col_str.split("/", maxsplit=1)  # noqa: PU001
        else:
            name_part, unit_part = col_str, ""
        norm_key = (
            "time"
            if name_part == "Time"
            else ("temperature" if name_part == "Temp." else name_part.lower())
        )
        meta = {"exo_up": True} if norm_key == "dta" else {}
        channels.append(
            ChannelDescriptor(
                column=norm_key,
                label=name_part,
                unit=unit_part,
                metadata=meta,
            )
        )
        data_map[norm_key] = arr

    return MeasurementRecord(
        manifest=MeasurementManifest(channels=channels),
        data=data_map,
        source_path=path,
        source_format="FUS-FMDT",
        source_version=version_str,
    )


FormatLoader = Callable[[Path], MeasurementRecord]

FORMAT_LOADERS: dict[str, FormatLoader] = {
    ".tda": load_tda,
    ".vtaz": load_vtaz,
    ".fus-mdt": load_fus_mdt,
    ".fus-fmdt": load_fus_fmdt,
    ".fus": load_fus,
    ".fusa": load_fus,
}


def load_measurement(path: Path) -> MeasurementRecord:
    """Загружает любой поддерживаемый анализатором формат измерений."""
    suffix = path.suffix.lower()
    loader = FORMAT_LOADERS.get(suffix)
    if loader is None:
        raise ValueError(f"Неподдерживаемый формат файла измерения: {suffix}")
    return loader(path)


class ImportSource(StrEnum):
    FUSION = "fusion"
    NETZSCH = "netzsch"
    SETARAM = "setaram"


def pick_open_measurement_path(
    parent: QtWidgets.QWidget | None = None,
) -> Path | None:
    fname, _ = QtWidgets.QFileDialog.getOpenFileName(  # noqa: PU001 — Qt QFileDialog API returns (path, filter)
        parent,
        "Открыть измерение или проект анализа",
        "",
        ALL_SUPPORTED_FILTER,
    )
    return Path(fname) if fname else None


def pick_save_fusa_path(
    source_path: Path | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> Path | None:
    """Запрашивает путь сохранения в отдельный файл анализа .fusa (сырые файлы не перезаписываются)."""
    default_path = (
        source_path.with_suffix(".fusa")
        if source_path is not None
        else Path("analysis.fusa")
    )
    fname, _ = QtWidgets.QFileDialog.getSaveFileName(  # noqa: PU001 — Qt QFileDialog API returns (path, filter)
        parent,
        "Сохранить результаты анализа (.fusa)",
        str(default_path),
        FUSA_EXT_FILTER,
    )
    if not fname:
        return None
    target = Path(fname)
    return target if target.suffix.lower() == ".fusa" else target.with_suffix(".fusa")


def record_to_measurement_data(record: MeasurementRecord) -> MeasurementData:
    """Преобразует MeasurementRecord в многоканальный MeasurementData."""
    seg: SegmentTable = {}
    units: dict[str, Any] = {}
    available: list[str] = []

    seg["Time"] = np.asarray(record.time_array, dtype=float) / 60.0
    units["Time"] = "min"

    temp_col = next(
        (k for k in ("temperature", "temp_1", "Temp.") if k in record.data),
        None,
    )
    emf_col = next(
        (k for k in ("emf", "emf_1", "EMF") if k in record.data),
        None,
    )

    if temp_col is not None:
        raw_t = np.asarray(record.data[temp_col], dtype=float)
        seg[raw_key_for("Temp.")] = raw_t.copy()
        sm_t_key = f"{temp_col}__smoothed"
        seg["Temp."] = (
            np.asarray(record.data[sm_t_key], dtype=float)
            if sm_t_key in record.data
            else raw_t.copy()
        )
        desc_t = record.get_descriptor(temp_col)
        units["Temp."] = desc_t.unit if (desc_t and desc_t.unit) else "°C"
        available.append("Temp.")

    if emf_col is not None:
        raw_e = np.asarray(record.data[emf_col], dtype=float)
        seg[raw_key_for("EMF")] = raw_e.copy()
        sm_e_key = f"{emf_col}__smoothed"
        seg["EMF"] = (
            np.asarray(record.data[sm_e_key], dtype=float)
            if sm_e_key in record.data
            else raw_e.copy()
        )
        desc_e = record.get_descriptor(emf_col)
        units["EMF"] = desc_e.unit if (desc_e and desc_e.unit) else "mV"
        available.append("EMF")

    raw_dta_col = next(
        (k for k in ("dta", "dta_1_2", "dsc", "heat_flow", "DTA") if k in record.data),
        None,
    )
    exo_sign = "+"
    raw_arr: np.ndarray | None = None
    if raw_dta_col is not None:
        raw_arr = np.asarray(record.data[raw_dta_col], dtype=float)
        desc_dta = record.get_descriptor(raw_dta_col)
        units["DTA"] = desc_dta.unit if (desc_dta and desc_dta.unit) else "mV"
        if desc_dta and desc_dta.metadata.get("exo_up") is False:
            exo_sign = "-"
    elif "emf_1" in record.data and "emf_2" in record.data:
        raw_arr = np.asarray(record.data["emf_1"] - record.data["emf_2"], dtype=float)
        units["DTA"] = "mV"

    if raw_arr is not None:
        seg[raw_key_for("DTA")] = raw_arr.copy()
        sm_dta_key = (
            "dta_smoothed"
            if "dta_smoothed" in record.data
            else f"{raw_dta_col or 'dta'}__smoothed"
        )
        if sm_dta_key in record.data:
            seg["DTA"] = np.asarray(record.data[sm_dta_key], dtype=float)
        else:
            seg["DTA"] = raw_arr.copy()
        if "DTA" not in available:
            available.insert(0, "DTA")

    if not available:
        raise ValueError("В файле измерения не найдено аналитических каналов")

    mass_col = next((k for k in ("mass", "Mass", "tg") if k in record.data), None)
    has_mass = mass_col is not None
    if mass_col is not None:
        raw_m = np.asarray(record.data[mass_col], dtype=float)
        seg[raw_key_for("Mass")] = raw_m.copy()
        sm_m_key = f"{mass_col}__smoothed"
        seg["Mass"] = (
            np.asarray(record.data[sm_m_key], dtype=float)
            if sm_m_key in record.data
            else raw_m.copy()
        )
        desc_m = record.get_descriptor(mass_col)
        units["Mass"] = desc_m.unit if (desc_m and desc_m.unit) else "%"
        available.append("Mass")

    state = dict(record.manifest.analysis_state)
    sm_windows: dict[str, int] = dict(state.get("smoothing_windows", {}))
    sm_desc = record.get_descriptor("dta_smoothed")
    if sm_desc is not None and "DTA" not in sm_windows:
        sm_windows["DTA"] = int(sm_desc.metadata.get("smoothing_window", 8))

    info: dict[str, Any] = {
        "sample": record.manifest.sample,
        "operator": record.manifest.operator,
        "instrument": record.manifest.instrument,
        "software_version": record.manifest.software_version,
        "common_version": record.manifest.common_version,
        "sample_mass_mg": record.manifest.sample_mass_mg,
        "crucible": record.manifest.crucible,
        "atmosphere": record.manifest.atmosphere,
        "comment": record.manifest.comment,
        "version": record.source_version,
        "EXO": exo_sign,
        "raw_dta_column": raw_dta_col or "dta",
        "smoothing_window": sm_windows.get("DTA", 1),
    }
    m_data = MeasurementData(
        segments=[seg],
        info=info,
        units=units,
        hasMassData=has_mass,
        record=record,
        source_path=record.source_path,
        available_channels=available,
        smoothing_windows=sm_windows,
        analysis_state=state,
    )
    for ch_name, win_val in sm_windows.items():
        if win_val > 1 and ch_name in m_data.available_channels:
            m_data.apply_channel_smoothing(ch_name, win_val)
    for d_spec in state.get("computed_derivatives", []):
        y_c = str(d_spec.get("y_col", ""))
        x_c = str(d_spec.get("x_col", ""))
        ord_v = int(d_spec.get("order", 1))
        if y_c and x_c:
            with contextlib.suppress(KeyError, ValueError):
                ch_d = m_data.compute_derivative_channel(y_c, x_c, order=ord_v)
                if sm_windows.get(ch_d, 1) > 1:
                    m_data.apply_channel_smoothing(ch_d, sm_windows[ch_d])
    return m_data


def save_measurement_analysis(
    measurement: MeasurementData,
    target_path: Path,
) -> Path:
    """Сохраняет все сглаженные кривые и состояние разметки в отдельный файл .fusa."""
    fusa_path = (
        target_path
        if target_path.suffix.lower() == ".fusa"
        else target_path.with_suffix(".fusa")
    )
    if (
        measurement.source_path is not None
        and measurement.source_path.suffix.lower() != ".fusa"
        and fusa_path.resolve() == measurement.source_path.resolve()
    ):
        raise ValueError("Запрещено перезаписывать исходный файл сырого измерения.")

    first_seg, *_ = measurement.segments
    rec = measurement.record
    if rec is None:
        channels = [
            ChannelDescriptor(column="time", label="Время", unit="s"),
        ]
        data_map: dict[str, np.ndarray] = {
            "time": np.asarray(first_seg["Time"], dtype=float) * 60.0,
        }
        if "DTA" in first_seg:
            data_map["dta"] = first_seg.get(raw_key_for("DTA"), first_seg["DTA"])
            channels.append(
                ChannelDescriptor(
                    column="dta",
                    label="ДТА",
                    unit=str(measurement.units.get("DTA", "mV")),
                    metadata={"exo_up": measurement.exo == 1},
                )
            )
        if "Temp." in first_seg:
            data_map["temperature"] = first_seg.get(
                raw_key_for("Temp."), first_seg["Temp."]
            )
            channels.append(
                ChannelDescriptor(column="temperature", label="Температура", unit="°C")
            )
        if "EMF" in first_seg:
            data_map["emf"] = first_seg.get(raw_key_for("EMF"), first_seg["EMF"])
            channels.append(ChannelDescriptor(column="emf", label="ЭДС", unit="mV"))
        if "Mass" in first_seg:
            data_map["mass"] = first_seg.get(raw_key_for("Mass"), first_seg["Mass"])
            channels.append(ChannelDescriptor(column="mass", label="Масса", unit="%"))
        rec = MeasurementRecord(
            manifest=MeasurementManifest(
                sample=str(measurement.info.get("sample", "")),
                operator=str(measurement.info.get("operator", "")),
                comment=str(measurement.info.get("comment", "")),
                channels=channels,
            ),
            data=data_map,
        )
        measurement.record = rec

    measurement.sync_smoothed_to_record()
    measurement.analysis_state["smoothing_windows"] = dict(
        measurement.smoothing_windows
    )
    rec.manifest.software_version = VERSION
    rec.manifest.common_version = common_version
    rec.manifest.analysis_state = dict(measurement.analysis_state)
    return save_fusa(rec, fusa_path)


def load_fusion_measurement(path: Path | str) -> MeasurementData:
    return record_to_measurement_data(load_measurement(Path(path)))


def _extract_segment(
    table: SegmentTable,
    mask: np.ndarray | None,
    has_mass: bool,
) -> SegmentTable:
    seg: SegmentTable = {}
    for key in ("Time", "Temp.", "DTA"):
        arr = table[key]
        seg[key] = arr[mask].copy() if mask is not None else arr.copy()
    if has_mass and "Mass" in table:
        arr_m = table["Mass"]
        seg["Mass"] = arr_m[mask].copy() if mask is not None else arr_m.copy()
    return seg


def import_netzsch_txt(filepath: Path) -> MeasurementData:
    lines = filepath.read_text(encoding="latin1", errors="replace").splitlines(
        keepends=True
    )
    info: dict[str, str] = {}
    units: dict[str, Any] = {}
    table: SegmentTable = {}
    for index, line in enumerate(lines):
        if line.startswith("##"):
            for hdr_line in lines[: index - 1]:
                if ":" in hdr_line:
                    k, v = hdr_line[1:].split(":", maxsplit=1)  # noqa: PU001
                    info[k] = v[:-1]
            if info.get("DECIMAL") != "POINT":
                raise RuntimeError(
                    f"Десятичный разделитель {info.get('DECIMAL')} не распознан."
                )
            if info.get("SEPARATOR") != "SEMICOLON":
                raise RuntimeError(f"Разделитель {info.get('SEPARATOR')} не распознан.")
            first_line, *body_lines = lines[index:]
            headers = first_line[2:-1].split(";")
            params: list[str] = []
            for col in headers:
                if "/" in col:
                    param, unit = col.split("/", maxsplit=1)  # noqa: PU001
                    params.append(param)
                    units[param] = unit.strip()
                else:
                    params.append(col)
                    units[col] = ""
            values = [ln.split(";") for ln in body_lines[:-1] if ln.strip()]
            np_values = np.array(values, dtype=float).transpose()
            for col_i, param in enumerate(params):
                table[param] = np.asarray(np_values[col_i], dtype=float)
            if "Time" in table:
                unit_time = str(units.get("Time", "")).lower()
                if "s" in unit_time or unit_time == "":
                    table["Time"] = table["Time"] / 60.0
                    units["Time"] = "min"
            break

    is_multi = "-" in info.get("SEGMENT", "")
    has_mass = "Mass" in table
    segments: list[SegmentTable] = []
    if is_multi and "Segment" in table:
        seg_col = table["Segment"]
        for seg_num in np.unique(seg_col):
            segments.append(_extract_segment(table, seg_col == seg_num, has_mass))
    else:
        segments.append(_extract_segment(table, None, has_mass))
    return MeasurementData(
        info=info,
        segments=segments,
        units=units,
        hasMassData=has_mass,
        source_path=filepath,
    )


def import_setaram_txt(path: Path, startmass: float) -> MeasurementData:
    lines = path.read_text(encoding="cp1251", errors="replace").splitlines()
    reader = csv.reader(lines[1:], delimiter="\t")
    header_row = next(reader, [])
    next(reader, None)

    col_idx = {name.strip(): idx for idx, name in enumerate(header_row)}
    idx_time = col_idx.get("Time", 0)
    idx_temp = col_idx.get("Sample temperature", 1)
    idx_dta = col_idx.get("HeatFlow", 2)
    idx_tg = col_idx.get("TG")

    t_list: list[float] = []
    temp_list: list[float] = []
    dta_list: list[float] = []
    tg_list: list[float] = []

    for row in reader:
        if len(row) <= max(idx_time, idx_temp, idx_dta):
            continue
        try:
            t_list.append(float(row[idx_time].strip().replace(",", ".")))
            temp_list.append(float(row[idx_temp].strip().replace(",", ".")))
            dta_list.append(float(row[idx_dta].strip().replace(",", ".")))
            if idx_tg is not None and idx_tg < len(row):
                tg_list.append(float(row[idx_tg].strip().replace(",", ".")))
        except ValueError as exc:
            log.bind(path=str(path), error=str(exc)).warning(
                "Skipping malformed Setaram data row"
            )
            continue

    dta_arr = np.array(dta_list, dtype=float)
    seg: SegmentTable = {
        "Time": np.array(t_list, dtype=float) / 60.0,
        "Temp.": np.array(temp_list, dtype=float),
        "DTA": dta_arr,
    }
    has_mass = bool(tg_list) and startmass > 0
    if has_mass:
        tg_arr = np.array(tg_list, dtype=float)
        seg["Mass"] = 100.0 * (tg_arr + startmass) / startmass

    return MeasurementData(
        segments=[seg],
        info={
            "EXO": "+",
            "sample_mass_mg": startmass if startmass > 0 else None,
        },
        units={
            "Time": "min",
            "Temp.": "°C",
            "DTA": "mW",
            "Mass": "%",
        },
        hasMassData=has_mass,
        source_path=path,
    )
