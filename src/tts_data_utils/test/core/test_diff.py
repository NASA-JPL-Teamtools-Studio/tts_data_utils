#Standard Library Imports
import json
import pytest
from pathlib import Path
import pdb
from datetime import datetime

#Installed Library Imports
import hashlib
import pandas as pd

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_utilities.test_utilities import safe_test_paths

#This Library Imports
from tts_data_utils.multimission.evr import EvrContainer
from tts_data_utils.core.diff import DiffContainer, DiffItem
from tts_data_utils.core.generic import GenericContainer

logger = create_logger(f'tts_data_utils.core.diff')
TEST_INPUT_DIR, TEST_OUTPUT_DIR = safe_test_paths(Path(__file__).parent, 'test_files/diff')

@pytest.fixture
def sample_diff():
    """
    Generates a DiffContainer with known differences for testing accessors.
    
    **The Concept:**
    We use GenericContainer here because it allows arbitrary keys without 
    triggering the strict validation errors seen in specialized containers 
    like EvrContainer.
    """
    left_data = [{'vcid': 1, 'name': 'TEST_CH_1', 'message': 'OK'}]
    right_data = [{'vcid': 1, 'name': 'TEST_CH_1', 'message': 'ERROR'}]
    
    left = GenericContainer(raw_data=left_data, name='test_container')
    right = GenericContainer(raw_data=right_data, name='test_container')
    return left.diff(right)

