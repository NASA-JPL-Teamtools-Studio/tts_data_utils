import pdb
from abc import ABC, abstractmethod

from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

from jpl_time import Time

class DataContainerHistoryItem(DataItem):
    """
    DataItem to go with DataContainerHistoryContainer

    :param Action: Which action was taken at the step represented in this row?
    :type Action: str

    :param Description: Description of the action taken at the step represented in this row
    :type Description: str
    
    :param Ending Count: Number of records after the action was taken
    :type Ending Count: int
    
    :param Starting Count: Number of records before the action was taken
    :type Starting Count: int
    
    :param Percent Remaining: Percentage of records at this step relative to previous step
    :type Percent Remaining: float
    
    """

    DICT_VALID_KEYS = [
        ('Action', str), 
        ('Description', str), 
        ('Ending Count', (int, float, str)), 
        ('Starting Count', (int, float, str)), 
        ('Percent Remaining', (int, float, str))
        ]

    def __sub_init(self):
        return

    def time(self):
        return

class DataContainerHistoryContainer(DataContainer):
    """
    A special container that is added by default to all data containers (except history 
    containers to avoid infinite recursion).

    As containers are filtered, appended, and sliced, it can become difficult to trace 
    how a particular came to be. The DataContainerHistoryContiner tracks actions that
    have been taken in order to build a container from its initial metadata and including
    each manipulation that happens going forward.

    Data Container history is not meant to make previous states of the container
    reproducable, but just to offer a crutch in debugging code.

    The number of records is also provided to enable some level of data analysis based
    on filtering values.

    :param name: The name of this instantiation of the data container.
    :type name: str

    :param metadata: Dictionary of open-ended metadata that can be provided in extensions of DataContainer
    :type metadata: dict
    """

    NAME = 'data container history'
    DATA_ITEM_CLS = DataContainerHistoryItem

    def __init__(self, name, metadata):
        super().__init__()
        self.name = name
        self.metadata = metadata
        self.records = []
        self._repr_cols = ['Action', 'Description', 'Starting Count', 'Ending Count', 'Percent Remaining']

    @property
    def repr_cols(self):
        return self._repr_cols