import numpy as np
import pandas as pd
import pint
from libfusiondata import MeasurementData, TYPE_COOL, TYPE_HEAT, TYPE_ISOTHERMAL

UREG: pint.UnitRegistry = pint.UnitRegistry()
UREG.default_format  = '~'

def _lines_to_infodict(lines) -> dict:
    info = dict()
    line: str
    for line in lines:
        k, v = line[1:].split(":", maxsplit=1)
        info[k] = v[:-1]
    return info

def _lines_to_df(lines: list[str], sep: str, dec: str) -> tuple[pd.DataFrame, dict]:
        headers = lines[0][2:-1].split(sep)
        units = dict()
        params = []
        for col in headers:
            if '/' in col:
                param, unit = col.split('/', maxsplit=1)
                params.append(param)
                units[param] = UREG.parse_units(unit)
            else:
                params.append(col)
                units[col] = UREG.dimensionless
        values = []
        for line in lines[1:-1]:
            values.append(line.split(sep))
        np_values = np.array(values).transpose()
        df = pd.DataFrame()
        for index, param in enumerate(params):
            df[param] = pd.Series(np_values[index], dtype=float)
        return df, units

def _split_lines(lines) -> tuple[dict, dict, pd.DataFrame]:
    for index, line in enumerate(lines):
        if line.startswith('##'):
            info = _lines_to_infodict(lines[:index-1])
            # pprint(self.info)
            if info['DECIMAL'] == 'POINT':
                dec = '.'
            else:
                raise RuntimeError(f'Десятичный разделитель {info["DECIMAL"]} не распознан.')
            if info['SEPARATOR'] == 'SEMICOLON':
                sep = ';'
            else:
                raise RuntimeError(f'Разделитель {info["SEPARATOR"]} не распознан.')
            df, units = _lines_to_df(lines[index:], sep, dec)
            return info, units, df

def data_to_segment(df: pd.DataFrame, hasMassData: bool) -> pd.DataFrame:
    segment = pd.DataFrame()
    segment['Time'] = df['Time']
    segment['Temp.'] = df['Temp.']
    segment['DTA'] = df['DTA']
    if hasMassData: segment['Mass'] = df['Mass']
    return segment

def n2f(filepath) -> MeasurementData:
    with open(filepath) as f:
        lines = f.readlines()
        info, units, df = _split_lines(lines)
        isMultiSegment = '-' in info['SEGMENT']
        hasMassData = 'Mass' in df.columns
    segments = []
    if isMultiSegment:
        for segment_num in df['Segment'].unique():
            segment_df = df[df['Segment'] == segment_num].drop(columns=['Segment'])
            segments.append(data_to_segment(df=segment_df, hasMassData=hasMassData))
    else:
        segments.append(data_to_segment(df=df, units=units, hasMassData=hasMassData))
    return MeasurementData(info=info, segments=segments, units=units, hasMassData=hasMassData)
