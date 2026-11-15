from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from fusion_common import get_appdata_path
from loguru import logger as log
from pydantic import BaseModel, Field


class PlotterSettings(BaseModel):
    autocolor: bool = False
    antialias: bool = True
    default_heat_color: list[float] = Field(default_factory=lambda: [1.0, 0.0, 0.0])
    default_cool_color: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])


class AnalysisConfig(BaseModel):
    Plotter: PlotterSettings = Field(default_factory=PlotterSettings)


APPDATA_PATH: Final[Path] = get_appdata_path("fusion-analysis")
DEFAULT_CONFIG_PATH: Final[Path] = APPDATA_PATH / "config.json"


def read_config(path: Path | None = None) -> AnalysisConfig:
    target = path if path is not None else DEFAULT_CONFIG_PATH
    if target.exists():
        try:
            return AnalysisConfig.model_validate_json(
                target.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            log.bind(path=str(target), error=str(exc)).warning(
                "Failed to read config.json, using default settings"
            )
    default_cfg = AnalysisConfig()
    write_config(default_cfg, path=target)
    return default_cfg


def write_config(
    cfg: AnalysisConfig | dict[str, Any], path: Path | None = None
) -> None:
    target = path if path is not None else DEFAULT_CONFIG_PATH
    validated = (
        cfg if isinstance(cfg, AnalysisConfig) else AnalysisConfig.model_validate(cfg)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(validated.model_dump_json(indent=2), encoding="utf-8")
