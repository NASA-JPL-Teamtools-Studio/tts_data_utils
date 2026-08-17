import pytest
import pandas as pd

from tts_data_utils.core.log import TtsLogFrame, TtsLogRowSeries


SAMPLE_ROWS = [
    {'scet': '2024-001T00:00:00', 'name': 'SEQ_LOAD',   'level': 'ACTIVITY_LO', 'message': 'Loading 41 cmds'},
    {'scet': '2024-001T00:01:00', 'name': 'CRC_FAIL',   'level': 'WARNING_HI',  'message': 'CRC mismatch on block 5'},
    {'scet': '2024-001T00:02:00', 'name': 'SAFE_MODE',  'level': 'FATAL',       'message': 'Entering safe mode'},
    {'scet': '2024-001T00:03:00', 'name': 'DIAG_BOOT',  'level': 'DIAGNOSTIC',  'message': 'Boot diagnostics OK'},
    {'scet': '2024-001T00:04:00', 'name': 'CRC_FAIL',   'level': 'WARNING_LO',  'message': 'CRC mismatch on block 7'},
]

LEVELS = ['DIAGNOSTIC', 'ACTIVITY_LO', 'WARNING_LO', 'WARNING_HI', 'FATAL']


class ConcreteLogFrame(TtsLogFrame):
    DEFAULT_TIME_LABEL = 'scet'
    LEVELS = LEVELS
    LEVEL_COLORS = {
        'DIAGNOSTIC':  {'background-color': '#ccc'},
        'ACTIVITY_LO': {'background-color': '#aaa'},
        'WARNING_LO':  {'background-color': '#ff0'},
        'WARNING_HI':  {'background-color': '#f80'},
        'FATAL':       {'background-color': '#f00'},
    }


class ConcreteLogRowSeries(TtsLogRowSeries):
    LEVEL_COL = 'level'
    LEVEL_COLORS = ConcreteLogFrame.LEVEL_COLORS


class TestTtsLogFrameClassVars:
    def test_label_col(self):
        assert TtsLogFrame.LABEL_COL == 'name'

    def test_value_col(self):
        assert TtsLogFrame.VALUE_COL == 'message'

    def test_level_col(self):
        assert TtsLogFrame.LEVEL_COL == 'level'

    def test_levels_empty_by_default(self):
        assert TtsLogFrame.LEVELS == []

    def test_filter_cols_empty_by_default(self):
        assert TtsLogFrame.FILTER_COLS == {}

    def test_row_series_class(self):
        assert TtsLogFrame.ROW_SERIES_CLASS is TtsLogRowSeries


class TestFilterLevel:
    def setup_method(self):
        self.frame = ConcreteLogFrame(SAMPLE_ROWS)

    def test_single_level_str(self):
        result = self.frame.filter_level('FATAL')
        assert len(result) == 1
        assert result.iloc[0]['name'] == 'SAFE_MODE'

    def test_multiple_levels_list(self):
        result = self.frame.filter_level(['WARNING_LO', 'WARNING_HI'])
        assert len(result) == 2
        assert set(result['name'].tolist()) == {'CRC_FAIL'}

    def test_nonexistent_level_returns_empty(self):
        result = self.frame.filter_level('COMMAND')
        assert len(result) == 0

    def test_returns_concrete_subclass(self):
        result = self.frame.filter_level('FATAL')
        assert type(result) is ConcreteLogFrame


class TestFilterAboveLevel:
    def setup_method(self):
        self.frame = ConcreteLogFrame(SAMPLE_ROWS)

    def test_threshold_inclusive(self):
        result = self.frame.filter_above_level('WARNING_LO')
        assert set(result['level'].tolist()) == {'WARNING_LO', 'WARNING_HI', 'FATAL'}

    def test_lowest_level_returns_all(self):
        result = self.frame.filter_above_level('DIAGNOSTIC')
        assert len(result) == len(SAMPLE_ROWS)

    def test_highest_level_returns_one(self):
        result = self.frame.filter_above_level('FATAL')
        assert len(result) == 1

    def test_empty_levels_raises(self):
        frame = TtsLogFrame(SAMPLE_ROWS)
        with pytest.raises(ValueError, match="non-empty LEVELS"):
            frame.filter_above_level('FATAL')

    def test_unknown_level_raises(self):
        with pytest.raises(ValueError, match="not in"):
            self.frame.filter_above_level('MADE_UP')


class TestFilterLabel:
    def setup_method(self):
        self.frame = ConcreteLogFrame(SAMPLE_ROWS)

    def test_single_name_str(self):
        result = self.frame.filter_label('SEQ_LOAD')
        assert len(result) == 1

    def test_multiple_names_list(self):
        result = self.frame.filter_label(['SEQ_LOAD', 'SAFE_MODE'])
        assert len(result) == 2

    def test_nonexistent_name_returns_empty(self):
        result = self.frame.filter_label('NO_SUCH_EVR')
        assert len(result) == 0


class TestSearch:
    def setup_method(self):
        self.frame = ConcreteLogFrame(SAMPLE_ROWS)

    def test_literal_substring(self):
        result = self.frame.search('CRC')
        assert len(result) == 2

    def test_regex_pattern(self):
        result = self.frame.search(r'block \d+')
        assert len(result) == 2

    def test_no_match_returns_empty(self):
        result = self.frame.search('no_such_string_xyz')
        assert len(result) == 0

    def test_returns_concrete_subclass(self):
        result = self.frame.search('CRC')
        assert type(result) is ConcreteLogFrame


class TestDisabledMethods:
    def setup_method(self):
        self.frame = ConcreteLogFrame(SAMPLE_ROWS)

    def test_derive_values_raises(self):
        with pytest.raises(NotImplementedError):
            self.frame.derive_values('name + 1')

    def test_at_times_where_raises(self):
        with pytest.raises(NotImplementedError):
            self.frame.at_times_where('name > 0')

    def test_pivot_to_wide_raises(self):
        with pytest.raises(NotImplementedError):
            self.frame.pivot_to_wide()


class TestTtsLogRowSeries:
    def test_known_level_returns_color(self):
        row = ConcreteLogRowSeries({'level': 'FATAL', 'name': 'X', 'message': 'Y'})
        assert row.default_html_row_style == {'background-color': '#f00'}

    def test_unknown_level_returns_empty(self):
        row = ConcreteLogRowSeries({'level': 'MYSTERY', 'name': 'X', 'message': 'Y'})
        assert row.default_html_row_style == {}

    def test_missing_level_col_returns_empty(self):
        row = ConcreteLogRowSeries({'name': 'X', 'message': 'Y'})
        assert row.default_html_row_style == {}
