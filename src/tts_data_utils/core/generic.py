#Python Imports
import pdb
from abc import ABC, abstractmethod
from datetime import datetime

#JPL Imports
from jpl_time import Time
from jpl_time.jpl_time import TimeConversionError

#This Library Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

class GenericItem(DataItem):
    """
    DataItem to go with GenericContainer

    No validation requirements on these items.
    """
    #these are the fields that will be validated against these
    #data types. Other fields are allowed

    DICT_VALID_KEYS = []

    TIME_FORMATS = {}
    NAME = 'Generic Data Item'


    @property
    def default_html_row_style(self):
        return {}
    
    @property
    def time(self):
        return

    @property
    def time_str(self):
        return

class GenericContainer(DataContainer):
    """
    Container provided for hooking into DataContainer infrastructure for which there is
    no extended class.

    Usually this class shouldn't be used in production, but is nice to have in development,
    especially when prototyping behavior for data types for which you are not certain you
    will want to eventually define an extension.

    Some behavior will be missing without data validation defined, and no default styles
    for html or text repr will be available.

    For parameters, see DataContainer
    """
    NAME = 'Generic Items'
    DATA_ITEM_CLS = GenericItem
    
    def __init__(self, raw_data=None, name=None, **kwargs):
        super().__init__(raw_data=raw_data, **kwargs)
        self.name = 'Generic Container' if name is None else name
        
        # Check if we have records to determine default columns
        if self.records:
            # Use the merged values from the first record instead of raw_data
            self._repr_cols = list(self.records[0].values.keys())
            self._csv_cols = self._repr_cols

    def _impl_init(self):
        return

    @property
    def repr_cols(self):
        return self._repr_cols

    @property
    def default_time_label(self):
        return

