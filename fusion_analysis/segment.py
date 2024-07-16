import numpy as np
from loguru import logger as log

from .converters.collection import CollectionData
from .converters.netzsch import NetzschSegmentData
from .plotter.segment_artist import (
    SegmentHandlerDTA,
    SegmentHandlerMass,
    SegmentHandlerTemp,
)
from .segment_data import FilteredData, SegmentData
from .segment_table_item import SegmentTableItem


class Segment:
    filtered_data = None

    def __init__(self, segment_data: SegmentData, index: int):
        self.index = index
        self.has_mass = segment_data.mass is not None
        self.is_selected = False
        self.is_enabled = True
        self.data = segment_data
        self.artist_dta = SegmentHandlerDTA(data=segment_data, index=index)
        self.artist_temp = SegmentHandlerTemp(data=segment_data, index=index)
        if self.has_mass:
            self.artist_mass = SegmentHandlerMass(data=segment_data, index=index)
        self.table_item = SegmentTableItem(segment=self)

    def set_filtered_data(self, temp: np.ndarray, dta: np.ndarray, window: int):
        self.filtered_data = FilteredData(
            time=self.data.time[window:-window], temp=temp, dta=dta
        )
        self.artist_dta.filtered_data = self.filtered_data
        self.artist_temp.filtered_data = self.filtered_data
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
