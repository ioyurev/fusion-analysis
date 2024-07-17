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

    def split(self, i: int):
        if self.temp is not None:
            temp1 = self.temp[:i]
            temp2 = self.temp[i:]
        else:
            temp1 = None
            temp2 = None
        if self.mass is not None:
            mass1 = self.mass[:i]
            mass2 = self.mass[i:]
        else:
            mass1 = None
            mass2 = None
        segment1 = SegmentData(
            time=self.time[:i], dta=self.dta[:i], temp=temp1, mass=mass1, emf=None
        )
        segment2 = SegmentData(
            time=self.time[i:], dta=self.dta[i:], temp=temp2, mass=mass2, emf=None
        )
        return segment1, segment2


class FilteredData:
    def __init__(
        self,
        dta: np.ndarray,
        temp: np.ndarray,
        time: np.ndarray,
        window: int,
        mass: np.ndarray | None = None,
    ):
        self.dta = dta
        self.temp = temp
        self.time = time
        self.mass = mass
        self.window = window

        self.min_time = time[0]
        self.max_time = time[-1]
        self.min_temp = min(temp)
        self.max_temp = max(temp)
        self.min_dta = min(dta)
        self.max_dta = max(dta)
        if mass is not None:
            self.min_mass = min(mass)
            self.max_mass = max(mass)

    def split(self, i: int):
        # i += self.window
        dta1 = self.dta[:i]
        dta2 = self.dta[i:]
        temp1 = self.temp[:i]
        temp2 = self.temp[i:]
        segment1 = FilteredData(
            dta=dta1, temp=temp1, time=self.time[:i], window=self.window, mass=self.mass
        )
        segment2 = FilteredData(
            dta=dta2, temp=temp2, time=self.time[i:], window=self.window, mass=self.mass
        )
        return segment1, segment2
