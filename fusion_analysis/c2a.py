import numpy as np
import pandas as pd

from .data_file import HEADER_T1, HEADER_T2, HEADER_TIME, Data, file_to_data
from .measurement_data import MeasurementData


def apply_calibration(data: Data, df: pd.DataFrame):
    yn_temp = np.poly1d(data.cal.coeff_temp)
    yn_sens = np.poly1d(data.cal.coeff_sens)
    df["Temp."] = yn_temp(data.df[HEADER_T1].values)
    df["Sens."] = yn_sens(data.df["Temp."].values)
    dt = data.df[HEADER_T2].values - data.df[HEADER_T1].values
    df["DTA"] = dt / df["Sens."].values


def c2a(path: str) -> MeasurementData:
    data = file_to_data(path)
    units = dict()
    df = pd.DataFrame()
    df["Time"] = data.df[HEADER_TIME].values
    if data.cal:
        apply_calibration(data, df)
        units["Temp."] = "°C"
    else:
        df["EMF"] = data.df[HEADER_T1].values
        df["DTA"] = data.df[HEADER_T1].values - data.df[HEADER_T2].values
        units["EMF"] = "mV"
    data.info["EXO"] = "+"
    units["Time"] = "s"
    units["DTA"] = "mV"
    return MeasurementData(
        segments=[df], info=data.info, units=units, hasMassData=False
    )
