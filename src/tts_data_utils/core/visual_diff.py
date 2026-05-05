#Python Imports
import pdb
from abc import ABC, abstractmethod
from datetime import datetime

#JPL Imports
from jpl_time import Time
from jpl_time.jpl_time import TimeConversionError

#Teamtool Studio Imports
from tts_html_utils.core.palette import VisDiffPalette

#This Library Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

class VisualDiffItem(DataItem):
    """
    A specialized data record designed for side-by-side comparison.

    **The Concept:**
    When comparing two versions of a dataset (a "Diff"), we don't just care about the 
    raw values—we care about the *state* of each row relative to its counterpart. 
    Is it new? Was it deleted? Was it modified?

    A `VisualDiffItem` carries the data values along with metadata (prefixed with `_visdiff`) 
    that tells a renderer exactly how to style the row (e.g., green for an insert, 
    red for a delete) to make differences immediately obvious to a human reviewer.

    **Styling Logic:**
    * **Row Level:** The entire background color is determined by the `_visdiff_match` status.
    * **Cell Level:** Individual cells are highlighted if their specific key exists in 
      the `_mismatched_keys` list.
    """

    DICT_VALID_KEYS = [
        ('_visdiff_index', (int, None)),
        ('_visdiff_match', (str, None)),
        ('_mismatched_keys', list)
        ]

    TIME_FORMATS = {
        'Time': '%Y-%jT%H:%M:%S.%f'
    }

    NAME = 'Generic Data Item'


    @property
    def default_html_row_style(self):
        """
        Returns the CSS style dictionary for the table row based on the match status.
        """
        try:
            return VisDiffPalette[self['_visdiff_match']]
        except:
            import pdb; pdb.set_trace()
    @property
    def default_html_cell_styles(self):
        """
        Returns a mapping of column keys to CSS styles, highlighting specific 
        mismatched cells.
        """
        return {k: {'background-color': '#218FFF'} if k in self['_mismatched_keys'] else {} for k in self.values.keys()}

    
    @property
    def time(self):
        """
        Returns the native time object for the item.
        """
        return

    @property
    def time_str(self):
        """
        Returns a formatted string representation of the item's timestamp.
        """
        return

class VisualDiffContainer(DataContainer):
    """
    A collection of VisualDiffItems, representing a full comparison report.

    **Concept:**
    The `VisualDiffContainer` acts as the manager for a set of diffed records. It 
    distinguishes between "Display" columns (what the user needs to see) and 
    "Metadata" columns (the internal flags used to calculate differences).

    **Usage Note:**
    By default, any column starting with an underscore (`_`) is treated as internal 
    metadata and is hidden from the standard `repr_cols` view, though it remains 
    accessible for CSV exports and logic processing.

    :param raw_data: A list of dictionaries representing the diffed rows.
    :type raw_data: list[dict]
    :param name: The name of the container/report. Defaults to 'Generic Container'.
    :type name: str, optional
    :param kwargs: Additional arguments passed to the parent `DataContainer`.
    """
    NAME = 'Visual Diff Container'
    DATA_ITEM_CLS = VisualDiffItem
    
    def __init__(self, raw_data=None, name=None, **kwargs):
        #TO DO; Clean this up. Shouldn't be checking for a string like this
        #and need to clean up at a higher level
        super().__init__(raw_data=raw_data, **kwargs)
        self.name = 'Generic Container' if name is None else name
        self._repr_cols = [x for x, _ in raw_data[0].items() if not x.startswith('_')]
        self._csv_cols = [x for x, _ in raw_data[0].items()]

    def _impl_init(self):
        """
        Internal initialization hook for custom setup logic.
        """
        return

    @property
    def repr_cols(self):
        """
        The list of columns intended for visual display (excludes internal metadata).
        """
        return self._repr_cols

    @property
    def default_time_label(self):
        """
        The primary time-based column label used for sorting or indexing.
        """
        return