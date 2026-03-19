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
    'FATAL':       {'background-color': '#FF5E66', 'color': '#F1F1F2'} ,
    'SIM ERROR':       {'background-color': '#FF5E66', 'color': '#F1F1F2'} 
}

class EvrItem(DataItem):
    """
    A specialized DataItem representing a single Event Record (EVR) from a spacecraft.

    **The Concept:**
    Event Records are the log messages of a spacecraft's Flight Software (FSW). 
    Unlike telemetry channels (EHA), which provide continuous numerical data, EVRs 
    provide discrete notifications about state changes, command executions, or 
    other events. They are the primary tool used by operators to understand the 
    *logical* flow of mission events.

    **How it works:**
    Each EVR carries a severity `level`, a unique `eventId`, and a human-readable 
    `message`. Because EVRs are critical for troubleshooting, they include high-fidelity 
    timestamps (SCET/ERT) and sequence indices to ensure they can be reassembled 
    chronologically, even if received out of order.

    :param recordType: The specific category of data point.
    :param sessionId: AMPCS session ID for traceability.
    :param sessionHost: The workstation/server host for the session.
    :param name: The mnemonic name for the specific event type.
    :param module: The specific FSW module that issued the report.
    :param level: Severity level (e.g. ACTIVITY_LO, DIAGNOSTIC, WARNING_HI, FATAL).
    :param eventId: A numeric hash uniquely identifying the event type.
    :param vcid: Virtual Channel ID used for transmission.
    :param dssId: Deep Space Station ID that received the data.
    :param fromSse: True if originating from Ground System Equipment; False for FSW.
    :type fromSse: bool
    :param realtime: True if received in realtime; False if played back from recorder.
    :type realtime: bool
    :param sclk: Spacecraft clock value at time of event.
    :param scet: Spacecraft Elapsed Time (UTC).
    :param ert: Earth Receive Time (UTC).
    :param rct: Range Corrected Time.
    :param lst: Local Mean Solar Time (string representation).
    :param message: The descriptive log text.
    :param metadata: Combined dictionary of keywords and values for event-specific data.
    """

    DICT_VALID_KEYS = [
        ('recordType', str), 
        ('sessionId', int), 
        ('sessionHost', str), 
        ('name', str), 
        ('module', str),
        ('level', str),
        ('eventId', int),
        ('vcid', int),
        ('dssId', int),
        ('fromSse', bool),
        ('realtime', bool),
        ('sclk', float),
        ('scet', datetime),
        ('ert', datetime),
        ('rct', (datetime, None)),
        ('lst', (datetime, None)),
        ('message', str),
        ('metadataKeywordList', str),
        ('metadataValuesList', str),
        ('metadata', dict), #TO DO: Make better validation of nested items
        ]

    TIME_FORMATS = {
        'scet': '%Y-%jT%H:%M:%S.%f',
        'ert': '%Y-%jT%H:%M:%S.%f',
        'rct': '%Y-%jT%H:%M:%S.%f',
        'lst': 'TBD' #need to incorporate jpl_time to make this work
    }
    NAME = 'evr'

    @property
    def default_html_row_style(self):
        """Returns row styling based on the EVR severity level."""
        return EVR_LEVEL_COLORS[self.level]
    
    @property
    def time(self):
        """Primary timestamp (SCET) for the event."""
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        return self.source['scet']
        return Time(self.source['scet'])

    @property
    def time_str(self):
        """String-formatted representation of the event time."""
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        #TO DO: consider making this NOT a property so we can pass
        #different time formats in
        return datetime.strftime(self.source['scet'], self.TIME_FORMATS['scet'])
        return Time(self.source['scet'])
    
    @property
    def name(self):
        """The mnemonic identifier of the EVR."""
        return self.source['name']

    @property
    def message(self):
        """The descriptive log message."""
        return self.source['message']

    @property
    def level(self):
        """The severity level of the event."""
        return self.source['level']

    def is_warning(self):
        """Returns True if the event level is WARNING or higher."""
        return self.level in ['WARNING_LO', 'WARNING_HI', 'FATAL']

