from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tts_html_utils.core.components.table import PowerTable
from tts_data_utils.core.data_frame import TtsDataFrame, TtsRowSeries
from tts_data_utils.test.core.inspection_utils import check_inspection_hash


class SimpleFrame(TtsDataFrame):
    """Plain frame with no custom styling — tests the graceful-default path."""
    DEFAULT_TIME_LABEL = "time"
    LABEL_COL = "label"
    VALUE_COL = "value"
    SCHEMA = None


class HighValueRowSeries(TtsRowSeries):
    @property
    def default_html_row_style(self):
        if self.get("value", 0) > 5:
            return {"background-color": "red"}
        return {}

    @property
    def default_html_cell_styles(self):
        return {"value": {"font-weight": "bold"}}


class StyledFrame(TtsDataFrame):
    """Frame whose rows carry custom row- and cell-level styling."""
    DEFAULT_TIME_LABEL = "time"
    LABEL_COL = "label"
    VALUE_COL = "value"
    SCHEMA = None
    ROW_SERIES_CLASS = HighValueRowSeries


class SubcontainerFrame(TtsDataFrame):
    """Frame with SUBCONTAINER_KEY set so expand-rows can be tested."""
    DEFAULT_TIME_LABEL = "time"
    LABEL_COL = "label"
    VALUE_COL = "value"
    SCHEMA = None
    SUBCONTAINER_KEY = "label"


_TIMES = [datetime(2020, 1, 1) + timedelta(seconds=i) for i in range(3)]
_DATA = [
    {"time": _TIMES[0], "label": "a", "value": 1.0},
    {"time": _TIMES[1], "label": "b", "value": 10.0},
    {"time": _TIMES[2], "label": "c", "value": 3.0},
]


@pytest.fixture
def simple_frame():
    return SimpleFrame(_DATA, coerce=False, validate=False)


@pytest.fixture
def styled_frame():
    return StyledFrame(_DATA, coerce=False, validate=False)


@pytest.fixture
def sub_frame():
    frame = SubcontainerFrame(_DATA, coerce=False, validate=False)
    sub_data = [{"time": _TIMES[0], "label": "x", "value": 99.0}]
    nested = SimpleFrame(sub_data, coerce=False, validate=False)
    frame.set_subcontainer("b", "detail", nested)
    return frame


@pytest.mark.unreviewed_ai_generated_test
class TestReprHtml:
    def test_returns_string(self, simple_frame):
        html = simple_frame._repr_html_()
        assert isinstance(html, str)
        assert len(html) > 0

    def test_contains_table_tag(self, simple_frame):
        html = simple_frame._repr_html_()
        assert "<table" in html

    def test_contains_data_values(self, simple_frame):
        html = simple_frame._repr_html_()
        assert "10.0" in html

    def test_not_plain_pandas_html(self, simple_frame):
        import pandas as pd
        pandas_html = pd.DataFrame.to_html(simple_frame)
        power_html = simple_frame._repr_html_()
        assert power_html != pandas_html


@pytest.mark.unreviewed_ai_generated_test
class TestRowSeriesDefaultStyles:
    def test_default_row_style_is_empty_dict(self, simple_frame):
        for _, row in simple_frame.iterrows():
            assert row.default_html_row_style == {}

    def test_default_cell_styles_is_empty_dict(self, simple_frame):
        for _, row in simple_frame.iterrows():
            assert row.default_html_cell_styles == {}


@pytest.mark.unreviewed_ai_generated_test
class TestCustomRowStyling:
    def test_high_value_rows_get_red_background(self, styled_frame):
        for _, row in styled_frame.iterrows():
            style = row.default_html_row_style
            if row["value"] > 5:
                assert style.get("background-color") == "red"
            else:
                assert "background-color" not in style

    def test_custom_row_style_appears_in_rendered_html(self, styled_frame):
        html = styled_frame._repr_html_()
        assert "red" in html

    def test_custom_cell_styles_applied(self, styled_frame):
        for _, row in styled_frame.iterrows():
            styles = row.default_html_cell_styles
            assert styles.get("value") == {"font-weight": "bold"}

    def test_custom_cell_style_appears_in_rendered_html(self, styled_frame):
        html = styled_frame._repr_html_()
        assert "font-weight" in html


@pytest.mark.unreviewed_ai_generated_test
class TestPowerTableMethod:
    def test_returns_power_table_instance(self, simple_frame):
        pt = simple_frame.power_table()
        assert isinstance(pt, PowerTable)

    def test_default_columns_are_all_frame_columns(self, simple_frame):
        pt = simple_frame.power_table()
        assert set(pt.col_fields) == set(simple_frame.columns)

    def test_custom_columns_subset(self, simple_frame):
        pt = simple_frame.power_table(columns=["label", "value"])
        assert pt.col_fields == ["label", "value"]

    def test_superheader_appears_in_render(self, simple_frame):
        pt = simple_frame.power_table(superheader="My Table Title")
        html = pt.render()
        assert "My Table Title" in html

    def test_bypass_styles_produces_valid_html(self, styled_frame):
        html = styled_frame.power_table(bypass_styles=True).render()
        assert "<table" in html
        assert "red" not in html

    def test_alternating_row_style_applied_when_no_custom_style(self, simple_frame):
        pt = simple_frame.power_table()
        html = pt.render()
        assert "#EEEEEE" in html

    def test_row_count_matches_frame_length(self, simple_frame):
        pt = simple_frame.power_table()
        assert len(pt.children) == len(simple_frame)

    def test_custom_row_styles_override(self, simple_frame):
        custom = [{"background-color": "blue"}] * len(simple_frame)
        html = simple_frame.power_table(row_styles=custom).render()
        assert "blue" in html

    def test_custom_row_styles_wrong_length_raises(self, simple_frame):
        with pytest.raises(ValueError):
            simple_frame.power_table(row_styles=[{}])

    def test_no_styling_subclass_renders_without_error(self, simple_frame):
        html = simple_frame.power_table().render()
        assert isinstance(html, str)


