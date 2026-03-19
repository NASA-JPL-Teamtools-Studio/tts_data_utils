#Standard Library Imports
from pathlib import Path
import pdb

#Installed Library Importsimport pytest
from datetime import datetime
import pytest

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_utilities.test_utilities import safe_test_paths

#This Library Imports
from tts_data_utils.core.generic import GenericContainer

logger = create_logger(f'data_utils.core.filters')
TEST_INPUT_DIR, TEST_OUTPUT_DIR = safe_test_paths(Path(__file__).parent, 'core/filters')

@pytest.fixture(scope="module")
def filter_container():
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

@pytest.fixture(scope="module")
def filter_container_case_sensitive():
    #I totally could have merged this alongside the other container fixture
    #but I didn't recognize the need for it until the tests that don't need
    #case sensitivity were mature enough that I didn't want to merge them
    #for essentially no value add.
    time = [datetime.fromtimestamp(ii) for ii in range(100)]
    col1 = [ii for ii in range(50)]*2
    col2 = [ii for ii in range(100, 200)]
    col3 = [str(ii) for ii in range(200, 300)]
    col4 = [ii for ii in range(300, 400)]
    col5 = [ii for ii in range(400, 500)]
    col3[30] = 'This is a string that is sentence case'
    col3[40] = 'This Is A String That Is Title Case'
    col3[50] = 'This is A string That has Mixed case'
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
    def test_summarize(self):
        assert False

    def test_unique(self, filter_container):
        assert filter_container.unique('Column 1') == [ii for ii in range(50)]

