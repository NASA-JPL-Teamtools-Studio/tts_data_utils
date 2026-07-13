import time
import pandas as pd
import numpy as np
import json
from datetime import datetime
from tts_dante.interpolators.interpolators import StepInterpolator, LinearInterpolator
from tts_data_utils.core.expr_engines import (
    _FilterExprError, _filter_engine,
    _MathExprError, _math_engine, _MathTransformer,
)
from tts_utilities.logger import create_logger

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


class TtsRowSeries(pd.Series):
    pass


class TtsColumnSeries(pd.Series):
    pass


def _strict_unique(s):
    """pivot_table aggfunc that passes through single values but raises on
    genuinely conflicting records (different values for the same index/column
    key). Exact duplicates — identical value appearing more than once — are
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
    _metadata = ["name", "metadata", "_subcontainers"]

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
    SUBCONTAINER_KEY = None

    # Expression engine configuration.
    MATH_ENGINE = _math_engine
    MATH_TRANSFORMER = _MathTransformer

    def __init__(self, *args, name=None, metadata=None, coerce=None, validate=None, csv_path=None, **kwargs):
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

        if coerce or validate:
            self._apply_schema(coerce=coerce, validate=validate)

    def moving_average(self, window_seconds, label_value=None, time_col=None, label_col=None, value_col=None):
        """Return a time-based moving average over ``window_seconds`` seconds."""
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

        if label_value is not None:
            if label_col is None or label_col not in df.columns:
                raise ValueError(
                    "label_value was provided but LABEL_COL/label_col is not configured "
                    "or not present in the frame."
                )
            df = df[df[label_col].eq(label_value)].copy()

        if label_value is None and label_col is not None and label_col in df.columns:
            unique_labels = pd.unique(df[label_col].dropna())
            if len(unique_labels) > 1:
                logger.warning(
                    "moving_average called on a frame containing multiple labels; "
                    "the aggregated result may not be meaningful."
                )

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

        return self._constructor(smoothed).__finalize__(self)

    def block_average(self, block_size, label_value=None, time_col=None, label_col=None, value_col=None):
        """Return a simple block (bin) average over non-overlapping blocks."""
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

        if label_value is not None:
            if label_col is None or label_col not in df.columns:
                raise ValueError(
                    "label_value was provided but LABEL_COL/label_col is not configured "
                    "or not present in the frame."
                )
            df = df[df[label_col].eq(label_value)].copy()

        sort_cols = []
        if label_col is not None and label_col in df.columns:
            sort_cols.append(label_col)
        if time_col is not None and time_col in df.columns:
            sort_cols.append(time_col)
        if sort_cols:
            df = df.sort_values(sort_cols)

        def _block_group(group):
            n = len(group)
            block_ids = np.arange(n) // block_size
            group = group.copy()
            group["_block_id"] = block_ids

            agg = group.groupby("_block_id", as_index=False).agg({value_col: "mean"})
            first = group.groupby("_block_id", as_index=False).nth(0)

            first = first.drop(columns=["_block_id"])
            agg[value_col] = agg[value_col].values
            first[value_col] = agg[value_col].values
            return first

        if label_col is not None and label_col in df.columns:
            reduced = df.groupby(label_col, group_keys=False).apply(_block_group)
        else:
            reduced = _block_group(df)

        return self._constructor(reduced).__finalize__(self)

    @classmethod
    def _read_csv_to_df(cls, filepath, *args, **kwargs):
        """Hook for subclasses to customize how CSVs are read."""
        return pd.read_csv(filepath, *args, **kwargs)

    @property
    def _constructor(self):
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
        """Retrieve a named subcontainer attached to ``row_key``."""
        return self._subcontainers.get(row_key, {}).get(name)

    def set_subcontainer(self, row_key, name: str, container):
        """Attach a named subcontainer to ``row_key``."""
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

    def select_wide(self, labels=None, label_col=None, value_col=None, index_col=None, how='outer'):
        """Return a wide-form DataFrame with one column per label."""
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

    def at_times_where(self, expr: str, *, tolerance=None, label_col=None, value_col=None, index_col=None):
        """Return all rows whose timestamp matches records where the expression is True."""
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

        qt_arr = np.sort(qualifying_times.values)
        row_times = self[index_col].values
        tol_td = np.timedelta64(int(tolerance.value), 'ns')

        lo = np.searchsorted(qt_arr, row_times - tol_td, side='left')
        hi = np.searchsorted(qt_arr, row_times + tol_td, side='right')
        return self[lo < hi]

    @property
    def wide(self):
        index = self.DEFAULT_TIME_LABEL
        columns = self.LABEL_COLUMN
        values = self.VALUE_COL
        id_cols = [index, columns]
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
        """Filter rows where the given boolean expression is True."""
        return self[_filter_engine.parse(expr).eval(self)]

    def get_interpolator(self, label: str):
        """Return the interpolator to use for ``label`` in :meth:`derive_values`."""
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
        """Compute a derived label from a math expression over existing labels."""
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
                rows.append({index_col: t, label_col: derived_name, value_col: result})
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
                rows.append({index_col: t, label_col: derived_name, value_col: result})

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
        """Find times where a label crosses a given value using interpolation."""
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
            return pd.DataFrame(columns=["time", "direction", "label", "target"])

        df = df.sort_values(time_col)
        times_raw = pd.to_datetime(df[time_col])
        if np.issubdtype(times_raw.dtype, np.datetime64):
            epoch = np.datetime64("1970-01-01T00:00:00Z")
            times = (times_raw.values - epoch) / np.timedelta64(1, "s")
        else:
            times = df[time_col].astype(float).values

        values = df[value_col].astype(float).values

        if len(times) < 2:
            return pd.DataFrame(columns=["time", "direction", "label", "target"])

        interp = interpolator if interpolator is not None else LinearInterpolator()
        crossings = []

        def _to_time_axis(t_numeric):
            if np.issubdtype(times_raw.dtype, np.datetime64):
                return (epoch + np.timedelta64(int(t_numeric * 1e9), "ns")).astype(times_raw.dtype)
            else:
                return t_numeric

        offsets = values - target
        for i in range(len(times) - 1):
            a, b = offsets[i], offsets[i + 1]
            if np.isnan(a) or np.isnan(b):
                continue

            if a == 0:
                t_cross = times[i]
            elif b == 0:
                t_cross = times[i + 1]
            elif a * b > 0:
                continue
            else:
                t_lo, t_hi = times[i], times[i + 1]
                v_lo, v_hi = values[i], values[i + 1]

                for _ in range(32):
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
                    a, b = v_lo - target, v_hi - target
                    direction = 1 if a < 0 and b > 0 else -1 if a > 0 and b < 0 else 0
                    crossings.append({
                        "time": _to_time_axis(t_cross),
                        "direction": direction,
                        "label": label,
                        "target": target,
                    })
                    continue

                t_cross = 0.5 * (times[i] + times[i + 1])

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

        return pd.DataFrame(crossings)

    def _apply_schema(self, coerce: bool, validate: bool) -> None:
        if self.SCHEMA is None:
            return

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
            if col in time_formats and time_formats[col] != "TBD":
                fmt = time_formats[col]
                self[col] = pd.to_datetime(series, format=fmt, errors="raise")
                continue

            allowed = types if isinstance(types, tuple) else (types,)
            non_none_types = [t for t in allowed if t is not None]
            if not non_none_types:
                continue

            if len(non_none_types) == 1:
                target_type = non_none_types[0]
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
            self._validate_columns()
            return True
        except Exception:
            return False

    def timer(self):
        """Return a :class:`_TimerProxy` that prints the wall-clock duration."""
        return _TimerProxy(self)

    # -------------------------------------------------------------------------
    # IDIOMATIC FILTER METHODS
    # -------------------------------------------------------------------------

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

    def eq(self, column, value, minimum=None, maximum=None, exactly=None, tolerance=0):
        """Return rows where ``column == value``."""
        if tolerance and isinstance(value, (int, float)):
            result = self[(self[column] - value).abs() <= tolerance]
        else:
            result = self[self[column] == value]
        return self._filter(result, minimum, maximum, exactly)

    def ne(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column != value``."""
        return self._filter(self[self[column] != value], minimum, maximum, exactly)

    def gt(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column > value``."""
        return self._filter(self[self[column] > value], minimum, maximum, exactly)

    def lt(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column < value``."""
        return self._filter(self[self[column] < value], minimum, maximum, exactly)

    def gte(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column >= value``."""
        return self._filter(self[self[column] >= value], minimum, maximum, exactly)

    def lte(self, column, value, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column <= value``."""
        return self._filter(self[self[column] <= value], minimum, maximum, exactly)

    def isin(self, column, values, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column`` value is in ``values``."""
        return self._filter(self[self[column].isin(values)], minimum, maximum, exactly)

    def notin(self, column, values, minimum=None, maximum=None, exactly=None):
        """Return rows where ``column`` value is not in ``values``."""
        return self._filter(self[~self[column].isin(values)], minimum, maximum, exactly)

    def contains(self, column, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        """Return rows where string ``column`` contains ``substring``."""
        mask = self[column].str.contains(substring, case=case_sensitive, na=False)
        return self._filter(self[mask], minimum, maximum, exactly)

    def doesnotcontain(self, column, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        """Return rows where string ``column`` does not contain ``substring``."""
        mask = self[column].str.contains(substring, case=case_sensitive, na=False)
        return self._filter(self[~mask], minimum, maximum, exactly)

    def between(self, column, lower, upper, inclusive='both', minimum=None, maximum=None, exactly=None):
        """Return rows where ``lower <= column <= upper``."""
        result = self[self[column].between(lower, upper, inclusive=inclusive)]
        return self._filter(result, minimum, maximum, exactly)

    def matches(self, column, pattern, minimum=None, maximum=None, exactly=None):
        """Return rows where string ``column`` matches regex ``pattern``."""
        mask = self[column].str.match(pattern, na=False)
        return self._filter(self[mask], minimum, maximum, exactly)

    def before(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        """Return rows where the time column is before ``time``."""
        col = time_label or self.DEFAULT_TIME_LABEL
        if col is None:
            raise ValueError("time_label must be provided or set as DEFAULT_TIME_LABEL on the class.")
        result = self[self[col] <= time] if inclusive else self[self[col] < time]
        return self._filter(result, minimum, maximum, exactly)

    def after(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        """Return rows where the time column is after ``time``."""
        col = time_label or self.DEFAULT_TIME_LABEL
        if col is None:
            raise ValueError("time_label must be provided or set as DEFAULT_TIME_LABEL on the class.")
        result = self[self[col] >= time] if inclusive else self[self[col] > time]
        return self._filter(result, minimum, maximum, exactly)

    @property
    def lad(self):
        """Return a LAD-style view: one row per label, last in time."""
        label_col = self.LABEL_COL
        time_col = self.DEFAULT_TIME_LABEL

        if label_col not in self.columns or time_col not in self.columns:
            return self.__class__(self.copy(), coerce=False, validate=False)

        idx = self.groupby(label_col)[time_col].idxmax()
        idx = list(idx)
        return self.__class__(self.loc[idx].copy(), coerce=False, validate=False)