#Python Imports
import pdb
from abc import ABC, abstractmethod
from datetime import datetime

#JPL Imports
from jpl_time import Time

#This Library Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

EVR_LEVEL_COLORS = {
    'DIAGNOSTIC':  {'background-color': '#90ED91', 'color': '#333333'},
    'COMMAND':     {'background-color': '#0D00FF', 'color': '#F1F1F2'},
    'ACTIVITY_LO': {'background-color': '#D3D3D3', 'color': '#333333'},
    'ACTIVITY_HI': {'background-color': '#666666', 'color': '#F1F1F2'},
    'WARNING_LO':  {'background-color': '#F0F001', 'color': '#333333'},
    'WARNING_HI':  {'background-color': '#FEA500', 'color': '#333333'},
    'FATAL':       {'background-color': '#FF5E66', 'color': '#F1F1F2'} 
}



class EvrGapItem(DataItem):
    """
    A specialized record representing a missing segment in Event Report (EVR) telemetry.

    **The Concept:**
    Event Reports (EVRs) are the "logs" of a spacecraft, describing actions taken or 
    states reached. Each EVR usually has a sequence index. If we see Index 100 
    followed immediately by Index 105, we have a "Gap." 

    An `EvrGapItem` doesn't represent a message from the spacecraft; it represents 
    the *absence* of messages. It quantifies how much information was lost and 
    during what timeframe, helping engineers determine the severity of data loss 
    based on the importance of the missing data (its "Level").

    :param Level: The severity level of the EVRs that are missing.
    :type Level: str
    :param Begin Time: The timestamp of the last successful EVR before the gap.
    :type Begin Time: datetime
    :param End Time: The timestamp of the first successful EVR after the gap.
    :type End Time: datetime
    :param First Missing Index: The sequence counter of the first missing report.
    :type First Missing Index: int
    :param Last Missing Index: The sequence counter of the last missing report.
    :type Last Missing Index: int
    :param Total Missing EVRs: The count of missing reports in this specific gap.
    :type Total Missing EVRs: int
    """

    #these are the fields that will be validated against these
    #data types. Other fields are allowed

    DICT_VALID_KEYS = [
        ('Level', str), 
        ('Begin Time', datetime), 
        ('End Time', datetime), 
        ('First Missing Index', int), 
        ('Last Missing Index', int),
        ('Total Missing EVRs', int),
        ]

    TIME_FORMATS = {
        'Begin Time': '%Y-%jT%H:%M:%S.%f',
    }
    NAME = 'evr gap'

    @property
    def default_html_row_style(self):
        """
        Returns the CSS style mapping associated with the EVR Level severity.
        """
        return EVR_LEVEL_COLORS[self.level]
    
    @property
    def time(self):
        """
        The start of the data gap window.
        """
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        return self.source['Begin Time']
        return Time(self.source['Begin Time'])

    @property
    def time_str(self):
        """
        Returns a string representation of the gap's beginning.
        """
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        #TO DO: consider making this NOT a property so we can pass
        #different time formats in
        return datetime.strftime(self.source['Begin Time'], self.TIME_FORMATS['Begin Time'])
        return Time(self.source['Begin Time'])
    
    @property
    def level(self):
        """Returns the severity level (e.g., FATAL, WARNING_HI) for this gap."""
        return self.source['level']

class EvrGapContainer(DataContainer):
    """
    A collection of EvrGapItems, typically used for telemetry health audits.

    **The Concept:**
    When mission operators download data, they need to know if the "story" 
    of the mission is complete. This container acts as an "Incompleteness Report." 
    By aggregating all detected gaps, it allows engineers to see at a glance if 
    critical data (like 'FATAL' or 'COMMAND' level EVRs) failed to reach the ground.

    **Severity Filtering:**
    The container uses a standard set of EVR severity levels to help color-code 
    and prioritize which gaps need immediate attention (e.g., investigating a 
    ground station outage).

    :param raw_data: A list of dicts representing detected EVR gaps.
    :param metadata: Header information from the telemetry source.
    :param name: Human-readable name for the container.
    :param nogaps: A flag used during initialization (internal use).
    :param cast_fields: If True, attempts to force data into the EvrGapItem schema.
    """
    NAME = 'evr gap container'
    DATA_ITEM_CLS = EvrGapItem
    LEVELS = ['DIAGNOSTIC', 'COMMAND', 'ACTIVITY_LO', 'ACTIVITY_HI', 'WARNING_LO', 'WARNING_HI', 'FATAL']
    
    def __init__(self, raw_data=None, metadata=None, name=None, nogaps=False, cast_fields=False, **kwargs):
        #TO DO; Clean this up. Shouldn't be checking for a string like this
        #and need to clean up at a higher level
        if metadata is not None:
            metadata = {k:v for k, v in metadata.items() if k[0] != '_' and k != 'dictionary'}
        super().__init__(raw_data=raw_data, metadata=metadata, cast_fields=cast_fields, **kwargs)

    def _impl_init(self):
        """Internal initialization hook."""
        return

    @property
    def repr_cols(self):
        """The specific columns to display in visual representations (HTML/Tables)."""
        return self._repr_cols

    @property
    def default_time_label(self):
        """The primary time key used for sorting gaps chronologically."""
        return self._default_time_label