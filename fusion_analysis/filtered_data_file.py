import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6 import QtWidgets

VERSION = 1
FILE_EXT_FILTER = "Файл отфильтрованного измерения Fusion(*.fus-fmdt)"


class Header:
    TIME = "Time/s"
    DTA = "DTA/{units}"
    EMF = "EMF/mV"
    TEMP = "Temp./°C"


def pick_save_path():
    return QtWidgets.QFileDialog.getSaveFileName(
        None, "Сохранить файл измерения", filter=FILE_EXT_FILTER
    )[0]


def pick_open_path():
    return Path(
        QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Открыть файл измерения",
            filter="Файл измерения Fusion(*.fus-mdt *.fus-fmdt)",
        )[0]
    )


def zipbuffer_to_data(buffer: io.BytesIO):
    with zipfile.ZipFile(buffer, "r") as zipf:
        version = float(zipf.open("VERSION").read())
        df = pd.read_csv(zipf.open("data.csv"), sep=",", decimal=".")
        time = df[Header.TIME].to_numpy()
        if Header.EMF in df:
            emf = df[Header.EMF].to_numpy()
        else:
            emf = None
        if Header.TEMP in df:
            temp = df[Header.TEMP].to_numpy()
        else:
            temp = None
        for col in df.columns:
            if col.startswith("DTA"):
                dta = df[col].to_numpy()
                dta_units = col.split("/")[1]
                break
    return FilteredData(
        time=time, dta=dta, emf=emf, temp=temp, dta_units=dta_units, version=version
    )


def file_to_zipbuffer(path):
    with open(path, "rb") as f:
        return io.BytesIO(f.read())


def file_to_data(path: str):
    return zipbuffer_to_data(file_to_zipbuffer(path))


class FilteredData:
    def __init__(
        self,
        time: np.ndarray,
        dta: np.ndarray,
        dta_units: str,
        emf: np.ndarray | None,
        temp: np.ndarray | None,
        version=VERSION,
    ):
        if version > VERSION:
            raise ValueError(
                "Файл отфильтрованного измерения создан в более новой версии Fusion Analysis."
            )
        self.version = version
        self.df = pd.DataFrame()
        self.dta_header = Header.DTA.format(units=dta_units)
        self.df[Header.TIME] = time
        self.df[self.dta_header] = dta
        if emf is not None:
            self.df[Header.EMF] = emf
        if temp is not None:
            self.df[Header.TEMP] = temp
        self.info = dict()
        self.info["version"] = self.version
        # self.info['time'] = str(datetime.now())

    def to_zipbuffer(self):
        buffer_zip = io.BytesIO()
        buffer_data = io.StringIO()

        self.df.to_csv(buffer_data, index=False)

        with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("VERSION", data=str(self.version))
            zipf.writestr("data.csv", data=buffer_data.getvalue())
        return buffer_zip

    def to_file(self, path: str):
        with open(path, "wb") as f:
            f.write(self.to_zipbuffer().getbuffer())

    @staticmethod
    def from_file(path: str):
        return file_to_data(path)
