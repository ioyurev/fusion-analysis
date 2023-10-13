from libfusiondata import MeasurementData
from helpers import find_nearest
import pandas as pd
import numpy as np
import pint

HEADER_TEMP ='Temp.'
HEADER_TIME = 'Time'
HEADER_DTA = 'DTA'
HEADER_MASS = 'Mass'

UREG: pint.UnitRegistry = pint.UnitRegistry()
UREG.default_format  = '~'

def detect_temperature_segments(df: pd.DataFrame) -> list[pd.DataFrame]:
    # segments = []
    # start_index = 0
    # is_rising = True
    # temperature = df[HEADER_TEMP]

    # for i in range(1, len(temperature)):
    #     if is_rising:
    #         if temperature[i] < temperature[i-1]:
    #             segments.append((start_index, i-1))
    #             start_index = i
    #             is_rising = False
    #     else:
    #         if temperature[i] > temperature[i-1]:
    #             segments.append((start_index, i-1))
    #             start_index = i
    #             is_rising = True

    # segments.append((start_index, len(temperature)-1))
    # return segments
    return [df]

def s2f(path: str, startmass: float) -> MeasurementData:
    rawdf = pd.read_csv(path, sep='\t', encoding='mbcs', skiprows=1, usecols=[0, 1, 2, 3], decimal=',')
    df = pd.DataFrame()
    df[HEADER_TEMP] = rawdf['Sample temperature'][1:].str.replace(',', '.').astype(float)
    df[HEADER_TIME] = rawdf['Time'][1:].astype(float)
    df[HEADER_DTA] = rawdf['HeatFlow'][1:].astype(float)
    if 'TG' in df.columns:
        has_massdata = True
        df[HEADER_MASS] = 100*(rawdf['TG'][1:].astype(float) + startmass)/startmass
    else:
        has_massdata = False
    info = dict()
    info['EXO'] = '+'
    units = dict()
    units[HEADER_TIME] = UREG.parse_units('s')
    units[HEADER_TEMP] = UREG.parse_units('°C')
    units[HEADER_DTA] = UREG.parse_units('mW')
    units[HEADER_MASS] = UREG.parse_units('%')
    return MeasurementData(segments=detect_temperature_segments(df), info=info, units=units, hasMassData=has_massdata)
