import pandas as pd
import pint

from .measurement_data import MeasurementData


class Header:
    TEMP = "Temp."
    TIME = "Time"
    DTA = "DTA"
    MASS = "Mass"


UREG: pint.UnitRegistry = pint.UnitRegistry()
UREG.default_format = "~"


def s2f(path: str, startmass: float) -> MeasurementData:
    rawdf = pd.read_csv(
        path, sep="\t", encoding="mbcs", skiprows=1, usecols=[0, 1, 2, 3], decimal=","
    )
    df = pd.DataFrame()
    df[Header.TEMP] = (
        rawdf["Sample temperature"][1:].str.replace(",", ".").astype(float)
    )
    df[Header.TIME] = rawdf["Time"][1:].astype(float)
    df[Header.DTA] = rawdf["HeatFlow"][1:].astype(float)
    if "TG" in df.columns:
        has_massdata = True
        df[Header.MASS] = 100 * (rawdf["TG"][1:].astype(float) + startmass) / startmass
    else:
        has_massdata = False
    info = dict()
    info["EXO"] = "+"
    units = dict()
    units[Header.TIME] = UREG.parse_units("s")
    units[Header.TEMP] = UREG.parse_units("°C")
    units[Header.DTA] = UREG.parse_units("mW")
    units[Header.MASS] = UREG.parse_units("%")
    return MeasurementData(
        segments=[df], info=info, units=units, hasMassData=has_massdata
    )
