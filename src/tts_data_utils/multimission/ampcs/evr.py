"""AMPCS Event/EVent Records (EVR) as a TtsDataFrame.

This module provides the TtsDataFrame-based successor to the legacy
EvrContainer/EvrItem pattern.  Row colors follow EVR severity levels
so operators can immediately spot FATAL and WARNING events.

See Also
--------
tts_data_utils.multimission.evr : legacy DataContainer/DataItem implementation
"""

from typing import Dict

from tts_data_utils.core.data_frame import TtsDataFrame, TtsRowSeries


class AmpcsEvrRowSeries(TtsRowSeries):
    """Row ergonomics for a single EVR event.

    Colours the table row by severity level.  Higher severity = warmer colour.
    """

    _LEVEL_COLORS: Dict[str, Dict] = {
        "FATAL":       {"background-color": "#FF9999"},
        "WARNING_HI":  {"background-color": "#FFCCCC"},
        "WARNING_LO":  {"background-color": "#FFE4CC"},
        "ACTIVITY_HI": {"background-color": "#FFFACC"},
        "ACTIVITY_LO": {"background-color": "#FFFFF0"},
        "COMMAND":     {"background-color": "#CCE5FF"},
        "DIAGNOSTIC":  {},
    }

    @property
    def default_html_row_style(self) -> Dict:
        """Row background based on EVR severity level."""
        level = self.get("level", "DIAGNOSTIC")
        return self._LEVEL_COLORS.get(level, {})

    @property
    def default_html_cell_styles(self) -> 'Dict[str, Dict]':
        """Bold the ``level`` cell for WARNING and FATAL events."""
        level = self.get("level", "DIAGNOSTIC")
        if level in ("FATAL", "WARNING_HI", "WARNING_LO"):
            return {"level": {"font-weight": "bold"}}
        return {}


class AmpcsEvrFrame(TtsDataFrame):
    """AMPCS Event/EVent Records as a TtsDataFrame.

    Long-form: one row per discrete spacecraft event.  Each row carries the
    severity ``level``, human-readable ``message``, originating ``module``,
    and high-fidelity timestamps (SCET, ERT) from the AMPCS ground system.

    Subclass this in your mission's data-utils repo to add mission-specific
    event filtering methods or override default display columns.

    Severity coloring is provided automatically via :class:`AmpcsEvrRowSeries`.
    FATAL rows are deep red; WARNING rows are pink/orange; informational rows
    are cool-toned or uncolored.
    """

    DEFAULT_TIME_LABEL = "scet"
    LABEL_COL = "name"
    VALUE_COL = "message"
    SCHEMA = None
    SUBCONTAINER_KEY = None
    ROW_SERIES_CLASS = AmpcsEvrRowSeries

    LEVELS = [
        "DIAGNOSTIC",
        "COMMAND",
        "ACTIVITY_LO",
        "ACTIVITY_HI",
        "WARNING_LO",
        "WARNING_HI",
        "FATAL",
    ]
