#Standard Library Imports
from abc import ABC, abstractmethod

#Installed Library Imports
import pdb
from datetime import datetime

#JPL Imports
from jpl_time import Time

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_data_utils.multimission.alarms import AlarmRecordContainer

#This Library Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

log = create_logger(__name__)

class EhaItem(DataItem):
    """
    A specialized DataItem representing a single telemetry point from an AMPCS-style stream.

    **The Concept:**
    Engineering Health Analysis (EHA) data is the "pulse" of a spacecraft. Each item 
    represents a single measurement (a channel) at a specific point in time. Because 
    spacecraft data can have very different timestamps depending on where it is
    in space, this class tracks multiple timestamps (SCET, ERT, SCLK) to reconcile 
    when an event happened at the spacecraft versus when it was received on Earth.

    **Data Logic (DN vs EU):**
    Telemetry is often received as a raw "Data Number" (DN). This class stores the 
    raw DN, its string representation, and—if calibration is applied—the 
    "Engineering Unit" (EU), which is the physical value (e.g., Volts, Celsius).

    :param recordType: Record Type for this data point.
    :type recordType: str
    :param sessionId: AMPCS session ID for this data point.
    :type sessionId: int
    :param sessionHost: AMPCS session host for this data point.
    :type sessionHost: str
    :param channelId: Unique identifier for the telemetry channel.
    :type channelId: str
    :param dssId: Deep Space Station identifier.
    :param vcid: Virtual Channel ID.
    :type vcid: int
    :param name: Human-readable name of the channel.
    :type name: str
    :param module: Flight Software Module that produced this channel.
    :type module: str or None
    :param ert: Earth Receive Time (UTC).
    :type ert: datetime
    :param scet: Spacecraft Elapsed Time (UTC).
    :type scet: datetime
    :param rct: Range Corrected Time.
    :type rct: datetime or None
    :param lst: Local Mean Solar Time (Mars surface time).
    :type lst: str or None
    :param sclk: Spacecraft clock (seconds since epoch).
    :type sclk: float
    :param dn: Raw Data Number.
    :type dn: int | float | str
    :param dnStr: String representation of the DN.
    :type dnStr: str
    :param eu: Calibrated Engineering Unit.
    :type eu: float or None
    :param status: Enumerated string value (e.g., 'OK', 'TIMEOUT').
    :type status: str
    :param dnAlarmState: Is the raw value in an alarm state?
    :type dnAlarmState: str
    :param euAlarmState: Is the engineering value in an alarm state?
    :type euAlarmState: str
    :param realtime: True if received in realtime; False if played back from recorders.
    :type realtime: bool
    :param type: Channel source (e.g., 'FSW' or 'SSE').
    :type type: str
    """

    DICT_VALID_KEYS = [
        ('recordType', str), 
        ('sessionId', int), 
        ('sessionHost', str), 
        ('channelId', str), 
        ('dssId', int),
        ('vcid', int),
        ('name', str),
        ('module', (str, None)),
        ('ert', datetime),
        ('scet', datetime),
        ('rct', (datetime, None)),
        ('lst', (str, None)), #this should be Time from jpl_time, but we're not there yet
        ('sclk', float),
        ('dn', (int, float, str)),
        ('dnStr', str), #what even is this field? String chanel value? I don't have any in my dateset
        ('eu', (float, None)),
        ('status', str),
        ('dnAlarmState', str),
        ('euAlarmState', str),
        ('realtime', bool),
        ('type', str),
        ]

    TIME_FORMATS = {
        'scet': '%Y-%jT%H:%M:%S.%f',
        'ert': '%Y-%jT%H:%M:%S.%f'
    }
    NAME = 'eha'


    @property
    def default_html_row_style(self):
        """Returns default CSS styles for HTML table rows."""
        return {}
    
    @property
    def time(self):
        """
        The primary timestamp for the telemetry point.

        **Usage Note:** Currently defaults to `scet` (Spacecraft Elapsed Time).
        """
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        return self.source['scet']
        return Time(self.source['scet'])

    @property
    def time_str(self):
        """
        Returns the primary timestamp formatted as a string.
        """
        #TO DO: Figure out path forward
        #that can use JPL Time or not
        #TO DO: consider making this NOT a property so we can pass
        #different time formats in
        return datetime.strftime(self.source['scet'], self.TIME_FORMATS['scet'])
        return Time(self.source['scet'])

