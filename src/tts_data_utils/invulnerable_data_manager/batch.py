from abc import ABC, abstractmethod

class Batcher(ABC):
    """
    An abstract factory for organizing raw data into logical processing groups.

    **The Concept:**
    Think of a `Batcher` as a sorting machine at a postal office. It takes a giant 
    unsorted bin of mail (`source_batch`) and uses specific internal rules to 
    place that mail into smaller, specialized bags (`batches`) based on 
    destination or priority (e.g., 'daily_maintenance' or 'system_updates').

    **How it works:**
    1. The `InvulnerableDataManager` provides the `source_batch`.
    2. The `Batcher` checks `REQUIRED_DATA` to ensure it has what it needs.
    3. The internal `_make_batches()` method runs the sorting logic.
    4. Each resulting `Batch` is stored in the `self.batches` list.

    :param source_batch: The pool of data to be sorted.
    :type source_batch: AllDataBatch
    """
    @classmethod
    @property
    @abstractmethod
    def NAME(cls):
        """Name of the data batch type, e.g. 'mobility_backbone' or 'daily_maintenance'"""
        raise NotImplementedError
        
    REQUIRED_DATA = []
        
    def __init__(self, source_batch):
        self.source_batch = source_batch
        
        self.batches = []
        self._make_batches()
        
    @abstractmethod
    def _make_batches(self):
        """
        Subclasses must implement this to define how the source data 
        is split into individual Batch objects.
        """
        pass
    
    def _add_batch(self, new_batch):
        """
        Internal helper to append a completed batch to the registry.
        """
        self.batches.append(new_batch)
        
class Batch:
    """
    A labeled container for a subset of data items.

    **The Concept:**
    A `Batch` is a logical "slice" of data. Unlike a standard `DataContainer`, 
    a Batch can hold multiple types of data containers simultaneously, grouped 
    by a common theme (like a specific time window or a shared asset ID).

    **Data Tagging:**
    If `tag_data` is True, every `DataItem` added to this batch is "stamped" 
    with a reference back to this batch. This allows individual data rows to 
    "know" which logical groups they belong to later in the pipeline.

    :param name: Human-readable name for the batch.
    :type name: str
    :param tag_data: If True, calls `.tag_with_batch()` on all ingested items.
    :type tag_data: bool
    """
    def __init__(self, name, tag_data=True):
        # Inputs
        self.NAME = name
        self.tag_data = tag_data
        # Data storage
        self._data_map = {}
        
    @property
    def data_map(self):
        """The internal dictionary mapping container names to DataContainers."""
        return self._data_map
        
    def has_data(self, name):
        """Check if a specific data container exists in this batch."""
        return name in self._data_map
    
    def set_data(self, **data_map):
        """
        Bulk-add data containers to the batch via keyword arguments.
        """
        for name, data in data_map.items():
            self.set_data_one(name, data)
        
    def set_data_one(self, name, data):
        """
        Add a single named DataContainer to the batch.

        :raises ValueError: If a container with the same name is already present.
        """
        if self.has_data(name):
            raise ValueError(f'Attempt to set data {name} in batch {self.NAME} twice')
        self._data_map[name] = data
        # Tag the data with this batch if desired
        if self.tag_data:
            for data_item in data:
                data_item.tag_with_batch(self)
        
    def get_data(self, name):
        """Retrieve a DataContainer by name from the internal map."""
        return self._data_map.get(name)
    
    def subdivide_on_condition(self, sub_f):
        """
        Creates a new data map by applying a filter function to every 
        container in the batch.

        :param sub_f: A function that returns a boolean for each DataItem.
        :type sub_f: function
        :return: A dictionary of filtered DataContainers.
        :rtype: dict
        """
        new_data_map = {}
        for name, data in self.data_map.items():
            new_data_map[name] = data.subdivide_f(sub_f)
        return new_data_map
    
    def subdivide_on_time(self, start_time=None, end_time=None):
        """
        A specialized subdivision helper for temporal windowing.

        **Usage Note:**
        This relies on the `DataItem.time` property being properly implemented 
        in the underlying data objects.

        :param start_time: The beginning of the window (inclusive).
        :param end_time: The end of the window (inclusive).
        :type start_time, end_time: datetime, optional
        """
        if start_time is None and end_time is None:
            raise ValueError(f'Attempting to subdivide batch {self.NAME} on time with no time arguments')
        if start_time is None:
            sub_f = lambda x: x.time <= end_time
        elif end_time is None:
            sub_f = lambda x: start_time <= x.time
        else:
            sub_f = lambda x: start_time <= x.time <= end_time
        return self.subdivide_on_condition(sub_f)
            
        
class AllDataBatch(Batch):
    """
    A specialized Batch that serves as the global "Master List" for all input data.

    **Concept:**
    This batch is initialized with `tag_data=False` because it represents the 
    raw, un-categorized state of the system. It is the "Source of Truth" from 
    which all other Batchers draw their data.
    """
    def __init__(self):
        super().__init__('All Data', tag_data=False)

class UntaggedBatch(Batch):
    """
    A "Lost and Found" batch for data that escaped categorization.

    **Concept:**
    After all Batchers have run, the `UntaggedBatch` scans the `AllDataBatch` 
    to find any `DataItem` that does not have any batch tags associated with it. 
    This is a critical auditing tool to ensure no data "fell through the cracks" 
    of the defined sorting logic.

    :param all_data_batch: The master data batch to scan for untagged items.
    :type all_data_batch: AllDataBatch
    """
    def __init__(self, all_data_batch):
        super().__init__('Untagged Data', tag_data=False)
        self.set_data(**all_data_batch.subdivide_on_condition(lambda x: not x.any_batches()))