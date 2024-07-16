import io
import zipfile
from pathlib import Path

import numpy as np

from fusion_analysis.files.calibration import Calibration, zipbuffer_to_cal


class CollectionData:
    temp: np.ndarray | None = None
    emf: np.ndarray | None = None
    time: np.ndarray
    dta: np.ndarray


def apply_calibration(cal: Calibration, data: CollectionData):
    yn_temp = np.poly1d(cal.coeff_temp)
    yn_sens = np.poly1d(cal.coeff_sens)
    temp = yn_temp(data.emf)
    sens = yn_sens(temp)
    data.dta = data.dta / sens


def zipfile_to_buffer(path: Path):
    with open(path, "rb") as f:
        return io.BytesIO(f.read())


def zipbuffer_to_data(buffer: io.BytesIO):
    with zipfile.ZipFile(buffer, "r") as zipf:
        version = float(zipf.open("VERSION").read())
        if version > 1:
            raise NotImplementedError()
        data = np.loadtxt(
            zipf.open("data.csv"), dtype=float, delimiter=",", skiprows=1
        ).transpose()
        time = data[0] / 60
        t1 = data[1]
        t2 = data[2]
        if "calibration.fus-cal" in zipf.namelist():
            cal = zipbuffer_to_cal(zipf.open("calibration.fus-cal"))
        else:
            cal = None
        data = CollectionData()
        data.emf = t1
        data.time = time
        data.dta = t1 - t2
        if cal is not None:
            apply_calibration(cal=cal, data=data)
    return data


def c2a(path: Path):
    return zipbuffer_to_data(zipfile_to_buffer(path))


if __name__ == "__main__":
    data = c2a(Path("examples/Sn-Pb.fus-mdt"))
    print(data.emf)
