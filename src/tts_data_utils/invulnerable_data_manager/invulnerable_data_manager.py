#Standard Library Imports
import pdb
from abc import ABC, abstractmethod

#Installed Library Imports
# None yet

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_data_utils.invulnerable_data_manager.batch import AllDataBatch, UntaggedBatch

#This Library Imports
from tts_data_utils.invulnerable_data_manager.utilities import invulnerable, exec_invulnerable

logger = create_logger(__name__)

class InvulnerableDataManager():
    """
    A high-level coordinator for managing data lifecycle in "failure-resistant" pipelines.

    **The Concept:**
    Think of the `InvulnerableDataManager` as a mission control center with a built-in 
    containment field. In standard data processing, a single malformed record or 
    missing file can cause the entire system to crash. This class is designed to 
    "swallow" those failures, log them, and keep the rest of the pipeline moving.

    **How it works:**
    It maintains separate registries for `AllDataBatch` (Inputs) and processed results 
    (Outputs). By wrapping data initialization in the `@invulnerable` decorator, it 
    ensures that even if a `DataContainer` fails to parse its source, the manager 
    remains alive, allowing other valid data sources to continue processing.

    **Batching & Untagged Data:**
    The manager also tracks "Batchers." When data is processed into batches, any data 
    that doesn't fit into a defined logical group is automatically tracked in an 
    `UntaggedBatch`, ensuring that no data is lost or ignored silently.
    """

    def __init__(self):
        # Initialize storage for ALL input data...
        # note that we didn't change the attr name yet because 
        self._all_input_data = AllDataBatch()
        # Initialize storage for ALL output data...
        self._all_output_data = AllDataBatch()
        # ...unique batches...
        self._batchers = {}
        # ...untagged batch placeholder...
        self._untagged_batch = None

    # :: Data
    @invulnerable
    def init_data(self, container_cls, data, name=None, **kwargs):
        """
        Registers and initializes a new DataContainer within the manager.

        **The Concept:**
        This is the primary "Ingestion" port. It takes raw data and attempts to 
        transform it into a structured `DataContainer`. Because it is decorated 
        with `@invulnerable`, a failure here will result in a warning log rather 
        than a fatal exception.

        :param container_cls: The class type (extending DataContainer) to instantiate.
        :type container_cls: Type[DataContainer]
        :param data: The raw input data (list of dicts, etc.)
        :param name: Optional override for the container name. Defaults to class NAME.
        :type name: str, optional
        :param kwargs: Additional arguments passed to the container constructor.
        """
        self._impl_init_data(container_cls, data, name=None, **kwargs)

        if name is None: name = container_cls.NAME

        if self.all_input_data.has_data(container_cls.NAME):
            raise ValueError(f'Input Data Container "{name}" initialized twice')
            
        if data is None:
            raise Exception(f'No data provided for Data Container "{name}", will not be initialized')
        
        if isinstance(data, container_cls):
            new_data = data
        else:
            # We use exec_invulnerable here to ensure the constructor itself
            # doesn't blow up the manager if the raw data is completely mangled.
            new_data = exec_invulnerable(container_cls, data, **kwargs)

        if (new_data is not None) and (new_data.valid):
            self.all_input_data.set_data_one(name, new_data)
        else:
            logger.warning(f'Failed to initialize "{name}" data container')
            
    @property
    def all_input_data(self):
        """Access the registry of all successfully initialized input containers."""
        return self._all_input_data

    @property
    def all_output_data(self):
        """Access the registry of all generated output containers."""
        return self._all_output_data
            
    def get_input_data(self, name):
        """Retrieves a specific input container by name."""
        return self.all_input_data.get_data(name)

    def get_output_data(self, name):
        """Retrieves a specific output container by name."""
        return self.all_output_data.get_data(name)
    
    def get_input_inventory(self):
        """Returns a summary of all loaded input data types and counts."""
        return self._all_input_data.get_inventory()

    def get_output_inventory(self):
        """Returns a summary of all generated output data types and counts."""
        return self._all_output_data.get_inventory()

    def get_data_inventory(self):
        """
        Returns a comprehensive map of all Inputs and Outputs currently 
        managed by the system.
        """
        return {
            'Inputs': self.get_input_inventory(),
            'Outputs': self.get_output_inventory(),
            }

    # :: Data Batching
    def init_batcher(self, batcher_cls, **kwargs):
        """
        Initializes a DataBatcher to organize input data into logical groups.

        **How it works:**
        Batchers often require specific input datasets to exist. This method 
        checks for `REQUIRED_DATA` before attempting to create the batcher. 
        If requirements are met, it uses `exec_invulnerable` to safely build 
        the batcher.

        **The Untagged Batch:**
        Every time a batcher is initialized, the manager re-syncs the 
        `UntaggedBatch` to ensure it captures any data that the new batcher 
        rules might have excluded.

        :param batcher_cls: The Batcher class to initialize.
        :type batcher_cls: Type[DataBatcher]
        :param kwargs: Additional arguments for the batcher initialization.
        """
        if batcher_cls.NAME in self._batchers:
            raise ValueError(f'Data Batcher "{batcher_cls.NAME}" initialized twice')
        
        missing_data = [_ for _ in batcher_cls.REQUIRED_DATA if not self.all_input_data.has_data(_)]
        if len(missing_data) > 0:
            logger.warning(f'Missing required data for batcher "{batcher_cls.NAME}": {", ".join(missing_data)}')
            
        new_batcher = exec_invulnerable(batcher_cls, self.all_input_data, **kwargs)
        if new_batcher is not None:
            self._batchers[batcher_cls.NAME] = new_batcher
            
        # Setup or re-setup the untagged batch
        self._untagged_batch = UntaggedBatch(self.all_input_data)

    def get_batcher(self, name):
        """Retrieves a registered batcher by its name."""
        return self._batchers.get(name)

    @abstractmethod
    def _impl_init_data(self):
        """
        Internal hook for subclasses to perform custom initialization logic 
        per data container.
        """
        return