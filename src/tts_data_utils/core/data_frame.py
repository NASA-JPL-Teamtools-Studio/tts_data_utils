import time
import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Optional, Dict, List
from tts_dante.interpolators.interpolators import StepInterpolator, LinearInterpolator
from tts_data_utils.core.expr_engines import (
    _FilterExprError, _filter_engine,
    _MathExprError, _math_engine, _MathTransformer,
)
from tts_utilities.logger import create_logger

try:
    from tts_dexter.core.row_mixin import DexterRowMixin
    DEXTER_PRESENT = True
except ModuleNotFoundError:
    DexterRowMixin = object
    DEXTER_PRESENT = False

logger = create_logger('tts_data_frame')

class _TimerProxy:
    """Proxy returned by :meth:`TtsDataFrame.timer` that prints wall-clock
    duration for any method call made on it."""

    def __init__(self, df):
        object.__setattr__(self, '_df', df)

    def __getattr__(self, name):
        df = object.__getattribute__(self, '_df')
        if isinstance(getattr(type(df), name, None), property):
            t0 = time.perf_counter()
            result = getattr(df, name)
            print(f"{name}: {time.perf_counter() - t0:.4f}s")
            return result
        attr = getattr(df, name)
        if callable(attr):
            def _timed(*args, **kwargs):
                t0 = time.perf_counter()
                result = attr(*args, **kwargs)
                print(f"{name}: {time.perf_counter() - t0:.4f}s")
                return result
            return _timed
        return attr
if DEXTER_PRESENT:
    class TtsRowSeries(DexterRowMixin, pd.Series):
        DICT_STAMP_KEY = 'disposition'

        @property
        def dispositions(self):
            frame = getattr(self, '_frame', None)
            if frame is not None:
                store = getattr(frame, '_row_dispositions', None)
                if store is None:
                    store = {}
                    frame._row_dispositions = store
                key = self.name
                if key not in store:
                    store[key] = []
                return store[key]
            if not hasattr(self, '_dispositions'):
                self._dispositions = []
            return self._dispositions

        @dispositions.setter
        def dispositions(self, value):
            frame = getattr(self, '_frame', None)
            if frame is not None:
                store = getattr(frame, '_row_dispositions', None)
                if store is None:
                    store = {}
                    frame._row_dispositions = store
                store[self.name] = list(value)
            else:
                self._dispositions = list(value)

        def stamp(self, dispo_value):
            frame = getattr(self, '_frame', None)
            if frame is not None:
                col = self.DICT_STAMP_KEY
                if col not in frame.columns:
                    frame[col] = None
                frame.loc[self.name, col] = dispo_value
            else:
                col = self.DICT_STAMP_KEY
                self[col] = dispo_value
else:
    class TtsRowSeries(pd.Series):
        pass


class TtsColumnSeries(pd.Series):
    pass


def _strict_unique(s):
    """pivot_table aggfunc that passes through single values but raises on
    genuinely conflicting records (different values for the same index/column
    key).  Exact duplicates — identical value appearing more than once — are
    silently collapsed, because they carry no new information."""
    if s.nunique() > 1:
        raise ValueError(
            f"Conflicting values for the same (index, column) key: {s.tolist()}")
    return s.iloc[0]


def _is_scalar_selector(key):
    return not isinstance(key, (slice, list, pd.Index, pd.Series))


class _SeriesWrappingIndexer:
    """Wraps a pandas loc/iloc indexer to return typed Row/Column Series."""
    def __init__(self, indexer, frame, row_cls, col_cls):
        self._indexer = indexer
        self._frame = frame
        self._row_cls = row_cls
        self._col_cls = col_cls

    def _wrap(self, result, key):
        if isinstance(result, pd.Series):
            if isinstance(key, tuple) and len(key) >= 2 and _is_scalar_selector(key[1]):
                result.__class__ = self._col_cls
            else:
                result.__class__ = self._row_cls
                if hasattr(result, '__dict__'):
                    result._frame = self._frame
        return result

    def __getitem__(self, key):
        return self._wrap(self._indexer[key], key)

    def __setitem__(self, key, value):
        self._indexer[key] = value

    def __getattr__(self, name):
        return getattr(self._indexer, name)

    def __call__(self, *args, **kwargs):
        return _SeriesWrappingIndexer(
            self._indexer(*args, **kwargs),
            self._frame,
            self._row_cls,
            self._col_cls,
        )