class EvrContainer(DataContainer):
    """
    A specialized container for managing collections of Spacecraft Event Records (EVRs).

    **The Concept:**
    In mission operations, EVRs are often the first place engineers look when 
    something goes wrong. This container provides high-level utilities to manage 
    these logs, most importantly the `gaps()` method, which verifies the 
    completeness of the data stream.

    **Data Context:**
    Designed to mimic AMPCS-like time-series logs, it follows standard NASA/JPL 
    patterns for multi-mission event reporting.

    :param raw_data: List of dictionaries matching the EvrItem schema.
    :param metadata: Header data for the telemetry set.
    """
    NAME = 'evrs'
    DATA_ITEM_CLS = EvrItem
    LEVELS = ['DIAGNOSTIC', 'COMMAND', 'ACTIVITY_LO', 'ACTIVITY_HI', 'WARNING_LO', 'WARNING_HI', 'FATAL']
    
    def __init__(self, raw_data=None, metadata=None, name=None, cast_fields=False, **kwargs):
        #TO DO; Clean this up. Shouldn't be checking for a string like this
        #and need to clean up at a higher level
        if metadata is not None:
            metadata = {k:v for k, v in metadata.items() if k[0] != '_' and k != 'dictionary'}
        super().__init__(raw_data=raw_data, metadata=metadata, cast_fields=cast_fields, **kwargs)
        self.name = 'EVR Container' if name is None else name
        self._repr_cols = ['vcid', 'name', 'scet', 'message']
        self._default_time_label = 'scet'
        self._repr_cols = [x for x, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]
        self._csv_cols = [x for x, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]

    def _impl_init(self):
        """Internal initialization hook."""
        return

    @property
    def repr_cols(self):
        """Columns to be displayed in visual representations."""
        return self._repr_cols

    @property
    def default_time_label(self):
        """The default time field used for chronological operations."""
        return self._default_time_label

    def gaps(self):
        """
        Analyzes sequence IDs to identify missing data segments.

        **The Concept:**
        EVRs are produced with sequential indices. If a dataset contains index 500 
        and 505 but is missing 501-504, a data gap has occurred (likely due to 
        station handover or downlink issues). This method performs a gap audit 
        across all severity levels to determine exactly what information is missing.

        :return: A container summarizing detected gaps.
        :rtype: EvrGapContainer
        """
        gaps = []
        all_missing_sequence_ids = []
        for level in self.LEVELS:
            evrs_this_level = self.eq('level', level)
            evrs_this_level = evrs_this_level.sort(lam=lambda r: int(r['metadata']['CategorySequenceId']))
            sequence_ids_this_level = [int(e['metadata']['CategorySequenceId']) for e in evrs_this_level]
            if len(sequence_ids_this_level) == 0: continue
            expected_sequence_ids = [ii for ii in range(sequence_ids_this_level[0], sequence_ids_this_level[-1]+1)]
            missing_sequence_ids = [ii for ii in expected_sequence_ids if ii not in sequence_ids_this_level]
            all_missing_sequence_ids += missing_sequence_ids
            befores = [ii - 1 for ii in missing_sequence_ids]
            afters = [ii + 1 for ii in missing_sequence_ids]
            befores = [ii for ii in befores if ii not in missing_sequence_ids]
            afters = [ii for ii in afters if ii not in missing_sequence_ids]
            for b, a in zip(befores, afters):
                preceding_evr = evrs_this_level._filter((lambda r: int(r['metadata']['CategorySequenceId']) == b, 'EVR Before Gap'), exactly=1)
                succeeding_evr = evrs_this_level._filter((lambda r: int(r['metadata']['CategorySequenceId']) == a, 'EVR After Gap'), exactly=1)
                gaps.append({
                    'Level': level,
                    'Begin Time (SCET)': preceding_evr['scet'],
                    'End Time (SCET)': succeeding_evr['scet'],
                    'Begin Time (ERT)': preceding_evr['ert'],
                    'End Time (ERT)': succeeding_evr['ert'],
                    'First Missing Index': b + 1,
                    'Last Missing Index': a - 1,
                    'Total Missing EVRs': a - b - 1
                    })

        #The code below is an unfinished attempt at squeezing some additional information out of this
        #the code above checks for gaps successfully, but only on a per-level basis
        #This means that if there is a gap that touches the beginning or end of our contiguous knowlege
        #of a level, it could still be useful to check the general sequence ID. But it's a little wonky
        #trying to understand which information is in there and which isn't.

        # all_sequence_ids = [int(e['metadata']['SequenceId']) for e in evrs]
        # all_expected_sequence_ids = [ii for ii in range(all_sequence_ids[0], all_sequence_ids[-1]+1)]
        # missing_sequence_ids = [ii for ii in all_expected_sequence_ids if ii not in all_sequence_ids]
        # befores = [ii - 1 for ii in missing_sequence_ids]
        # afters = [ii + 1 for ii in missing_sequence_ids]
        # befores = [ii for ii in befores if ii not in missing_sequence_ids]
        # afters = [ii for ii in afters if ii not in missing_sequence_ids]
        # pdb.set_trace()

        return EvrGapContainer(raw_data=gaps)

