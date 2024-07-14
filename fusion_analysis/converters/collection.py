from pathlib import Path

# import numpy as np
# import pandas as pd

# from ..files.data_file import Data, Header, file_to_data
# from ..files.filtered_data_file import FilteredData
# from .measurement_data import MeasurementData


# def apply_calibration(data: Data, df: pd.DataFrame):
#     yn_temp = np.poly1d(data.cal.coeff_temp)
#     yn_sens = np.poly1d(data.cal.coeff_sens)
#     df["Temp."] = yn_temp(data.df[Header.T1].values)
#     df["Sens."] = yn_sens(data.df["Temp."].values)
#     dt = data.df[Header.T2].values - data.df[Header.T1].values
#     df["DTA"] = dt / df["Sens."].values


def c2a(path: Path):
    pass


#     data = file_to_data(path)
#     units = dict()
#     df = pd.DataFrame()
#     df["Time"] = data.df[Header.TIME].values
#     if data.cal:
#         apply_calibration(data, df)
#         units["Temp."] = "°C"
#     else:
#         df["EMF"] = data.df[Header.T1].values
#         df["DTA"] = data.df[Header.T1].values - data.df[Header.T2].values
#         units["EMF"] = "mV"
#     data.info["EXO"] = "+"
#     units["Time"] = "s"
#     units["DTA"] = "mV"
#     return MeasurementData(
#         segments=[df], info=data.info, units=units, hasMassData=False
#     )


# def fc2a(path: str) -> MeasurementData:
#     data = FilteredData.from_file(path)
#     df = pd.DataFrame()
#     units = dict()
#     for col in data.df.columns:
#         mes, unit = col.split("/")
#         units[mes] = unit
#         df[mes] = data.df[col].values
#     data.info["EXO"] = "+"
#     return MeasurementData(
#         segments=[df], info=data.info, units=units, hasMassData=False
#     )
