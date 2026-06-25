import pandas as pd
import numpy as np
import json
from datetime import datetime
from tts_data_utils.core.expr_engines import (
    _FilterExprError, _filter_engine,
    _MathExprError, _math_engine,
)

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

    def __init__(self, indexer, row_cls, col_cls):
        self._indexer = indexer
        self._row_cls = row_cls
        self._col_cls = col_cls

    def _wrap(self, result, key):
        if isinstance(result, pd.Series):
            if isinstance(key, tuple) and len(key) >= 2 and _is_scalar_selector(key[1]):
                result.__class__ = self._col_cls
            else:
                result.__class__ = self._row_cls
        return result

    def __getitem__(self, key):
        return self._wrap(self._indexer[key], key)

    def __setitem__(self, key, value):
        self._indexer[key] = value

    def __getattr__(self, name):
        return getattr(self._indexer, name)


class TtsDataFrame(pd.DataFrame):
    """Base DataFrame subclass for tts_data_utils.

    Stores lightweight container-style metadata (``name`` and ``metadata``)
    and ensures subclasses are preserved across pandas operations via the
    ``_constructor`` hook and ``_metadata``.
    """

    # Attributes in this list are copied by pandas when creating new
    # objects via methods like .copy(), .loc, .sort_values(), etc.
    _metadata = ["name", "metadata"]

    # Optional associated row class for ergonomic row views (not used for typing).
    ROW_ITEM_CLS = None

    # Container-level schema: list of (column_name, type or tuple of types)
    SCHEMA = None

    # Optional mapping of time-like columns to strptime/strftime formats
    TIME_FORMATS = {}

    # Default column used for time-based operations; subclasses should override.
    DEFAULT_TIME_LABEL = None

    ROW_SERIES_CLASS = TtsRowSeries

    COLUMN_SERIES_CLASS = TtsColumnSeries

    LABEL_COL = None

    VALUE_COL = None

    LABEL_COLUMN = None

    def __init__(self, *args, **kwargs):
        # Pull container-style metadata and validation flags out of kwargs
        name = kwargs.pop("name", None)
        metadata = kwargs.pop("metadata", None)
        coerce = kwargs.pop("coerce", True)
        validate = kwargs.pop("validate", True)

        # Optional CSV-based construction
        csv_path = kwargs.pop("csv_path", None)
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


        if coerce or validate:
            self._apply_schema(coerce=coerce, validate=validate)

    @classmethod
    def _read_csv_to_df(cls, filepath, *args, **kwargs):
        """Hook for subclasses to customize how CSVs are read.

        Default implementation simply calls :func:`pandas.read_csv`.
        """
        return pd.read_csv(filepath, *args, **kwargs)

    @property
    def _constructor(self):  # pragma: no cover - exercised indirectly
        cls = type(self)
        def _internal_constructor(*args, **kwargs):
            kwargs['coerce'] = False
            kwargs['validate'] = False
            return cls(*args, **kwargs)
        return _internal_constructor

    def __getitem__(self, key):
        result = super().__getitem__(key)
        if isinstance(result, pd.Series):
            result.__class__ = self.COLUMN_SERIES_CLASS
        return result

    @property
    def loc(self):
        return _SeriesWrappingIndexer(super().loc, self.ROW_SERIES_CLASS, self.COLUMN_SERIES_CLASS)

    @property
    def iloc(self):
        return _SeriesWrappingIndexer(super().iloc, self.ROW_SERIES_CLASS, self.COLUMN_SERIES_CLASS)

    def xs(self, key, axis=0, level=None, drop_level=True):
        result = super().xs(key, axis=axis, level=level, drop_level=drop_level)
        if isinstance(result, pd.Series):
            result.__class__ = self.ROW_SERIES_CLASS if axis in (0, 'index') else self.COLUMN_SERIES_CLASS
        return result

    def iterrows(self):
        for idx, row in super().iterrows():
            row.__class__ = self.ROW_SERIES_CLASS
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

    def pivot_table(self):
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

    def derive_values(
        self,
        expr: str,
        *,
        interpolator=None,
        timeout=None,
        label_col=None,
        value_col=None,
        index_col=None,
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
            Defaults to ``StepInterpolator()``.
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
        from tts_dante.interpolators.interpolators import StepInterpolator

        label_col = label_col or self.LABEL_COL
        value_col = value_col or self.VALUE_COL
        index_col = index_col or self.DEFAULT_TIME_LABEL

        if label_col is None:
            raise ValueError("label_col must be provided or set as LABEL_COL on the class.")
        if value_col is None:
            raise ValueError("value_col must be provided or set as VALUE_COL on the class.")
        if index_col is None:
            raise ValueError("index_col must be provided or set as DEFAULT_TIME_LABEL on the class.")

        if interpolator is None:
            interpolator = StepInterpolator()

        if '=' not in expr:
            raise ValueError(
                f"derive_values expr must be an assignment 'name = expression', got {expr!r}")
        derived_name, rhs = expr.split('=', 1)
        derived_name = derived_name.strip()

        parsed = _math_engine.parse(rhs.strip())

        grouped = self.groupby(label_col)
        label_data = {}
        for lbl in parsed.labels:
            if lbl not in grouped.groups:
                raise _MathExprError(f"Label {lbl!r} not found in {label_col!r}.")
            grp = grouped.get_group(lbl).sort_values(index_col)
            label_data[lbl] = (grp[index_col].tolist(), grp[value_col].tolist())

        all_times = sorted({t for times, _ in label_data.values() for t in times})

        rows = []
        for t in all_times:
            slot = {}
            valid = True
            for lbl, (times, vals) in label_data.items():
                v = interpolator.interpolate(t, times, vals, timeout)
                if v is None:
                    valid = False
                    break
                slot[lbl] = v
            if not valid:
                continue
            try:
                result = parsed.eval(slot)
            except _MathExprError:
                continue
            rows.append({index_col: t, label_col: derived_name, value_col: result})

        if not rows:
            return type(self)(validate=False, coerce=False)
        return type(self)(rows, validate=False, coerce=False)

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
                fmt = time_formats[col]
                self[col] = pd.to_datetime(series, format=fmt, errors="raise")
                continue

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

    def eq(self, column, value):
        if isinstance(value, str):
            return self.query(f'{column} == "{value}"')
        else:
            return self.query(f'{column} == {value}')