from __future__ import annotations

from typing import Any

import numpy as np
import pyqtgraph as pg
from fusion_common import resolve_ui_icon
from PySide6 import QtCore, QtGui, QtWidgets

from fusion_analysis.helpers import fraser_suzuki_curve
from fusion_analysis.segment import (
    CurveSegment,
    OnsetLine,
    Peak,
    SegmentDTA,
)


def color_to_qcolor(c: Any) -> QtGui.QColor:
    if isinstance(c, QtGui.QColor):
        return c
    if isinstance(c, (tuple, list)) and len(c) >= 3:
        r_f, g_f, b_f, *_ = c
        if max(float(r_f), float(g_f), float(b_f)) <= 1.0:
            return QtGui.QColor(
                int(255 * float(r_f)),
                int(255 * float(g_f)),
                int(255 * float(b_f)),
            )
        return QtGui.QColor(int(r_f), int(g_f), int(b_f))
    return QtGui.QColor(str(c))


class SegmentPropertiesWindow(QtWidgets.QDialog):
    def __init__(
        self,
        segment: CurveSegment,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Свойства сегмента")
        self.setFixedSize(256, 128)
        self.changes_are_made = False
        self.color = color_to_qcolor(segment.get_color())

        grid = QtWidgets.QGridLayout(self)
        grid.addWidget(QtWidgets.QLabel("Цвет:"), 0, 0)
        self.w_color = QtWidgets.QWidget()
        self.w_color.setMinimumSize(24, 24)
        self.w_color.setStyleSheet(f"background-color: {self.color.name()};")
        self.btn_color = QtWidgets.QPushButton("Изменить")
        self.btn_color.clicked.connect(self.change_color)
        grid.addWidget(self.w_color, 0, 1)
        grid.addWidget(self.btn_color, 0, 2)
        grid.setColumnStretch(3, 1)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        grid.addWidget(btns, 1, 0, 1, 4)

    def change_color(self) -> None:
        dlg = QtWidgets.QColorDialog(self)
        dlg.setCurrentColor(self.color)
        color = dlg.getColor()
        if color.isValid():
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")
            self.color = color
            self.w_color.setStyleSheet(f"background-color: {self.color.name()};")


class ConversionCurveDialog(QtWidgets.QDialog):
    """Окно кривой степени превращения / доли фазы alpha(T, t) по пику на PyQtGraph."""

    def __init__(
        self,
        peak: Peak,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Кривая степени превращения α(T, t)")
        self.resize(740, 450)
        outer = QtWidgets.QVBoxLayout(self)
        lbl_coords = QtWidgets.QLabel("Курсор: —")
        lbl_coords.setStyleSheet("font-family: Consolas, monospace;")
        outer.addWidget(lbl_coords)
        layout = QtWidgets.QHBoxLayout()
        outer.addLayout(layout, 1)

        is_dark = (
            QtGui.QGuiApplication.styleHints().colorScheme()
            == QtCore.Qt.ColorScheme.Dark
        )
        bg_hex = "#0F172A" if is_dark else "#FFFFFF"
        fg_hex = "#CBD5E1" if is_dark else "#1E293B"

        plot_alpha = pg.PlotWidget(title="α(t)")
        plot_alpha.setBackground(bg_hex)
        plot_alpha.showGrid(x=True, y=True, alpha=0.3)
        plot_alpha.setLabel("bottom", "Время, мин", color=fg_hex)
        plot_alpha.setLabel("left", "Степень превращения α, %", color=fg_hex)
        alpha_pct = np.asarray(peak.conversion_alpha, dtype=float) * 100.0
        plot_alpha.plot(
            np.asarray(peak.df["Time"], dtype=float),
            alpha_pct,
            pen=pg.mkPen("#0D9AFD", width=2),
        )
        half_line = pg.InfiniteLine(
            pos=50.0,
            angle=0,
            pen=pg.mkPen("#94A3B8", width=1, style=QtCore.Qt.PenStyle.DashLine),
        )
        plot_alpha.addItem(half_line)

        plot_rate = pg.PlotWidget(
            title=f"dα/dt и профиль Фрейзера-Сузуки (T₅₀%={peak.temp_half:.1f})"
        )
        plot_rate.setBackground(bg_hex)
        plot_rate.showGrid(x=True, y=True, alpha=0.3)
        plot_rate.setLabel("bottom", str(peak.temp_axis), color=fg_hex)
        plot_rate.setLabel("left", "Скорость dα/dt, мин⁻¹", color=fg_hex)
        plot_rate.addLegend()

        t_vals = np.asarray(peak.df[peak.temp_axis], dtype=float)
        rate_vals = np.asarray(peak.conversion_rate, dtype=float)
        plot_rate.plot(
            t_vals,
            rate_vals,
            pen=pg.mkPen("#FD700D", width=2),
            name="dα/dt (эксп.)",
        )
        if len(rate_vals) > 0 and peak.fwhm_temp > 1e-6:
            r_max = float(np.max(rate_vals))
            fs_fit = fraser_suzuki_curve(
                t_vals,
                height=r_max,
                center=peak.temp_peak,
                fwhm=peak.fwhm_temp,
                asymmetry=peak.asymmetry_a3,
            )
            plot_rate.plot(
                t_vals,
                fs_fit,
                pen=pg.mkPen(fg_hex, width=1.6, style=QtCore.Qt.PenStyle.DashLine),
                name=f"Fraser-Suzuki (a3={peak.asymmetry_a3:.2f})",
            )

        def _on_move_alpha(pos: QtCore.QPointF) -> None:
            p_item = plot_alpha.getPlotItem()
            if p_item and p_item.vb.sceneBoundingRect().contains(pos):
                pt = p_item.vb.mapSceneToView(pos)
                lbl_coords.setText(f"α(t): t = {pt.x():.3f} мин | α = {pt.y():.2f} %")

        def _on_move_rate(pos: QtCore.QPointF) -> None:
            p_item = plot_rate.getPlotItem()
            if p_item and p_item.vb.sceneBoundingRect().contains(pos):
                pt = p_item.vb.mapSceneToView(pos)
                lbl_coords.setText(
                    f"dα/dt: {peak.temp_axis} = {pt.x():.2f} | "
                    f"dα/dt = {pt.y():.4f} мин⁻¹"
                )

        plot_alpha.scene().sigMouseMoved.connect(_on_move_alpha)
        plot_rate.scene().sigMouseMoved.connect(_on_move_rate)
        layout.addWidget(plot_alpha, 1)
        layout.addWidget(plot_rate, 1)


class PeakPropertiesWindow(QtWidgets.QDialog):
    def __init__(
        self,
        peak: Peak,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.peak = peak
        self.setWindowTitle("Свойства пика / интервала")
        self.resize(380, 300)
        self.changes_are_made = False

        layout = QtWidgets.QVBoxLayout(self)
        info_box = QtWidgets.QTextEdit()
        info_box.setReadOnly(True)
        tg = peak.tg_metrics
        dm_str = (
            f" ({peak.delta_mass_mg:+.3f} мг)" if peak.delta_mass_mg is not None else ""
        )
        sta_lines = ""
        if (
            peak.sync_mass_change_pct is not None
            and peak.sync_mass_start_pct is not None
        ):
            sync_mg_s = (
                f" ({peak.sync_mass_change_mg:+.3f} мг)"
                if peak.sync_mass_change_mg is not None
                else ""
            )
            eff_s = (
                f"\nЭффект на ед. прореагировавшей массы (ур. 1): {peak.effect_per_reacted_mass}"
                if peak.effect_per_reacted_mass is not None
                else "\nТип процесса: переход без существенного изменения массы"
            )
            sta_lines = (
                f"\n--- Синхронный анализ ТГА-ДТА (STA) ---\n"
                f"Масса к началу пика: {peak.sync_mass_start_pct:.2f} % | "
                f"Δm под пиком: {peak.sync_mass_change_pct:+.3f} %{sync_mg_s}"
                f"{eff_s}"
            )
        mm = peak.melting_metrics
        info_box.setPlainText(
            f"Площадь: {peak.area}\n"
            f"Вершина пика (Tp): {peak.temp_peak:.2f} (tp: {peak.t_peak:.3f} мин)\n"
            f"Точка 50% превращения (T50%): {peak.temp_half:.2f}\n"
            f"Высота пика (Hp): {peak.peak_height:.4f} | Полуширина (FWHM): {peak.fwhm_temp:.2f}\n"
            f"Асимметрия Фрейзера-Сузуки (a3): {peak.asymmetry_a3:+.3f}\n"
            f"Перепад на границах (ΔY): {peak.delta_y:+.4f}{dm_str}\n"
            f"--- Интервал плавления и релаксация ---\n"
            f"Первое отклонение T_init: {mm.t_init_dev:.2f} | Возврат T_ret: {mm.t_return_dev:.2f}\n"
            f"Релаксация спада τ: {mm.tau_relax_sec:.2f} с | Оценка T(tp - τ): {mm.temp_lag_corrected:.2f}\n"
            f"--- Метрики ступени стеклования ---\n"
            f"Tg (mid, Cp_red=0.5): {tg.tg_mid:.2f} | T перегиба: {tg.t_inflection:.2f}\n"
            f"Фиктивная температура Мойнхана (Tf): {tg.t_fictive:.2f} | Скачок ΔY: {tg.delta_y_step:+.4f}"
            f"{sta_lines}"
        )
        layout.addWidget(info_box, 1)

        self.checkbox_label = QtWidgets.QCheckBox("Отображать подпись на графике")
        self.checkbox_label.setChecked(peak.label_enabled)
        self.checkbox_label.stateChanged.connect(self.change_label)
        layout.addWidget(self.checkbox_label)

        self.checkbox_delta_mode = QtWidgets.QCheckBox(
            "Показывать перепад ΔY вместо площади (для ступеней ТГА)"
        )
        self.checkbox_delta_mode.setChecked(peak.show_delta_y_in_label)
        self.checkbox_delta_mode.stateChanged.connect(self.change_label)
        layout.addWidget(self.checkbox_delta_mode)

        btn_alpha = QtWidgets.QPushButton(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.DocumentProperties,
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogInfoView,
            ),
            "График степени превращения α(T, t)",
        )
        btn_alpha.clicked.connect(
            lambda: ConversionCurveDialog(self.peak, parent=self).exec()
        )
        layout.addWidget(btn_alpha)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def change_label(self) -> None:
        if not self.changes_are_made:
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")


class OnsetPropertiesWindow(QtWidgets.QDialog):
    def __init__(
        self,
        onsetline: OnsetLine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.onsetline = onsetline
        super().__init__(parent)
        self.setFixedSize(256, 200)
        self.changes_are_made = False
        self.setWindowTitle(
            "Свойства начала пика" if self.onsetline.is_onset else "Свойства конца пика"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("<b>Отображение информации</b>"))
        self.checkbox_label = QtWidgets.QCheckBox("Подпись")
        self.checkbox_time = QtWidgets.QCheckBox("Время")
        self.checkbox_temp = QtWidgets.QCheckBox("Температура")
        self.checkbox_dta = QtWidgets.QCheckBox("ДТА")

        self.checkbox_label.setChecked(self.onsetline.label_enabled)
        self.checkbox_time.setChecked(self.onsetline.label_time_enabled)
        self.checkbox_temp.setChecked(self.onsetline.label_temp_enabled)
        self.checkbox_dta.setChecked(self.onsetline.label_dta_enabled)

        for cb in (
            self.checkbox_label,
            self.checkbox_time,
            self.checkbox_temp,
            self.checkbox_dta,
        ):
            cb.stateChanged.connect(self.change_label)
            layout.addWidget(cb)
        layout.addStretch()

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def change_label(self) -> None:
        if not self.changes_are_made:
            self.changes_are_made = True
            self.setWindowTitle(f"{self.windowTitle()} *")

    def exec(self) -> int:
        result = super().exec()
        self.onsetline.label_enabled = self.checkbox_label.isChecked()
        self.onsetline.label_time_enabled = self.checkbox_time.isChecked()
        self.onsetline.label_temp_enabled = self.checkbox_temp.isChecked()
        self.onsetline.label_dta_enabled = self.checkbox_dta.isChecked()
        return result


SUMMARY_TABLE_HEADERS: tuple[str, ...] = (
    "Сегмент",
    "T_init (ур. 19.1)",
    "T_onset (экстрап.)",
    "T_peak (Tp)",
    "T(tp - τ)",
    "T_end (экстрап.)",
    "T_ret",
    "T_50%",
    "Площадь",
    "Высота Hp",
    "FWHM",
    "ΔY / Δm",
)


def build_peaks_summary_rows(
    segments_dta: list[SegmentDTA],
) -> list[tuple[str, ...]]:
    """Формирует строки сводной таблицы всех выделенных пиков по всем кривым сегментов."""
    rows: list[tuple[str, ...]] = []
    for seg in segments_dta:
        for curve in seg.curves.values():
            for pk in curve.peaks:
                onset_vals = [
                    ol.info.get(ol.temp_axis, 0.0)
                    for ol in pk.onset_lines
                    if ol.is_onset
                ]
                end_vals = [
                    ol.info.get(ol.temp_axis, 0.0)
                    for ol in pk.onset_lines
                    if not ol.is_onset
                ]
                t_on_s = f"{onset_vals[0]:.2f}" if onset_vals else "—"  # noqa: MI001
                t_end_s = f"{end_vals[0]:.2f}" if end_vals else "—"  # noqa: MI001
                mm = pk.melting_metrics
                dm_part = (
                    f"{pk.delta_y:+.3f} ({pk.delta_mass_mg:+.3f} мг)"
                    if pk.delta_mass_mg is not None
                    else f"{pk.delta_y:+.3f}"
                )
                rows.append(
                    (
                        f"Сегмент {seg.index} ({curve.channel_name})",
                        f"{mm.t_init_dev:.2f}",
                        t_on_s,
                        f"{pk.temp_peak:.2f}",
                        f"{mm.temp_lag_corrected:.2f}",
                        t_end_s,
                        f"{mm.t_return_dev:.2f}",
                        f"{pk.temp_half:.2f}",
                        str(pk.area).replace(" / ", "/"),
                        f"{pk.peak_height:.4f}",
                        f"{pk.fwhm_temp:.2f}",
                        dm_part,
                    )
                )
    return rows


class SummaryTableDialog(QtWidgets.QDialog):
    """Окно сводной таблицы всех пиков и фазовых переходов измерения с экспортом в TSV."""

    def __init__(
        self,
        segments_dta: list[SegmentDTA],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Сводная таблица пиков и фазовых переходов")
        self.resize(960, 360)
        self.rows = build_peaks_summary_rows(segments_dta)

        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(len(self.rows), len(SUMMARY_TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(list(SUMMARY_TABLE_HEADERS))
        self.table.horizontalHeader().setStretchLastSection(True)
        for r_idx, row_vals in enumerate(self.rows):
            for c_idx, cell_text in enumerate(row_vals):
                item = QtWidgets.QTableWidgetItem(cell_text)
                item.setFlags(item.flags() & ~QtGui.Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r_idx, c_idx, item)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_copy = QtWidgets.QPushButton(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.EditCopy,
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
            "Копировать таблицу в буфер обмена (TSV для Excel)",
        )
        btn_close = QtWidgets.QPushButton(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.WindowClose,
                QtWidgets.QStyle.StandardPixmap.SP_DialogCloseButton,
            ),
            "Закрыть",
        )
        btn_copy.clicked.connect(self._copy_tsv)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _copy_tsv(self) -> None:
        lines = ["\t".join(SUMMARY_TABLE_HEADERS)]
        for r in self.rows:
            lines.append("\t".join(r))
        QtGui.QGuiApplication.clipboard().setText("\n".join(lines))