class TestFiltering:
    def test_gt(self, filter_container):
        gt_container = filter_container.gt('Column 2', 125)
        assert len(gt_container) == 74
        assert [r['Column 1'] for r in gt_container] == ([ii for ii in range(50)]*2)[26:]
        assert [r['Column 2'] for r in gt_container] == [ii for ii in range(126, 200)]
        assert [r['Column 3'] for r in gt_container] == [str(ii) for ii in range(226, 300)]
        assert [r['Column 4'] for r in gt_container] == [ii for ii in range(326, 400)]
        assert [r['Column 5'] for r in gt_container] == [ii for ii in range(426, 500)]

    def test_lt(self, filter_container):
        lt_container = filter_container.lt('Column 2', 125)
        assert len(lt_container) == 25
        assert [r['Column 1'] for r in lt_container] == ([ii for ii in range(50)]*2)[:25]
        assert [r['Column 2'] for r in lt_container] == [ii for ii in range(100, 125)]
        assert [r['Column 3'] for r in lt_container] == [str(ii) for ii in range(200, 225)]
        assert [r['Column 4'] for r in lt_container] == [ii for ii in range(300, 325)]
        assert [r['Column 5'] for r in lt_container] == [ii for ii in range(400, 425)]

    def test_gte(self, filter_container):
        gte_container = filter_container.gte('Column 2', 125)
        assert len(gte_container) == 75
        assert [r['Column 1'] for r in gte_container] == ([ii for ii in range(50)]*2)[25:]
        assert [r['Column 2'] for r in gte_container] == [ii for ii in range(125, 200)]
        assert [r['Column 3'] for r in gte_container] == [str(ii) for ii in range(225, 300)]
        assert [r['Column 4'] for r in gte_container] == [ii for ii in range(325, 400)]
        assert [r['Column 5'] for r in gte_container] == [ii for ii in range(425, 500)]

    def test_lte(self, filter_container):
        lte_container = filter_container.lte('Column 2', 125)
        assert len(lte_container) == 26
        assert [r['Column 1'] for r in lte_container] == ([ii for ii in range(50)]*2)[:26]
        assert [r['Column 2'] for r in lte_container] == [ii for ii in range(100, 126)]
        assert [r['Column 3'] for r in lte_container] == [str(ii) for ii in range(200, 226)]
        assert [r['Column 4'] for r in lte_container] == [ii for ii in range(300, 326)]
        assert [r['Column 5'] for r in lte_container] == [ii for ii in range(400, 426)]

    def test_eq(self, filter_container):
        eq_container = filter_container.eq('Column 1', 32)
        assert len(eq_container) == 2
        assert [r['Column 1'] for r in eq_container] == [32, 32]
        assert [r['Column 2'] for r in eq_container] == [132, 182]
        assert [r['Column 3'] for r in eq_container] == ['232', '282']
        assert [r['Column 4'] for r in eq_container] == [332, 382]
        assert [r['Column 5'] for r in eq_container] == [432, 482]

    def test_ne(self, filter_container):
        ne_container = filter_container.ne('Column 1', 32)
        assert len(ne_container) == 98
        assert [r['Column 1'] for r in ne_container] == [ii for ii in range(50) if ii != 32]*2
        assert [r['Column 2'] for r in ne_container] == [ii for ii in range(100, 200) if ii not in [132, 182]]
        assert [r['Column 3'] for r in ne_container] == [str(ii) for ii in range(200, 300) if ii not in [232, 282]]
        assert [r['Column 4'] for r in ne_container] == [ii for ii in range(300, 400) if ii not in [332, 382]]
        assert [r['Column 5'] for r in ne_container] == [ii for ii in range(400, 500) if ii not in [432, 482]]

    def test_isin(self, filter_container):
        isin_container_int = filter_container.isin('Column 2', [10, 125, 150, 175, 200, 225, 'A', {}, []])
        isin_container_str = filter_container.isin('Column 3', ['10', '225', '250', '275', '300', '325', 900, {}, []])

        assert len(isin_container_int) == 3
        assert [r['Column 1'] for r in isin_container_int] == [25, 0, 25]
        assert [r['Column 2'] for r in isin_container_int] == [125, 150, 175]
        assert [r['Column 3'] for r in isin_container_int] == ['225', '250', '275']
        assert [r['Column 4'] for r in isin_container_int] == [325, 350, 375]
        assert [r['Column 5'] for r in isin_container_int] == [425, 450, 475]

        assert len(isin_container_str) == 3
        assert [r['Column 1'] for r in isin_container_str] == [25, 0, 25]
        assert [r['Column 2'] for r in isin_container_str] == [125, 150, 175]
        assert [r['Column 3'] for r in isin_container_str] == ['225', '250', '275']
        assert [r['Column 4'] for r in isin_container_str] == [325, 350, 375]
        assert [r['Column 5'] for r in isin_container_str] == [425, 450, 475]

    def test_notin(self, filter_container):
        notin_container_int = filter_container.notin('Column 2', [10, 125, 150, 175, 200, 225, 'A', {}, []])
        notin_container_str = filter_container.notin('Column 3', ['10', '225', '250', '275', '300', '325', 900, {}, []])

        assert len(notin_container_int) == 97
        assert [r['Column 1'] for r in notin_container_int] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]
        assert [r['Column 2'] for r in notin_container_int] == [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199]
        assert [r['Column 3'] for r in notin_container_int] == ['200', '201', '202', '203', '204', '205', '206', '207', '208', '209', '210', '211', '212', '213', '214', '215', '216', '217', '218', '219', '220', '221', '222', '223', '224', '226', '227', '228', '229', '230', '231', '232', '233', '234', '235', '236', '237', '238', '239', '240', '241', '242', '243', '244', '245', '246', '247', '248', '249', '251', '252', '253', '254', '255', '256', '257', '258', '259', '260', '261', '262', '263', '264', '265', '266', '267', '268', '269', '270', '271', '272', '273', '274', '276', '277', '278', '279', '280', '281', '282', '283', '284', '285', '286', '287', '288', '289', '290', '291', '292', '293', '294', '295', '296', '297', '298', '299']
        assert [r['Column 4'] for r in notin_container_int] == [300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399]
        assert [r['Column 5'] for r in notin_container_int] == [400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424, 426, 427, 428, 429, 430, 431, 432, 433, 434, 435, 436, 437, 438, 439, 440, 441, 442, 443, 444, 445, 446, 447, 448, 449, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 461, 462, 463, 464, 465, 466, 467, 468, 469, 470, 471, 472, 473, 474, 476, 477, 478, 479, 480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493, 494, 495, 496, 497, 498, 499]

        assert len(notin_container_str) == 97
        assert [r['Column 1'] for r in notin_container_str] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]
        assert [r['Column 2'] for r in notin_container_str] == [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199]
        assert [r['Column 3'] for r in notin_container_str] == ['200', '201', '202', '203', '204', '205', '206', '207', '208', '209', '210', '211', '212', '213', '214', '215', '216', '217', '218', '219', '220', '221', '222', '223', '224', '226', '227', '228', '229', '230', '231', '232', '233', '234', '235', '236', '237', '238', '239', '240', '241', '242', '243', '244', '245', '246', '247', '248', '249', '251', '252', '253', '254', '255', '256', '257', '258', '259', '260', '261', '262', '263', '264', '265', '266', '267', '268', '269', '270', '271', '272', '273', '274', '276', '277', '278', '279', '280', '281', '282', '283', '284', '285', '286', '287', '288', '289', '290', '291', '292', '293', '294', '295', '296', '297', '298', '299']
        assert [r['Column 4'] for r in notin_container_str] == [300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399]
        assert [r['Column 5'] for r in notin_container_str] == [400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424, 426, 427, 428, 429, 430, 431, 432, 433, 434, 435, 436, 437, 438, 439, 440, 441, 442, 443, 444, 445, 446, 447, 448, 449, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 461, 462, 463, 464, 465, 466, 467, 468, 469, 470, 471, 472, 473, 474, 476, 477, 478, 479, 480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493, 494, 495, 496, 497, 498, 499]


    def test_contains_case_sensitive(self, filter_container_case_sensitive):
        #There's no technical reason to separate this from test_contains.
        #It's really just because I didn't recognize I needed this when I built
        #the fixtures, and then when I decided to add these couple tests that
        #care about sensitiviy/insensitivity, I didn't want to have to rewrite
        #all the rest
        contains_container_case_sensitive = filter_container_case_sensitive.contains('Column 3', 'This is a string')

        assert len(contains_container_case_sensitive) == 1
        assert [r['Column 1'] for r in contains_container_case_sensitive] == [30]
        assert [r['Column 2'] for r in contains_container_case_sensitive] == [130]
        assert [r['Column 3'] for r in contains_container_case_sensitive] == ['This is a string that is sentence case']
        assert [r['Column 4'] for r in contains_container_case_sensitive] == [330]
        assert [r['Column 5'] for r in contains_container_case_sensitive] == [430]

    def test_doesnotcontain_case_sensitive(self, filter_container_case_sensitive):
        #There's no technical reason to separate this from test_contains.
        #It's really just because I didn't recognize I needed this when I built
        #the fixtures, and then when I decided to add these couple tests that
        #care about sensitiviy/insensitivity, I didn't want to have to rewrite
        #all the rest
        contains_container_case_insensitive = filter_container_case_sensitive.contains('Column 3', 'This is a string', case_sensitive=False)

        assert len(contains_container_case_insensitive) == 3
        assert [r['Column 1'] for r in contains_container_case_insensitive] == [30, 40, 0]
        assert [r['Column 2'] for r in contains_container_case_insensitive] == [130, 140, 150]
        assert [r['Column 3'] for r in contains_container_case_insensitive] == ['This is a string that is sentence case', 'This Is A String That Is Title Case', 'This is A string That has Mixed case']
        assert [r['Column 4'] for r in contains_container_case_insensitive] == [330, 340, 350]
        assert [r['Column 5'] for r in contains_container_case_insensitive] == [430, 440, 450]

    def test_contains(self, filter_container):
        contains_container = filter_container.contains('Column 3', '3')

        assert len(contains_container) == 19
        assert [r['Column 1'] for r in contains_container] == [3, 13, 23, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 43, 3, 13, 23, 33, 43]
        assert [r['Column 2'] for r in contains_container] == [103, 113, 123, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 143, 153, 163, 173, 183, 193]
        assert [r['Column 3'] for r in contains_container] == ['203', '213', '223', '230', '231', '232', '233', '234', '235', '236', '237', '238', '239', '243', '253', '263', '273', '283', '293']
        assert [r['Column 4'] for r in contains_container] == [303, 313, 323, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 343, 353, 363, 373, 383, 393]
        assert [r['Column 5'] for r in contains_container] == [403, 413, 423, 430, 431, 432, 433, 434, 435, 436, 437, 438, 439, 443, 453, 463, 473, 483, 493]

    def test_doesnotcontain(self, filter_container):
        doesnotcontain_container = filter_container.doesnotcontain('Column 3', '3')

        assert len(doesnotcontain_container) == 81
        assert [r['Column 1'] for r in doesnotcontain_container] == [0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 40, 41, 42, 44, 45, 46, 47, 48, 49, 0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49]
        assert [r['Column 2'] for r in doesnotcontain_container] == [100, 101, 102, 104, 105, 106, 107, 108, 109, 110, 111, 112, 114, 115, 116, 117, 118, 119, 120, 121, 122, 124, 125, 126, 127, 128, 129, 140, 141, 142, 144, 145, 146, 147, 148, 149, 150, 151, 152, 154, 155, 156, 157, 158, 159, 160, 161, 162, 164, 165, 166, 167, 168, 169, 170, 171, 172, 174, 175, 176, 177, 178, 179, 180, 181, 182, 184, 185, 186, 187, 188, 189, 190, 191, 192, 194, 195, 196, 197, 198, 199]
        assert [r['Column 3'] for r in doesnotcontain_container] == ['200', '201', '202', '204', '205', '206', '207', '208', '209', '210', '211', '212', '214', '215', '216', '217', '218', '219', '220', '221', '222', '224', '225', '226', '227', '228', '229', '240', '241', '242', '244', '245', '246', '247', '248', '249', '250', '251', '252', '254', '255', '256', '257', '258', '259', '260', '261', '262', '264', '265', '266', '267', '268', '269', '270', '271', '272', '274', '275', '276', '277', '278', '279', '280', '281', '282', '284', '285', '286', '287', '288', '289', '290', '291', '292', '294', '295', '296', '297', '298', '299']
        assert [r['Column 4'] for r in doesnotcontain_container] == [300, 301, 302, 304, 305, 306, 307, 308, 309, 310, 311, 312, 314, 315, 316, 317, 318, 319, 320, 321, 322, 324, 325, 326, 327, 328, 329, 340, 341, 342, 344, 345, 346, 347, 348, 349, 350, 351, 352, 354, 355, 356, 357, 358, 359, 360, 361, 362, 364, 365, 366, 367, 368, 369, 370, 371, 372, 374, 375, 376, 377, 378, 379, 380, 381, 382, 384, 385, 386, 387, 388, 389, 390, 391, 392, 394, 395, 396, 397, 398, 399]
        assert [r['Column 5'] for r in doesnotcontain_container] == [400, 401, 402, 404, 405, 406, 407, 408, 409, 410, 411, 412, 414, 415, 416, 417, 418, 419, 420, 421, 422, 424, 425, 426, 427, 428, 429, 440, 441, 442, 444, 445, 446, 447, 448, 449, 450, 451, 452, 454, 455, 456, 457, 458, 459, 460, 461, 462, 464, 465, 466, 467, 468, 469, 470, 471, 472, 474, 475, 476, 477, 478, 479, 480, 481, 482, 484, 485, 486, 487, 488, 489, 490, 491, 492, 494, 495, 496, 497, 498, 499]

    def test_before(self, filter_container):
        before_container = filter_container.before(datetime.fromtimestamp(3), 'Time')
        before_container_inclusive = filter_container.before(datetime.fromtimestamp(3), 'Time', inclusive=True)

        assert len(before_container) == 3
        assert [r['Column 1'] for r in before_container] == [0, 1, 2]
        assert [r['Column 2'] for r in before_container] == [100, 101, 102]
        assert [r['Column 3'] for r in before_container] == ['200', '201', '202']
        assert [r['Column 4'] for r in before_container] == [300, 301, 302]
        assert [r['Column 5'] for r in before_container] == [400, 401, 402]

        assert len(before_container_inclusive) == 4
        assert [r['Column 1'] for r in before_container_inclusive] == [0, 1, 2, 3]
        assert [r['Column 2'] for r in before_container_inclusive] == [100, 101, 102, 103]
        assert [r['Column 3'] for r in before_container_inclusive] == ['200', '201', '202', '203']
        assert [r['Column 4'] for r in before_container_inclusive] == [300, 301, 302, 303]
        assert [r['Column 5'] for r in before_container_inclusive] == [400, 401, 402, 403]

    def test_after(self, filter_container):
        after_container = filter_container.after(datetime.fromtimestamp(97), 'Time')
        after_container_inclusive = filter_container.after(datetime.fromtimestamp(97), 'Time', inclusive=True)

        assert len(after_container) == 2
        assert [r['Column 1'] for r in after_container] == [48, 49]
        assert [r['Column 2'] for r in after_container] == [198, 199]
        assert [r['Column 3'] for r in after_container] == ['298', '299']
        assert [r['Column 4'] for r in after_container] == [398, 399]
        assert [r['Column 5'] for r in after_container] == [498, 499]

        assert len(after_container_inclusive) == 3
        assert [r['Column 1'] for r in after_container_inclusive] == [47, 48, 49]
        assert [r['Column 2'] for r in after_container_inclusive] == [197, 198, 199]
        assert [r['Column 3'] for r in after_container_inclusive] == ['297', '298', '299']
        assert [r['Column 4'] for r in after_container_inclusive] == [397, 398, 399]
        assert [r['Column 5'] for r in after_container_inclusive] == [497, 498, 499]

    def test_between(self, filter_container):
        between_container_both_inclusive    = filter_container.between('Time', datetime.fromtimestamp(30), datetime.fromtimestamp(35))
        between_container_lower_inclusive   = filter_container.between('Time', datetime.fromtimestamp(30), datetime.fromtimestamp(35), inclusive='lower')
        between_container_upper_inclusive   = filter_container.between('Time', datetime.fromtimestamp(30), datetime.fromtimestamp(35), inclusive='upper')
        between_container_neither_inclusive = filter_container.between('Time', datetime.fromtimestamp(30), datetime.fromtimestamp(35), inclusive='neither')

        assert len(between_container_both_inclusive) == 6
        assert [r['Column 1'] for r in between_container_both_inclusive] == [30, 31, 32, 33, 34, 35]
        assert [r['Column 2'] for r in between_container_both_inclusive] == [130, 131, 132, 133, 134, 135]
        assert [r['Column 3'] for r in between_container_both_inclusive] == ['230', '231', '232', '233', '234', '235']
        assert [r['Column 4'] for r in between_container_both_inclusive] == [330, 331, 332, 333, 334, 335]
        assert [r['Column 5'] for r in between_container_both_inclusive] == [430, 431, 432, 433, 434, 435]

        assert len(between_container_lower_inclusive) == 5
        assert [r['Column 1'] for r in between_container_lower_inclusive] == [30, 31, 32, 33, 34]
        assert [r['Column 2'] for r in between_container_lower_inclusive] == [130, 131, 132, 133, 134]
        assert [r['Column 3'] for r in between_container_lower_inclusive] == ['230', '231', '232', '233', '234']
        assert [r['Column 4'] for r in between_container_lower_inclusive] == [330, 331, 332, 333, 334]
        assert [r['Column 5'] for r in between_container_lower_inclusive] == [430, 431, 432, 433, 434]

        assert len(between_container_upper_inclusive) == 5
        assert [r['Column 1'] for r in between_container_upper_inclusive] == [31, 32, 33, 34, 35]
        assert [r['Column 2'] for r in between_container_upper_inclusive] == [131, 132, 133, 134, 135]
        assert [r['Column 3'] for r in between_container_upper_inclusive] == ['231', '232', '233', '234', '235']
        assert [r['Column 4'] for r in between_container_upper_inclusive] == [331, 332, 333, 334, 335]
        assert [r['Column 5'] for r in between_container_upper_inclusive] == [431, 432, 433, 434, 435]

        assert len(between_container_neither_inclusive) == 4
        assert [r['Column 1'] for r in between_container_neither_inclusive] == [31, 32, 33, 34]
        assert [r['Column 2'] for r in between_container_neither_inclusive] == [131, 132, 133, 134]
        assert [r['Column 3'] for r in between_container_neither_inclusive] == ['231', '232', '233', '234']
        assert [r['Column 4'] for r in between_container_neither_inclusive] == [331, 332, 333, 334]
        assert [r['Column 5'] for r in between_container_neither_inclusive] == [431, 432, 433, 434]

    def test_matches(self, filter_container):
        matches_container = filter_container.matches('Column 3', r'\d0\d')
        assert [r['Column 1'] for r in matches_container] == [ii for ii in range(10)]
        assert [r['Column 2'] for r in matches_container] == [ii for ii in range(100, 110)]
        assert [r['Column 3'] for r in matches_container] == [str(ii) for ii in range(200, 210)]
        assert [r['Column 4'] for r in matches_container] == [ii for ii in range(300, 310)]
        assert [r['Column 5'] for r in matches_container] == [ii for ii in range(400, 410)]

    def test_doesnotmatch(self, filter_container):
        does_not_match_container = filter_container.doesnotmatch('Column 3', r'\d0\d')
        assert [r['Column 1'] for r in does_not_match_container] == ([ii for ii in range(50)]*2)[10:]
        assert [r['Column 2'] for r in does_not_match_container] == [ii for ii in range(100, 200)][10:]
        assert [r['Column 3'] for r in does_not_match_container] == [str(ii) for ii in range(200, 300)][10:]
        assert [r['Column 4'] for r in does_not_match_container] == [ii for ii in range(300, 400)][10:]
        assert [r['Column 5'] for r in does_not_match_container] == [ii for ii in range(400, 500)][10:]

    def test_min(self, filter_container):
        try:
            filter_container.eq('Column 1', 1000, minimum=1)
        except Exception as e:
            assert str(e) == 'Filtered length is not at least 1 as specified'
        assert len(filter_container.eq('Column 1', 10, minimum=2)) == 2

    def test_max(self, filter_container):
        try:
            filter_container.eq('Column 1', 10, maximum=1)
        except Exception as e:
            assert str(e) == 'Filtered length is not less than or equal to 1 as specified'
        assert len(filter_container.eq('Column 1', 10, maximum=2)) == 2

    def test_exactly(self, filter_container):
        try:
            filter_container.eq('Column 1', 10, exactly=1)
        except Exception as e:
            assert str(e) == 'Filtered length is not exactly 1 as specified'
        assert len(filter_container.eq('Column 1', 10, exactly=2)) == 2
