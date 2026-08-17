"""AMPCS Event/EVent Records (EVR) as a TtsDataFrame.

This module provides the TtsDataFrame-based successor to the legacy
EvrContainer/EvrItem pattern.  Row colors follow EVR severity levels
so operators can immediately spot FATAL and WARNING events.

See Also
--------
tts_data_utils.multimission.evr : legacy DataContainer/DataItem implementation
tts_data_utils.core.log : TtsLogFrame base class
"""

import json
from typing import Dict

import pandas as pd
from tts_html_utils.core.palette import EvrPalette
from tts_data_utils.core.log import TtsLogFrame, TtsLogRowSeries


class AmpcsEvrRowSeries(TtsLogRowSeries):
    """Row ergonomics for a single EVR event.

    Delegates row colouring to :data:`EvrPalette` — the canonical source of
    EVR level colours shared with the legacy EvrItem/EvrContainer path.
    """

    LEVEL_COL = 'level'

    @property
    def default_html_row_style(self) -> Dict:
        """Row style sourced from EvrPalette, keyed by EVR severity level."""
        level = self.get("level", "DIAGNOSTIC")
        try:
            return EvrPalette[level]
        except KeyError:
            return {}

    @property
    def default_html_cell_styles(self) -> 'Dict[str, Dict]':
        """Bold the ``level`` cell for WARNING and FATAL events."""
        level = self.get("level", "DIAGNOSTIC")
        if level in ("FATAL", "WARNING_HI", "WARNING_LO"):
            return {"level": {"font-weight": "bold"}}
        return {}


class AmpcsEvrFrame(TtsLogFrame):
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
    LEVEL_COL = "level"
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

    FILTER_COLS = {
        'level': LEVELS,
        'module': None,
        'name': None,
    }

    def gaps(self):
        """Analyze per-level sequence IDs to find missing data segments.

        Each EVR row is expected to carry a ``metadata`` column that is either
        a dict or a Python dict literal string containing a
        ``CategorySequenceId`` key.  Gaps are identified per severity level:
        if the integer IDs are not contiguous the missing range is reported.

        Returns
        -------
        pd.DataFrame
            One row per detected gap with columns:
            ``level``, ``scet_before``, ``scet_after``,
            ``ert_before``, ``ert_after``,
            ``first_missing_index``, ``last_missing_index``,
            ``total_missing``.
        """

        def _parse_seq(meta):
            if isinstance(meta, dict):
                return int(meta['CategorySequenceId'])
            return int(json.loads(meta)['CategorySequenceId'])

        gap_rows = []
        for level in self.LEVELS:
            level_df = self.filter_level(level).copy()
            if len(level_df) == 0:
                continue

            level_df['_seq_id'] = level_df['metadata'].apply(_parse_seq)
            level_df = level_df.sort_values('_seq_id')
            seq_ids = level_df['_seq_id'].tolist()

            expected = set(range(seq_ids[0], seq_ids[-1] + 1))
            missing = sorted(expected - set(seq_ids))
            if not missing:
                continue

            missing_set = set(missing)
            befores = [s - 1 for s in missing if s - 1 not in missing_set]
            afters  = [s + 1 for s in missing if s + 1 not in missing_set]

            seq_index = level_df.set_index('_seq_id')
            for b, a in zip(befores, afters):
                preceding  = seq_index.loc[b]
                succeeding = seq_index.loc[a]
                gap_rows.append({
                    'level':               level,
                    'scet_before':         preceding.get('scet'),
                    'scet_after':          succeeding.get('scet'),
                    'ert_before':          preceding.get('ert'),
                    'ert_after':           succeeding.get('ert'),
                    'first_missing_index': b + 1,
                    'last_missing_index':  a - 1,
                    'total_missing':       a - b - 1,
                })

        return pd.DataFrame(gap_rows)
