import pandas as pd

TYPE_ISOTHERMAL = 2
TYPE_HEAT = 1
TYPE_COOL = 0

class MeasurementData:
    def __init__(self, segments: list[pd.DataFrame], info: dict, units: dict, hasMassData: bool) -> None:
        self.segments = segments
        self.info = info
        self.units = units
        self.has_massdata = hasMassData
        self.has_tempdata = 'Temp.' in self.units
        if '+' in self.info['EXO']:
            self.exo = 1
        elif '-' in self.info['EXO']:
            self.exo = 0
        else:
            raise RuntimeError(f'Значение EXO {self.info["EXO"]} не распознано.')
        self.exo
