from loguru import logger as log

from .converters.netzsch import NetzschSegmentData
from .plotter.segment_artist import (
    SegmentHandlerDTA,
    SegmentHandlerMass,
    SegmentHandlerTemp,
)
from .segment_data import SegmentData
from .segment_table_item import SegmentTableItem


class Segment:
    def __init__(self, segment_data: SegmentData, index: int):
        self.index = index
        self.is_selected = False
        self.is_enabled = True
        self.data = segment_data
        self.artist_dta = SegmentHandlerDTA(data=segment_data, index=index)
        self.artist_temp = SegmentHandlerTemp(data=segment_data, index=index)
        self.artist_mass = SegmentHandlerMass(data=segment_data, index=index)
        self.table_item = SegmentTableItem(segment=self)

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
        self.artist_mass.set_enabled(b)
        log.debug(f"Сегмент {self.index} включен {b}")
        if not b and self.is_selected:
            self.set_selected(False)
        self.is_enabled = b

    @staticmethod
    def from_netzsch(netzsch_segment: NetzschSegmentData):
        segment_data = SegmentData(
            time=netzsch_segment.time,
            dta=netzsch_segment.dta,
            temp=netzsch_segment.temp,
            mass=netzsch_segment.mass,
        )
        return Segment(segment_data, netzsch_segment.index)
