#Standard Library Imports
from datetime import datetime, timedelta

#Installed Library Imports
import numpy as np
import pandas as pd
import pytest

#This Library Imports
from tts_data_utils.core.data_frame import TtsDataFrame, _FilterExprError, _MathExprError
from tts_dexter.core.data import DISPO_CHOICE
from tts_dexter.core.dispo import DISPO_FORMAT

class MockFrame(TtsDataFrame):
    DEFAULT_TIME_LABEL = "time"
    LABEL_COL = "label"
    VALUE_COL = "value"
    LABEL_COLUMN = "label"

    SCHEMA = [
        ("time", datetime),
        ("label", str),
        ("value", (int, float, type(None))),
        ("meta", dict),
    ]

    TIME_FORMATS = {"time": "%Y-%m-%d %H:%M:%S"}


@pytest.fixture
def simple_frame():
    times = [datetime(2020, 1, 1) + timedelta(seconds=i) for i in range(5)]
    data = [
        {"time": times[0], "label": "a", "value": 1.0, "meta": {"k": 1}},
        {"time": times[1], "label": "a", "value": 3.0, "meta": {"k": 2}},
        {"time": times[2], "label": "a", "value": 5.0, "meta": {"k": 3}},
        {"time": times[3], "label": "b", "value": 10.0, "meta": {"k": 4}},
        {"time": times[4], "label": "b", "value": 20.0, "meta": {"k": 5}},
    ]
    return MockFrame(data, coerce=False, validate=False)


class MockNameColumnFrame(TtsDataFrame):
    """Frame whose LABEL_COL is literally 'name', matching real-world
    chanvals-style frames (name/value/scet)."""

    DEFAULT_TIME_LABEL = "scet"
    LABEL_COL = "name"
    VALUE_COL = "value"
    LABEL_COLUMN = "name"


@pytest.mark.unreviewed_ai_generated_test
class TestContainerNameColumnCollision:
    """Regression test: selecting a column literally called 'name' must
    not clobber the resulting Series' reserved .name with the
    DataFrame's container-level .name metadata attribute, and must not
    raise even when the container name is unhashable."""

    def test_select_name_column_with_unhashable_container_name(self):
        data = [
            {"scet": datetime(2020, 1, 1), "value": 1, "name": "chan_a"},
            {"scet": datetime(2020, 1, 1), "value": 2, "name": "chan_b"},
        ]
        df = MockNameColumnFrame(data, name=["not", "hashable"], coerce=False, validate=False)

        # Should not raise TypeError: Series.name must be a hashable type
        column = df["name"]

        assert list(column) == ["chan_a", "chan_b"]
        # The Series' own .name should reflect the column label, not the
        # container's metadata name.
        assert column.name == "name"
        # The container-level name metadata should be preserved on df.
        assert df.name == ["not", "hashable"]


@pytest.mark.unreviewed_ai_generated_test
class TestSchema:
    def test_cast_and_validate(self):
        raw = [
            {"time": "2020-01-01 00:00:00", "label": "a", "value": "1", "meta": "{'k': 1}"},
            {"time": "2020-01-01 00:00:01", "label": "b", "value": "2", "meta": "{'k': 2}"},
        ]
        df = MockFrame(raw, coerce=True, validate=True)

        assert isinstance(df.loc[0, "time"], datetime)
        # Allow numpy integer types as well as built-in ints/floats
        assert isinstance(df.loc[0, "value"], (int, float, np.integer))
        assert isinstance(df.loc[0, "meta"], dict)
        assert df.valid

    def test_validate_rejects_bad_type(self):
        raw = [
            {"time": "2020-01-01 00:00:00", "label": "a", "value": "not_num", "meta": "{'k': 1}"},
        ]
        with pytest.raises(Exception) as excinfo:
            MockFrame(raw, coerce=True, validate=True)
        msg = str(excinfo.value)
        assert "Column 'value'" in msg
        assert "invalid type for schema" in msg

    def test_valid_property_flags_invalid_values(self):
        raw = [
            {"time": "2020-01-01 00:00:00", "label": "a", "value": "not_num", "meta": "{'k': 1}"},
        ]
        df = MockFrame(raw, coerce=True, validate=False)
        assert not df.valid


