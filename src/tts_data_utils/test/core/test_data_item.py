import pytest
from datetime import datetime
from tts_data_utils.core.data_item import DataItem

class MockItem(DataItem):
    DICT_VALID_KEYS = [
        ('id', int),
        ('label', (str, type(None))), # Test tuple types and None
        ('metadata', dict),           # Test JSON casting
        ('tags', list)                # Test nested hashing
    ]
    TIME_FORMATS = {'timestamp': '%Y-%jT%H:%M:%S'}
    
    @property
    def time(self):
        return datetime.now()

@pytest.fixture
def mock_item():
    return MockItem({
        'id': 1, 
        'label': 'test', 
        'metadata': "{'version': '1.0'}", 
        'tags': ['a', 'b']
    }, cast_fields=True)


class TestDataItemValidation:
    def test_tuple_and_none_validation(self):
        # Covers logic where types are tuples and None is allowed
        item = MockItem({'id': 1, 'label': None, 'metadata': {}, 'tags': []})
        assert item.valid
        assert item['label'] is None

    def test_json_string_casting(self):
        # Covers lines 145-158: casting string with single quotes to dict
        raw_json_str = "{'key': 'value', 'nested': {'a': 1}}"
        item = MockItem({
            'id': 1, 
            'label': 'x', 
            'metadata': raw_json_str, 
            'tags': []
        }, cast_fields=True)
        
        assert isinstance(item['metadata'], dict)
        assert item['metadata']['key'] == 'value'

    def test_failed_cast_raises(self):
        # Covers lines 167-169
        with pytest.raises(Exception, match="Casting of value"):
            MockItem({'id': 'not_an_int', 'label': 'x', 'metadata': {}, 'tags': []}, cast_fields=True) 

class TestDataItemSignatures:
    def test_nested_hashing(self, mock_item):
        # Covers the recursive make_hashable for lists and dicts
        # If this doesn't work, hash() will raise a TypeError
        h1 = hash(mock_item)
        assert isinstance(h1, int)

        # Ensure order of keys in nested dicts doesn't change hash
        item_a = MockItem({'id': 1, 'label': 'x', 'metadata': {'a': 1, 'b': 2}, 'tags': []})
        item_b = MockItem({'id': 1, 'label': 'x', 'metadata': {'b': 2, 'a': 1}, 'tags': []})
        assert hash(item_a) == hash(item_b)

    def test_copy_derived_integrity(self, mock_item):
        # Covers lines 247-256
        mock_item['new_key'] = 'original'
        child = mock_item._copy()
        child['new_key'] = 'modified'
        
        assert mock_item['new_key'] == 'original'
        assert child['new_key'] == 'modified'

class TestDataItemStubs:
    def test_default_styles(self, mock_item):
        # Covers lines 307-319
        assert mock_item.default_html_row_style == {}
        assert mock_item.default_rich_text_row_style == {}
        assert isinstance(mock_item.default_html_cell_styles, dict)

    def test_batch_tagging_stubs(self, mock_item):
        # Covers lines 343-361
        assert not mock_item.any_batches()
        mock_item.tag_with_batch("Batch_A")
        assert mock_item.in_batch("Batch_A")
        assert mock_item.any_batches()

    def test_empty_constructor(self):
        # Covers lines 322-326
        empty_item = MockItem.empty(keys=['id', 'label'])
        assert empty_item['id'] is None
        assert not empty_item.valid # Should fail validation since 'id' expects int               