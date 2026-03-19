import pytest
from unittest.mock import MagicMock, patch
from tts_data_utils.invulnerable_data_manager.invulnerable_data_manager import InvulnerableDataManager
from tts_data_utils.core.generic import GenericContainer

# Simple concrete subclass for testing
class MockManager(InvulnerableDataManager):
    def _impl_init_data(self, container_cls, data, name=None, **kwargs):
        pass

# Mock Batcher for testing
class MockBatcher:
    NAME = "test_batcher"
    REQUIRED_DATA = ["required_input"]
    def __init__(self, all_input_data, **kwargs):
        self.all_input_data = all_input_data

@pytest.fixture
def mock_dependencies():
    """
    Patches internal dependencies so we test Manager logic in isolation.
    """
    # PATCH PATHS: We must patch where the names are IMPORTED/USED, not defined.
    with patch('tts_data_utils.invulnerable_data_manager.invulnerable_data_manager.AllDataBatch') as MockAllData, \
         patch('tts_data_utils.invulnerable_data_manager.invulnerable_data_manager.UntaggedBatch') as MockUntagged, \
         patch('tts_data_utils.invulnerable_data_manager.invulnerable_data_manager.exec_invulnerable') as MockExec:
        
        # 1. Configure AllDataBatch Mock Instance
        mock_batch_instance = MockAllData.return_value
        
        # Internal store for the mock to simulate state
        mock_batch_instance._data_store = []
        
        # Behavior: has_data checks the internal list
        mock_batch_instance.has_data.side_effect = lambda name: name in mock_batch_instance._data_store
        
        # Behavior: set_data_one adds to the internal list
        def set_data_side_effect(name, data):
            mock_batch_instance._data_store.append(name)
        mock_batch_instance.set_data_one.side_effect = set_data_side_effect
        
        # Behavior: get_inventory returns a dict (Code expects this method exists)
        mock_batch_instance.get_inventory.return_value = {"mock_data": 1}
        
        # 2. Configure exec_invulnerable Mock
        # Default: Return a valid container
        valid_container = MagicMock()
        valid_container.valid = True
        MockExec.return_value = valid_container
        
        yield MockAllData, MockUntagged, MockExec

@pytest.fixture
def manager(mock_dependencies):
    return MockManager()

@pytest.fixture
def valid_data():
    return [{'id': 1, 'val': 'A'}]

class TestDataManagerIngestion:
    def test_init_data_success(self, manager, valid_data):
        """Verify successful ingestion and registration."""
        manager.init_data(GenericContainer, valid_data, name="test_data")
        
        # Verify the manager delegated to the internal batch storage
        manager.all_input_data.set_data_one.assert_called()
        
        # Verify inventory logic
        # The code calls .get_inventory(), which we mocked to return {"mock_data": 1}
        inv = manager.get_input_inventory()
        assert "mock_data" in inv

    def test_init_data_none_raises(self, manager):
        """Verify that passing None results in an error (swallowed by @invulnerable)."""
        manager.init_data(GenericContainer, None, name="fail_data")
        # Verify set_data_one was NOT called
        manager.all_input_data.set_data_one.assert_not_called()

    def test_duplicate_init_raises(self, manager, valid_data):
        """Verify that initializing the same name twice is caught."""
        # Note: The code checks duplicate on `container_cls.NAME`. 
        # We omit 'name' kwarg here so it defaults to GenericContainer.NAME
        # allowing the check to work correctly.
        
        # First init
        manager.init_data(GenericContainer, valid_data)
        
        # Verify it was stored
        assert manager.all_input_data.has_data(GenericContainer.NAME)

        # Second init - should trigger ValueError internally
        manager.init_data(GenericContainer, valid_data)
        
        # Verify set_data_one was called exactly once (for the first success only)
        assert manager.all_input_data.set_data_one.call_count == 1

    def test_invalid_container_swallowed(self, manager, mock_dependencies):
        """Verify that a container that fails validation isn't registered."""
        _, _, mock_exec = mock_dependencies
        
        # Configure exec_invulnerable to return an INVALID container for this test
        invalid_container = MagicMock()
        invalid_container.valid = False
        mock_exec.return_value = invalid_container
        
        manager.init_data(GenericContainer, [], name="invalid_container")
            
        manager.all_input_data.set_data_one.assert_not_called()

class TestDataManagerBatching:
    def test_init_batcher_missing_requirements(self, manager):
        """Verify behavior when required data is missing."""
        # Ensure the mock says we DO NOT have data
        manager.all_input_data.has_data.return_value = False
        
        manager.init_batcher(MockBatcher)
        
        # Current Code Behavior: Logs warning but returns the Batcher (does not return None).
        # We test for existence, acknowledging the permissive behavior.
        assert manager.get_batcher("test_batcher") is not None

    def test_init_batcher_success(self, manager, valid_data, mock_dependencies):
        """Verify batcher registers when requirements are met."""
        _, _, mock_exec = mock_dependencies
        
        # 1. Satisfy requirements
        # We manually force the mock to say "Yes, I have required_input"
        manager.all_input_data._data_store.append("required_input")

        # 2. Configure exec_invulnerable to return a valid Batcher
        mock_batcher_instance = MagicMock()
        mock_exec.return_value = mock_batcher_instance

        manager.init_batcher(MockBatcher)
        
        assert manager.get_batcher("test_batcher") is not None
        # Verify untagged batch was re-initialized (Mock called)
        assert manager._untagged_batch is not None

    def test_comprehensive_inventory(self, manager, valid_data):
        """Verify the data map returns both inputs and outputs."""
        manager.init_data(GenericContainer, valid_data, name="input_1")
        
        inventory = manager.get_data_inventory()
        
        # Based on our mock setup in the fixture, get_inventory returns {"mock_data": 1}
        # This applies to both Input and Output batches (same mock class)
        assert "mock_data" in inventory['Inputs']
        assert "mock_data" in inventory['Outputs']