@pytest.mark.unreviewed_ai_generated_test
class TestWide:
    def test_wide_from_long(self, simple_frame):
        wide = simple_frame.select_wide()
        assert list(wide.columns) == ["a", "b"]

        times = list(simple_frame[MockFrame.DEFAULT_TIME_LABEL].unique())
        assert list(wide.index) == times
        assert len(wide) == len(times)
        assert wide.loc[times[0], "a"] == 1.0
        assert wide.loc[times[1], "a"] == 3.0
        assert wide.loc[times[2], "a"] == 5.0
        assert pd.isna(wide.loc[times[3], "a"])
        assert pd.isna(wide.loc[times[4], "a"])
        assert pd.isna(wide.loc[times[0], "b"])
        assert pd.isna(wide.loc[times[1], "b"])
        assert pd.isna(wide.loc[times[2], "b"])
        assert wide.loc[times[3], "b"] == 10.0
        assert wide.loc[times[4], "b"] == 20.0


@pytest.mark.unreviewed_ai_generated_test
class TestMovingAndBlockAverage:
    def test_moving_average_single_label(self, simple_frame):
        df = simple_frame[simple_frame["label"] == "a"].copy()
        result = df.moving_average(window_seconds=2, time_col="time", value_col="value")

        assert isinstance(result, MockFrame)
        assert result["time"].tolist() == df["time"].tolist()
        assert result["value"].tolist() == [1.0, 2.0, 4.0]

    def test_block_average_two_labels(self, simple_frame):
        result = simple_frame.block_average(block_size=2, time_col="time", label_col="label", value_col="value")

        assert isinstance(result, MockFrame)
        # One row per block across both labels: 2 blocks of 'a' and 1 block of 'b'
        assert len(result) == 3

        # Expected block means: for label 'a', blocks [1,3] -> 2, [5] -> 5; for 'b', [10,20] -> 15
        assert result["value"].tolist() == [2.0, 5.0, 15.0]
        times = simple_frame["time"]
        expected_times = [times.iloc[0], times.iloc[2], times.iloc[3]]
        assert result["time"].tolist() == expected_times


@pytest.mark.unreviewed_ai_generated_test
class TestFilterExpr:
    def test_filter_expr_success(self, simple_frame):
        df = simple_frame.filter_expr("value > 2 and label == 'a'")
        assert set(df["label"]) == {"a"}
        assert (df["value"] > 2).all()
        assert len(df) == 2

        expected_times = [
            simple_frame["time"].iloc[1],
            simple_frame["time"].iloc[2],
        ]
        assert df["time"].tolist() == expected_times

    def test_filter_expr_bad_column(self, simple_frame):
        with pytest.raises(_FilterExprError):
            simple_frame.filter_expr("does_not_exist > 0")

    def test_filter_expr_in_not_in(self, simple_frame):
        df_in = simple_frame.filter_expr("label in ['a']")
        assert set(df_in["label"]) == {"a"}

        df_not_in = simple_frame.filter_expr("label not in ['a']")
        assert set(df_not_in["label"]) == {"b"}

        # Combined boolean logic with membership
        df_combined = simple_frame.filter_expr("(label in ['a'] and value > 2) or label in ['b']")
        assert set(df_combined["label"]) == {"a", "b"}


@pytest.mark.unreviewed_ai_generated_test
class TestAtTimesWhere:
    def test_at_times_where_basic(self, simple_frame):
        df = simple_frame.at_times_where("a > 1")
        assert set(df["label"]) == {"a"}
        assert (df["value"] > 1).all()
        assert len(df) == 2

        expected_times = [
            simple_frame["time"].iloc[1],
            simple_frame["time"].iloc[2],
        ]
        assert df["time"].tolist() == expected_times

    def test_at_times_where_with_tolerance_includes_nearby_rows(self, simple_frame):
        df = simple_frame.at_times_where("a > 1", tolerance=1)

        expected_times = [simple_frame["time"].iloc[i] for i in range(4)]
        expected_labels = ["a", "a", "a", "b"]

        assert df["time"].tolist() == expected_times
        assert df["label"].tolist() == expected_labels

    def test_at_times_where_missing_label(self, simple_frame):
        with pytest.raises(_FilterExprError):
            simple_frame.at_times_where("missing_label > 0")

    def test_at_times_where_in_list(self, simple_frame):
        # Use membership on label-based expressions; here just a simple value list
        df = simple_frame.at_times_where("a in [3, 5]")
        assert set(df["label"]) == {"a"}
        assert set(df["value"]) == {3.0, 5.0}


