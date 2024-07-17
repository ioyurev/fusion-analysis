import numpy as np
from loguru import logger as log
from PySide6 import QtCore

from .converters.collection import CollectionData
from .converters.netzsch import NetzschSegmentData
from .helpers import find_nearest
from .plotter.segment_artist import (
    SegmentHandlerDTA,
    SegmentHandlerMass,
    SegmentHandlerTemp,
)
from .segment_data import FilteredData, SegmentData
from .segment_table_item import SegmentTableItem


class Segment(QtCore.QObject):
    filtered_data = None
    updated_artists = QtCore.Signal()

    def __init__(self, segment_data: SegmentData, index: int):
        super().__init__()
        self.index = index
        self.has_mass = segment_data.mass is not None
        self.is_selected = False
        self.is_enabled = True
        self.data = segment_data
        self.artist_dta = SegmentHandlerDTA(segment=self)
        self.artist_temp = SegmentHandlerTemp(segment=self)
        if self.has_mass:
            self.artist_mass = SegmentHandlerMass(segment=self)
        self.table_item = SegmentTableItem(segment=self)

    def get_data(self):
        if self.filtered_data is not None:
            return self.filtered_data
        return self.data

    def set_index(self, i: int):
        self.index = i
        self.artist_dta.line.index = i
        self.artist_temp.line.index = i
        if self.has_mass:
            self.artist_mass.line.index = i

    def remove(self):
        self.artist_dta.remove()
        self.artist_temp.remove()
        if self.has_mass:
            self.artist_mass.remove()

    def set_filtered_data(self, temp: np.ndarray, dta: np.ndarray, window: int):
        if window == 1:
            return
        self.filtered_data = FilteredData(
            time=self.data.time[window:-window], temp=temp, dta=dta, window=window
        )
        self.set_filter()
        log.debug(f"Отфильтрован сегмент {self.index}, окно={window}")
        self.updated_artists.emit()

    def unfilter(self):
        self.filtered_data = None
        self.artist_dta.unfilter()
        self.artist_temp.unfilter()
        log.debug(f"Снята фильтрация с сегмента {self.index}")

    def set_filter(self):
        self.artist_dta.set_filter()
        self.artist_temp.set_filter()

    def set_selected(self, b: bool):
        if self.is_enabled:
            self.artist_dta.set_pick_effect(b)
            if b:
                log.debug(f"Выбран сегмент {self.index}")
            self.is_selected = b
        self.table_item.set_selected(b)

    def set_enabled(self, b: bool):
        self.artist_dta.set_enabled(b)
        self.artist_temp.set_enabled(b)
        if self.has_mass:
            self.artist_mass.set_enabled(b)
        log.debug(f"Сегмент {self.index} включен {b}")
        if not b and self.is_selected:
            self.set_selected(False)
        self.is_enabled = b

    def split(self, x: float):
        if self.artist_dta.is_time_xaxis:
            if self.filtered_data is not None:
                xdata = self.filtered_data.time
            else:
                xdata = self.data.time
        else:
            if self.filtered_data is not None:
                xdata = self.filtered_data.temp
            else:
                xdata = self.data.temp
        i = find_nearest(array=xdata, value=x)

        segment1_data, segment2_data = self.data.split(i)
        if self.filtered_data is not None:
            segment1_fdata, segment2_fdata = self.filtered_data.split(i)
        else:
            segment1_fdata, segment2_fdata = None, None

        segment1 = Segment(segment1_data, self.index)
        segment2 = Segment(segment2_data, self.index + 1)
        segment1.filtered_data = segment1_fdata
        segment2.filtered_data = segment2_fdata
        return segment1, segment2

    @staticmethod
    def from_collection(collection_data: CollectionData):
        data = SegmentData(
            time=collection_data.time,
            dta=collection_data.dta,
            temp=collection_data.temp,
            emf=collection_data.emf,
        )
        return Segment(data, 0)

    @staticmethod
    def from_netzsch(segment: NetzschSegmentData):
        data = SegmentData(
            time=segment.time,
            dta=segment.dta,
            temp=segment.temp,
            mass=segment.mass,
        )
        return Segment(data, segment.index)
