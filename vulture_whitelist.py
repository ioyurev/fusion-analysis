"""Vulture whitelist for Qt/Matplotlib virtual hooks and Pydantic fields in fusion-analysis."""

from PySide6 import QtWidgets

from fusion_analysis.main_window import MainWindow
from fusion_analysis.measurement_data import AxisChannel
from fusion_analysis.segment import Peak
from fusion_analysis.segment_properties_window import OnsetPropertiesWindow
from fusion_analysis.video_overlay.models import (
    BG_COLOR_BGR,
    TEXT_COLOR_BGR,
    AlignedInfo,
    Alignment,
    OverlayConfig,
    VideoInfo,
)
from fusion_analysis.video_overlay.widgets import (
    AspectRatioLabel,
    CropSelectionDialog,
)

_HOOKS = (
    QtWidgets.QWidget.mousePressEvent,
    QtWidgets.QWidget.mouseMoveEvent,
    AspectRatioLabel.hasHeightForWidth,
    AspectRatioLabel.heightForWidth,
    AspectRatioLabel.sizeHint,
    AspectRatioLabel.resizeEvent,
    CropSelectionDialog.closeEvent,
    MainWindow.closeEvent,
    AxisChannel.TIME,
    AxisChannel.TEMP,
    AxisChannel.DTA,
    AxisChannel.EMF,
    AxisChannel.MASS,
    OnsetPropertiesWindow.exec,
    Peak.t_peak,
    TEXT_COLOR_BGR,
    BG_COLOR_BGR,
    Alignment.CENTER,
    OverlayConfig.logo_enabled,
    VideoInfo.timestamps_source,
    VideoInfo.timestamps_available,
    VideoInfo.first_timestamp_sec,
    VideoInfo.last_timestamp_sec,
    VideoInfo.used_end_sec,
    VideoInfo.kept_duration_sec,
    AlignedInfo.interpolation,
    AlignedInfo.normalized_timestamps,
)
