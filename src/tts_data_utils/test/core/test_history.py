#Standard Library Imports
from pathlib import Path
import pdb

#Installed Library Imports
import pytest
from datetime import datetime

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_utilities.test_utilities import safe_test_paths

#This Library Imports
from tts_data_utils.core.generic import GenericContainer

logger = create_logger(f'data_utils.core.history')
TEST_INPUT_DIR, TEST_OUTPUT_DIR = safe_test_paths(Path(__file__).parent, 'test_files/history')

@pytest.fixture(scope="module")
def generic_container():
    time = [datetime.fromtimestamp(ii) for ii in range(100)]
    col1 = [ii for ii in range(50)]*2
    col2 = [ii for ii in range(100, 200)]
    col3 = [str(ii) for ii in range(200, 300)]
    col4 = [ii for ii in range(300, 400)]
    col5 = [ii for ii in range(400, 500)]
    raw_data = [{
        'Time': t,
        'Column 1': c1,
        'Column 2': c2,
        'Column 3': c3,
        'Column 4': c4,
        'Column 5': c5,
    } for t, c1, c2, c3, c4, c5 in zip(time, col1, col2, col3, col4, col5)]
    filter_container = GenericContainer(raw_data=raw_data)
    return filter_container

class TestDiffContainer:
    @pytest.mark.xfail(reason="Feature currently untested")
    def test_unique(self, generic_container):
        #I started writign this, but then realized I really needed
        #to add the ignore test to test_diff, so I quit. But this
        #is still a nice place to put history tests when we have time to
        assert False
