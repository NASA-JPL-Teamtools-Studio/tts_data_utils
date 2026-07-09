import pdb
from datetime import datetime
from abc import ABC, abstractmethod
from copy import copy, deepcopy
from enum import Enum, auto
import json
try:
    from tts_dexter.core.dispo import Disposition, get_dispo_joiner, DISPO_FORMAT, DISPO_SEVERITY, PALETTE
    from tts_dexter.core.data import DISPO_CHOICE
    DEXTER_PRESENT = True
except ModuleNotFoundError:
    DEXTER_PRESENT = False
from tts_html_utils.core.components.text import Strong

class DataItem(ABC):
    """
    The fundamental atomic unit of a DataContainer, representing a single row.

    **The Concept:**
    A `DataItem` acts as a "Smart Dictionary" with a memory. It separates data into 
    two layers: **Source** and **Derived**. 
    
    Think of it like a piece of trace paper over an original document. The `source` 
    (the document) remains untouc hed for auditability. Any edits, calculations, 
    or augmentations are written on the `derived_values` (the trace paper). 
    When you ask for a value, the `DataItem` looks at the trace paper first; 
    if nothing is there, it reads from the original document.

    **Traceability & Integrity:**
    This architecture ensures that the original raw data is never destroyed or 
    altered by processing logic, which is critical for engineering applications 
    requiring data lineage.

    :param source: Dictionary of raw data for the row.
    :type source: dict
    :param subcontainers: Nested containers attached to this row.
    :type subcontainers: dict[str, DataContainer], optional
    :param copy_data: If True, deep-copies the source data to prevent mutation.
    :type copy_data: bool
    :param cast_fields: If True, attempts to force fields into canonical datatypes.
    :type cast_fields: bool
    :param fill: If True, adds None for missing columns defined in DICT_VALID_KEYS.
    :type fill: bool
    :param validate: Should we raise an exception if fields are the wrong type?
    :type validate: bool
    :param default_dispo: Default disposition object (Dexter only).
    :type default_dispo: str
    """

    DO_NOT_DIFF = []
    """
    Fields to ignore in diffs
    """
    
    NAME = 'data item'
    """
    Name of the data item to be printed in some situations
    """
    
    if DEXTER_PRESENT:
        DICT_STAMP_KEY = 'disposition'
        DEFAULT_DISPO = Disposition()
        #TO DO: pull pallette into utils and call PURPLE instead of #AD44AD
        DEFAULT_DISPO.populate('No Autodisposition', 'Manual Disposition Needed', DISPO_SEVERITY.NONE, color=PALETTE.PURPLE)
    else:
        DEFAULT_DISPO = None
        
    def __init__(self, source, subcontainers=None, copy_data=False, cast_fields=False, fill=False, validate=True, default_dispo=None):
        # Save off a copy of the source data
        self.source = deepcopy(source) if copy_data else source

        self.subcontainers = subcontainers if subcontainers is not None else {}

        self.derived_values = {}

        if not validate: return

        #TO DO: Look into if we can make this faster. List comprehension?

        for k, t in deepcopy(self.DICT_VALID_KEYS):
            if isinstance(t, type):
                #allow developers to pass either a single
                #type or a tuple of types
                t = (t,)
            if not isinstance(t, tuple):
                raise Exception('Acceptable types must be either types or tuples of types')
            for x in t:
                if not isinstance(x, type) and x is not None:
                    raise Exception('Acceptable types must be either type or None')
            t_with_none = copy(t)
            if None in t: 
                #isinstance doesn't like none, but
                #sometimes it's OK for something to be none                
                t = tuple(x for x in copy(t) if x is not None)
                none_present = True
            else:
                none_present = False
            if k not in self.source.keys():
                #is this the smartest thing to do here?
                #I'm not sure...
                if fill: self.source[k] = None
            elif isinstance(self.source[k], t):
                #if it's already the right type, then move on to next field
                continue
            elif none_present and self.source[k] is None:
                #this just extends the prior elif because
                #isinstance doen't do None
                continue
            elif not cast_fields:
                #if it's not the right data type and we're not casting, then fail
                raise Exception(f'Key "{k}" of value "{self.source[k]}" is not type "{t}", and cast is False.')
            elif t == tuple([datetime]):            
                #if we are casting and it's a datetime, use this
                #data item's TIME_FORMATS
                #
                #the logical inthis elif is a little clunky, but
                #I had to do it this way because I force all
                #of these to be tuples for generalizing the way
                #we use isinstance above
                if k not in self.TIME_FORMATS.keys():
                    raise Exception(f'No time format for {self.source[k]} defined. Cannot cast to datetime')
                try:
                    self.source[k] = datetime.strptime(self.source[k], self.TIME_FORMATS[k])
                except:
                    raise Exception(f'Casting of value: "{self.source[k]}", key: "{k}" to datetime with format "{self.TIME_FORMATS[k]}" failed')
            else:
                #if it's not a datetime, then go one item through
                #the types tuple to try casting it. Raise an exception
                #if none of these work. This use case was originally
                #forced by EHA, where DN can be int, float, or string,
                #eu can be float or None, and state can be string or none.
                cast_failed = True
                for this_type in t_with_none:
                    #I hate this_type as a var name here, but I didn't
                    #want to overload t
                    if this_type is None and self.source[k] is None:
                        cast_failed = False
                        continue
                    elif this_type == dict:
                        if isinstance(self.source[k], str):
                            #This was put in here to get evr metadata, but I'm not
                            #sure it's a good idea because more complex json might
                            #be have quotes that need to be escaped. I hate json.
                            #Very unlikely that this will fail silently if that's the
                            #case, so I'm just going to leave it.
                            #If this causes problems, then the right solution will be
                            #to figure out how to get the user to know that can direct
                            #padas to df['Data'].apply(lambda x: json.dumps(x)) in the data
                            #container class. It doesn't have that funcitonalty right now
                            #so we'd have to write it, too.
                            #for now we're pushing ahead on risk.
                            self.source[k] = json.loads(self.source[k].replace("'",'"'))
                            cast_failed = False
                    else:
                        try:
                            self.source[k] = this_type(self.source[k])
                            cast_failed = False
                            break
                        except ValueError:
                            pass

                if cast_failed:
                    failed_types = ','.join([x.__name__ for x in t])
                    raise Exception(f'Casting of value: {self.source[k]} for key: {k} to type(s): {failed_types} failed')
            

        if fill:
            #do we want to be able to separately call fill? Or is it OK that
            #it's just in the cast_fields block?
            pass

        if not self.valid:
            validation_errors = self.validate()
            error_msg = 'Data not valid:\n' + '\n'.join(f'  - {err}' for err in validation_errors)
            raise Exception(error_msg)

        ##################################################################################
        # Dexter-specific attributes, consider reorganizing this so not every DataItem gets this
        ##################################################################################
        # Setup dispositions
        self.dispositions = []

        self.default_dispo = default_dispo if default_dispo is not None else self.DEFAULT_DISPO
        
        # Initialize Batch pointers
        self._batch_tags = []

        # Optional sub-init hook
        self.__sub_init()
                
    def __sub_init(self):
        """
        Hook for extensions of this class. For DataItems that need some sort of special handling beyond
        the default init behavior
        """
        pass

    def __getitem__(self, key):
        """
        Returns values like a dictionary, choosing from derived_values if the key is present there,
        and falling back to source.
        """
        if key in self.derived_values.keys():
            return self.derived_values[key]
        return self.source[key]

    def __setitem__(self, key, value):
        """
        Sets item in derived_values only.
        """
        self.derived_values[key] = value

    def __hash__(self):
        """Returns a hash based on the unique signature of the row's data."""
        return hash(self.row_signature())


    def row_signature(self, ignore_cols=[]):
        """
        Generates a hashable representation of the row.
        
        **Concept:**
        Used to determine if two items are effectively identical. It recursively 
        converts mutable types (lists, dicts) into immutable tuples to ensure 
        the signature can be hashed.
        """
        def make_hashable(v):
            if isinstance(v, list):
                return tuple(make_hashable(x) for x in v)
            elif isinstance(v, dict):
                return tuple(sorted((k, make_hashable(val)) for k, val in v.items()))
            elif isinstance(v, set):
                return frozenset(make_hashable(x) for x in v)
            return v  # assume it's already hashable

        sig = tuple(sorted(
            (k, make_hashable(v)) 
            for k, v in self.values.items() 
            if k not in ignore_cols
        ))
        return sig


    def _copy(self):
        """
        Makes a copy of the object with a deep copy of derived_values only.

        This was done to ensure that altering derived_values in downstream items generated from this one
        does not change those upstream. The shallow copy of the rest of the object is for speed.
        """
        new_obj = copy(self)
        new_obj.derived_values = deepcopy(self.derived_values)
        return new_obj

    @property
    def values(self):
        """
        Property to return all values, be they from the original source, newly added, or altered.
        """
        return {**self.source, **self.derived_values}

    # Define an empty FLOAT_FORMAT dictionary by default
    # Subclasses can override this to specify custom float formatting
    FLOAT_FORMAT = {}
    
    # Define an empty TIME_FORMAT_PRECISION dictionary by default
    # Subclasses can override this to specify decimal precision for timestamps with %f
    # Example: {'Time': 2} will show only 2 decimal places for microseconds
    TIME_FORMAT_PRECISION = {}
    
    @property
    def printable_values(self):
        """
        Same as values(), but with formatting applied:
        - TIME_FORMATS used to convert datetimes to strings
        - FLOAT_FORMAT used to format float values (if defined)
        """
        # Start with the original values
        values = self.values.copy()
        
        # Apply datetime formatting
        for key, format_spec in self.TIME_FORMATS.items():
            if key in values and isinstance(values[key], datetime) and values[key] is not None:
                # Check if we need to limit decimal places in microseconds
                if '%f' in format_spec and key in getattr(self, 'TIME_FORMAT_PRECISION', {}):
                    # Replace %f with a unique placeholder
                    placeholder = '___MICROSECONDS___'
                    base_format = format_spec.replace('%f', placeholder)
                    formatted_time = values[key].strftime(base_format)
                    
                    # Format microseconds with specified precision
                    precision = self.TIME_FORMAT_PRECISION[key]
                    microseconds = values[key].microsecond / 1000000
                    # Format microseconds to the specified number of decimal places
                    microseconds_str = f"{{:.{precision}f}}".format(microseconds)[2:]
                    
                    # Insert formatted microseconds where the placeholder is
                    values[key] = formatted_time.replace(placeholder, microseconds_str)
                else:
                    # Use standard strftime if no precision is specified
                    values[key] = values[key].strftime(format_spec)
        
        # Apply float formatting if FLOAT_FORMAT is defined
        for key, format_spec in getattr(self, 'FLOAT_FORMAT', {}).items():
            if key in values and isinstance(values[key], float):
                values[key] = f"{values[key]:{format_spec}}"
        
        return values

    @property
    @abstractmethod
    def time(self):
        """
        Must define some way to time-tag each data item.
        """
        pass 

    def validate(self):
        """
        Compares values in each field to those provided in DICT_VALID_KEYS, which must be provided in each extension
        of DataItem.
        """
        invalid_records = []
        for key, acceptable_types in self.DICT_VALID_KEYS:
            if key not in self.source: 
                invalid_records.append(f'Missing required column: "{key}"')
            elif self.source[key] is None:
                #is this the best way to handle this?
                #this is here to go with the fill pattern above,
                #but could cause issues?
                continue
            elif not isinstance(self.source[key], acceptable_types):
                invalid_records.append(f'Invalid type for column "{key}": got {type(self.source[key]).__name__}, expected {acceptable_types}')
        return invalid_records        

    @property
    def valid(self):
        """
        Runs self.validate, but retunds a simple bool instead of a list of invalid records.
        """
        return self.validate() == []

    @property
    def default_html_row_style(self):
        """Default CSS styles for an HTML table row."""
        return {}

    @property
    def default_rich_text_row_style(self):
        """Default styles for rich-text terminal output."""
        return {}

    @property
    def default_html_cell_styles(self):
        """A mapping of keys to CSS styles for individual HTML cells."""
        return {k: {} for k in self.values.keys()}


    @classmethod
    def empty(cls, keys=[]):
        """Returns an instance with all columns set to empty strings or None."""
        # Returns an instance with all columns set to empty strings
        return cls(source={k: None for k in keys}, validate=False)

    ##################################################################################
    # Dexter-specific methods, consider reorganizing this so not every DataItem gets this
    ##################################################################################

    def in_batch(self, batch):
        """
        Dexter only, and should be broken out into its own extension if possible.

        TBD. Ask Nick Peper FMI

        :param batch: Pointer to the data on which a disposition should be checked
        :type batch: DataUtils Batch
        """
        return batch in self._batch_tags
    
    def any_batches(self):
        """
        Dexter only, and should be broken out into its own extension if possible.

        TBD. Ask Nick Peper FMI
        """
        return len(self._batch_tags) > 0

    def tag_with_batch(self, batch):
        """
        Dexter only, and should be broken out into its own extension if possible.

        TBD. Ask Nick Peper FMI

        :param batch: Pointer to the data on which a disposition should be checked
        :type batch: DataUtils Batch
        """
        if batch not in self._batch_tags:
            self._batch_tags.append(batch)
    
    def add_dispo(self, disposition):
        """
        Dexter only, and should be broken out into its own extension if possible.

        Add a disposition to a dexter object.

        TBD. Ask Nick Peper FMI        

        :param disposition: Disposition for whatever has happened to this DataItem
        :type disposition: Dexter Disposition
        """
        self.dispositions.append(disposition)

    def new_dispo(self):
        """
        Dexter only, and should be broken out into its own extension if possible.

        Add a disposition to a dexter object. Like add_dispo, but just adds an empty disposition.

        TBD. Ask Nick Peper FMI        
        """
        new_dispo = Disposition()
        self.dispositions.append(new_dispo)
        return new_dispo
    
    def choose_dispo(self, dispo_choice):
        """
        Dexter only, and should be broken out into its own extension if possible.

        In Dexter, any DataItem can receive many dispositions. This method chooses which to present
        to the user

        :param dispo_choice: How would you like to roll up dispositions? FIST, LAST, ALL?
        :type dispo_choice: DISPO_CHOICE
        """        
        all_dispositions = [_ for _ in self.dispositions if _.populated]
        if len(all_dispositions) == 0:
            if self.default_dispo is None:
                return
            return [self.default_dispo]
        
        if dispo_choice == DISPO_CHOICE.FIRST:
            return [all_dispositions[0]]
        elif dispo_choice == DISPO_CHOICE.LAST:
            return [all_dispositions[-1]]
        elif dispo_choice == DISPO_CHOICE.ALL:
            return all_dispositions
        else:
            raise ValueError(f'Unhandled dispo choice value: {dispo_choice}')
    
    def choose_and_stamp(self, dispo_choice, dispo_format):
        """
        Dexter only, and should be broken out into its own extension if possible.

        Does the same as choose_dispo(), but also stamps the original DataItem with 
        either a string or a list of dispositions.

        :param dispo_choice: FIRST, LAST, ALL
        :type dispo_choice: DISPO_CHOICE

        :param dispo_format: HTML, EXCEL, TEXT
        :type dispo_format: DISPO_FORMATL
        """
        dispos = self.choose_dispo(dispo_choice)
        if not dispos:
            return
        dispo_values = [_.format(dispo_format) for _ in dispos]
        if dispo_format == DISPO_FORMAT.EXCEL:
            #for Excel, this will be done in papertrail
            dispo_full = dispo_values
        else:
            dispo_full = get_dispo_joiner(dispo_format).join(dispo_values)
        self.stamp(dispo_full)
    
    def stamp(self, dispo_value):
        """
        Dexter only, and should be broken out into its own extension if possible.
        
        Adds a disposition value to source. Not used in isolation, and should probably be
        made private in a future version
        """        
        # TODO: Consider making this private
        self.source[self.DICT_STAMP_KEY] = dispo_value