"""AMPCS Engineering Health and Alarms (EHA) as a TtsDataFrame.

This module provides the TtsDataFrame-based successor to the legacy
EhaContainer/EhaItem pattern.  Row colors reflect the worst-case alarm
state — EU alarm takes priority over DN alarm.

See Also
--------
tts_data_utils.multimission.eha : legacy DataContainer/DataItem implementation
"""

from typing import Dict

from tts_data_utils.core.data_frame import TtsDataFrame, TtsRowSeries


class AmpcsEhaRowSeries(TtsRowSeries):
    """Row ergonomics for a single EHA telemetry point.

    Colours the table row by worst-case alarm state:
    RED (EU or DN) → pink, YELLOW (EU or DN) → pale yellow, otherwise clear.
    EU alarm state takes priority over DN alarm state.
    """

    _ALARM_COLORS: Dict[str, Dict] = {
        "RED":    {"background-color": "#FFCCCC"},
        "YELLOW": {"background-color": "#FFF3CC"},
    }

    @property
    def default_html_row_style(self) -> Dict:
        """Row background based on worst-case alarm state (EU > DN)."""
        for col in ("euAlarmState", "dnAlarmState"):
            state = self.get(col, "")
            if state in self._ALARM_COLORS:
                return self._ALARM_COLORS[state]
        return {}

    @property
    def default_html_cell_styles(self) -> 'Dict[str, Dict]':
        """Bold the ``eu`` cell when it is in alarm."""
        eu_state = self.get("euAlarmState", "")
        if eu_state in ("RED", "YELLOW"):
            return {"eu": {"font-weight": "bold"}}
        return {}


class AmpcsEhaFrame(TtsDataFrame):
    """AMPCS Engineering Health and Alarms telemetry as a TtsDataFrame.

    Long-form: one row per (scet, channelId) measurement.  Each row carries
    the raw Data Number (DN), calibrated Engineering Unit (EU), alarm states,
    and provenance fields from the AMPCS ground system.

    Subclass this in your mission's data-utils repo to add mission-specific
    channel methods or override default display columns.

    Alarm coloring is provided automatically via :class:`AmpcsEhaRowSeries`.
    RED rows signal an active alarm; YELLOW rows signal a caution limit.
    """

    DEFAULT_TIME_LABEL = "scet"
    LABEL_COL = "channelId"
    VALUE_COL = "eu"
    SCHEMA = None
    SUBCONTAINER_KEY = None
    ROW_SERIES_CLASS = AmpcsEhaRowSeries