@pytest.mark.unreviewed_ai_generated_test
class TestSubcontainerExpansion:
    def test_nested_frame_data_in_html(self, sub_frame):
        html = sub_frame._repr_html_()
        assert "99.0" in html

    def test_row_without_subcontainer_has_no_expansion(self, sub_frame):
        html = sub_frame._repr_html_()
        assert isinstance(html, str)

    def test_empty_subcontainers_renders_cleanly(self, simple_frame):
        html = simple_frame._repr_html_()
        assert isinstance(html, str)


_ARTIFACT_PATH = Path(__file__).parent / "test_files" / "power_table_inspection.html"

_RICH_TIMES = [datetime(2026, 1, 1, 12, 0, 0) + timedelta(minutes=i * 5) for i in range(8)]
_RICH_DATA = [
    {"time": _RICH_TIMES[0], "label": "battery_voltage", "value": 28.4, "unit": "V", "status": "nominal"},
    {"time": _RICH_TIMES[1], "label": "battery_voltage", "value": 27.9, "unit": "V", "status": "nominal"},
    {"time": _RICH_TIMES[2], "label": "battery_voltage", "value": 24.1, "unit": "V", "status": "caution"},
    {"time": _RICH_TIMES[3], "label": "battery_voltage", "value": 19.8, "unit": "V", "status": "critical"},
    {"time": _RICH_TIMES[4], "label": "solar_current",   "value": 3.21, "unit": "A", "status": "nominal"},
    {"time": _RICH_TIMES[5], "label": "solar_current",   "value": 3.18, "unit": "A", "status": "nominal"},
    {"time": _RICH_TIMES[6], "label": "cpu_temp",        "value": 42.5, "unit": "C", "status": "nominal"},
    {"time": _RICH_TIMES[7], "label": "cpu_temp",        "value": 71.3, "unit": "C", "status": "caution"},
]

_TELEMETRY_DETAIL = [
    {"time": _RICH_TIMES[0], "label": "raw_dn", "value": 4095, "unit": "DN"},
    {"time": _RICH_TIMES[1], "label": "raw_dn", "value": 4020, "unit": "DN"},
    {"time": _RICH_TIMES[2], "label": "raw_dn", "value": 3498, "unit": "DN"},
    {"time": _RICH_TIMES[3], "label": "raw_dn", "value": 2873, "unit": "DN"},
]


class TelemetryRowSeries(TtsRowSeries):
    _STATUS_COLORS = {
        "critical": {"background-color": "#FFCCCC"},
        "caution":  {"background-color": "#FFF3CC"},
        "nominal":  {},
    }

    @property
    def default_html_row_style(self):
        return self._STATUS_COLORS.get(self.get("status", "nominal"), {})

    @property
    def default_html_cell_styles(self):
        status = self.get("status", "nominal")
        value_style = {"font-weight": "bold"} if status != "nominal" else {}
        return {"value": value_style, "status": {"font-style": "italic"}}


class TelemetryFrame(TtsDataFrame):
    DEFAULT_TIME_LABEL = "time"
    LABEL_COL = "label"
    VALUE_COL = "value"
    SCHEMA = None
    SUBCONTAINER_KEY = "label"
    ROW_SERIES_CLASS = TelemetryRowSeries


@pytest.mark.human_review
@pytest.mark.unreviewed_ai_generated_test
class TestHumanInspectable:
    """Writes a full HtmlCompiler artifact for human visual inspection.

    Open the file printed to stdout after running this test to verify:
    - Row coloring (red=critical, yellow=caution, white=nominal)
    - Bold values on non-nominal rows
    - Italic status column
    - Sortable columns (click column headers)
    - Filterable columns (filter boxes below headers)
    - Expandable sub-table row for battery_voltage showing raw DN values
    - Alternating shading on the nested sub-table
    """

    def test_write_inspection_html(self):
        from tts_html_utils.core.compiler import HtmlCompiler

        _ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)

        frame = TelemetryFrame(_RICH_DATA, coerce=False, validate=False)

        detail_frame = SimpleFrame(_TELEMETRY_DETAIL, coerce=False, validate=False)
        frame.set_subcontainer("battery_voltage", "raw DN readings", detail_frame)

        styled_table = frame.power_table(
            superheader="Telemetry LAD — 2026-01-01T12:00 to 12:35 UTC",
            add_sorting="local",
            add_filters="local",
        )

        compiler = HtmlCompiler("PowerTable Inspection: TtsDataFrame → PowerTable (ticket #12)")
        compiler.add_body_component(styled_table)
        compiler.render_to_file(_ARTIFACT_PATH)

        print(f"\n\n  Human-inspectable output → open in browser:\n  {_ARTIFACT_PATH.resolve()}\n")

        assert _ARTIFACT_PATH.exists()
        assert _ARTIFACT_PATH.stat().st_size > 0
        content = _ARTIFACT_PATH.read_text()
        assert "battery_voltage" in content
        assert "FFCCCC" in content
        assert "raw DN readings" in content

        check_inspection_hash(_ARTIFACT_PATH)