class TestDiffContainer:
    def test_ignore(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_simple_types/left.csv'), cast_fields=True)
        right = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_simple_types/right.csv'), cast_fields=True)
        assert len(left.diff(right)) == 17893
        assert len(left.diff(right, ignore='history')) == 17893 - 36
        assert len(left.diff(right, ignore='_repr_cols')) == 17893 - 23
        assert len(left.diff(right, ignore='history/EVR Container/_repr_cols')) == 17893 - 8
        assert len(left.diff(right, ignore='history/EVR Container/_repr_cols/4')) == 17893 - 3

    def test_diff_simple_types(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_simple_types/left.csv'), cast_fields=True)
        right = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_simple_types/right.csv'), cast_fields=True)
        actual_diff = left.diff(right)
        actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_simple_types/actual_diff.csv'), mkdirs=True)
        # actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_simple_types/expected_diff.csv'), mkdirs=True)
        expected_diff = DiffContainer('tbd', 'tdb', csv_path=TEST_INPUT_DIR.joinpath('diff_simple_types/expected_diff.csv'))
        assert len(actual_diff) == 17893 #simple test to hedge against the diff just being empty and succeeding for that reason
        assert len(expected_diff.diff(actual_diff, ignore='history').not_same()) == 0

    def test_diff_self_v_self(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_simple_types/left.csv'), cast_fields=True)
        left_diff_left = left.diff(left)
        assert left.diff(left, summarize=True)
        assert len(left_diff_left) == 1
        source_wo_lr = {k:v for k, v in left_diff_left[0].values.items() if k not in ['left', 'right']}
        assert source_wo_lr['Key'] == '/'
        assert source_wo_lr['Same'] is True
        assert source_wo_lr['Type'] == 'EvrContainer'
        assert source_wo_lr['Left'] == 'Same memory location'
        assert source_wo_lr['Right'] == 'Same memory location'

    def test_different_list_size(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_list_size/left.csv'), cast_fields=True)
        actual_diff = left[1:].diff(left)
        actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_list_size/actual_diff.csv'), mkdirs=True)
        # actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_list_size/expected_diff.csv'), mkdirs=True)
        expected_diff = DiffContainer('tbd', 'tdb', csv_path=TEST_INPUT_DIR.joinpath('diff_list_size/expected_diff.csv'))
        assert len(actual_diff) == 32 #simple test to hedge against the diff just being empty and succeeding for that reason
        assert len(expected_diff.diff(actual_diff, ignore='history').not_same()) == 0

    def test_diff_list(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_list/left.csv'), cast_fields=True)
        right = left._copy()
        #Need this to force the value to exist in derived values
        #need to think though hwo to better illustrate this to users
        left.records[0]['sclk'] = left.records[0]['sclk']
        right.records[0]['sclk'] = 156.03352
        actual_diff = left.diff(right)
        actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_list/actual_diff.csv'), mkdirs=True)
        # actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_list/expected_diff.csv'), mkdirs=True)
        expected_diff = DiffContainer('tbd', 'tdb', csv_path=TEST_INPUT_DIR.joinpath('diff_list/expected_diff.csv'))
        assert len(actual_diff) == 5134 #simple test to hedge against the diff just being empty and succeeding for that reason
        assert len(expected_diff.diff(actual_diff, ignore='history').not_same()) == 0

    def test_diff_type(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_type/left.csv'), cast_fields=True)
        right = left._copy()
        left.records[0]['sclk'] = 156.
        right.records[0]['sclk'] = 156
        actual_diff = left.diff(right)
        actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_type/actual_diff.csv'), mkdirs=True)
        # actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_type/expected_diff.csv'), mkdirs=True)
        expected_diff = DiffContainer('tbd', 'tdb', csv_path=TEST_INPUT_DIR.joinpath('diff_type/expected_diff.csv'))
        assert len(actual_diff) == 5134 #simple test to hedge against the diff just being empty and succeeding for that reason
        assert len(expected_diff.diff(actual_diff, ignore='history').not_same()) == 0

    def test_diff_dict(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_type/left.csv'), cast_fields=True)
        right = left._copy()
        left.records[0]['sclk'] = 156
        right.records[1]['sclk'] = 156
        left.records[2]['sclk'] = 156
        right.records[2]['sclk'] = 157
        actual_diff = left.diff(right)
        actual_diff.eq('Same', False)
        actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_dict/actual_diff.csv'), mkdirs=True)
        # actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('diff_dict/expected_diff.csv'), mkdirs=True)        
        expected_diff = DiffContainer('tbd', 'tdb', csv_path=TEST_INPUT_DIR.joinpath('diff_dict/expected_diff.csv'))
        assert len(actual_diff) == 5134 #simple test to hedge against the diff just being empty and succeeding for that reason
        assert len(expected_diff.diff(actual_diff, ignore='history').not_same()) == 0

    def test_same_not_same(self):
        left = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('diff_type/left.csv'), cast_fields=True)
        right = left._copy()
        left.records[0]['sclk'] = 156
        right.records[1]['sclk'] = 156
        left.records[2]['sclk'] = 156
        right.records[2]['sclk'] = 157 
        actual_diff = left.diff(right)
        actual_diff.to_csv(TEST_OUTPUT_DIR.joinpath('same_not_same/actual_diff.csv'), mkdirs=True)
        try: 
            #These tests will trigger differently if dexter is here or not
            import tts_dexter
            assert len(actual_diff.is_same()) == 5115
            assert len(actual_diff.not_same()) == 19
        except ModuleNotFoundError:
            assert len(actual_diff.is_same()) == 5121
            assert len(actual_diff.not_same()) == 13



class TestDiffAccessors:
    """Brittle tests for DiffContainer lookup logic."""
    
    def test_find_row_by_key(self, sample_diff):
        """Strictly validates that the breadcrumb path matches expectations."""
        # This key assumes the recursive logic produces exactly this string
        target_key = '/test_container/records/0/test_container/source/message'
        
        # Verify value extraction using the exact hardcoded key
        assert sample_diff.left(target_key) == 'OK'
        assert sample_diff.right(target_key) == 'ERROR'
        
        # Verify error handling for missing keys (Line 107)
        with pytest.raises(Exception, match='No key "INVALID" found'):
            sample_diff._find_row_by_key("INVALID")

    def test_repr_cols(self, sample_diff):
        """Covers line 155."""
        cols = sample_diff.repr_cols
        assert 'Key' in cols
        assert 'Same' in cols

class TestDiffItemInternals:
    """Covers DiffItem stubs (Lines 53, 62)."""
    
    def test_item_stubs(self):
        item = DiffItem({'Key': 'K', 'Same': True, 'Type': 'str', 'Left': 'A', 'Right': 'A'})
        # Hits the disabled time method (Line 62)
        assert item.time() is None
        # Hits the sub_init stub indirectly during initialization
        assert item['Key'] == 'K'