@pytest.mark.unreviewed_ai_generated_test
class TestDeriveValues:
    def test_derive_values_timeout_zero(self):
        # Build a frame where labels 'a' and 'b' share timestamps so the
        # timeout=0 path can find common times without interpolation.
        times = [datetime(2020, 1, 1) + timedelta(seconds=i) for i in range(3)]
        data = []
        for i, t in enumerate(times):
            data.append({"time": t, "label": "a", "value": float(i + 1), "meta": {"k": 1}})
            data.append({"time": t, "label": "b", "value": float((i + 1) * 2), "meta": {"k": 2}})

        frame = MockFrame(data, coerce=False, validate=False)
        expr = "derived = a + b"
        df = frame.derive_values(expr, index_col="time", label_col="label", value_col="value", timeout=0)

        assert set(df["label"]) == {"derived"}
        # One row per common timestamp
        assert {t for t in df["time"]} == set(times)
        # Values should be the sum of a and b at each time
        expected = [float(i + 1) + float((i + 1) * 2) for i in range(3)]
        assert df["value"].tolist() == expected

    def test_derive_values_bad_label(self, simple_frame):
        with pytest.raises(_MathExprError):
            simple_frame.derive_values("derived = missing + 1", index_col="time", label_col="label", value_col="value")

    def test_derive_values_in_operator(self, simple_frame):
        # Build a frame with matching timestamps for labels 'a' and 'b'
        times = [datetime(2020, 1, 1) + timedelta(seconds=i) for i in range(3)]
        data = []
        for i, t in enumerate(times):
            data.append({"time": t, "label": "a", "value": float(i + 1), "meta": {"k": 1}})
            data.append({"time": t, "label": "b", "value": float((i + 1) * 2), "meta": {"k": 2}})

        frame = MockFrame(data, coerce=False, validate=False)
        expr = "derived = a in [1, 3] and b > 2"
        df = frame.derive_values(expr, index_col="time", label_col="label", value_col="value", timeout=0)

        assert set(df["label"]) == {"derived"}
        # a values: [1,2,3], b values: [2,4,6]
        # derived is True only at t2 where a=3 and b>2
        results = df.sort_values("time")["value"].tolist()
        assert results == [False, False, True]


@pytest.mark.unreviewed_ai_generated_test
class TestHelpers:
    def test_eq_tolerance(self, simple_frame):
        df = simple_frame.eq("value", 10, tolerance=0.5)
        assert all(abs(v - 10) <= 0.5 for v in df["value"])
        assert len(df) == 1

        row = df.iloc[0]
        assert row["label"] == "b"
        assert row["time"] == simple_frame["time"].iloc[3]

    def test_count_constraints(self, simple_frame):
        with pytest.raises(ValueError) as excinfo_exact:
            simple_frame.eq("label", "a", exactly=1)
        assert "Expected exactly 1 rows" in str(excinfo_exact.value)

        with pytest.raises(ValueError) as excinfo_min:
            simple_frame.eq("label", "a", minimum=10)
        assert "Expected at least 10 rows" in str(excinfo_min.value)

        with pytest.raises(ValueError) as excinfo_max:
            simple_frame.eq("label", "a", maximum=1)
        assert "Expected at most 1 rows" in str(excinfo_max.value)

    def test_count_constraints_pass_when_in_range(self, simple_frame):
        df_exact = simple_frame.eq("label", "a", exactly=3)
        assert len(df_exact) == 3
        assert set(df_exact["label"]) == {"a"}

        df_min_max = simple_frame.eq("label", "a", minimum=1, maximum=3)
        assert len(df_min_max) == 3
        assert set(df_min_max["label"]) == {"a"}


