#Python Imports
import pdb
from abc import ABC, abstractmethod
from datetime import datetime

#JPL Imports
from jpl_time import Time

#This Library Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

ALARM_LEVEL_COLORS = {
    'YELLOW':  {'background-color': '#F0F001', 'color': '#333333'},
    'RED':       {'background-color': '#FF5E66', 'color': '#F1F1F2'} ,
}

class AlarmRecordItem(DataItem):
    DICT_VALID_KEYS = [
        ('Level', str), 
        ('Type', str), 
        ('Count', int),
        ('First Time (scet)', (datetime, None)),
        ('Last Time (scet)', (datetime, None)),
        ('First Time (sclk)', (float, None)),
        ('Last Time (sclk)', (float, None)),
        ('First Time (lst)', (datetime, None)),
        ('Last Time (lst)', (datetime, None)),
        ('Largest Violating Value', (float, int, str)),
        ('Smallest Violating Value', (float, int, str)),

        ]

    TIME_FORMATS = {
        'scet': '%Y-%jT%H:%M:%S.%f',
        'ert': '%Y-%jT%H:%M:%S.%f',
        'rct': '%Y-%jT%H:%M:%S.%f',
        'lst': 'TBD' #need to incorporate jpl_time to make this work
    }
    NAME = 'alarm record'

    @property
    def default_html_row_style(self):
        """Returns row styling based on the EVR severity level."""
        return ALARM_LEVEL_COLORS[self.level]
    
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
        return self.source['Level']

class AlarmRecordContainer(DataContainer):
    NAME = 'Alarm Records Container'
    DATA_ITEM_CLS = AlarmRecordItem
    
    def __init__(self, raw_data=None, metadata=None, name=None, cast_fields=False, **kwargs):
        #TO DO; Clean this up. Shouldn't be checking for a string like this
        #and need to clean up at a higher level
        if metadata is not None:
            metadata = {k:v for k, v in metadata.items() if k[0] != '_' and k != 'dictionary'}
        super().__init__(raw_data=raw_data, metadata=metadata, cast_fields=cast_fields, **kwargs)
        self.name = 'Alarm Record Container' if name is None else name
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

