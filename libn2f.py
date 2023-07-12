import numpy as np
import pandas as pd


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
                        raise f'Decimal is {self.info["DECIMAL"]}'
                    if self.info['SEPARATOR'] == 'SEMICOLON':
                        sep = ';'
                    else:
                        raise f'Separator is {self.info["SEPARATOR"]}'
                    rawdf = self._lines_to_df(lines[index:], sep, dec)
        self.isMultiSegment = '-' in self.info['SEGMENT']
        self.segments = []
        for val in rawdf['Segment'].unique():
            self.segments.append(rawdf[rawdf['Segment'] == val])
    
    def _lines_to_df(self, lines, sep, dec):
        self.headers: str = lines[0][2:-1].split(sep)
        self.units = []
        params = []
        col: str
        for col in self.headers:
            if '/' in col:
                param, unit = col.split('/', maxsplit=1)
                params.append(param)
                # if "(" in unit  and ")" in unit:
                #     self.units.append(unit[1:-1])
                # else:
                self.units.append(unit)
            else:
                params.append(col)
                self.units.append(None)
        values = []
        for line in lines[1:-1]:
            values.append(line.split(sep))
        np_values = np.array(values).transpose()
        df = pd.DataFrame()
        for index, param in enumerate(params):
            df[param] = pd.Series(np_values[index], dtype=float)
        return df

# if __name__ == "__main__":
    # pass