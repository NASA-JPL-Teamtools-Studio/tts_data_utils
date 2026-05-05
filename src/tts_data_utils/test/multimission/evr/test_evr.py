#Standard Library Imports
import pytest
from datetime import datetime

#Installed Library Imports
from pathlib import Path
import pdb

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_utilities.test_utilities import safe_test_paths

#This Library Imports
from tts_data_utils.multimission.evr import EvrContainer, EvrGapContainer

logger = create_logger(f'data_utils.multimission.evr')
TEST_INPUT_DIR, TEST_OUTPUT_DIR = safe_test_paths(Path(__file__).parent, 'test_files')

class TestEvrGaps:
    def test_gap_finder(self):
        evrs = EvrContainer(csv_path=TEST_INPUT_DIR.joinpath('evrs_with_gaps.csv'), cast_fields=True)
        #evrs.gaps().to_csv(TEST_OUTPUT_DIR.joinpath('expected_evr_gaps.csv'))
        expected_evr_gaps = EvrGapContainer(csv_path=TEST_INPUT_DIR.joinpath('expected_evr_gaps.csv'), cast_fields=True)
        evrs.gaps().to_csv(TEST_OUTPUT_DIR.joinpath('actual_evr_gaps.csv'))

        expected_evr_gaps.diff(evrs.gaps())
        import pdb
        pdb.set_trace()
        assert len(expected_evr_gaps.diff(evrs.gaps()).eq('Same', False)) == 0
        assert len(expected_evr_gaps.diff(evrs.gaps())) == 236

