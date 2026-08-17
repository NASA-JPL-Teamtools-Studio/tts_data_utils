"""General-purpose log data frame and row series for tts_data_utils.

TtsLogFrame is the base class for any tabular log data -- EVRs, FSW logs,
ground system messages, or any other record-per-event data source.  It
establishes the long-form contract (LABEL_COL / VALUE_COL / LEVEL_COL) and
provides common filtering helpers that work across ground systems.

Missions subclass both TtsLogFrame and TtsLogRowSeries to add ground-system-
specific schema, level vocabularies, and row-coloring logic.

See Also
--------
tts_data_utils.multimission.ampcs.evr : AMPCS-specific EVR frame
"""

from typing import Dict, List, Union

from tts_data_utils.core.data_frame import TtsDataFrame, TtsRowSeries


class TtsLogRowSeries(TtsRowSeries):
    """Row ergonomics for a single log event.

    Class variables mirror the parent frame so that default_html_row_style
    can color rows by severity without needing a reference back to the frame.
    Mission subclasses override LEVEL_COL and LEVEL_COLORS to match their
    log data schema.
    """

    LEVEL_COL = 'level'
    LEVEL_COLORS = {}

    @property
    def default_html_row_style(self) -> Dict:
        """Row style keyed by severity level.

        Returns an empty dict for unknown levels so unknown severities render
        with the default table style rather than raising.
        """
        level = self.get(self.LEVEL_COL)
        return self.LEVEL_COLORS.get(level, {})


class TtsLogFrame(TtsDataFrame):
    """Base DataFrame for any log-like tabular data.

    Long-form: one row per discrete log event.  LABEL_COL identifies the log
    source (e.g. EVR mnemonic); VALUE_COL carries the human-readable message
    text; LEVEL_COL names the severity column.

    LEVELS is an ordered list (low to high) that drives filter_above_level().
    Leave LEVELS empty for log sources with no severity concept.

    FILTER_COLS declares which columns the query layer should expose as filter
    kwargs, and what values are valid for each.  A None value means free-form
    string filtering; a list means an enumerated set.

    Operations that assume numeric value semantics (derive_values,
    at_times_where, pivot_to_wide) are disabled and raise NotImplementedError.
    """

    DEFAULT_TIME_LABEL = None
    LABEL_COL = 'name'
    VALUE_COL = 'message'
    LEVEL_COL = 'level'
    LEVELS = []
    LEVEL_COLORS = {}
    FILTER_COLS = {}
    SCHEMA = []
    ROW_SERIES_CLASS = TtsLogRowSeries

    def filter_level(self, levels):
        """Return rows where LEVEL_COL is in *levels*.

        Parameters
        ----------
        levels : str or list of str
            One or more severity level strings to include.
        """
        if isinstance(levels, str):
            levels = [levels]
        return self[self[self.LEVEL_COL].isin(levels)]

    def filter_above_level(self, level):
        """Return rows at or above *level* in the LEVELS ordering.

        Parameters
        ----------
        level : str
            Minimum severity level (inclusive).  All rows whose level appears
            at this index or later in LEVELS are returned.

        Raises
        ------
        ValueError
            If LEVELS is empty or *level* is not found in LEVELS.
        """
        if not self.LEVELS:
            raise ValueError(
                "filter_above_level requires a non-empty LEVELS list on "
                f"{type(self).__name__}."
            )
        try:
            threshold = self.LEVELS.index(level)
        except ValueError:
            raise ValueError(
                f"{level!r} is not in {type(self).__name__}.LEVELS: "
                f"{self.LEVELS}"
            )
        return self.filter_level(self.LEVELS[threshold:])

    def filter_label(self, names):
        """Return rows where LABEL_COL is in *names*.

        Parameters
        ----------
        names : str or list of str
            One or more label values to include.
        """
        if isinstance(names, str):
            names = [names]
        return self[self[self.LABEL_COL].isin(names)]

    def search(self, pattern):
        """Return rows where VALUE_COL contains *pattern* (regex).

        Parameters
        ----------
        pattern : str
            Regular expression to match against VALUE_COL.
        """
        return self[self[self.VALUE_COL].str.contains(pattern, regex=True, na=False)]

    def derive_values(self, *args, **kwargs):
        raise NotImplementedError(
            "TtsLogFrame does not support derive_values. "
            "Log frames carry text messages, not numeric channel values."
        )

    def at_times_where(self, *args, **kwargs):
        raise NotImplementedError(
            "TtsLogFrame does not support at_times_where. "
            "Log frames carry text messages, not numeric channel values."
        )

    def pivot_to_wide(self, *args, **kwargs):
        raise NotImplementedError(
            "TtsLogFrame does not support pivot_to_wide. "
            "Log frames carry text messages, not numeric channel values."
        )
