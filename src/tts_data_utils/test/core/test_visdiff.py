#Standard Library Imports
from pathlib import Path
import pdb

#Installed Library Importsimport pytest
from datetime import datetime
import pytest

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_utilities.test_utilities import safe_test_paths
from tts_html_utils.visdiff.visdiff import VisualDiff
from tts_html_utils.core.compiler import HtmlCompiler

#This Library Imports
from tts_data_utils.core.generic import GenericContainer

logger = create_logger(f'data_utils.core.filters')
TEST_INPUT_DIR, TEST_OUTPUT_DIR = safe_test_paths(Path(__file__).parent, 'test_files/visdiff')

def save_html(visdiff_left, visdiff_right, filepath):
    power_table_left = visdiff_left.power_table(id='visdiff-left', style={'width': '130%', 'float': 'left'})
    power_table_right = visdiff_right.power_table(id='visdiff-right', style={'width': '130%', 'float': 'right'})
    compiler = HtmlCompiler('VisDiff Test')
    compiler.add_body_component(VisualDiff(power_table_left, power_table_right))
    file = open(filepath, 'w')
    file.write(compiler.render())
    file.close()

@pytest.fixture(scope="module")
def test_container():
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
    test_container = GenericContainer(raw_data=raw_data)
    return test_container


class TestVisDiff:
    def test_no_diff(self, test_container):
        visdiff_left, visdiff_right = test_container.visual_diff(test_container)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('no_diff.html'))

        assert visdiff_left['_visdiff_match'] == ['equal']*100
        assert visdiff_left['_visdiff_index'] == [ii for ii in range(100)]
        assert visdiff_left['_mismatched_keys'] == [[]]*100

        assert visdiff_right['_visdiff_match'] == ['equal']*100
        assert visdiff_right['_visdiff_index'] == [ii for ii in range(100)]
        assert visdiff_right['_mismatched_keys'] == [[]]*100

    def test_simple_delete(self, test_container):
        left = test_container
        right = test_container[:10] + test_container[20:]
        visdiff_left, visdiff_right = left.visual_diff(right)

        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('simple_delete.html'))

        assert visdiff_left['_visdiff_match'] == ['equal']*10 + ['delete']*10 + ['equal']*80
        assert visdiff_left['_visdiff_index'] == [ii for ii in range(10)] + [None]*10 + [ii for ii in range(10, 90)]
        assert visdiff_left['_mismatched_keys'] == [[]]*100

        assert visdiff_right['_visdiff_match'] == ['equal']*10 + ['empty_from_delete']*10 + ['equal']*80
        assert visdiff_right['_visdiff_index'] == [ii for ii in range(10)] + [None]*10 + [ii for ii in range(20, 100)]
        assert visdiff_right['_mismatched_keys'] == [[]]*100

    def test_simple_insert(self, test_container):
        left = test_container[:10] + test_container[20:]
        right = test_container
        visdiff_left, visdiff_right = left.visual_diff(right)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('simple_insert.html'))

        assert visdiff_left['_visdiff_match'] == ['equal']*10 + ['empty_from_insert']*10 + ['equal']*80
        assert visdiff_left['_visdiff_index'] == [ii for ii in range(10)] + [None]*10 + [ii for ii in range(20,100)]
        assert visdiff_left['_mismatched_keys'] == [[]]*100

        assert visdiff_right['_visdiff_match'] == ['equal']*10 + ['insert']*10 + ['equal']*80
        assert visdiff_right['_visdiff_index'] == [ii for ii in range(10)] + [None]*10 + [ii for ii in range(10, 90)]
        assert visdiff_right['_mismatched_keys'] == [[]]*100

    def test_insert_and_delete(self, test_container):

        left = test_container[:10] + test_container[20:]
        right = test_container[:50] + test_container[60:]
        visdiff_left, visdiff_right = left.visual_diff(right)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('insert_and_delete.html'))

        assert visdiff_left['_visdiff_match'] == ['equal']*10 + ['empty_from_insert']*10 + ['equal']*30 + ['delete']*10 + ['equal']*40
        assert visdiff_left['_visdiff_index'] == [ii for ii in range(10)] + [None]*10 + [ii for ii in range(20,50)] + [None]*10 + [ii for ii in range(50, 90)]
        assert visdiff_left['_mismatched_keys'] == [[]]*100

        assert visdiff_right['_visdiff_match'] == ['equal']*10 + ['insert']*10 + ['equal']*30 + ['empty_from_delete']*10 + ['equal']*40
        assert visdiff_right['_visdiff_index'] == [ii for ii in range(10)] + [None]*10 + [ii for ii in range(10,40)] + [None]*10 + [ii for ii in range(50, 90)]
        assert visdiff_right['_mismatched_keys'] == [[]]*100


    def test_adjacent_insert_delete(self, test_container):

        left = test_container[:10] + test_container[20:]
        right = test_container[:20] + test_container[30:]
        visdiff_left, visdiff_right = left.visual_diff(right)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('adjacent_insert_delete.html'))

        assert visdiff_left['_visdiff_match'] == ['equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal']
        assert visdiff_left['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89]
        assert visdiff_left['_mismatched_keys'] == [[]]*100

        assert visdiff_right['_visdiff_match'] == ['equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal']
        assert visdiff_right['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89]
        assert visdiff_right['_mismatched_keys'] == [[]]*100

    def test_overlapping_insert_delete(self, test_container):
        left = test_container[:10] + test_container[20:]
        right = test_container[:15] + test_container[25:]
        visdiff_left, visdiff_right = left.visual_diff(right)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('overlapping_insert_delete.html'))

        assert visdiff_left['_visdiff_match'] == ['equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'delete', 'delete', 'delete', 'delete', 'delete', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal']
        assert visdiff_left['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, None, None, None, None, None, None, None, None, None, None, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89]
        assert visdiff_left['_mismatched_keys'] == [[], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []]

        assert visdiff_right['_visdiff_match'] == ['equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'insert', 'insert', 'insert', 'insert', 'insert', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal', 'equal']
        assert visdiff_right['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, None, None, None, None, None, None, None, None, None, None, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89]
        assert visdiff_right['_mismatched_keys'] == [[], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []]

    def test_replace(self, test_container):
        left = test_container._copy()
        right = left._copy()
        for ii in range(len(right)):
            if ii%3 == 0: right[ii]['Column 1'] += 3
            if ii%5 == 0: right[ii]['Column 2'] += 2

        visdiff_left, visdiff_right = left.visual_diff(right)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('replace.html'))

        assert visdiff_left['_visdiff_match'] == ['replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace']
        assert visdiff_left['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99]
        assert visdiff_left['_mismatched_keys'] == [['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1']]

        assert visdiff_right['_visdiff_match'] == ['replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace']
        assert visdiff_right['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99]
        assert visdiff_right['_mismatched_keys'] == [['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1']]

    def test_replace_with_delete(self, test_container):
        left = test_container._copy()
        right = left._copy()
        for ii in range(len(right)):
            if ii%3 == 0: right[ii]['Column 1'] += 3
            if ii%5 == 0: right[ii]['Column 2'] += 2
        right = right[:20] + right[40:]

        visdiff_left, visdiff_right = left.visual_diff(right)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('replace_with_delete.html'))

        assert visdiff_left['_visdiff_match'] == ['replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace']
        assert visdiff_left['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79]
        assert visdiff_left['_mismatched_keys'] == [['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], ['Column 2', '_visdiff_match', '_visdiff_index'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1']]

        assert visdiff_right['_visdiff_match'] == ['replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace', 'replace', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'equal', 'replace', 'equal', 'replace', 'replace', 'equal', 'equal', 'replace']
        assert visdiff_right['_visdiff_index'] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99]
        assert visdiff_right['_mismatched_keys'] == [['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], ['Column 2', '_visdiff_index', '_mismatched_keys'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1'], ['Column 2'], [], ['Column 1'], [], [], ['Column 1', 'Column 2'], [], [], ['Column 1'], [], ['Column 2'], ['Column 1'], [], [], ['Column 1']]


    def test_stressing_case(self, test_container):
        left = test_container._copy()
        right = left._copy()
        for ii in range(len(right)):
            right[ii]['Column 1'] += 3
            right[ii]['Column 2'] += 2
        left = left[:30] + left[50:]
        right = right[:20] + right[40:]

        visdiff_left, visdiff_right = left.visual_diff(right)
        save_html(visdiff_left, visdiff_right, TEST_OUTPUT_DIR.joinpath('stressing_case.html'))

        assert visdiff_left['_visdiff_match'] == ['delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'delete', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert', 'empty_from_insert']
        assert visdiff_left['_visdiff_index'] == [None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None]
        assert visdiff_left['_mismatched_keys'] == [[], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []]

        assert visdiff_right['_visdiff_match'] == ['empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'empty_from_delete', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert', 'insert']
        assert visdiff_right['_visdiff_index'] == [None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None]
        assert visdiff_right['_mismatched_keys'] == [[], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []]