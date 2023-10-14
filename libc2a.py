from libfusiondata import MeasurementData
from DataFile import file_to_data, HEADER_TIME, HEADER_T1, HEADER_T2, Data
import pandas as pd
import numpy as np

def apply_calibration(data: Data):
    coeff_temp = data.cal.coeff_temp
    coeff_sens = data.cal.coeff_sens
    df = pd.DataFrame()
    yn_temp = np.poly1d(coeff_temp)
    yn_sens = np.poly1d(coeff_sens)
    df['Time'] = data.df[HEADER_TIME]
    df['Temp.'] = yn_temp(data.df[HEADER_T1])
    df['DTA'] = data.df[HEADER_T2] - data.df[HEADER_T1]
    return df

def c2a(path: str) -> MeasurementData:
    data = file_to_data(path)
    data.info['EXO'] = '+'
    units = dict()
    units['Time'] = 's'
    units['Temp.'] = '°C'
    units['DTA'] = 'mcV'
    return MeasurementData(segments=[apply_calibration(data)], info=data.info, units=units, hasMassData=False)