class TtsDataFrame(pd.DataFrame):
    """Base DataFrame subclass for tts_data_utils.

    Stores lightweight container-style metadata (``name`` and ``metadata``)
    and ensures subclasses are preserved across pandas operations via the
    ``_constructor`` hook and ``_metadata``.
    """

    # Attributes in this list are copied by pandas when creating new
    # objects via methods like .copy(), .loc, .sort_values(), etc.
    _metadata = ["name", "metadata", "_subcontainers", "_row_dispositions"]

    # Optional associated row class for ergonomic row views (not used for typing).
    ROW_ITEM_CLS = None

    # Container-level schema: list of (column_name, type or tuple of types)
    SCHEMA = None

    # Optional mapping of time-like columns to strptime/strftime formats
    TIME_FORMATS = {}

    # Default column used for time-based operations; subclasses should override.
    DEFAULT_TIME_LABEL = 'scet'

    ROW_SERIES_CLASS = TtsRowSeries

    COLUMN_SERIES_CLASS = TtsColumnSeries

    LABEL_COL = 'name'

    VALUE_COL = 'value'

    LABEL_COLUMN = 'name'

    SUBCONTAINER_KEY = None

    # Expression engine configuration.
    #
    #  - MATH_ENGINE: shared parser/grammar singleton (kept for backward
    #    compatibility; normally you should not override this).
    #  - MATH_TRANSFORMER: transformer class used to evaluate parsed math
    #    expressions. Subclasses override this to customize semantics while
    #    reusing the core grammar.
    MATH_ENGINE = _math_engine
    MATH_TRANSFORMER = _MathTransformer

    def __init__(self, *args, name=None, metadata=None, coerce=None, validate=None, csv_path=None, **kwargs):
        # Pull container-style metadata and validation flags out of kwargs

        # Optional CSV-based construction
        if csv_path is not None:
            if args:
                raise Exception("Cannot pass positional data and csv_path together.")
            if "data" in kwargs:
                raise Exception("Cannot pass both 'data' and 'csv_path'.")

            # Split kwargs between DataFrame ctor kwargs and read_csv kwargs
            df_init_keys = {"index", "columns", "dtype", "copy"}
            df_kwargs = {}
            csv_kwargs = {}
            for k, v in list(kwargs.items()):
                if k in df_init_keys:
                    df_kwargs[k] = v
                else:
                    csv_kwargs[k] = v

            # Use class hook so subclasses can customize CSV ingest
            raw_df = self._read_csv_to_df(csv_path, **csv_kwargs)
            args = (raw_df,)
            kwargs = df_kwargs

        super().__init__(*args, **kwargs)
        self.name = name
        self.metadata = metadata if metadata is not None else {}
        self._data_hash = None
        self._pivot_cache = None
        self._subcontainers = {}
        self._row_dispositions = {}

        if coerce or validate:
            self._apply_schema(coerce=coerce, validate=validate)

    def moving_average(self, window_seconds, label_value=None, time_col=None, label_col=None, value_col=None):
        """Return a time-based moving average over ``window_seconds`` seconds.

        This operates on long-form telemetry where labels and values are
        carried in configured columns, and timestamps are in
        :attr:`DEFAULT_TIME_LABEL`.  A rolling mean is computed
        separately for each label over a trailing window of
        ``window_seconds`` seconds.

        Parameters
        ----------
        window_seconds : float or int
            Width of the rolling window in seconds.
        time_col : str or None, optional
            Column to use as the time axis; defaults to
            :attr:`DEFAULT_TIME_LABEL` when None.
        label_col : str or None, optional
            Column holding label names; defaults to :attr:`LABEL_COL`.
        value_col : str or None, optional
            Column holding numeric values; defaults to :attr:`VALUE_COL`.

        Returns
        -------
        TtsDataFrame
            New frame of the same subclass with the same rows and
            columns, but ``value_col`` replaced by the moving-average
            values.
        """

        time_col = time_col or self.DEFAULT_TIME_LABEL
        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL

        if time_col is None or value_col is None:
            raise ValueError(
                "moving_average requires DEFAULT_TIME_LABEL and VALUE_COL to be configured "
                "or passed explicitly."
            )

        if time_col not in self.columns or value_col not in self.columns:
            raise ValueError(
                f"moving_average requires time and value columns present on the frame; "
                f"missing {time_col!r} or {value_col!r}."
            )

        df = self.copy()

        # Optional label filtering: restrict to a single label value when
        # provided, using the same semantics as the Series.eq helper.
        if label_value is not None:
            if label_col is None or label_col not in df.columns:
                raise ValueError(
                    "label_value was provided but LABEL_COL/label_col is not configured "
                    "or not present in the frame."
                )
            df = df[df[label_col].eq(label_value)].copy()

        # If no label_value was provided but multiple labels are present,
        # log that aggregating across them may not be meaningful.
        if label_value is None and label_col is not None and label_col in df.columns:
            unique_labels = pd.unique(df[label_col].dropna())
            if len(unique_labels) > 1:
                logger.warning(
                    "moving_average called on a frame containing multiple labels; "
                    "the aggregated result may not be meaningful."
                )

        # Ensure datetime time column and stable ordering for rolling
        df[time_col] = pd.to_datetime(df[time_col])
        sort_cols = [time_col]
        if label_col is not None and label_col in df.columns:
            sort_cols = [label_col, time_col]
        df = df.sort_values(sort_cols)

        window = pd.to_timedelta(window_seconds, unit="s")

        if label_col is not None and label_col in df.columns:
            def _apply(group):
                s = group.set_index(time_col)[value_col]
                rolled = s.rolling(window, min_periods=1).mean()
                group[value_col] = rolled.values
                return group

            smoothed = df.groupby(label_col, group_keys=False).apply(_apply)
        else:
            s = df.set_index(time_col)[value_col]
            rolled = s.rolling(window, min_periods=1).mean()
            df[value_col] = rolled.values
            smoothed = df

        # Preserve subclass type via _constructor
        return self._constructor(smoothed).__finalize__(self)

    def time_average(self, freq, label_value=None, time_col=None, label_col=None, value_col=None):
        """Return a time-based average over fixed-width time bins.

        This operates on long-form telemetry where labels and values are
        carried in configured columns, and timestamps are in
        :attr:`DEFAULT_TIME_LABEL`.  Samples are grouped into
        non-overlapping time bins of width ``freq`` (a pandas
        offset string such as ``'98min'``), and each bin is replaced by a
        single row whose value is the arithmetic mean of the samples in
        that bin.

        When a label column is present, bins are formed separately for
        each label value.

        Parameters
        ----------
        freq : str or DateOffset
            Resampling frequency understood by :meth:`pandas.Series.resample`,
            e.g. ``'98min'``.
        label_value : any or None, optional
            When provided, restrict averaging to rows where ``label_col``
            equals this value.
        time_col : str or None, optional
            Column to use as the time axis; defaults to
            :attr:`DEFAULT_TIME_LABEL` when None.
        label_col : str or None, optional
            Column holding label names; defaults to :attr:`LABEL_COL`.
        value_col : str or None, optional
            Column holding numeric values; defaults to :attr:`VALUE_COL`.

        Returns
        -------
        TtsDataFrame
            New frame of the same subclass containing one row per time
            bin, with ``value_col`` replaced by the bin-mean values. The
            time column for each bin is taken from the bin's resample
            index (typically the left edge of the interval).
        """

        time_col = time_col or self.DEFAULT_TIME_LABEL
        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL

        if time_col is None or value_col is None:
            raise ValueError(
                "time_average requires DEFAULT_TIME_LABEL and VALUE_COL to be configured "
                "or passed explicitly."
            )

        if time_col not in self.columns or value_col not in self.columns:
            raise ValueError(
                f"time_average requires time and value columns present on the frame; "
                f"missing {time_col!r} or {value_col!r}."
            )

        df = self.copy()

        # Optional label filtering
        if label_value is not None:
            if label_col is None or label_col not in df.columns:
                raise ValueError(
                    "label_value was provided but LABEL_COL/label_col is not configured "
                    "or not present in the frame."
                )
            df = df[df[label_col].eq(label_value)].copy()

        # Ensure datetime time column and stable ordering for resampling
        df[time_col] = pd.to_datetime(df[time_col])

        def _resample_group(group):
            # Work on a copy with a datetime index for resampling.
            g = group.copy()
            g[time_col] = pd.to_datetime(g[time_col])
            g = g.set_index(time_col).sort_index()

            # Resample the value column to compute mean per bin.
            agg = g[value_col].resample(freq).mean()

            # Drop bins with no data (NaN means no contributing samples).
            mask = ~agg.isna()
            if not mask.any():
                return g.iloc[0:0]

            agg = agg[mask]

            # Take representative metadata from the first row in each bin.
            first = g.resample(freq).first()
            first = first.loc[agg.index]

            # Overwrite value column with the bin means and restore time column.
            first[value_col] = agg.values
            first = first.reset_index()
            return first

        if label_col is not None and label_col in df.columns:
            reduced = df.groupby(label_col, group_keys=False).apply(_resample_group)
        else:
            reduced = _resample_group(df)

        return self._constructor(reduced).__finalize__(self)

    def block_average(self, block_size, label_value=None, time_col=None, label_col=None, value_col=None):
        """Return a simple block (bin) average over non-overlapping blocks.

        This operates on long-form telemetry where labels and values are
        carried in configured columns. Samples are grouped into
        non-overlapping blocks of ``block_size`` consecutive points,
        and each block is replaced by a single row whose value is the
        arithmetic mean of the block.

        When a label column is present, blocks are formed separately for
        each label value.

        Parameters
        ----------
        block_size : int
            Number of samples per block. The last partial block for each
            label is included with whatever number of samples remain.
        time_col : str or None, optional
            Column to use as the time axis for sorting; defaults to
            :attr:`DEFAULT_TIME_LABEL` when None.
        label_col : str or None, optional
            Column holding label names; defaults to :attr:`LABEL_COL`.
        value_col : str or None, optional
            Column holding numeric values; defaults to :attr:`VALUE_COL`.

        Returns
        -------
        TtsDataFrame
            New frame of the same subclass containing one row per
            block, with ``value_col`` replaced by the block-mean
            values. The time column for each block is taken from the
            first sample in the block.
        """

        time_col = time_col or self.DEFAULT_TIME_LABEL
        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL

        if value_col is None:
            raise ValueError(
                "block_average requires VALUE_COL to be configured or passed explicitly."
            )

        if value_col not in self.columns:
            raise ValueError(
                f"block_average requires value column present on the frame; missing {value_col!r}."
            )

        if block_size <= 0:
            raise ValueError("block_size must be a positive integer")

        df = self.copy()

        # Optional label filtering
        if label_value is not None:
            if label_col is None or label_col not in df.columns:
                raise ValueError(
                    "label_value was provided but LABEL_COL/label_col is not configured "
                    "or not present in the frame."
                )
            df = df[df[label_col].eq(label_value)].copy()

        # Stable ordering within each label by time and then index
        sort_cols = []
        if label_col is not None and label_col in df.columns:
            sort_cols.append(label_col)
        if time_col is not None and time_col in df.columns:
            sort_cols.append(time_col)
        if sort_cols:
            df = df.sort_values(sort_cols)

        def _block_group(group):
            n = len(group)
            # Block id 0,1,2,... over the index position within the group
            block_ids = np.arange(n) // block_size
            group = group.copy()
            group["_block_id"] = block_ids

            # Compute mean per block for the value column
            agg = group.groupby("_block_id", as_index=False).agg({value_col: "mean"})

            # Take representative time/label from the first row in each block
            first = group.groupby("_block_id", as_index=False).nth(0)

            # Align the aggregated values with the representative rows
            first = first.drop(columns=["_block_id"])
            agg[value_col] = agg[value_col].values

            # Use the columns from the representative rows, updating value_col
            first[value_col] = agg[value_col].values
            return first

        if label_col is not None and label_col in df.columns:
            reduced = df.groupby(label_col, group_keys=False).apply(_block_group)
        else:
            reduced = _block_group(df)

        # Preserve subclass type via _constructor
        return self._constructor(reduced).__finalize__(self)

    @classmethod
    def _read_csv_to_df(cls, filepath, *args, **kwargs):
        """Hook for subclasses to customize how CSVs are read.

        Default implementation simply calls :func:`pandas.read_csv`.
        """
        return pd.read_csv(filepath, *args, **kwargs)

    def to_csv(self, *args, **kwargs):  # pragma: no cover - thin wrapper around pandas
        """Write object to a CSV file, formatting time columns via ``TIME_FORMATS``.

        This behaves like :meth:`pandas.DataFrame.to_csv`, but for any columns
        listed in :attr:`TIME_FORMATS` that are datetime-like, values are first
        converted to strings using the configured strftime format. When a column
        has multiple formats configured (list/tuple), the first entry is used
        for export.
        """

        time_formats = getattr(self, "TIME_FORMATS", None) or {}
        if not time_formats:
            # No configured time formats: fall back to the base implementation.
            return pd.DataFrame.to_csv(self, *args, **kwargs)

        df = self.copy()

        for col, fmt_spec in time_formats.items():
            if col not in df.columns:
                continue
            if fmt_spec == "TBD" or fmt_spec is None:
                continue

            # When multiple formats are configured, use the first one for export.
            if isinstance(fmt_spec, (list, tuple)):
                if not fmt_spec:
                    continue
                fmt = fmt_spec[0]
            else:
                fmt = fmt_spec

            if not isinstance(fmt, str):
                continue

            series = df[col]

            # If the column is already datetime-like, format directly.
            if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_datetime64tz_dtype(series):
                df[col] = series.dt.strftime(fmt)
                continue

            # For object columns, try to coerce to datetime first and only
            # format entries that successfully convert.
            if series.dtype == "object":
                dt_series = pd.to_datetime(series, errors="coerce")
                if dt_series.notna().any():
                    formatted = dt_series.dt.strftime(fmt)
                    mask = dt_series.notna()
                    new_series = series.astype(object)
                    new_series[mask] = formatted[mask]
                    df[col] = new_series

        # Delegate to pandas using the formatted copy.
        return pd.DataFrame.to_csv(df, *args, **kwargs)

    @property
    def _constructor(self):  # pragma: no cover - exercised indirectly
        cls = type(self)
        def _internal_constructor(*args, **kwargs):
            kwargs['coerce'] = False
            kwargs['validate'] = False
            return cls(*args, **kwargs)
        return _internal_constructor

    def __finalize__(self, other, method=None, **kwargs):
        for attr in self._metadata:
            object.__setattr__(self, attr, getattr(other, attr, None))
        if self._subcontainers is None:
            object.__setattr__(self, '_subcontainers', {})
        else:
            object.__setattr__(self, '_subcontainers', dict(self._subcontainers))
        key_cfg = self.SUBCONTAINER_KEY
        if self._subcontainers and key_cfg is not None:
            before = len(self._subcontainers)
            if key_cfg == 'pandas_index':
                live = set(self.index)
            else:
                cols = [key_cfg] if isinstance(key_cfg, str) else list(key_cfg)
                if all(c in self.columns for c in cols):
                    live = set(zip(*(self[c] for c in cols))) if len(cols) > 1 else set(self[cols[0]])
                else:
                    live = set()
            for k in list(self._subcontainers):
                if k not in live:
                    del self._subcontainers[k]
            lost = before - len(self._subcontainers)
            if lost:
                msg = (f"{lost} subcontainer entr{'y' if lost == 1 else 'ies'} "
                       f"pruned after a pandas operation.")
                if key_cfg == 'pandas_index':
                    msg += (" Consider setting SUBCONTAINER_KEY to stable column(s) instead.")
                print(msg)
        return self

    def get_subcontainer(self, row_key, name: str):
        """Retrieve a named subcontainer attached to ``row_key``.

        Parameters
        ----------
        row_key :
            The key for the parent row.  A single value when
            ``SUBCONTAINER_KEY`` is a string or ``'pandas_index'``; a tuple
            when it is a list of columns.
        name : str
            Name of the subcontainer slot.
        """
        return self._subcontainers.get(row_key, {}).get(name)

    def set_subcontainer(self, row_key, name: str, container):
        """Attach a named subcontainer to ``row_key``.

        Parameters
        ----------
        row_key :
            The key identifying the parent row (see :attr:`SUBCONTAINER_KEY`).
        name : str
            Name of the subcontainer slot.
        container :
            Any object to store — typically a ``TtsDataFrame``.

        Raises
        ------
        ValueError
            If :attr:`SUBCONTAINER_KEY` has not been configured on the class.
        """
        if self.SUBCONTAINER_KEY is None:
            raise ValueError(
                "SUBCONTAINER_KEY is not configured on this class. "
                "Set it to a column name, list of columns, or 'pandas_index'."
            )
        if row_key not in self._subcontainers:
            self._subcontainers[row_key] = {}
        self._subcontainers[row_key][name] = container

    def __getitem__(self, key):
        result = super().__getitem__(key)
        if isinstance(result, pd.Series):
            result.__class__ = self.COLUMN_SERIES_CLASS
        return result


    @property
    def loc(self):
        return _SeriesWrappingIndexer(super().loc, self, self.ROW_SERIES_CLASS, self.COLUMN_SERIES_CLASS)

    @property
    def iloc(self):
        return _SeriesWrappingIndexer(super().iloc, self, self.ROW_SERIES_CLASS, self.COLUMN_SERIES_CLASS)

    def xs(self, key, axis=0, level=None, drop_level=True):
        result = super().xs(key, axis=axis, level=level, drop_level=drop_level)
        if isinstance(result, pd.Series):
            result.__class__ = self.ROW_SERIES_CLASS if axis in (0, 'index') else self.COLUMN_SERIES_CLASS
            if axis in (0, 'index') and hasattr(result, '__dict__'):
                result._frame = self
        return result

    def iterrows(self):
        for idx, row in super().iterrows():
            row.__class__ = self.ROW_SERIES_CLASS
            if hasattr(row, '__dict__'):
                row._frame = self
            yield idx, row

    def select_wide(
        self,
        labels=None,
        label_col=None,
        value_col=None,
        index_col=None,
        how='outer',
    ):
        """Return a wide-form DataFrame with one column per label.

        Parameters
        ----------
        labels : list or None
            Labels to include. None means all unique values in label_col.
        label_col : str or None
            Column containing label names. Defaults to LABEL_COL.
        value_col : str or None
            Column containing values. Defaults to VALUE_COL.
        index_col : str or None
            Column to use as the row index (e.g. time). Defaults to DEFAULT_TIME_LABEL.
        how : str
            Join strategy when concatenating label groups ('outer', 'inner'). Default 'outer'.
        """
        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL
        index_col = index_col or self.DEFAULT_TIME_LABEL

        if label_col is None:
            raise ValueError("label_col must be provided or set as LABEL_COL on the class.")
        if value_col is None:
            raise ValueError("value_col must be provided or set as VALUE_COL on the class.")
        if index_col is None:
            raise ValueError("index_col must be provided or set as DEFAULT_TIME_LABEL on the class.")

        grouped = self.groupby(label_col)

        if labels is None:
            labels = list(grouped.groups.keys())

        available = grouped.groups
        frames = [
            grouped.get_group(lbl)[[index_col, value_col]]
                   .rename(columns={value_col: lbl})
                   .set_index(index_col)
            for lbl in labels
            if lbl in available
        ]

        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, axis=1, join=how)

    def at_times_where(
        self,
        expr: str,
        *,
        tolerance=None,
        label_col=None,
        value_col=None,
        index_col=None,
    ):
        """Return all rows whose timestamp matches records where the expression is True.

        Each identifier in ``expr`` is treated as a label name looked up in
        ``label_col``. The matching values are pivoted to a temporary wide
        view (one column per label, indexed by ``index_col``) and the
        expression is evaluated row-wise against that view. All rows in the
        original DataFrame whose ``index_col`` timestamp qualifies are returned.

        Parameters
        ----------
        expr : str
            Boolean expression string where identifiers are label names, e.g.
            ``'sensor_001 > 0.7 and sensor_002 < 0.5'``.
            Supports >, >=, <, <=, ==, !=, is, is not, and, or, not,
            parentheses, numeric and quoted string literals.
        tolerance : number or pd.Timedelta or None
            If given, also include rows within this time window of a qualifying
            timestamp. A plain number is interpreted as seconds.
        label_col, value_col, index_col : str or None
            Column overrides; fall back to class attributes.

        Examples
        --------
        >>> df.at_times_where('sensor_001 > 0.7')
        >>> df.at_times_where('sensor_001 > 0.7 and sensor_002 < 0.5')
        >>> df.at_times_where('sensor_001 > 0.7 or status == "ok"', tolerance=5)
        """
        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL
        index_col = index_col or self.DEFAULT_TIME_LABEL

        if label_col is None:
            raise ValueError("label_col must be provided or set as LABEL_COL on the class.")
        if value_col is None:
            raise ValueError("value_col must be provided or set as VALUE_COL on the class.")
        if index_col is None:
            raise ValueError("index_col must be provided or set as DEFAULT_TIME_LABEL on the class.")

        parsed = _filter_engine.parse(expr)

        grouped = self.groupby(label_col)
        frames = {}
        for lbl in parsed.labels:
            if lbl not in grouped.groups:
                raise _FilterExprError(f"Label {lbl!r} not found in {label_col!r}.")
            frames[lbl] = (
                grouped.get_group(lbl)
                .set_index(index_col)[value_col]
                .rename(lbl)
                .groupby(level=0).last()
            )

        wide = pd.concat(frames.values(), axis=1, join='inner')
        mask = parsed.eval(wide)

        qualifying_times = wide.index[mask]

        if tolerance is None:
            qt_frame = pd.DataFrame({index_col: qualifying_times})
            return self.merge(qt_frame, on=index_col, how='inner')

        if not isinstance(tolerance, pd.Timedelta):
            tolerance = pd.Timedelta(seconds=tolerance)

        qt_arr = np.sort(qualifying_times.values)        # sorted datetime64[ns]
        row_times = self[index_col].values               # datetime64[ns]
        tol_td = np.timedelta64(int(tolerance.value), 'ns')

        lo = np.searchsorted(qt_arr, row_times - tol_td, side='left')
        hi = np.searchsorted(qt_arr, row_times + tol_td, side='right')
        return self[lo < hi]

    def contiguous_runs(
        self,
        labels,
        *,
        tolerance=None,
        min_repeats: int = 1,
        target_value=None,
        label_col: Optional[str] = None,
        value_col: Optional[str] = None,
        index_col: Optional[str] = None,
    ) -> Dict[str, List['TtsDataFrame']]:
        """Return contiguous runs of constant values for one or more labels.

        For each label name in ``labels``, this method scans the long-form
        telemetry in time order and identifies maximal contiguous runs where
        the label's ``value_col`` is constant across successive samples. Each
        qualifying run (after filtering) is converted into a new
        :class:`TtsDataFrame` that includes *all* labels present in the
        original frame over the corresponding time window, using
        :meth:`at_times_where` to honor the ``tolerance`` parameter.

        Parameters
        ----------
        labels : str or iterable of str
            Label name or collection of label names to analyze.
        tolerance : number or pd.Timedelta or None, optional
            Passed through to :meth:`at_times_where` to include rows within
            this time window of qualifying timestamps. A plain number is
            interpreted as seconds.
        min_repeats : int, default 1
            Minimum number of consecutive samples with the same value
            required for a run to be kept. Shorter runs are discarded.
        target_value : any or None, optional
            When provided, only runs where the label's value equals
            ``target_value`` are kept. Runs with other values are discarded.
        label_col, value_col, index_col : str or None, optional
            Column overrides; fall back to class attributes.

        Returns
        -------
        dict[str, list[TtsDataFrame]]
            Mapping from each label name to a list of run-specific frames.
        """
        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL
        index_col = index_col or self.DEFAULT_TIME_LABEL

        if label_col is None:
            raise ValueError("label_col must be provided or set as LABEL_COL on the class.")
        if value_col is None:
            raise ValueError("value_col must be provided or set as VALUE_COL on the class.")
        if index_col is None:
            raise ValueError("index_col must be provided or set as DEFAULT_TIME_LABEL on the class.")
        if min_repeats <= 0:
            raise ValueError("min_repeats must be a positive integer")

        # Normalize labels argument to a list of names
        if isinstance(labels, str):
            label_names = [labels]
        else:
            label_names = list(labels)

        result: dict[str, list['TtsDataFrame']] = {}

        for lbl in label_names:
            # Extract time-ordered series for this label
            label_df = self[self[label_col] == lbl].copy()
            if label_df.empty:
                result[lbl] = []
                continue

            label_df = label_df.sort_values(index_col)
            vals = label_df[value_col].values

            # Identify contiguous runs of constant values
            runs: list[tuple[int, int, object]] = []
            start_idx = 0
            current_value = vals[0]

            for i in range(1, len(label_df)):
                v = vals[i]
                if v == current_value:
                    continue
                # End of current run at i-1
                runs.append((start_idx, i - 1, current_value))
                start_idx = i
                current_value = v

            # Final run
            runs.append((start_idx, len(label_df) - 1, current_value))

            # Filter runs by length and optional target_value
            filtered_runs: list[tuple[int, int, object]] = []
            for start, end, run_value in runs:
                length = end - start + 1
                if length < min_repeats:
                    continue
                if target_value is not None and run_value != target_value:
                    continue
                filtered_runs.append((start, end, run_value))

            run_frames: list['TtsDataFrame'] = []

            for start, end, run_value in filtered_runs:
                t_start = label_df.iloc[start][index_col]
                t_end = label_df.iloc[end][index_col]

                # Restrict to the time window for this run
                time_mask = (self[index_col] >= t_start) & (self[index_col] <= t_end)
                window = self[time_mask].copy()
                if window.empty:
                    continue

                # Build a filter expression matching this label/value.  Booleans
                # are rendered as 0/1 so that they are parsed as numeric
                # literals by the filter engine rather than as label names.
                if isinstance(run_value, str):
                    expr_value = repr(run_value)
                elif isinstance(run_value, bool):
                    expr_value = "1" if run_value else "0"
                else:
                    expr_value = str(run_value)
                expr = f"{lbl} == {expr_value}"

                run_df = window.at_times_where(
                    expr,
                    tolerance=tolerance,
                    label_col=label_col,
                    value_col=value_col,
                    index_col=index_col,
                )
                if not run_df.empty:
                    run_frames.append(run_df)

            result[lbl] = run_frames

        return result

    @property
    def wide(self):
        index   = self.DEFAULT_TIME_LABEL
        columns = self.LABEL_COLUMN
        values  = self.VALUE_COL
        id_cols  = [index, columns]
        val_cols = [values]

        data_hash = pd.util.hash_pandas_object(
            self[id_cols + val_cols], index=False).sum()

        if getattr(self, '_data_hash', None) == data_hash:
            return self._pivot_cache

        dupes = self.duplicated(subset=id_cols, keep=False)
        if dupes.any():
            bad = (self[dupes]
                   .groupby(id_cols)[val_cols]
                   .nunique()
                   .pipe(lambda df: df[(df > 1).any(axis=1)]))
            if not bad.empty:
                raise ValueError(
                    f"Conflicting values for the same (index, column) key:\n{bad}")

        self._pivot_cache = super().pivot_table(index=index, columns=columns, values=values, aggfunc='last')
        self._data_hash = data_hash


        return self._pivot_cache

    def filter_expr(self, expr: str) -> 'TtsDataFrame':
        """Filter rows where the given boolean expression is True.

        Column names refer to columns of this DataFrame. Supports >, >=,
        <, <=, ==, !=, is, is not, and the logical combinators and, or,
        not, with parentheses for grouping. String literals use single or
        double quotes. None/null/none match NaN via Series.isna().

        Parameters
        ----------
        expr : str
            Boolean expression string, e.g.
            '(sensor_001 > 0.7 and sensor_002 == 2) or sensor_3 is "unknown"'

        Returns
        -------
        TtsDataFrame
            Rows where the expression evaluates to True.
        """
        return self[_filter_engine.parse(expr).eval(self)]

    def inspect_expr_language(self):
        math_engine = self.MATH_ENGINE
        math_transformer = self.MATH_TRANSFORMER
        funcs = getattr(math_transformer, "_FUNCS", {})
        math_functions = sorted(funcs.keys()) if isinstance(funcs, dict) else []
        filter_engine = _filter_engine
        info = {
            "math_engine": type(math_engine),
            "math_transformer": math_transformer,
            "math_functions": math_functions,
            "math_keywords": {
                "boolean": {"and", "or", "not"},
                "comparison": {">", ">=", "<", "<=", "==", "!=", "in"},
            },
            "filter_engine": type(filter_engine),
            "filter_keywords": {
                "boolean": {"and", "or", "not"},
                "comparison": {">", ">=", "<", "<=", "==", "!=", "is", "is not", "in", "not in"},
                "literals": {"None", "null", "none", "True", "true", "False", "false"},
            },
        }
        return info


    def get_interpolator(self, label: str):
        """Return the interpolator to use for ``label`` in :meth:`derive_values`.

        Override this in subclasses to implement per-label or type-driven
        interpolator selection.  The base implementation always returns a
        :class:`StepInterpolator`.

        This method is extremely simple in the base class and is meant to be
        overridden based on need. For AMPCS missions, this can mean comparing the 
        channel label to the channel dictionary to look up the channel's data
        type and using a different interpolator for each.

        e.g. use a step interpolator for enums, a linear for floats, and a linear
        that also clamps to integer values for integers.

        The overrride of this method can also be a place to put even more granularity.
        For example, an int channel may be better as a step interpolation or 
        a linear one depending on the exact information in the channel.

        Parameters
        ----------
        label : str
            The label name whose interpolator is being resolved.

        Returns
        -------
        Interpolator
            An interpolator instance from ``tts_dante.interpolators``.
        """
        return StepInterpolator()

    def derive_values(
        self,
        expr: str,
        *,
        interpolator=None,
        timeout=0,
        label_col=None,
        value_col=None,
        index_col=None,
        append=False,
    ) -> 'TtsDataFrame':
        """Compute a derived label from a math expression over existing labels.

        Values from different labels are aligned by time using ``interpolator``
        before the expression is evaluated.  Timestamps where any referenced
        label cannot be interpolated (returns None) are silently skipped.

        Parameters
        ----------
        expr : str
            Assignment of the form ``'name = math_expression'`` where
            identifiers on the right are label names, e.g.
            ``'derived = sensor_001 * 2 - abs(sensor_002)'``.
            Supports +, -, *, /, **, unary -, parentheses, and the functions
            abs, sqrt, sin, cos, tan, log, log10, exp, floor, ceil.
        interpolator : Interpolator or None
            tts_dante Interpolator used to align label values across time.
            When ``None`` (default), :meth:`get_interpolator` is called for
            each label, allowing per-label interpolator selection.  Pass a
            single Interpolator instance to force it for all labels.
        timeout : float or None
            Max age of a sample passed to the interpolator's ``timeout``
            argument.  Units must match ``index_col`` (seconds for float
            timestamps, or a timedelta for datetime columns).  Timestamps
            where any label returns None are skipped.
        label_col, value_col, index_col : str or None
            Column overrides; fall back to class attributes.

        Returns
        -------
        TtsDataFrame
            Long-form rows for the derived label, one per aligned timestamp.

        Examples
        --------
        >>> df.derive_values('derived = sensor_001 * 2 - abs(sensor_002)')
        >>> df.derive_values('derived = sensor_001 + sensor_002',
        ...                  interpolator=LinearInterpolator(), timeout=5)
        """        

        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL
        index_col = index_col or self.DEFAULT_TIME_LABEL

        if label_col is None:
            raise ValueError("label_col must be provided or set as LABEL_COL on the class.")
        if value_col is None:
            raise ValueError("value_col must be provided or set as VALUE_COL on the class.")
        if index_col is None:
            raise ValueError("index_col must be provided or set as DEFAULT_TIME_LABEL on the class.")

        if '=' not in expr:
            raise ValueError(
                f"derive_values expr must be an assignment 'name = expression', got {expr!r}")
        derived_name, rhs = expr.split('=', 1)
        derived_name = derived_name.strip()

        # Support multiple target names on the left-hand side, e.g.:
        #   "M_val, T_val, RTS_val = fmt_match(message, 'M=%d; T=%d; RTS=%d')"
        # In this case, the RHS must evaluate to an iterable of the same
        # length as the number of target names.
        derived_names = [n.strip() for n in derived_name.split(',') if n.strip()]
        if not derived_names:
            raise ValueError(
                f"derive_values expr must have at least one target name before '=', got {expr!r}")
        multi_output = len(derived_names) > 1

        # Parse using the shared math engine and this class's transformer.
        parsed = self.MATH_ENGINE.parse(rhs.strip(), transformer_cls=self.MATH_TRANSFORMER)

        grouped = self.groupby(label_col)
        label_data = {}
        for lbl in parsed.labels:
            if lbl not in grouped.groups:
                raise _MathExprError(f"Label {lbl!r} not found in {label_col!r}.")
            grp = grouped.get_group(lbl).sort_values(index_col)
            label_data[lbl] = (grp[index_col].tolist(), grp[value_col].tolist())

        rows = []
        label_interpolators = {
            lbl: interpolator if interpolator is not None else self.get_interpolator(lbl)
            for lbl in parsed.labels
        }

        if timeout == 0: 
            # Speeds up derivation when timeout is zero by not even calling the Interpolator.
            # Should be equivalent to setting interplator timeout to zero (e.g. do not interpolate.
            # only combine channels at times when they are all present)
            common_times = sorted(
                set.intersection(*[set(times) for times, _ in label_data.values()])
            )
            lookup = {
                lbl: dict(zip(times, vals))
                for lbl, (times, vals) in label_data.items()
            }
            for t in common_times:
                slot = {lbl: lookup[lbl][t] for lbl in parsed.labels}
                result = parsed.eval(slot)

                if multi_output:
                    try:
                        values = list(result)
                    except TypeError as exc:
                        raise _MathExprError(
                            "derive_values: multi-target assignment requires the "
                            "expression to return an iterable of values."
                        ) from exc

                    if len(values) != len(derived_names):
                        raise _MathExprError(
                            f"derive_values: expression returned {len(values)} values "
                            f"but {len(derived_names)} target names were given."
                        )

                    for name, val in zip(derived_names, values):
                        rows.append({index_col: t, label_col: name, value_col: val})
                else:
                    rows.append({index_col: t, label_col: derived_names[0], value_col: result})
        else:
            all_times = sorted({t for times, _ in label_data.values() for t in times})
            for t in all_times:
                slot = {}
                valid = True
                for lbl, (times, vals) in label_data.items():
                    v = label_interpolators[lbl].interpolate(t, times, vals, timeout)
                    if v is None:
                        valid = False
                        break
                    slot[lbl] = v
                if not valid:
                    continue
                result = parsed.eval(slot)

                if multi_output:
                    try:
                        values = list(result)
                    except TypeError as exc:
                        raise _MathExprError(
                            "derive_values: multi-target assignment requires the "
                            "expression to return an iterable of values."
                        ) from exc

                    if len(values) != len(derived_names):
                        raise _MathExprError(
                            f"derive_values: expression returned {len(values)} values "
                            f"but {len(derived_names)} target names were given."
                        )

                    for name, val in zip(derived_names, values):
                        rows.append({index_col: t, label_col: name, value_col: val})
                else:
                    rows.append({index_col: t, label_col: derived_names[0], value_col: result})

        if not rows:
            if append:
                return self.copy()
            return type(self)(validate=False, coerce=False)

        derived_df = type(self)(rows, validate=False, coerce=False)

        if append:
            combined = pd.concat([self, derived_df], ignore_index=True, sort=False)
            return type(self)(combined, name=self.name, metadata=self.metadata,
                              coerce=False, validate=False)

        return derived_df

    def find_crossings(
        self,
        label,
        target=0.0,
        *,
        interpolator=None,
        timeout=None,
        time_col=None,
        label_col=None,
        value_col=None,
    ):
        """Find times where a label crosses a given value using interpolation.

        This is useful for detecting zero-crossings (e.g. latitude == 0) and
        determining direction (negative-to-positive vs positive-to-negative).

        Parameters
        ----------
        label : str
            Label name to analyze.
        target : float, default 0.0
            Target value to detect crossings of (e.g. 0 for zero-crossings).
        interpolator : Interpolator or None, optional
            ``tts_dante`` interpolator instance to use for refining the
            crossing time. When None, a :class:`LinearInterpolator` is used.
        timeout : float or None, optional
            Max distance (in time units of ``time_col``) passed to the
            interpolator. See interpolator docs for semantics.
        time_col, label_col, value_col : str or None, optional
            Column overrides; fall back to class attributes.

        Returns
        -------
        TtsDataFrame
            Frame with one row per crossing, columns:

            - time: estimated crossing time
            - direction: +1 for negative->positive crossings,
              -1 for positive->negative crossings
            - label: the label name
            - target: the target value crossed
        """
        time_col = time_col or self.DEFAULT_TIME_LABEL
        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL

        if time_col is None or label_col is None or value_col is None:
            raise ValueError(
                "find_crossings requires DEFAULT_TIME_LABEL, LABEL_COL, and VALUE_COL "
                "to be configured or passed explicitly."
            )

        df = self[self[label_col] == label].copy()
        if df.empty:
            empty = pd.DataFrame(columns=["time", "direction", "label", "target"])
            return self._constructor(empty).__finalize__(self)

        # Ensure sorted by time and convert to a numeric axis that matches the
        # interpolator's expectation. For datetime, use seconds since epoch.
        df = df.sort_values(time_col)
        col = df[time_col]
        if np.issubdtype(col.dtype, np.datetime64):
            times_raw = pd.to_datetime(col)
            epoch = np.datetime64("1970-01-01T00:00:00Z")
            times = (times_raw.values - epoch) / np.timedelta64(1, "s")
        else:
            times_raw = col
            times = col.astype(float).values

        values = df[value_col].astype(float).values

        if len(times) < 2:
            empty = pd.DataFrame(columns=["time", "direction", "label", "target"])
            return self._constructor(empty).__finalize__(self)

        interp = interpolator if interpolator is not None else LinearInterpolator()

        crossings = []

        # Helper to map numeric seconds back to time_col dtype
        def _to_time_axis(t_numeric):
            if np.issubdtype(times_raw.dtype, np.datetime64):
                return (epoch + np.timedelta64(int(t_numeric * 1e9), "ns")).astype(times_raw.dtype)
            else:
                return t_numeric

        # Scan adjacent samples for sign changes around target
        offsets = values - target
        for i in range(len(times) - 1):
            a, b = offsets[i], offsets[i + 1]
            if np.isnan(a) or np.isnan(b):
                continue

            # Check if the segment [i, i+1] contains a crossing
            if a == 0:
                t_cross = times[i]
            elif b == 0:
                t_cross = times[i + 1]
            elif a * b > 0:
                # Same sign, no crossing
                continue
            else:
                # Signs differ: refine crossing time within [times[i], times[i+1]]
                t_lo, t_hi = times[i], times[i + 1]
                v_lo, v_hi = values[i], values[i + 1]

                # Simple bisection using the interpolator to locate where
                # interpolated value == target.
                for _ in range(32):  # sufficient for typical float precision
                    t_mid = 0.5 * (t_lo + t_hi)
                    v_mid = interp.interpolate(t_mid, [t_lo, t_hi], [v_lo, v_hi], timeout)
                    if v_mid is None:
                        break
                    if (v_lo - target) * (v_mid - target) <= 0:
                        t_hi, v_hi = t_mid, v_mid
                    else:
                        t_lo, v_lo = t_mid, v_mid
                else:
                    t_cross = 0.5 * (t_lo + t_hi)
                    # Determine direction based on refined endpoints
                    a, b = v_lo - target, v_hi - target
                    direction = 1 if a < 0 and b > 0 else -1 if a > 0 and b < 0 else 0
                    crossings.append({
                        "time": _to_time_axis(t_cross),
                        "direction": direction,
                        "label": label,
                        "target": target,
                    })
                    continue

                # Fallback: use mid-point without bisection success
                t_cross = 0.5 * (times[i] + times[i + 1])

            # If we got here via exact endpoint or fallback, infer direction
            direction = 0
            if a < 0 and b > 0:
                direction = 1
            elif a > 0 and b < 0:
                direction = -1

            crossings.append({
                "time": _to_time_axis(t_cross),
                "direction": direction,
                "label": label,
                "target": target,
            })

        cross_df = pd.DataFrame(crossings)
        return self._constructor(cross_df).__finalize__(self)

    def _apply_schema(self, coerce: bool, validate: bool) -> None:
        
        if self.SCHEMA is None:
            return

        # Report missing columns rather than silently adding NA
        missing = [col for col, _ in self.SCHEMA if col not in self.columns]
        if missing:
            raise Exception(
                f"Missing expected schema columns: {missing}; "
                f"present columns: {list(self.columns)}"
            )

        if coerce:
            self._cast_columns()

        if validate:
            self._validate_columns()

    def _cast_columns(self) -> None:
        time_formats = self.TIME_FORMATS or {}

        for col, types in self.SCHEMA:
            if col not in self.columns:
                continue

            series = self[col]

            # Time-like columns: use pandas to_datetime with declared format
            if col in time_formats and time_formats[col] != "TBD":
                fmt_spec = time_formats[col]

                # Single explicit format string: preserve strict behaviour and
                # raise on invalid parses.
                if isinstance(fmt_spec, str):
                    self[col] = pd.to_datetime(series, format=fmt_spec, errors="raise")
                    continue

                # Multiple formats: attempt each in order, allowing a mixture of
                # datetime objects and differently-formatted strings. This is
                # useful for missions where a given column (e.g. SCET) may
                # appear in more than one textual representation.
                if isinstance(fmt_spec, (list, tuple)):

                    def _is_datetime_like(v):
                        return isinstance(v, (datetime, pd.Timestamp, np.datetime64))

                    if pd.api.types.is_object_dtype(series):
                        is_dt = series.apply(_is_datetime_like)
                    else:
                        # Non-object dtypes are unlikely to be mixed, but treat
                        # them as non-datetime to be safe.
                        is_dt = pd.Series(False, index=series.index)

                    # Start by preserving any existing datetime-like values
                    result = pd.to_datetime(series.where(is_dt, None), errors="coerce")

                    for fmt in fmt_spec:
                        remaining = result.isna()
                        if not remaining.any():
                            break
                        to_parse = series[remaining]
                        parsed = pd.to_datetime(to_parse, format=fmt, errors="coerce")
                        result.loc[remaining] = parsed

                    # Only overwrite the column if we successfully parsed at
                    # least one value; otherwise leave as-is so callers can
                    # handle unexpected formats themselves.
                    if result.notna().any():
                        self[col] = result
                    continue

                # Unknown fmt_spec type: fall through and treat as a normal column

            # Non-time columns: attempt simple casting based on primary type
            allowed = types if isinstance(types, tuple) else (types,)
            non_none_types = [t for t in allowed if t is not None]
            if not non_none_types:
                continue
                 

            if len(non_none_types) == 1:
                target_type = non_none_types[0]

                # Special handling for dict columns coming from JSON-like strings
                if target_type is dict:
                    self[col] = series.apply(
                        lambda v: json.loads(v.replace("'", '"')) if isinstance(v, str) else v
                    )
                    continue

                try:
                    self[col] = series.astype(target_type)
                except Exception:
                    def _cast_value(v, _t=target_type):
                        if pd.isna(v):
                            return v
                        if isinstance(v, _t):
                            return v
                        try:
                            return _t(v)
                        except Exception:
                            return v
                    self[col] = series.apply(_cast_value)

            else:
                def _cast_value(v):
                    if pd.isna(v):
                        return v
                    if isinstance(v, tuple(non_none_types)):
                        return v
                    for t in non_none_types:
                        try:
                            if t is dict:
                                if isinstance(v, dict):
                                    return v
                                if isinstance(v, str):
                                    return json.loads(v.replace("'", '"'))
                                continue
                            return t(v)
                        except Exception:
                            continue
                    return v

                self[col] = series.apply(_cast_value)

    def _validate_columns(self) -> None:
        for col, types in self.SCHEMA:
            if col not in self.columns:
                continue

            series = self[col]
            allowed = types if isinstance(types, tuple) else (types,)
            allow_none = any(t is None for t in allowed)
            allowed_non_none = tuple(t for t in allowed if t is not None)

            def _is_valid(v):
                if pd.isna(v):
                    # Treat NaN/NaT as None-equivalent for validation purposes
                    return allow_none or bool(allowed_non_none)
                if not allowed_non_none:
                    return True
                return isinstance(v, allowed_non_none)

            bad_mask = ~series.apply(_is_valid)
            if bad_mask.any():
                bad_indices = list(series.index[bad_mask])[:5]
                raise Exception(
                    f"Column '{col}' has values with invalid type for schema {types}. "
                    f"Example bad indices: {bad_indices}"
                )

    @property
    def valid(self):
        if self.SCHEMA is None:
            return True
        try:
            # Re-run validation without casting
            self._validate_columns()
            return True
        except Exception:
            return False

    def timer(self):
        """Return a :class:`_TimerProxy` that prints the wall-clock duration of
        the next chained method call.

        Example
        -------
        >>> df.timer().eq('label', 'temp')
        eq: 0.0003s
        """
        return _TimerProxy(self)

    def _filter(self, result, minimum, maximum, exactly):
        """Raise ValueError if result length violates count constraints."""
        n = len(result)
        if exactly is not None:
            if (minimum is not None or maximum is not None):
                logger.warning('"exactly" overrides "minimum"/"maximum" when all are set.')
            if n != exactly:
                raise ValueError(f'Expected exactly {exactly} rows, got {n}.')
        else:
            if minimum is not None and n < minimum:
                raise ValueError(f'Expected at least {minimum} rows, got {n}.')
            if maximum is not None and n > maximum:
                raise ValueError(f'Expected at most {maximum} rows, got {n}.')
        return result

    def _get_column_for_filter(self, column):
        # Exact column name wins.
        if column in self.columns:
            return self[column]

        def _parse_bracket_path(spec):
            s = spec
            n = len(s)
            if n == 0:
                return None
            # Parse leading NAME (Python identifier style)
            i = 0
            if not (s[0].isalpha() or s[0] == "_"):
                return None
            i += 1
            while i < n and (s[i].isalnum() or s[i] == "_"):
                i += 1
            base = s[:i]
            keys = []
            while i < n:
                if s[i] != "[":
                    return None
                i += 1
                if i >= n or s[i] not in ("'", '"'):
                    return None
                quote = s[i]
                i += 1
                start = i
                while i < n and s[i] != quote:
                    i += 1
                if i >= n:
                    return None
                key = s[start:i]
                keys.append(key)
                i += 1  # skip closing quote
                if i >= n or s[i] != "]":
                    return None
                i += 1  # skip closing bracket
            if i != n:
                return None
            return base, keys

        # Bracket syntax: arguments['rts_no']['inner'] ...
        parsed = _parse_bracket_path(column)
        if parsed is not None:
            base, keys = parsed
            if base in self.columns:
                series = self[base]

                def _extract(value):
                    v = value
                    for key in keys:
                        if not isinstance(v, dict):
                            return np.nan
                        v = v.get(key, np.nan)
                    return v

                return series.map(_extract)

        # Fallback: dotted dict access (for backwards compatibility).
        if "." in column:
            base, *keys = column.split(".")
            if base in self.columns:
                series = self[base]

                def _extract(value):
                    v = value
                    for key in keys:
                        if not isinstance(v, dict):
                            return np.nan
                        v = v.get(key, np.nan)
                    return v

                return series.map(_extract)

        # Default behavior: treat as a normal column (will raise if missing).
        return self[column]

    def eq(self, column, value, minimum=None, maximum=None, exactly=None, tolerance=0):
        """Return rows where ``column == value``.

        Parameters
        ----------
        column : str
        value : any
        tolerance : float
            When non-zero and ``value`` is numeric, matches rows within
            ``abs(col - value) <= tolerance``.
        minimum, maximum, exactly : int or None
            Raise ``ValueError`` if result count violates constraint.
        """
        col = self._get_column_for_filter(column)

        # Treat comparisons to None as null checks for convenience.
        if value is None:
            result = self[col.isna()]
        elif tolerance and isinstance(value, (int, float)):
            result = self[(col - value).abs() <= tolerance]
        else:
            result = self[col == value]

        return self._filter(result, minimum, maximum, exactly)

    def ne(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column != value``.

        When ``value`` is ``None``, this behaves as a non-null check
        (rows where ``column`` is not null).
        """
        col = self._get_column_for_filter(column)

        if value is None:
            result = self[col.notna()]
        else:
            result = self[col != value]

        return self._filter(result, minimum, maximum, exactly)

    def gt(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column > value``."""
        col = self._get_column_for_filter(column)
        return self._filter(self[col > value], minimum, maximum, exactly)

    def lt(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column < value``."""
        col = self._get_column_for_filter(column)
        return self._filter(self[col < value], minimum, maximum, exactly)

    def gte(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column >= value``."""
        col = self._get_column_for_filter(column)
        return self._filter(self[col >= value], minimum, maximum, exactly)

    def lte(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column <= value``."""
        col = self._get_column_for_filter(column)
        return self._filter(self[col <= value], minimum, maximum, exactly)

    def isin(self, column, values, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column`` value is in ``values``."""
        col = self._get_column_for_filter(column)
        return self._filter(self[col.isin(values)], minimum, maximum, exactly)

    def notin(self, column, values, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column`` value is not in ``values``."""
        col = self._get_column_for_filter(column)
        return self._filter(self[~col.isin(values)], minimum, maximum, exactly)

    def dict_key_eq(self, column, key, value, minimum=None, maximum=None, exactly=None):
        """Return rows where a dict-valued ``column`` has ``key == value``.

        This is intended for columns that store dictionaries, such as the
        ``arguments`` column on EVR frames produced by ``extract_arguments``.
        Rows where the cell is not a dict or does not contain ``key`` are
        treated as non-matching and are not included in the result.
        """
        col = self[column]

        sentinel = object()

        def _matches(d):
            if not isinstance(d, dict):
                return False
            v = d.get(key, sentinel)
            if v is sentinel:
                return False
            return v == value

        mask = col.map(_matches)
        result = self[mask]
        return self._filter(result, minimum, maximum, exactly)

    def contains(self, column, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        """Return rows where string ``column`` contains ``substring``."""
        col = self._get_column_for_filter(column)
        mask = col.str.contains(substring, case=case_sensitive, na=False)
        return self._filter(self[mask], minimum, maximum, exactly)

    def doesnotcontain(self, column, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        """Return rows where string ``column`` does not contain ``substring``."""
        col = self._get_column_for_filter(column)
        mask = col.str.contains(substring, case=case_sensitive, na=False)
        return self._filter(self[~mask], minimum, maximum, exactly)

    def between(self, column, lower, upper, inclusive='both', minimum=None, maximum=None, exactly=None):
        """Return rows where ``lower <= column <= upper`` (configurable via ``inclusive``)."""
        col = self._get_column_for_filter(column)
        result = self[col.between(lower, upper, inclusive=inclusive)]
        return self._filter(result, minimum, maximum, exactly)

    def matches(self, column, pattern, minimum=None, maximum=None, exactly=None):
        """Return rows where string ``column`` matches regex ``pattern``."""
        col = self._get_column_for_filter(column)
        mask = col.str.match(pattern, na=False)
        return self._filter(self[mask], minimum, maximum, exactly)

    def before(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        """Return rows where the time column is before ``time``.

        Parameters
        ----------
        time_label : str or None
            Column to compare. Falls back to ``DEFAULT_TIME_LABEL``.
        inclusive : bool
            If True, includes rows where time == ``time``.
        """
        col = time_label or self.DEFAULT_TIME_LABEL
        if col is None:
            raise ValueError("time_label must be provided or set as DEFAULT_TIME_LABEL on the class.")
        result = self[self[col] <= time] if inclusive else self[self[col] < time]
        return self._filter(result, minimum, maximum, exactly)

    def after(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        """Return rows where the time column is after ``time``.

        Parameters
        ----------
        time_label : str or None
            Column to compare. Falls back to ``DEFAULT_TIME_LABEL``.
        inclusive : bool
            If True, includes rows where time == ``time``.
        """
        col = time_label or self.DEFAULT_TIME_LABEL
        if col is None:
            raise ValueError("time_label must be provided or set as DEFAULT_TIME_LABEL on the class.")
        result = self[self[col] >= time] if inclusive else self[self[col] > time]
        return self._filter(result, minimum, maximum, exactly)

    def lad(self, value=None, *, label_col=None, time_col=None):
        """LAD-style helper.

        When ``value`` is None (default), return a LAD-style view: one
        row per label, last in time — identical to the previous
        :pyattr:`lad` property.

        When ``value`` is not None, treat it as a label value and return
        the latest row for that label using ``label_col`` (default
        :attr:`LABEL_COL`) and ``time_col`` (default
        :attr:`DEFAULT_TIME_LABEL`).
        """
        label_col = label_col or self.LABEL_COL
        time_col = time_col or self.DEFAULT_TIME_LABEL

        if label_col is None:
            raise ValueError("LABEL_COL/label_col must be configured to use lad().")

        if value is None:
            # Original LAD behavior: one row per label, last in time.
            if label_col not in self.columns or time_col not in self.columns:
                return self.__class__(self.copy(), coerce=False, validate=False)

            idx = self.groupby(label_col)[time_col].idxmax()
            idx = list(idx)  # Preserve original order of labels
            return self.__class__(self.loc[idx].copy(), coerce=False, validate=False)

        # value-specific path: latest row for the given label.
        if label_col not in self.columns:
            raise ValueError(f"Label column {label_col!r} not present in frame.")

        df = self[self[label_col] == value]
        if df.empty:
            raise KeyError(f"Label {value!r} not found in {label_col!r}.")

        if time_col is not None and time_col in df.columns:
            idx = df[time_col].idxmax()
            row = df.loc[idx]
        else:
            # Fall back to last row if no usable time column.
            row = df.iloc[-1]

        row.__class__ = self.ROW_SERIES_CLASS
        return row

    @property
    def lad_view(self):
        """Backward-compatible LAD property: one row per label, last in time."""
        return self.lad(value=None)

    def lad_value(self, value, *, label_col=None, time_col=None, value_col=None, as_native=True):
        """Return the latest value for a given label as a scalar.

        This is a convenience wrapper around :meth:`lad` that:

        - looks up the latest row for the given label ``value``
        - extracts the column specified by ``value_col`` (default
          :attr:`VALUE_COL`)
        - optionally converts 0-d arrays / pandas scalars to native
          Python types when ``as_native`` is True.
        """
        value_col = value_col or self.VALUE_COL
        row = self.lad(value=value, label_col=label_col, time_col=time_col)
        scalar = row[value_col]

        if as_native:
            # Preserve None / NaN / non-scalar objects as-is.
            try:
                # pandas and numpy scalars have .item(); normal Python
                # scalars will raise AttributeError and be returned
                # unchanged.
                return scalar.item()  # type: ignore[attr-defined]
            except AttributeError:
                return scalar
        return scalar
