#Python Imports
from abc import ABC, abstractmethod
from copy import copy, deepcopy
from datetime import datetime, timedelta
import hashlib
import inspect
import json
from math import isnan
import os
import pandas as pd
from difflib import SequenceMatcher
import pdb
import re
import sys
from tabulate import tabulate
from itertools import product

#JPL Imports
from tts_html_utils.core.components.table import PowerTable
from tts_utilities.logger import create_logger

#This Library Imports
from tts_data_utils.core.data_item import DataItem


log = create_logger(__name__)

#TO DO: Move this to utils
def find_bad_utf8_characters(filepath):
    """
    Helper function to identify non-UTF-8 characters in CSV files, common when 
    interacting with Windows-generated Microsoft Excel files.

    **The Problem:**
    When CSVs are saved via Excel on Windows, non-UTF-8 characters—like curled 
    quotation marks, single-character arrows, and degree symbols—are often added. 
    Attempting to read these into Pandas causes a `UnicodeDecodeError`.

    **The Solution:**
    This script allows developers to catch that exception, read the file in binary 
    mode, and report the exact line and byte offset of the first error to 
    facilitate cleaning.

    **Future Improvements:**
    * Amend to repair the file automatically (referencing the M20 dictionary 
      input management logic).
    * Report all encoding errors instead of just the first.

    See ticket #31 ( TO DO: Migrate out of JPL-internal issues))

    :param filepath: Path to the CSV file to be checked.
    :type filepath: str or pathlib.Path
    """
    with open(filepath, 'rb') as file:
        for line_num, line_bytes in enumerate(file, start=1):
            try:
                line_bytes.decode('utf-8')
            except UnicodeDecodeError as e:
                print(f"UnicodeDecodeError on line {line_num}")
                print(f"  Problem at byte offset: {e.start}")
                print(f"  Invalid byte: {line_bytes[e.start]:#04x}")
                
                # Print context (optional)
                context = line_bytes[max(0, e.start-10):e.start+10]
                print(f"  Context (raw bytes): {context}")
                print(f"  Full Line (raw bytes): {line_bytes}")
        
        # TO DO: Make it so instead of just reporting and bailing, this
        # function repairs the bad byte. They're essentially never due to 
        # file corruption. Only due to Microsoft thinking they're more clever
        # than everyone else and using curly quotes or similar.
        # In the M20 dictionary input management code, we handled this more
        # gracefully, and this should be built into a general soltion to do the same.
        sys.exit()