class EvrGapItem(DataItem):
    """
    A record quantifying a missing segment of Event Report telemetry.

    **The Concept:**
    Instead of representing a message, this item represents a "hole" in the 
    spacecraft logs. It identifies the timestamps and sequence indices that 
    the ground system *expected* to receive but did not. This is critical for 
    determining if the team is making decisions based on incomplete telemetry.

    :param Level: The severity level of the missing reports.
    :param Begin Time (SCET): Time of the last successful report before the gap.
    :param End Time (SCET): Time of the first successful report after the gap.
    :param First Missing Index: The sequence ID of the first missing report.
    :param Last Missing Index: The sequence ID of the last missing report.
    :param Total Missing EVRs: Count of indices missing in this specific gap.
    """

    DICT_VALID_KEYS = [
        ('Level', str), 
        ('Begin Time (SCET)', datetime), 
        ('End Time (SCET)', datetime), 
        ('Begin Time (ERT)', datetime), 
        ('End Time (ERT)', datetime), 
        ('First Missing Index', int), 
        ('Last Missing Index', int),
        ('Total Missing EVRs', int),
        ]

    TIME_FORMATS = {
        'Begin Time (SCET)': '%Y-%jT%H:%M:%S.%f',
        'End Time (SCET)': '%Y-%jT%H:%M:%S.%f',
        'Begin Time (ERT)': '%Y-%jT%H:%M:%S.%f',
        'End Time (ERT)': '%Y-%jT%H:%M:%S.%f',
    }
    NAME = 'evr gap'

    @property
    def default_html_row_style(self):
        """Styles the row based on the severity of the missing EVRs."""
        return EVR_LEVEL_COLORS[self.level]
    
    @property
    def time(self):
        """The starting timestamp of the detected gap."""
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        return self.source['Begin Time']
        return Time(self.source['Begin Time'])

    @property
    def time_str(self):
        """String representation of the gap's beginning."""
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        #TO DO: consider making this NOT a property so we can pass
        #different time formats in
        return datetime.strftime(self.source['Begin Time'], self.TIME_FORMATS['Begin Time'])
        return Time(self.source['Begin Time'])
    
    @property
    def level(self):
        """The severity level for which this gap was detected."""
        return self.source['Level']

class EvrGapContainer(DataContainer):
    """
    A container for auditing and reporting missing EVR data.

    **The Concept:**
    In operations, unavoidable data gaps occur (e.g., atmospheric interference). 
    This container provides the "Audit Trail" for those gaps, allowing operators 
    to proceed with caution if they know critical 'FATAL' or 'COMMAND' level 
    messages are missing from their current view.
    """

    NAME = 'evr gap container'
    DATA_ITEM_CLS = EvrGapItem
    LEVELS = ['DIAGNOSTIC', 'COMMAND', 'ACTIVITY_LO', 'ACTIVITY_HI', 'WARNING_LO', 'WARNING_HI', 'FATAL', 'SIM ERROR']
    
    def __init__(self, raw_data=None, metadata=None, name=None, cast_fields=False, **kwargs):
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
        """Columns displayed in reports."""
        return self._repr_cols

    @property
    def default_time_label(self):
        """Primary chronological key for sorting gaps."""
        return self._default_time_label