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
        self.temp = temp
        self.emf = emf
        self.mass = mass
