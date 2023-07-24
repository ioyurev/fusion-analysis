import numpy as np
import pandas as pd
import pint

UREG: pint.UnitRegistry = pint.UnitRegistry()
UREG.default_format  = '~'
TYPE_HEAT = 1
TYPE_COOL = 0

def _lines_to_infodict(lines) -> dict:
    info = dict()
    line: str
    for line in lines:
        k, v = line[1:].split(":", maxsplit=1)
        info[k] = v[:-1]
    return info

class STAFile:
    def __init__(self, filepath) -> None:
        with open(filepath) as f:
            lines = f.readlines()
            for index, line in enumerate(lines):
                if line.startswith('##'):
                    self.info = _lines_to_infodict(lines[:index-1])
                    # pprint(self.info)
                    if self.info['DECIMAL'] == 'POINT':
                        dec = '.'
                    else:
                        raise RuntimeError(f'Десятичный разделитель {self.info["DECIMAL"]} не распознан.')
                    if self.info['SEPARATOR'] == 'SEMICOLON':
                        sep = ';'
                    else:
                        raise RuntimeError(f'Разделитель {self.info["SEPARATOR"]} не распознан.')
                    rawdf = self._lines_to_df(lines[index:], sep, dec)
        self.isMultiSegment = '-' in self.info['SEGMENT']
        self.segments = []
        self.segments_type = []
        for val in rawdf['Segment'].unique():
            self.segments.append(rawdf[rawdf['Segment'] == val].drop(columns=['Segment']))
        for segment in self.segments:
            t1 = round(segment["Temp."].values[0])
            t2 = round(segment["Temp."].values[-1])
            if t2 > t1:
                self.segments_type.append(TYPE_HEAT)
            elif t2 < t1:
                self.segments_type.append(TYPE_COOL)
            else:
                raise RuntimeError(f'Непредусмотренное отношение температур {t1} и {t2}')
    
    def _lines_to_df(self, lines, sep, dec):
        self.headers: str = lines[0][2:-1].split(sep)
        self.units = dict()
        self.params = []
        col: str
        # print(self.headers)
        for col in self.headers:
            # print(col)
            if '/' in col:
                param, unit = col.split('/', maxsplit=1)
                self.params.append(param)
                self.units[param] = UREG.parse_units(unit)
            else:
                # print(param)
                self.params.append(col)
                self.units[col] = UREG.dimensionless
        # print(self.units)
        values = []
        for line in lines[1:-1]:
            values.append(line.split(sep))
        np_values = np.array(values).transpose()
        df = pd.DataFrame()
        for index, param in enumerate(self.params):
            df[param] = pd.Series(np_values[index], dtype=float)
        return df

# if __name__ == "__main__":
    # pass