class EhaContainer(DataContainer):
    """
    A specialized container for AMPCS time-series telemetry data.

    **JPL/NASA Context:**
    While designed for AMPCS (Advanced Multi-Mission Operations System) data formats 
    common at JPL, this serves as a general-purpose pattern for any NASA mission 
    tracking time-stamped channel values.

    :param raw_data: List of dictionaries matching the EhaItem schema.
    :param metadata: Header or session metadata from the telemetry source.
    :param name: Override name for the container instance.
    :param cast_fields: If True, attempts to convert raw inputs to EhaItem types.
    """

    NAME = 'eha'
    DATA_ITEM_CLS = EhaItem
    
    def __init__(self, raw_data=None, metadata=None, name=None, cast_fields=False, **kwargs):
        #TO DO; Clean this up. Shouldn't be checking for a string like this
        #and need to clean up at a higher level
        if metadata is not None:
            metadata = {k:v for k, v in metadata.items() if k[0] != '_' and k != 'dictionary'}
        super().__init__(raw_data=raw_data, metadata=metadata, cast_fields=cast_fields, **kwargs)
        self.name = 'EHA Container' if name is None else name
        self._repr_cols = ['channelId', 'name', 'scet', 'dn', 'eu', 'status', 'type']
        self._default_time_label = 'scet'
        self._repr_cols = [x for x, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]
        self._csv_cols = [x for x, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]

    def _impl_init(self):
        """Internal initialization hook."""
        return

    def lad(self, time_type=None):
        """
        Calculates and returns the "Latest Available Data" (LAD).

        **The Concept:**
        In a stream containing thousands of data points, you often only want to 
        know the *current* state of the spacecraft. LAD collapses the time series 
        by identifying every unique channel and returning only the record with 
        the most recent timestamp for that channel.

        :param time_type: The time field to use for determining 'recency' (e.g., 'scet', 'ert').
        :type time_type: str
        :return: A new EhaContainer containing only the latest points.
        :rtype: EhaContainer
        """
        sorted_records = self.sort(time_type)
        unique_values = self.unique('channelId')
        records = []
        for unique_value in unique_values:
            records.append(sorted_records.eq('channelId', unique_value)[-1])

        new_obj = self._copy(new_records=records)

        #TO DO: This is duplicated in DataContainer.filter(), pull it out into
        #its own method so we can share better.
        if len(self.records):
            percent_remaining = f'{len(new_obj.records)/len(self.records)*100:.2f}'
        else:
            percent_remaining = 'NA'

        new_obj.history._add_record({
            'Action': 'Filtered', 
            'Description': 'LAD', 
            'Ending Count': len(new_obj.records),
            'Starting Count': len(self.records), 
            'Percent Remaining': percent_remaining
        })
        return new_obj

    @property
    def repr_cols(self):
        """The list of columns used for visual/table representations."""
        return self._repr_cols

    @property
    def default_time_label(self):
        """The default time field used for sorting and LAD operations."""
        return self._default_time_label


    def _build_unique_alarm_record(self, typ, level):
        alarmed_chanvals = self.eq(f'{typ}AlarmState', level)
        unique_channels_this_state = alarmed_chanvals.unique('channelId')
        records = []
        for channel_id in unique_channels_this_state:
            chanvals_this_channel = alarmed_chanvals.eq('channelId', channel_id).sort()           
            record = {
                'Level': level,
                'Type': typ,
                'Count': len(chanvals_this_channel),
                'First Time (scet)': chanvals_this_channel[0]['scet'],
                'Last Time (scet)': chanvals_this_channel[-1]['scet'],
                'First Time (sclk)': chanvals_this_channel[0]['sclk'],
                'Last Time (sclk)': chanvals_this_channel[-1]['sclk'],
                'First Time (lst)': chanvals_this_channel[0]['lst'],
                'Last Time (lst)': chanvals_this_channel[-1]['lst'],
                'Smallest Violating Value': min(chanvals_this_channel[typ]),
                'Largest Violating Value': max(chanvals_this_channel[typ])
            }
            records.append(record)
        return records

    def unique_alarms(self):

        records = self._build_unique_alarm_record('dn', 'YELLOW')
        records += self._build_unique_alarm_record('eu', 'YELLOW')
        records += self._build_unique_alarm_record('dn', 'RED')
        records += self._build_unique_alarm_record('eu', 'RED')        

        return AlarmRecordContainer(raw_data=records)