@pytest.mark.unreviewed_ai_generated_test
class TestInspectExprLanguage:
    def test_inspect_expr_language_structure(self, simple_frame):
        info = simple_frame.inspect_expr_language()

        assert "math_engine" in info
        assert "math_transformer" in info
        assert "math_functions" in info
        assert "math_keywords" in info
        assert "filter_engine" in info
        assert "filter_keywords" in info

        math_funcs = info["math_functions"]
        assert "abs" in math_funcs

        math_bool = info["math_keywords"]["boolean"]
        assert {"and", "or", "not"}.issubset(math_bool)

        math_cmp = info["math_keywords"]["comparison"]
        assert {">", ">=", "<", "<=", "==", "!=", "in"}.issubset(math_cmp)

        filter_bool = info["filter_keywords"]["boolean"]
        assert {"and", "or", "not"}.issubset(filter_bool)

        filter_cmp = info["filter_keywords"]["comparison"]
        assert {">", ">=", "<", "<=", "==", "!=", "is", "is not", "in", "not in"}.issubset(filter_cmp)


@pytest.mark.unreviewed_ai_generated_test
class TestLad:
    def test_lad_last_per_label(self, simple_frame):
        simple_frame.DEFAULT_TIME_LABEL = "time"
        simple_frame.LABEL_COL = "label"
        lad = simple_frame.lad()

        assert set(lad["label"]) == {"a", "b"}
        for lbl in ["a", "b"]:
            src = simple_frame[simple_frame["label"] == lbl]
            last_time = src["time"].max()
            lad_time = lad[lad["label"] == lbl]["time"].iloc[0]
            assert lad_time == last_time

    def test_lad_value_latest_row_for_label(self, simple_frame):
        simple_frame.DEFAULT_TIME_LABEL = "time"
        simple_frame.LABEL_COL = "label"

        row = simple_frame.lad(value="a")
        src = simple_frame[simple_frame["label"] == "a"]
        last_time = src["time"].max()

        assert row["label"] == "a"
        assert row["time"] == last_time

    def test_lad_value_returns_scalar(self, simple_frame):
        simple_frame.DEFAULT_TIME_LABEL = "time"
        simple_frame.LABEL_COL = "label"
        simple_frame.VALUE_COL = "value"

        # latest row for label "a" should have the max time and its value
        src = simple_frame[simple_frame["label"] == "a"]
        latest = src.loc[src["time"].idxmax()]

        val = simple_frame.lad_value("a")

        # Should be a bare scalar, matching the underlying value column
        assert val == latest["value"]

@pytest.mark.unreviewed_ai_generated_test
class TestDexterRowBehavior:
    def test_row_dispositions_and_stamp(self, simple_frame):
        df = simple_frame.copy()
        # Take a row via loc (ensures _frame is attached)
        row = df.loc[df.index[0]]
        # Create dispositions and stamp
        dispo = row.new_dispo()
        dispo.expected("OK")
        row.choose_and_stamp(DISPO_CHOICE.ALL, DISPO_FORMAT.HTML)

        # Disposition column should now exist and have a non-empty value
        assert "disposition" in df.columns
        assert df.loc[df.index[0], "disposition"]

        # Frame-level store should know about this row
        dispos = df.get_row_dispositions(df.index[0])
        assert len(dispos) == 1

    def test_row_dispositions_pruned_on_filter(self, simple_frame):
        df = simple_frame.copy()
        # Add a disposition on first row
        idx0 = df.index[0]
        row0 = df.loc[idx0]
        row0.new_dispo().expected("OK")
        row0.choose_and_stamp(DISPO_CHOICE.ALL, DISPO_FORMAT.HTML)

        # Filter to drop the first row
        df2 = df[df["label"] == "b"].copy()

        # First index should no longer be present
        assert idx0 not in df2.index
        # And its dispositions should be pruned
        all_dispos = df2.get_row_dispositions()
        assert idx0 not in all_dispos