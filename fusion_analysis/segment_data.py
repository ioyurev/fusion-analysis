import numpy as np


class SegmentData:
    def __init__(
        self,
        time: np.ndarray,
        dta: np.ndarray,
        temp: np.ndarray | None = None,
        emf: np.ndarray | None = None,
        mass: np.ndarray | None = None,
    ):
        self.time = time
        self.dta = dta
        self.mass = mass
        if temp is not None:
            self.temp = temp
        else:
            self.temp = emf

        self.min_time = time[0]
        self.max_time = time[-1]
        self.min_temp = min(self.temp)
        self.max_temp = max(self.temp)
        self.min_dta = min(dta)
        self.max_dta = max(dta)
        if mass is not None:
            self.min_mass = min(mass)
            self.max_mass = max(mass)


class FilteredData:
    def __init__(
        self,
        dta: np.ndarray,
        temp: np.ndarray,
        time: np.ndarray,
        mass: np.ndarray | None = None,
    ):
        self.dta = dta
        self.temp = temp
        self.time = time
        self.mass = mass

        self.min_time = time[0]
        self.max_time = time[-1]
        self.min_temp = min(temp)
        self.max_temp = max(temp)
        self.min_dta = min(dta)
        self.max_dta = max(dta)
        if mass is not None:
            self.min_mass = min(mass)
            self.max_mass = max(mass)