class DataContainer(ABC):
    """
    Primary (abstract) class for this library. Provides representation of 2D data with 
    extension hooks for easy definition of quality-of-life features for any bespoke 
    data type across projects.

    **Concept:**
    Allows for easy tabular representation in terminals and HTML, playing nicely with 
    `html_utils` to provide easy reporting of tabular data and nested tabular data.

    When defining an extension of this class, a `DataItem` class is also provided, 
    which controls the expected columns in each row.

    Each row of the 2D data is represented by an instance of the associated `DataItem` 
    class, stored in `self.records`. Most dunder methods have been defined such that 
    this class behaves like a list (mapping to `self.records`), but carries the 
    container's metadata and history along with it.

    **TO DO:** Provide gallery of examples of outputs (see ticket #34 TO DO: Migrate out of JPL-internal issues)

    :param raw_data: 2D data to be transformed into DataContainer.
    :type raw_data: list[dict], optional
    :param subcontainers: List of dictionaries where key is a label and value is a 
                          DataContainer. Must match length of raw_data.
    :type subcontainers: list[dict[str, DataContainer]], optional
    :param csv_path: Path for CSV to be transformed into DataContainer.
    :type csv_path: Path | str, optional
    :param xlsx_path: Path for XLSX to be transformed into DataContainer.
    :type xlsx_path: Path | str, optional
    :param django_records: Django object containing data to be transformed.
    :type django_records: QuerySet, optional
    :param metadata: Arbitrary user information to be carried with the container.
    :type metadata: dict, optional
    :param name: Name of the DataContainer instance.
    :type name: str, optional
    :param cast_fields: If True, attempts to force data into types defined in DataItem.
    :type cast_fields: bool
    :param validate: If True, validates inputs against DataItem's valid keys/types.
    :type validate: bool
    :param lorem: If provided as an integer, generates that many rows of dummy data.
    :type lorem: int, optional
    """
    DATA_ITEM_CLS = None
    """Associated DataItem that must be defined alongside a DataContainer."""

    DO_NOT_DIFF = []
    """Keys to ignore when running self.diff."""

    def __init__(self, raw_data=None, subcontainers=None, csv_path=None, xlsx_path=None, django_records=None, metadata=None, name=None, cast_fields=False, validate=True, lorem=None, **kwargs):
        self.name = self.NAME if name is None else name

        if metadata is not None:
            metadata = {k:v for k, v in metadata.items() if k[0] != '_' and k != 'dictionary'}

        if '_repr_cols' not in self.__dict__.keys():
            self._repr_cols = [x for x, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]
        if '_csv_cols' not in self.__dict__.keys():
            self._csv_cols = [x for x, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]
        if '_repr_filters' not in self.__dict__.keys():
            self._repr_filters = []
        if 'name' not in self.__dict__.keys():
            self.name = self.NAME

        mutually_exclusive_kwargs = [raw_data, csv_path, xlsx_path, django_records, lorem]
        if sum([m is not None for m in mutually_exclusive_kwargs]) > 1:
            raise Exception('Cannot have more than one data source.')
        
        is_django = False
        if csv_path is not None:
            # did you know that DataFrame.fillna(None) doens't work???
            try:
                raw_data = self.read_csv(csv_path)
            except UnicodeDecodeError:
                find_bad_utf8_characters(csv_path)
            for row in raw_data:
                for k, v in row.items():
                    if not isinstance(v, (int, float)): continue
                    if isnan(v): row[k] = None
        elif xlsx_path is not None:
            raw_data = self.read_xlsx(xlsx_path)
        elif raw_data is not None:
            pass
        elif django_records is not None:
            raw_data = django_records
            is_django = True
        elif lorem is not None:
            # Import here to avoid circular imports
            from tts_data_utils.core.lorem_utils import generate_lorem_data_for_item
            
            # Generate lorem ipsum data based on the DATA_ITEM_CLS
            if not isinstance(lorem, int) or lorem <= 0:
                lorem = 10  # Default to 10 records if not specified correctly
            raw_data = generate_lorem_data_for_item(self.DATA_ITEM_CLS, num_records=lorem)
        else:
            raw_data = []

        if subcontainers is None:
            self.records = [self.DATA_ITEM_CLS(r, cast_fields=cast_fields, validate=validate, is_django=is_django) for r in raw_data]
        elif len(raw_data) != len(subcontainers):
            raise Exception('"subcontainers" must be the same length as data that forms DataItems (e.g raw_data, data at csv_path, data coming from django object)')
        else:
            self.records = [self.DATA_ITEM_CLS(r, cast_fields=cast_fields, validate=validate, is_django=is_django, subcontainers=s) for r, s in zip(raw_data, subcontainers)]
        
        self.metadata = metadata
        # Avoids circular dependency. Probably a better way to do it
        # but here we are...
        from tts_data_utils.core.container_history import DataContainerHistoryContainer
        if not isinstance(self, DataContainerHistoryContainer):
            self.history = DataContainerHistoryContainer(self.name, self.metadata)
            self.history._add_record({
                'Action': 'Initialized', 
                'Description': str(self.metadata),
                'Ending Count': len(self.records),
                'Starting Count': '0', 
                'Percent Remaining': 'NA'
                })
        else:
            # Avoid infinite recursion. 
            # I tried once, but never got to the bottom of it.
            self.history = None


        ##################################################################################
        # Dexter-specific attributes, consider reorganizing this so not every DataItem gets this
        ##################################################################################        
        self._bypass_validation = False
        self._sub_container = False

    def _impl_init(self):
        """Internal setup hook for subclasses."""
        return

    def _impl_populate(self):
        """Internal data population hook for subclasses."""
        return

    @classmethod
    @property
    @abstractmethod
    def NAME(cls):
        """Name of the data type being contained, i.e. 'evr', 'transpire_commands'."""
        raise NotImplementedError


    @property
    def repr_cols(self):
        """Columns to be used for representations (terminal, HTML, etc.)."""
        if '_repr_cols' in self.__dict__.keys():
            return self._repr_cols
        else:
            return [x for x, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]
    
    def docx_table(self, template=None):
        """
        Produces a Microsoft Word table representation.

        :param template: Path to an optional template docx for styling.
        :return: Rendered DocxTable object.
        """

        #TO DO: Fix this without a circular dependency. Data utils can't require
        #Papertrail because Papertrail already depends on data_utils
        table_builder = DocxTable(template, self.records, headers=self._repr_cols, row_styles=[r.default_rich_text_row_style for r in self.records])
        return table_builder.render()

    def power_table(self, superheader=None, columns=None, bypass_styles=False, row_styles=None, cell_styles=None, **kwargs):
        """
        Produce a rich, interactive HTML table representation of this DataContainer.

        **Concept:**
        This method integrates with `html_utils` to translate the 2D records into a 
        `PowerTable`. It handles complex nesting by recursively calling `power_table` 
        on any subcontainers linked to specific rows.

        :param superheader: Title row spanning the full width of the table.
        :type superheader: str
        :param columns: Labels to include. Defaults to `self.repr_cols`.
        :type columns: list[str]
        :param bypass_styles: If True, default CSS and row-level styles are ignored.
        :type bypass_styles: bool
        :param row_styles: Custom CSS for each row. Must match `self.records` length.
        :type row_styles: list[dict[str, str]]
        :param cell_styles: Custom CSS for each cell. Must match `self.records` length.
        :type cell_styles: list[list[dict[str, str]]]
        :param kwargs: Passthrough arguments for PowerTable (e.g., `id`, `add_filters`).
        :return: A rendered PowerTable component.
        """

        # TO DO: Rethink how we handle repr_cols here when you're not so braindead
        row_data = [(r.values, [subcontainer_obj.power_table(subcontainer_name) for subcontainer_name, subcontainer_obj in r.subcontainers.items()]) for r in self.records]

        if columns is not None:
            repr_cols = columns
        elif self.repr_cols:
            repr_cols = self.repr_cols
        elif len(self.records):
            repr_cols = []
            for r in row_data: repr_cols += [k for k in r[0].keys() if not k.startswith('_')]
            repr_cols = list(set(repr_cols))
        else:
            repr_cols = self.repr_cols if self.repr_cols else [k for k, _ in self.DATA_ITEM_CLS.DICT_VALID_KEYS]

        if bypass_styles:
            row_styles = [{} for r in self.records]
        elif row_styles is not None:
            if len(row_styles) != len(self.records):
                raise ValueError("Row styles must match the number of records")
        else:
            row_styles = [{'background-color': '#EEEEEE'} if ii%2 else {} for ii in range(len(self.records))]
            row_styles = [{**rs, **r.default_html_row_style} for r, rs in zip(self.records, row_styles)]

        if bypass_styles:
            cell_styles = [[{} for k in r.printable_values.keys()] for r in self.records]
        elif cell_styles is not None:
            pass
        else:
            cell_styles = [[r.default_html_cell_styles.get(k,{}) for k in self._repr_cols] for r in self.records]

        table = PowerTable(
            column_fields=repr_cols, 
            row_data=row_data,
            row_styles=row_styles,
            cell_styles=cell_styles,
            **kwargs
            )
        if superheader:
            table.add_superheader(superheader)            
        table.add_header(column_names=repr_cols)
        return table

    @property
    def default_html_row_style(self):
        """Returns default CSS dictionary for HTML rows."""
        return {}

    @property
    def default_time_label(self):
        """Returns the primary key used for time-based operations."""
        return None

    @property
    def valid(self):
        """Returns True if all records pass validation (or if validation is bypassed)."""
        return self._bypass_validation or all(_.valid for _ in self)        

    @property
    def source(self):
        """Returns a list of raw source dictionaries for all contained records."""
        return [_.source for _ in self]

    def __iter__(self):
        """
        Iterates through the container's records.
        
        Allows the DataContainer to be used in loops:
        `for record in container: ...`
        """
        for r in self.records:
            yield r

    def __len__(self):
        """
        Returns the total number of records currently held in the container.
        """
        return len(self.records)

    def __getitem__(self, ii):
        """
        Provides flexible access to data using indexing, slicing, or column keys.

        **Supported Behaviors:**
        * **Integer (`int`):** Returns the specific `DataItem` at that index.
        * **Slice (`slice`):** Returns a new `DataContainer` containing the subset of records.
        * **String (`str`):** Returns a list of all values found in the specified column.
        * **List (`list[str]`):** (Not yet implemented) Intended to return a container with subset columns.

        :param ii: The index, slice, or column name requested.
        :type ii: int | slice | str | list[str]
        :return: A DataItem, a new DataContainer, or a list of values.
        """
        if isinstance(ii, slice):  # Handle slicing
            new_obj = self._copy(self.records[ii.start:ii.stop:ii.step])
            indexes = f'{ii.start}:{ii.stop}:{ii.step}'
        elif isinstance(ii, int):  # Handle index
            return self.records[ii]
        elif isinstance(ii, str):
            if isinstance(self.records, list):
                return [r[ii] for r in self.records]
            else:
                return self.records[ii]
        elif isinstance(ii, list):
            raise NotImplementedError("Lists not implemented yet")
        else:
            raise TypeError("Invalid argument type")

        # Performance check and history logging for sliced objects
        if len(self.records):
            percent_remaining = f'{len(new_obj.records)/len(self.records)*100:.2f}'
        else:
            percent_remaining = 'NA'

        new_obj.history._add_record({
            'Action': 'Get Item', 
            'Description': f'Sliced to {indexes}',
            'Ending Count': len(new_obj.records),
            'Starting Count': len(self.records), 
            'Percent Remaining': percent_remaining
            })

        return new_obj

    def __str__(self):
        """
        Returns the human-readable name of the container.
        """
        return self.name

    def __repr__(self):
        """
        Produces a formatted ASCII grid table for terminal display.

        **Concept:**
        Uses the `tabulate` library to render rows. It filters for columns 
        defined in `self.repr_cols` and uses printable_values to ensure proper formatting.
        """
        if self._repr_filters:
            for repr_filter in self._repr_filters:
                records = self.records
        else:
            records = self.records
            
        # Use printable_values instead of raw values to ensure proper formatting
        rows = [{k: v for k,v in r.printable_values.items() if k in self.repr_cols} for r in records]
        
        if len(rows):
            headers = 'keys'
        else:
            headers = self.repr_cols
            
        return tabulate(rows, headers=headers, tablefmt="grid")

    def _repr_html_(self):
        """
        IPython/Jupyter hook to automatically render an interactive 
        PowerTable when the container is displayed in a notebook.
        """
        table = self.power_table()
        return table.render()

    def __add__(self, other, sort_by=None):
        """
        Concatenates two DataContainers together using the '+' operator.

        **The Concept:**
        This allows for intuitive dataset combination (e.g., `combined = list_a + list_b`). 
        The operation creates a new container copy, preserves the history of the 
        original, and logs the merge event with updated record counts.

        :param other: The other DataContainer to append to this one.
        :type other: DataContainer
        :param sort_by: (Placeholder) Optional key to sort by after merging.
        :return: A new DataContainer containing records from both parents.
        """
        new_obj = self._copy(self.records + other.records)

        if len(self.records):
            percent_remaining = f'{len(new_obj.records)/len(self.records)*100:.2f}'
        else:
            percent_remaining = 'NA'

        new_obj.history._add_record({
            'Action': 'Merged', 
            'Description': 'TBD, need to figure out how to represent this',
            'Ending Count': len(new_obj.records),
            'Starting Count': len(self.records), 
            'Percent Remaining': percent_remaining
            })
        return new_obj


    def table(self, columns=None):
        """
        Explicitly prints the ASCII grid table representation to standard output.

        **Concept:**
        While `__repr__` handles automatic display in the terminal, this method 
        allows for programmatic printing with an optional subset of columns.

        :param columns: List of column labels to include. Defaults to `self.repr_cols`.
        :type columns: list[str], optional
        """
        if columns is None: columns = self.repr_cols
        
        # Use printable_values instead of raw values to ensure proper formatting
        rows = [{k: v for k,v in r.printable_values.items() if k in columns} for r in self.records]

        if len(rows):
            headers = 'keys'
        else:
            headers = self.repr_cols

        print(tabulate(rows, headers=headers, tablefmt="grid"))

    def _diff(self, left, right):
        """
        Internal stub for shared diffing logic. 
        Override or implement to provide custom comparison behaviors.
        """
        return
        #make this the common diff

    def diff(self, left='48vf34VD)$', right='48vf34VD)$', name='', ancestors='', diff_container=None, summarize=False, debug=False, do_not_diff_keys=[], ignore=[], float_tol=1e-10):
        """
        Generates a DiffContainer with a comprehensive comparison between two objects.
        Recursively trees down through all attributes until the structures are fully diffed.

        **The Concept:**
        This method is the backbone of the library's regression testing suite. It is designed 
        to compare a runtime DataContainer against a "vetted" baseline (typically from a CSV).
        It identifies missing keys, mismatched values, and type discrepancies across 
        nested lists and dictionaries.

        **Handling Differently Ordered Data:**
        Note that this method does not yet handle reordered containers gracefully; it is 
        optimized for structures that are expected to be very similar in sequence.

        **The Null Guard:**
        The default value '48vf34VD)$' is used instead of None to allow `None` to be 
        passed as a valid value to be diffed without triggering the "missing argument" logic.

        :param left: The primary value or container to compare.
        :param right: The second value or container to compare. If omitted, `self` is 
                      treated as `left` and the first argument is treated as `right`.
        :param name: Internal tracker for the current field name (used in recursion).
        :param ancestors: Internal tracker for the breadcrumb path (used in recursion).
        :param diff_container: The accumulator for diff results.
        :param summarize: If True, returns a boolean (True if all match) instead of the container.
        :param do_not_diff_keys: Keys to skip (useful for history or dynamic IDs).
        :param ignore: Output paths to prune from the final results.
        :param float_tol: Maximum allowance for floating-point precision drift.
        :return: A DiffContainer object or a boolean result.
        """

        # Logic to handle self-diffing if only one argument is provided
        if left == '48vf34VD)$':
            raise Exception('Need something to diff against!')
        if right == '48vf34VD)$':
            # This allows a user to call self.diff(other_obj).
            # self becomes left, and the argument becomes right.
            right = left
            left = self

        if isinstance(ignore, str): ignore = [ignore]

        ancestors += '/' + name

        if len(ancestors) >= 2:
            if ancestors[:2] == '//': ancestors = ancestors[1:]

        # Import locally to avoid circular dependency issues
        if diff_container is None:
            from tts_data_utils.core.diff import DiffContainer
            diff_container = DiffContainer('tbd', 'tdb')

        # 1. Compare Types
        if type(left) != type(right):
            left_str = f'Type: {type(left).__name__}'
            right_str = f'Type: {type(right).__name__}'
            typename = 'various'
            same = False
            
        # 2. Compare Floats with Tolerance
        elif isinstance(left, float):
            left_str = str(left)
            right_str = str(right)
            typename = f'float ({float_tol} diff tolerance)'
            if abs(left - right) < float_tol:
                same = True
            else:
                same = False
                
        # 3. Compare Base Types (Int, Bool, Str, Datetime)
        elif isinstance(left, (int, bool, str, datetime)):
            left_str = str(left)
            right_str = str(right)
            typename = type(left).__name__
            if left == right:
                same = True
            else:
                same = False
                
        # 4. Compare via Identity (Fallback for complex objects)
        elif left is right:
            left_str = f'Same memory location'
            right_str = f'Same memory location'
            same = True
            typename = type(left).__name__    
            
        # 5. Recursive List Comparison
        elif isinstance(left, list):
            same = True
            left_str = 'Children All Same'
            right_str = 'Children All Same'
            typename = 'list'
            if len(left) != len(right):
                same = False
                left_str = f'List size differs ({len(left)})'
                right_str = f'List size differs ({len(right)})'
            else:
                for ii, (l, r) in enumerate(zip(left, right)):
                    ii_same = self.diff(l, r, name=str(ii), ancestors=ancestors, diff_container=diff_container, summarize=True, debug=debug)
                    if not ii_same: 
                        same = False
                        left_str = 'Children Differ'
                        right_str = 'Children Differ'

        # 6. Recursive Dictionary Comparison
        elif isinstance(left, dict):
            same = True
            keys_with_different_values = []
            keys_in_left_not_right = []
            keys_in_right_not_left = []
            typename = 'dict'
            for k, v in left.items():
                if k in do_not_diff_keys:
                    # we only skip keys if the dict is an internal __dict__ 
                    # of a DataContainer or DataItem.
                    continue
                elif k in right.keys():
                    if isinstance(do_not_diff_keys, dict) and k in do_not_diff_keys.keys(): 
                        shared_kv_same = self.diff(left[k], right[k], name=k, ancestors=ancestors, diff_container=diff_container, summarize=True, do_not_diff_keys=do_not_diff_keys[k])
                    else:
                        shared_kv_same = self.diff(left[k], right[k], name=k, ancestors=ancestors, diff_container=diff_container, summarize=True)
                    if not shared_kv_same: keys_with_different_values.append(k)
                else:
                    keys_in_left_not_right.append(k)
                    
            for k, v in right.items():
                if k in do_not_diff_keys:
                    continue
                elif k in left.keys():
                    pass
                else:
                    keys_in_right_not_left.append(k)

            left_comments = []
            right_comments = []
            if keys_with_different_values:
                same = False
                left_comments.append('Keys with diffs: ' + ', '.join(keys_with_different_values))
                right_comments.append('Keys with diffs: ' + ', '.join(keys_with_different_values))
            if keys_in_left_not_right:
                same = False
                right_comments.append('Missing Keys: ' + ', '.join(keys_in_left_not_right))
            if keys_in_right_not_left:
                same = False
                left_comments.append('Missing Keys: ' + ', '.join(keys_in_right_not_left))
            if same:
                left_comments.append('All k/v pairs same')
                right_comments.append('All k/v pairs same')

            left_str = '\n'.join(left_comments)
            right_str = '\n'.join(right_comments)

        # 7. Library Object Comparison (DataItem/DataContainer)
        elif isinstance(left, (globals().get('DataContainer'), DataItem)):
            from tts_data_utils.core.diff import DiffItem
            same = self.diff(left.__dict__, right.__dict__, name=self.name, ancestors=ancestors, diff_container=diff_container, summarize=True, debug=debug, do_not_diff_keys=left.DO_NOT_DIFF)
        
            if not same:
                left_str = 'See children'
                right_str = 'See children'
            else:
                left_str = 'All children same'
                right_str = 'All children same'                
            typename = type(left).__name__
        else:
            same = False
            left_str = 'Undiffable Type'
            right_str = 'Undiffable Type'
            typename = type(left).__name__

        # Log results to the accumulator
        diff_container.append({
            'Key': ancestors ,
            'Same': same,
            'Type': typename,
            'Left': left_str,
            'Right': right_str,
            'left': left,
            'right': right
            })

        # Apply ignoring logic for output pruning
        for ignored_path in ignore:
            diff_container = diff_container.ne('Key', '/')
            diff_container = diff_container.ne('Key', f'/{self.name}')
            diff_container = diff_container.ne('Key', f'/{self.name}/{ignored_path}')
            diff_container = diff_container.doesnotmatch('Key', f'/{self.name}/{ignored_path}/.*')

        if summarize:
            return same
        return diff_container

    def compare_rows(self, l, r):
        """
        Calculates the similarity between two DataItems by counting matching values.

        **Concept:**
        This is used by the visual diff engine to determine if two rows are similar 
        enough to be considered a 'replacement' rather than an 'insertion' and 
        'deletion'. It iterates through keys in the left item and checks for 
        equality in the right item.

        :param l: The left DataItem.
        :type l: DataItem
        :param r: The right DataItem.
        :type r: DataItem
        :return: Integer count of identical fields.
        :rtype: int
        """
        return sum(1 for key in l.values if l.values.get(key) == r.values.get(key))

    def _get_index_from_hash(self, target_hash):
        """
        Returns the index of the first element whose hash() matches the target.

        **Concept:**
        Used to re-align records after visual diff processing. It performs a 
        linear search through `self.records` comparing the Python `hash()` 
        of each record to the target.

        :param target_hash: The hash value to locate.
        :type target_hash: int
        :raises ValueError: If no record matching the hash is found.
        :return: The index of the matching record.
        :rtype: int
        """
        for i, rec in enumerate(self.records):
            if hash(rec) == target_hash:          # compare the hash
                return i
        
        # Trigger debugger to investigate why a record signature was lost
        pdb.set_trace()
        raise ValueError(f'Hash "{target_hash}" not found in records')

    def visual_diff(self, right, ignore_cols=[], tolerance={}):
        """
        Generates a side-by-side visual alignment between this container and another.

        **The Concept:**
        This uses `SequenceMatcher` to find the best horizontal alignment between two 
        datasets. It identifies identical rows, modified rows (replace), and 
        inserted/deleted rows. It then injects "empty" placeholders into the 
        resulting containers so that matching records stay horizontally synchronized 
        when rendered.

        :param right: The DataContainer to compare against.
        :type right: DataContainer
        :param ignore_cols: Columns to exclude from the row-matching signature.
        :type ignore_cols: list[str]
        :param tolerance: Drift allowance for numeric or datetime columns.
        :type tolerance: dict[str, float]
        :return: A tuple of two VisualDiffContainers (left, right).
        """

        #Avoids circular dependency. Probably a better way to do it
        #but here we are...
        from tts_data_utils.core.visual_diff import VisualDiffContainer

        left = self._copy()
        right = right._copy()

        # Generate row signatures
        aa = [{k: v for k, v in r.values.items() if k not in ignore_cols} for r in left.records]
        bb = [{k: v for k, v in r.values.items() if k not in ignore_cols} for r in right.records]

        for a, b in zip(aa, bb):
            for k, v in tolerance.items():
                match = False
                if isinstance(a[k], datetime) and isinstance(b[k], datetime):
                    match = abs((a[k] - b[k]).total_seconds()) < v
                elif isinstance(a[k], datetime) or isinstance(b[k], datetime):
                    raise Exception(f'Compared values for "{k}" must either both be datetimes or both not be datetimes. Got "{type(a[k]).__name__}" and "{type(b[k]).__name__}"')
                else:
                    try:
                        match = abs(a[k] - b[k]) < v
                    except TypeError:
                        raise Exception(f'Compared values for "{k}" must both be numbers or both datetimes. Got "{type(a[k]).__name__} "and "{type(b[k]).__name__}"')
                a[k] = match
                b[k] = match

        aa = [tuple(sorted((k, v) for k, v in a.items())) for a in aa]
        bb = [tuple(sorted((k, v) for k, v in b.items())) for b in bb]
        sm = SequenceMatcher(None, aa, bb)
        # Iterate over opcodes to assign row status
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                # Rows are the same in both, mark as equal
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    left[i]['_visdiff_match'] = 'equal'
                    left[i]['_visdiff_index'] = j
                    right[j]['_visdiff_match'] = 'equal'
                    right[j]['_visdiff_index'] = i
                    left[i]['_mismatched_keys'] = []
                    right[j]['_mismatched_keys'] = []

            elif tag == 'replace':
                # Who hurt you?
                if i2 - i1 != j2 - j1:
                    left_chunk = left[i1:i2]
                    right_chunk = right[j1:j2]

                    #to begin, assume all lefts are deleted and all rights
                    #are added. When we attempt to find best matches below
                    #we will overwrite the best we can
                    for i in range(i1, i2):
                        left[i]['_visdiff_match'] = 'delete'
                        left[i]['_visdiff_index'] = None
                        left[i]['_mismatched_keys'] = []
                    for j in range(j1, j2):
                        right[j]['_visdiff_match'] = 'insert'
                        right[j]['_visdiff_index'] = None
                        right[j]['_mismatched_keys'] = []

                    L = [left[ii] for ii in range(i1,i2)]
                    R = [right[jj] for jj in range(j1,j2)]
                    comparison_triples = [(l, r, self.compare_rows(l,r)) for l, r in product(L,R)]
                    #only consider it a diff if fewer than half the fields have changed. Otherwise it's an add and a delete
                    comparison_triples = [(l, r, score) for l, r, score in comparison_triples if score > len(r.values.keys())/2]
                    comparison_triples.sort(key=lambda x: x[2], reverse=True)

                    assigned_r = set()
                    assigned_l = set()
                    final_matches = {}

                    for l, r, score in comparison_triples:
                        if l not in assigned_l and r not in assigned_r:
                            final_matches[l] = r
                            assigned_l.add(l)
                            assigned_r.add(r)

                    for l, r in final_matches.items():
                        l['_visdiff_match'] = 'replace'
                        # this shouldn't be none, but the way I've done this the code doesn't
                        # have the index at this moment.
                        l['_visdiff_index'] = right._get_index_from_hash(hash(r)) 
                        l['_mismatched_keys'] = [k for k in l.values.keys() if l[k] != r[k]]
                        r['_visdiff_match'] = 'replace'
                        # this shouldn't be none, but the way I've done this the code doesn't
                        # have the index at this moment.
                        r['_visdiff_index'] = left._get_index_from_hash(hash(l))  
                        r['_mismatched_keys'] = [k for k in l.values.keys() if l[k] != r[k]]

                else:
                    for i, j in zip(range(i1, i2), range(j1, j2)):
                        #if the rows don't have at least half their cells in common, then
                        #treat them as add/delete instead of as replace
                        if self.compare_rows(left[i], right[j]) <= (i2 - i1)/2 and i2 - i1 >= 3:
                            left[i]['_visdiff_match'] = 'delete'
                            right[j]['_visdiff_match'] = 'insert'
                            mismatched_keys = []
                            left[i]['_visdiff_index'] = None
                            right[j]['_visdiff_index'] = None
                            left[i]['_mismatched_keys'] = []
                            right[j]['_mismatched_keys'] = []
                        else:
                            left[i]['_visdiff_match'] = 'replace'
                            right[j]['_visdiff_match'] = 'replace'
                            mismatched_keys = [k for k in left[i].values.keys() if left[i][k] != right[j][k]]

                            left[i]['_visdiff_index'] = j
                            right[j]['_visdiff_index'] = i
                            left[i]['_mismatched_keys'] = mismatched_keys
                            right[j]['_mismatched_keys'] = mismatched_keys
            
            elif tag == 'delete':
                # Rows exist in left only
                for i in range(i1, i2):
                    left[i]['_visdiff_match'] = 'delete'
                    left[i]['_visdiff_index'] = None
                    left[i]['_mismatched_keys'] = []

            elif tag == 'insert':
                # Rows exist in right only
                for j in range(j1, j2):
                    right[j]['_visdiff_match'] = 'insert'
                    right[j]['_visdiff_index'] = None
                    right[j]['_mismatched_keys'] = []


        longer_table_len = max(len(left), len(right))
        new_left  = left._copy(new_records=[])
        new_right = right._copy(new_records=[])

        if len(left) > len(right):
            longer_table = left
            shorter_table = right
            new_longer_table = new_left
            new_shorter_table = new_right
        else:
            longer_table = right
            shorter_table = left
            new_longer_table = new_right
            new_shorter_table = new_left


        ii = 0
        jj = 0

        while max(ii, jj) < longer_table_len:
            try:
                l = left[ii]
                r = right[jj]
            except:
                pdb.set_trace()
            empty_left_record = self.DATA_ITEM_CLS(source=r.values)
            empty_left_record['_mismatched_keys'] = []
            empty_left_record['_visdiff_match'] = 'empty_from_insert'

            empty_right_record = self.DATA_ITEM_CLS(source=l.values)
            empty_right_record['_mismatched_keys'] = []
            empty_right_record['_visdiff_match'] = 'empty_from_delete'

            if l['_visdiff_index'] is None and r['_visdiff_index'] is None:
                new_right.append(empty_right_record)
                new_right.append(r)
                new_left.append(l)
                new_left.append(empty_left_record)
                ii += 1
                jj += 1
            elif l['_visdiff_index'] is None:
                new_left.append(l)
                new_right.append(empty_right_record)
                ii += 1
            elif r['_visdiff_index'] is None:
                new_left.append(empty_left_record)
                new_right.append(r)
                jj += 1
            else:
                new_left.append(l)
                new_right.append(r)
                ii += 1
                jj += 1

        left = new_left
        right = new_right

        empties = []

        right = self._de_interlace_diffs(['insert', 'empty_from_delete'], right)
        left = self._de_interlace_diffs(['delete', 'empty_from_insert'], left, False)
        # pdb.set_trace()

        try:
            visdiff_left, visdiff_right = VisualDiffContainer(raw_data=[r.values for r in left.records]), VisualDiffContainer(raw_data=[r.values for r in right.records])
        except:
            pdb.set_trace()

        return visdiff_left, visdiff_right

    def _de_interlace_diffs(self, target_values, container, empties_first=True):
        """
        Internal helper: Reorganizes alignment blocks so that empty placeholders 
        and actual data rows are grouped logically for display.
        """
        matching_sections = []
        non_matching_sections = []
        start = None
        in_matching = None

        for i, val in enumerate(container):
            if val['_visdiff_match'] in target_values:
                if in_matching is False:
                    non_matching_sections.append((start, i - 1))
                    start = i
                elif in_matching is None:
                    start = i
                in_matching = True
            else:
                if in_matching is True:
                    matching_sections.append((start, i - 1))
                    start = i
                elif in_matching is None:
                    start = i
                in_matching = False

        # Finalize the last section
        if start is not None:
            if in_matching:
                matching_sections.append((start, len(container) - 1))
            else:
                non_matching_sections.append((start, len(container) - 1))

        all_sections = [{'start': x, 'end': y, 'reorder': True} for x, y in matching_sections] + \
                       [{'start': x, 'end': y, 'reorder': False} for x, y in non_matching_sections]
        all_sections.sort(key=lambda x:x['start'])

        de_interlaced_container = None
        for section in all_sections:
            new_chunk = container[section['start']:section['end']+1]
            if section['reorder']:
                if empties_first:
                    new_chunk = new_chunk.contains('_visdiff_match', 'empty') + \
                                new_chunk.doesnotcontain('_visdiff_match', 'empty')
                else:
                    new_chunk = new_chunk.doesnotcontain('_visdiff_match', 'empty') + \
                                new_chunk.contains('_visdiff_match', 'empty')
            if de_interlaced_container is None:
                de_interlaced_container = new_chunk
            else:
                de_interlaced_container += new_chunk        

        return de_interlaced_container

    def insert(self, index, record):
        """
        Inserts a record at the specified index and returns a new container instance.
        """
        records_before = [r for r in self[:index]]
        records_after = [r for r in self[index:]]
        new_records = records_before + [record] + records_after
        return self._copy(new_records=new_records)

    def _add_record(self, record):
        """
        Internal: Directly appends a record dictionary converted to a DATA_ITEM_CLS.
        """
        self.records.append(self.DATA_ITEM_CLS(record))

    def _copy(self, new_records=None):
        """
        Creates a deep copy of the container, its history, and its records.
        """
        if new_records is None: new_records = self.records
        new_obj = copy(self)
        new_obj._unlock()
        new_obj.history = deepcopy(self.history)
        new_obj.records = [r._copy() for r in new_records]
        new_obj._lock()
        return new_obj

    def _lock(self):
        """
        Placeholder for locking state, primarily to support TOWER InputClient compatibility.
        """
        # Note: In the OCO-2 implementation of TOWER, input clients inherit from both 
        # TOWER InputClient and this class. Stubs here prevent failures when calling 
        # these methods outside of the TOWER environment.
        # TO DO: Consider bringing TOWER-like lock/unlock functionality into this class.
        return

    def _unlock(self):
        """
        Placeholder for unlocking state. See _lock for details.
        """
        return

    def _filter(self, filter_lambda, minimum=None, maximum=None, exactly=None):
        """
        The core engine for all chainable filtering methods.
        
        **Performance Optimization:**
        Rather than a full deep copy of the entire container (which is slow for large datasets), 
        we perform a targeted copy that excludes the full record set, then apply the filter 
        logic to generate the new decimated record list.
        """
        condition = filter_lambda[0]
        comparison_string = filter_lambda[1]

        #Note that this uses private methods from InputClient, but I propose
        #we move all of this down into InputClient, so that won't be a big
        #deal anymore once we do.        

        #what the heck is going on here? Glad you asked.
        #I'm basically doing a deep copy of self. In fact, when
        #I originally did this, that's exactly what I did.
        #but it was slooooooooooow. So instead I loop through the
        #attributes of the copy one at a time and only copy them
        #if they're NOT the records attribute.
        #
        #That way we don't waste time copying a huge amount of data
        #that we're not going to use most of anyway. Instead of copying
        #I just do the filterign that we want to do right there.

        #TO DO: EXPLAIN WTF YOU ARE DOING HERE

        # Filter the records based on the provided condition
        filtered_records = [r for r in self.records if condition(r)]

        # Validate result counts based on constraints
        if exactly is not None and minimum is not None:
            log.warning('"exactly" and "minimum" kwargs are both set. Only "exactly" will be honored.')
        if exactly is not None and maximum is not None:
            log.warning('"exactly" and "maximum" kwargs are both set. Only "exactly" will be honored.')
        
        if exactly is not None and len(filtered_records) != exactly:
            raise Exception(f'Filtered length is not exactly {exactly} as specified')
        if minimum is not None and len(filtered_records) < minimum:
            raise Exception(f'Filtered length is not at least {minimum} as specified')
        if maximum is not None and len(filtered_records) > maximum:
            raise Exception(f'Filtered length is not less than or equal to {maximum} as specified')

        # Create the new decimated container
        new_obj = self._copy(filtered_records)
        
        if len(self.records):
            percent_remaining = f'{len(new_obj.records)/len(self.records)*100:.2f}'
        else:
            percent_remaining = 'NA'

        # Log the filter action to the audit history
        new_obj.history._add_record({
            'Action': 'Filtered', 
            'Description': comparison_string, 
            'Ending Count': len(new_obj.records),
            'Starting Count': len(self.records), 
            'Percent Remaining': percent_remaining
            })

        # Special case: return the DataItem itself if exactly=1 requested
        if exactly == 1:
            new_obj._unlock()
            new_obj.records = new_obj.records[0]
            new_obj._lock()

        return new_obj

    def with_cols(self, columns):
        """
        Returns a new version of this container with the display columns changed.
        Will add new (empty) columns if they do not currently exist in the records.

        :param columns: List of column names to display/return.
        :type columns: list[str]
        :return: A new DataContainer instance with updated column settings.
        """
        self._unlock()
        new_obj = self._copy()
        new_obj._repr_cols = columns
        new_obj._csv_cols = columns
        self._lock()
        return new_obj

    def summarize(self, key, expected_values=None, include_times=True):
        """
        Generates a summary table counting occurrences and time ranges for unique values 
        in a specific column.

        **The Concept:**
        This method transforms the current data into a frequency report. If `expected_values` 
        are provided, it validates the data against them and ensures the output table 
        follows the user's preferred ordering, while still appending any unexpected "rogue" 
        values at the end of the list.

        :param key: The column name to summarize.
        :type key: str
        :param expected_values: Optional list of values to check for and order by.
        :type expected_values: list, optional
        :param include_times: If True, adds "First Occurrence" and "Last Occurrence" columns.
        :type include_times: bool
        :return: A GenericContainer containing the summary records.
        """
        unique_values = self.unique(key)
        
        if expected_values is not None:
            unexpected_values = [u for u in unique_values if u not in expected_values]
            if len(unexpected_values):
                log.warning(f'Unexpected values found in column "{key}": {unexpected_values}')
            
            # This logic preserves the user's requested order for expected values
            # while ensuring any actual values found in the data are included.
            summary_values = []
            for value in expected_values + unique_values:
                if value not in summary_values: 
                    summary_values.append(value)
        else:
            summary_values = unique_values

        summary_records = []
        for summary_value in summary_values:
            summary_record = {key: summary_value}
            
            # Filter for current value
            filtered = self.eq(key, summary_value)
            
            # Fix: Only sort if we have a valid time label, 
            # otherwise just use the filtered results order
            if self.default_time_label:
                sorted_records = filtered.sort()
            else:
                sorted_records = filtered
                
            summary_record['Occurances'] = str(len(sorted_records))

            if include_times:
                if len(sorted_records):
                    # TO DO: Turn this into a string instead of relying on time_str property
                    summary_record['First Occurence'] = sorted_records[0].time_str
                    summary_record['Last Occurence'] = sorted_records[-1].time_str
                else:
                    summary_record['First Occurence'] = 'NA'
                    summary_record['Last Occurence'] = 'NA'
            
            summary_records.append(summary_record)

        # Import here to avoid circular dependency since GenericContainer inherits from DataContainer
        from tts_data_utils.core.generic import GenericContainer
        return GenericContainer(raw_data=summary_records)

    def unique(self, key, exclude=[], sort=True):
        """
        Returns a list of unique values found in a specific column.

        :param key: Name of the column to inspect.
        :type key: str
        :param exclude: List of values to filter out of the final unique list.
        :type exclude: list
        :param sort: If True, the resulting list is sorted ascending.
        :type sort: bool
        :return: A list of unique values.
        """
        if not isinstance(exclude, list): 
            exclude = [exclude]
            
        unique = list(set([x[key] for x in self.records if x[key] not in exclude]))
        
        if sort:
            unique.sort()
            
        return unique

    def gt(self, key, value, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field is greater than value in "value" parameter.

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type value: Varies depending on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(gt(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def lt(self, key, value, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field is less than value in "value" parameter.

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type value: Varies depending on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(lt(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def gte(self, key, value, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field is greater than or equal to value in "value" parameter.

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type value: Varies depending on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(gte(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def lte(self, key, value, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field is less than or equal to value in "value" parameter.

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type value: Varies depending on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """        
        return self._filter(lte(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def eq(self, key, value, minimum=None, maximum=None, exactly=None, tolerance=0):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field matches value in "value" field.

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type value: Varies depending on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(eq(key, value, tolerance=tolerance), minimum=minimum, maximum=maximum, exactly=exactly)

    def ne(self, key, value, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field does not match value in "value" field.

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type value: Varies depending on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """

        return self._filter(ne(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def isin(self, key, values, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field matches value any of the values in the list "values".

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type values: list. Type of list contents depends on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """

        return self._filter(isin(key, values), minimum=minimum, maximum=maximum, exactly=exactly)

    def notin(self, key, values, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field does not match any value in the list "values".

        :param key: Name of column to filter on
        :type key: str

        :param value: Value to compare against
        :type values: list. Type of list contents depends on contents of "key" column

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(notin(key, values), minimum=minimum, maximum=maximum, exactly=exactly)

    def contains(self, key, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field contains the value in the "substring" parameter as a substring.

        :param key: Name of column to filter on
        :type key: str

        :param substring: Value to compare against
        :type substring: str

        :param value: Should the substring match be case sensitive?
        :type value: bool

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(contains(key, substring, case_sensitive=case_sensitive), minimum=minimum, maximum=maximum, exactly=exactly)

    def doesnotcontain(self, key, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        field does not contain the value in the "substring" parameter as a substring.

        :param key: Name of column to filter on
        :type key: str

        :param substring: Value to compare against
        :type substring: str

        :param value: Should the substring match be case sensitive?
        :type value: bool

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(doesnotcontain(key, substring, case_sensitive=case_sensitive), minimum=minimum, maximum=maximum, exactly=exactly)

    def before(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        occur before the value in the "time" parameter.

        Unlike most other filter methods, time MUST be a datetime.

        Note that "key" is not requried since DataItems have default time columns. If an object takes multiple
        time columns (or if using something like GenericContainer with no default time label), the time_label
        kwarg is provided.

        :param value: Time to compare against
        :type value: datetime

        :param time_label: Name of time column to use if not the default
        :type time_label: str

        :param inclusive: If a row's time matches "time" exactly, should it be included?
        :type inclusive: bool

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """

        #TO DO: Fix this.. shouldn't have to reference a record just to get this
        if len(self.records):
            if time_label is None: time_label = [x for x in self.records[0].TIME_FORMATS.keys()][0]
        else:
            if time_label is None: time_label = 'NA'
        return self._filter(before(time, time_label, inclusive=inclusive), minimum=minimum, maximum=maximum, exactly=exactly)

    def after(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        occur after the value in the "time" parameter.

        Unlike most other filter methods, time MUST be a datetime.

        Note that "key" is not requried since DataItems have default time columns. If an object takes multiple
        time columns (or if using something like GenericContainer with no default time label), the time_label
        kwarg is provided.

        :param value: Time to compare against
        :type value: datetime

        :param time_label: Name of time column to use if not the default
        :type time_label: str

        :param inclusive: If a row's time matches "time" exactly, should it be included?
        :type inclusive: bool

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """

        #TO DO: Fix this.. shouldn't have to reference a record just to get this
        if len(self.records):
            if time_label is None: time_label = [x for x in self.records[0].TIME_FORMATS.keys()][0]
        else:
            if time_label is None: time_label = 'NA'
        return self._filter(after(time, time_label, inclusive=inclusive), minimum=minimum, maximum=maximum, exactly=exactly)

    def between(self, key, lower, upper, inclusive="both", minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        occur between the values in the "lower" and "upper" parameters.

        Unlike most other filter methods, time MUST be a datetime.

        Note that "key" is required on this method unlike the before and after methods. This is just an error
        by the developer. It is slated to be fixed at the next major release since it will be a breaking change:
        issue #32 (TO DO: Migrate out of JPL-internal issues)

        :param key: Name of time column to use
        :type key: str

        :param value: Time to compare against
        :type value: datetime

        :param inclusive: If a row's time matches "time" exactly, should it be included?
        :type inclusive: str (should be upper, lower, both, or neither)

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(between(key, lower, upper, inclusive=inclusive), minimum=minimum, maximum=maximum, exactly=exactly)

    def matches(self, key, pattern, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        matches the regex in the parameter "pattern".

        :param key: Name of column to match against
        :type key: str

        :param pattern: Regex pattern
        :type pattern: r-string

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(matches(key, pattern), minimum=minimum, maximum=maximum, exactly=exactly)

    def doesnotmatch(self, key, pattern, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        does not match the regex in the parameter "pattern".

        :param key: Name of column to not match against
        :type key: str

        :param time_label: Name of time column to use if not the default
        :type time_label: str

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(doesnotmatch(key, pattern), minimum=minimum, maximum=maximum, exactly=exactly)


    def on_change(self, key, minimum=None, maximum=None, exactly=None):
        """
        Return a decimated verison of this DataContainer where all rows where column in "key" 
        is different than in the row before. Will always include first row.

        :param key: Name of column to inspect for changes
        :type key: str

        :param time_label: Name of time column to use if not the default
        :type time_label: str

        :param minimum: Minimum number of records to return. Will raise an exception if too few records match
        :type minimum: int

        :param maximum: Maximum number of records to return. Will raise an exception if too many records match
        :type maximum: int 

        :param exactly: Exact number of records to return. Will raise an exception any other number of records match
        :type exactly: int

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        filtered outputs (except if exactly=1, in which case it will return a DataItem only).
        :rtype: DataContainer or DataItem
        """
        return self._filter(on_change(key), minimum=minimum, maximum=maximum, exactly=exactly)

    def sort(self, by=None, lam=None, reverse=False):
        """
        Return a version of the DataContainer with rows sorted by the row in the "by" kwarg or by
        the lambda funciton in the "lam" kwarg.

        Always sorts by ascending (for now, see https://github.jpl.nasa.gov/teamtools-studio/data_utils/issues/33)

        :param by: Name of column to sort by
        :type by: str

        :param lam: Lambda to control how values are sorted
        :type lam: lambda

        :param reverse: By default, sorts like Python list sort. This works the same as reverse kwarg on default list sort
        :type reverse: bool

        :return: Returns a new DataContainer exactly the same as this one, but with updated history and
        sorted outputs.
        :rtype: DataContainer
        """
        if by is not None and lam is not None:
            log.warning('"by" and "lamb" are both defined. Honoring "lamb" and not "by"')
            by = None

        records_copy = copy(self.records)
        if by is None and lam is None: 
            by = self.default_time_label
            records_copy.sort(key=lambda r: r.source[by], reverse=reverse)
        elif lam is not None:
            records_copy.sort(key=lam, reverse=reverse)
        else:
            records_copy.sort(key=lambda r: r.values[by], reverse=reverse)
        return self._copy(records_copy)
        
    def append(self, items, cast_fields=False, fill=False):
        """
        Adds one or more items to the end of the container's records.

        :param items: A dictionary, DataItem, or a list of either to append.
        :param cast_fields: If True, attempts to force data into types defined in DataItem.
        :param fill: If True, fills in missing keys with default values.
        """
        self._unlock()
        if not isinstance(items, list):
            items = [items]

        for item in items:
            if isinstance(item, dict):
                self.records.append(self.DATA_ITEM_CLS(item, cast_fields=cast_fields, fill=fill))
            elif isinstance(item, self.DATA_ITEM_CLS):
                self.records.append(item)
            else:
                raise Exception('Unexpected item type!')
        self._lock()

    def inject_error(self, lamb):
        """
        Iterates through records and applies a transformation lambda. 
        Useful for error injection or data simulation.

        :param lamb: A function that accepts a record and returns (bool, key, value).
        """
        # not super crazy about this implementation but I like the idea and 
        # should continue to iterate on it
        self._unlock()
        for r in self.records:
            change_this_record, key, value = lamb(r)
            if change_this_record:
                r.source[key] = value
        self._lock()

    def simple_record_table(self, *args, **kwargs):
        """Placeholder for breaking tests. One day at a time here..."""
        return

    def file_contents_as_string(self, *args, **kwargs):
        """Placeholder for breaking tests. One day at a time here..."""
        return

    def to_csv(self, csv_path, mkdirs=False):        
        """
        Writes the container's records to a CSV file.

        :param csv_path: Target file path.
        :param mkdirs: If True, creates the target directory if it does not exist.
        """
        if len(self.records):
            formatted_records = []
            
            # Internal helper to handle JSON serialization of complex types
            def json_serialize_fallback(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj) # Fallback for HistoryItems and other objects

            for r in self.records:
                row = r.printable_values.copy()
                
                for k, v in row.items():
                    if isinstance(v, (dict, list)):
                        # Use the default parameter to handle datetimes/custom objects
                        row[k] = json.dumps(v, default=json_serialize_fallback)
                formatted_records.append(row)

            df = pd.DataFrame(formatted_records)
            
            for col in self._csv_cols:
                if col not in df.columns:
                    df[col] = [''] * len(df)
            df = df[self._csv_cols]
        else:
            df = pd.DataFrame(columns=self._csv_cols)

        if mkdirs: os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        df.to_csv(csv_path, index=False, date_format=None)
    def read_csv(self, csv_path):
        """Reads a CSV file into a list of record dictionaries."""
        return pd.read_csv(csv_path).to_dict('records')

    def read_xlsx(self, xlsx_path):
        """
        Reads an Excel file into a list of record dictionaries, 
        handling NaN values as None.
        """
        raw_data = pd.read_excel(xlsx_path).to_dict('records')
        for row in raw_data:
            for k, v in row.items():
                if not isinstance(v, (int, float)): continue
                if isnan(v): row[k] = None
        return raw_data

    def calculate_records_hash(self):
        """
        Generates a SHA256 hash representing the current state of all records.
        
        **The Process:**
        Normalizes timestamps based on DataItem time formats to ensure consistent 
        string representation before hashing the JSON-encoded record set.
        """
        records = [deepcopy(r.source) for r in self.records]
        for time_label, time_format in self.records[0].TIME_FORMATS.items():
            for record in records:
                record[time_label] = record[time_label].strftime(time_format)
        
        dict_str = json.dumps(records)
        dict_hash = hashlib.sha256(dict_str.encode()).hexdigest()
        return dict_hash

    ##################################################################################
    # Dexter-specific methods, consider reorganizing this so not every DataContainer gets this
    ##################################################################################

    def assert_records_match_hash(self, expected_hash):
        """
        Validates the integrity of the records against a known hash.
        """
        actual_hash = self.calculate_records_hash()
        log.info(f'Expected hash: {expected_hash}')
        log.info(f'Actual hash: {actual_hash}')
        if expected_hash != actual_hash:
            raise Exception(f'Expected and Actual hashes do not match!\n'
                            f'Expected hash: {expected_hash}\n'
                            f'Actual hash: {actual_hash}')

    def stamp_all(self, dispo_choice, dispo_format):
        """Iterates through all data and applies a disposition stamp."""
        for _data in self:
            _data.choose_and_stamp(dispo_choice, dispo_format)
                        
    def subdivide_f(self, sub_f):
        """Returns a subdivided container based on a filter function."""
        sub_data = [_ for _ in self if sub_f(_)]
        return self.subdivide(sub_data, bypass_validation=self._bypass_validation)
    
    @classmethod
    def subdivide(cls, sub_data, bypass_validation=False):
        """
        Class method to create a new 'sub-container' instance.
        """
        return cls(
            sub_data,
            bypass_validation=bypass_validation,
            sub_container=True
        )

def gt(key, value):
    """
    Returns a predicate for: field > value.

    :param key: column to filter on
    :type key: str
    :param value: value to check against
    :type value: int or float    
    """
    return lambda r: r[key] > value, f'"{key}" > {value}'

def lt(key, value):
    """
    Returns a predicate for: field < value.

    :param key: column to filter on
    :type key: str
    :param value: value to check against
    :type value: int or float
    """
    return lambda r: r[key] < value, f'"{key}" < {value}'

def gte(key, value):
    """
    Returns a predicate for: field >= value.

    :param key: column to filter on
    :type key: str
    :param value: value to check against
    :type value: int or float
    """
    return lambda r: r[key] >= value, f'"{key}" >= {value}'

def lte(key, value):
    """
    Returns a predicate for: field <= value.

    :param key: column to filter on
    :type key: str
    :param value: value to check against
    :type value: int or float
    """
    return lambda r: r[key] <= value, f'"{key}" <= {value}'

def eq(key, value, tolerance=0):
    """
    Returns a predicate for: field == value.

    :param key: column to filter on
    :type key: str, int, float, datetime
    :param value: value to check against
    :type value: any
    """
    if isinstance(value, str):
        return lambda r: r[key] == value, f'"{key}" == {value}'
    elif isinstance(value, datetime):
        if not isinstance(tolerance, timedelta):
            tolerance = timedelta(seconds=tolerance)
        return lambda r: abs(r[key] - value) <= tolerance, f'"{key}" == {value}'
    elif isinstance(value, (int, float)):
        return lambda r: abs(r[key] - value) <= tolerance, f'"{key}" == {value}'


def ne(key, value):
    """
    Returns a predicate for: field != value.

    :param key: column to filter on
    :type key: str
    :param value: value to check against
    :type value: any
    """    
    return lambda r: r[key] != value, f'"{key}" != {value}'

def isin(key, values):
    """
    Returns a predicate for: field in list_of_values.

    :param key: column to filter on
    :type key: str
    :param value: value to check against
    :type value: list
    """
    return lambda r: r[key] in values, f'"{key}" is in {values}'

def notin(key, values):
    """
    Returns a predicate for: field not in list_of_values.

    :param key: column to filter on
    :type key: str
    :param value: value to check against
    :type value: list
    """
    return lambda r: r[key] not in values, f'"{key}" is not in {values}'

def contains(key, substring, case_sensitive=True):
    """
    Returns a predicate for substring matching.

    :param key: column to filter on
    :type key: str
    :param substring: Substring to check values for
    :type substring: str
    :param case_sensitive: whether to check with case sensitiveiy or not. Defaults to True
    :type case_sensitive: bool
    """
    if case_sensitive:
        return lambda r: substring in r[key], f'"{key}" contains {substring} (case sensitive)'
    else:
        return lambda r: substring.lower() in r[key].lower(), f'"{key}" contains {substring} (case insensitive)'

def doesnotcontain(key, substring, case_sensitive=True):
    """
    Returns a predicate for negative substring matching.

    :param key: column to filter on
    :type key: str
    :param substring: Substring to check values for
    :type substring: str
    :param case_sensitive: whether to check with case sensitiveiy or not. Defaults to True
    :type case_sensitive: bool
    """
    if case_sensitive:
        return lambda r: substring not in r[key], f'"{key}" does not contain {substring} (case sensitive)'
    else:
        return lambda r: substring.lower() not in r[key].lower(), f'"{key}" does not contain {substring} (case insensitive)'

def before(time, time_label, inclusive=False):
    """
    Returns a predicate for datetime comparison (earlier than).

    :param time: Time for comparison
    :type time: datetime
    :param time_label: Label for time column
    :type time_label: str
    :param inclusive: Should we include a time that is exactly equal? Defaults to False
    :type inclusive: bool
    """
    if inclusive:
        return lambda r: r[time_label] <= time, f'"{time_label}" <= {time}'
    else:
        return lambda r: r[time_label] < time, f'"{time_label}" < {time}'

def after(time, time_label, inclusive=False):
    """
    Returns a predicate for datetime comparison (later than).

    :param time: Time for comparison
    :type time: datetime
    :param time_label: Label for time column
    :type time_label: str
    :param inclusive: Should we include a time that is exactly equal? Defaults to False
    :type inclusive: bool
    """
    if inclusive:
        return lambda r: r[time_label] >= time, f'"{time_label}" >= {time}'
    else:
        return lambda r: r[time_label] > time, f'"{time_label}" > {time}'

def between(key, lower, upper, inclusive="both"):
    """
    Returns a predicate for range comparison.
    
    :param key: column to filter on
    :type key: str    
    :param lower: Lower value for range comparison
    :param upper: Upper value for range comparison
    :param inclusive: One of 'both', 'neither', 'lower', or 'upper'.
    """
    if inclusive == "both":
        return lambda r: lower <= r[key] <= upper, f'{lower} <= "{key}" <= {upper}'
    elif inclusive == "neither":
        return lambda r: lower < r[key] < upper, f'{lower} < "{key}" < {upper}'
    elif inclusive == "lower":    
        return lambda r: lower <= r[key] < upper, f'{lower} <= "{key}" < {upper}'
    elif inclusive == "upper":
        return lambda r: lower < r[key] <= upper, f'{lower} < "{key}" <= {upper}'
    else:
        raise ValueError("inclusive must be 'both', 'neither', 'lower', or 'upper'")

def matches(key, pattern):
    """
    Returns a predicate for regex matching.

    :param key: column to filter on
    :type key: str
    :param pattern: regex pattern to match with
    :type pattern: str
    """
    return lambda r: re.match(pattern, r[key]), 'matches'

def doesnotmatch(key, pattern):
    """
    Returns a predicate for negative regex matching.

    :param key: column to filter on
    :type key: str
    :param pattern: regex pattern to match with
    :type pattern: str
    """
    return lambda r: not(re.match(pattern, r[key])), 'does not match'

def on_change(key):
    """
    Returns a stateful predicate that triggers when the value in a column 
    changes relative to the previous record.

    :param key: Column to check for changes in
    :type key: str
    """
    last_value = [None]  # mutable closure to track previous value
    is_first = [True]    # flag to catch the first record

    def condition(record):
        nonlocal last_value, is_first
        if is_first[0]:
            is_first[0] = False
            last_value[0] = record[key]
            return True
        elif record[key] != last_value[0]:
            last_value[0] = record[key]
            return True
        else:
            return False

    return (condition, f"on_change({key})")


FILTERS = {
    'gt': gt,
    'lt': lt,
    'gte': gte,
    'lte': lte,
    'eq': eq,
    'ne': ne,
    'isin': isin,
    'notin': notin,
    'contains': contains,
    'doesnotcontain': doesnotcontain,
    'before': before,
    'after': after,
    'between': between,
    'matches': matches
}
