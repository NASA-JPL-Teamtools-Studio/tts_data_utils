# ADR 004: jpl_time Integration — First-Class Time Support in TtsDataFrame

**Status:** Accepted  
**Date:** 2026-08-08

---

## Context

`tts_data_utils` has listed `jpl_time` as a package dependency since early in the
`TtsDataFrame` era, but the dependency was never honored. Time columns in `TtsDataFrame`
subclasses are parsed and stored as `pd.Timestamp` (`datetime64[ns]`) using Python's
`datetime` / `pd.to_datetime()` pipeline, with `TIME_FORMATS` providing strptime/strftime
format strings for CSV round-tripping.

Three concrete problems arise from this state:

1. **Leap-second blindness.** `datetime64[ns]` is POSIX-based and does not count leap
   seconds. Converting between UTC and SCLK across a leap-second boundary (e.g.
   2016-12-31T23:59:60) produces silently wrong results when `datetime` is used as the
   intermediate. For anomaly investigation this matters.

2. **No mission time system support.** Users who want `row['scet']` to return a `jpl_time.Time`
   object — so they can call `.to_lmst()`, `.to_sclkd()`, `.to_ert()`, etc. — have no
   supported path. They must construct `Time` objects by hand from the string in the cell.

3. **Mixed time system ingestion.** Some missions (e.g. M20) ingest telemetry where a time
   column may arrive in SCLK or LMST, not UTC. Without a jpl_time-aware parse layer, the
   subclass must do its own ad-hoc conversion in `_read_csv_to_df`.

`jpl_time` 2.0 (Flora Ridenhour, PR #3 on `nasa-jpl/jpl_time`, branch `jpl-time-2.0`)
resolves the primary performance objection to using jpl_time broadly: UTC parsing,
formatting, TAI/ET/GPS conversions, timezone math, and all duration arithmetic are
expected to be implemented in pure Python using a built-in leap-second table.

> **⚠ Verify before implementing:** The scope of jpl_time 2.0's pure-Python coverage
> (specifically which time systems and operations are SPICE-free) must be confirmed
> with Flora before implementation begins. Do not assume the above list is complete or
> final — check PR #3 on `nasa-jpl/jpl_time` for the current state.

SPICE kernels are expected to remain required only for mission-specific time systems (SCLK, LMST, LTST, ERT/ETT). The jpl_time 1.x objection — that every `Time()` construction triggered a SPICE kernel call — is expected to be moot for 2.0 and for all UTC-only usage, but this must be verified.

**Scope exclusion.** `DataContainer` and `DataItem` are excluded from this design. They are
deprecated in favor of `TtsDataFrame` (see ADR 001) and will not receive new features.

**Performance stressing case.** The canonical stressing case for this integration is 10M
rows at 512 Hz (robotics missions). At that scale, scalar Python loops per-row are not
acceptable. The design stores time values as `float64` (ET seconds) — a NumPy-native dtype
that supports fully vectorized sort, filter, and arithmetic on the column without any Python
object overhead.

---

## Decision

### 1. SCHEMA is the authoritative declaration of time column type

A `TtsDataFrame` subclass declares the type of each time column in its `SCHEMA`:

```python
from jpl_time import Time

class FssEhaFrame(TtsDataFrame):
    SCHEMA = [
        ('scet', Time),
        ('label', str),
        ('value', float),
    ]
    TIME_FORMATS = {
        'scet': '%Y-%jT%H:%M:%S.%f',
    }
```

If a column's SCHEMA type is `jpl_time.Time`, the framework treats it as a jpl_time time
column and applies the behaviors below. Columns whose SCHEMA type is `datetime`,
`pd.Timestamp`, or any non-`Time` type continue to use the existing `datetime64[ns]`
pipeline unchanged. There is no new class variable; the SCHEMA is the single source of
truth (see TTS coding standard: prefer explicit over implicit).

### 2. Internal column storage: ET float64

Columns declared as `jpl_time.Time` in SCHEMA are stored internally as `float64` columns
of ET seconds (TDB seconds past J2000). This gives:

- Fully vectorized sort and filter (NumPy `float64` comparisons)
- Correct arithmetic across leap-second boundaries (ET is continuous)
- No SPICE requirement for UTC-family time systems when jpl_time 2.0+ is installed

**Parse path (CSV ingest / construction):** Each string value is parsed via
`Time.strptime(value, format)` using the strptime format from `TIME_FORMATS`, which yields
a `Time` object. The `.et` float is extracted and stored. If `TIME_FORMATS` has no entry
for the column, `Time(value)` is called directly (jpl_time's auto-detect parser).

**Format path (to_csv / display):** The stored float is wrapped as `Time(et_value)` and
formatted via `Time(et_value).to_utc_strftime(format)` using the strftime format from
`TIME_FORMATS`. If `TIME_FORMATS` has no entry, `Time(et_value).to_utc()` is used.

### 3. TtsRowSeries: automatic Time conversion on scalar access

`TtsRowSeries.__getitem__(key)` checks the parent frame's SCHEMA for the column type. If
the declared type is `jpl_time.Time`, the raw stored `float` is wrapped and returned as
`Time(value)`. For all other column types, existing behavior is unchanged.

```python
row = frame.iloc[0]        # TtsRowSeries
row['scet']                # → jpl_time.Time  (if SCHEMA declares Time)
row.raw('scet')            # → float (ET seconds) — always the raw stored value
```

`row.raw(key)` is a new escape hatch that always returns the primitive stored value,
bypassing schema-driven conversion. It is intended for performance-sensitive code paths and
for users who need the underlying number.

`TtsRowSeries` instances created without a parent frame (e.g. standalone construction)
return the raw stored value and do not apply schema-driven conversion, since no SCHEMA is
available.

### 4. Duration/timedelta coercion at method boundaries

A private helper `_to_seconds(x)` is added to `data_frame.py`. It accepts:
- `float` or `int` (assumed seconds — unchanged behavior)
- `datetime.timedelta`
- `pandas.Timedelta`
- `jpl_time.Duration`

and returns a `float` of seconds. The `isinstance` check for `jpl_time.Duration` is
explicit; `jpl_time` is a required dependency of `tts_data_utils` core. Duck-typing is not
used here (TTS coding standard: prefer explicit over implicit).

The following method parameters are widened to accept all four types:
- `moving_average(window=...)` (was `window_seconds: float`)
- `time_average(freq=...)` (unchanged — pandas offset strings still work; `_to_seconds`
  applies when a numeric or Duration type is passed)
- `at_times_where(tolerance=...)` (was `number or pd.Timedelta`)
- `derive_values(timeout=...)` (float or Duration)

### 5. Time point coercion at filter method boundaries

Future time-filtering methods (`before`, `after`, `between`, and `at_times_where`) compare
user-supplied time arguments against the ET float64 column. A private helper `_to_et(x)`
is added to `data_frame.py` to normalize time arguments at these method boundaries:

- `float` or `int` — assumed to be ET seconds already; returned as-is
- `jpl_time.Time` — `.et` attribute extracted
- `datetime.datetime` — converted via `jpl_time.Time(x).et` (UTC assumed)
- `pd.Timestamp` — converted via `jpl_time.Time(x.to_pydatetime()).et`

**Both `jpl_time.Time` and `datetime.datetime` must be accepted.** Many callers will not
have `jpl_time` imported and will pass plain `datetime` objects. `datetime.datetime` is the
correct interoperability type for Python users who are not jpl_time-aware.

Usage at a filter method boundary:
```python
def before(self, t, time_col=None):
    col = time_col or self.DEFAULT_TIME_LABEL
    return self[self[col] < _to_et(t)]
```

### 6. No vectorized bulk conversion at this time

Vectorized bulk conversion (array of strings → array of ET floats without a Python loop)
is deferred. The 10M-row performance budget is met by storing as `float64` — the expensive
conversion from strings to ET floats happens once at ingest, and all downstream operations
(sort, filter, average, derive) operate on the float column natively. Ingest of a 10M-row
CSV at one SPICE call per row is slow; this is expected and acceptable (users who ingest at
that scale should pre-convert and store the float column). Vectorized bulk parse will be
addressed in a follow-on ticket if benchmarking shows it is necessary in practice.

---

## Consequences

**Positive:**
- Leap-second-correct arithmetic for SCLK-correlated timestamps
- `row['scet']` returns `jpl_time.Time` for declared columns — users get `.to_lmst()`,
  `.to_sclkd()`, `.to_ert()` etc. for free
- Duration, timedelta, and float seconds all work at API boundaries — jpl_time is a
  first-class partner without being a forced dependency for all users
- ET float64 storage is the fastest possible internal representation for sort and filter
- Fully backward compatible — existing subclasses with `datetime` or no SCHEMA entry are
  unaffected

**Negative / Watch items:**
- `df['scet']` now returns a `float64` Series for jpl_time-typed columns, not a
  `datetime64` Series. Code that calls `df['scet'].dt.strftime(...)` or passes the column
  to a pandas datetime-aware operation will break. Subclasses must migrate explicitly.
- SPICE kernels must still be loaded before `row['scet'].to_sclkd()` or any other
  mission-specific conversion is called. This is unchanged from jpl_time 1.x behavior —
  the integration does not make kernel loading automatic.
- `TtsRowSeries` `__getitem__` override adds one dict-lookup overhead per scalar access.
  This is acceptable for interactive / row-by-row use; bulk access should use `df['col']`.
- jpl_time is now a hard dependency of `tts_data_utils` core (it was already listed but
  not enforced). Missions that cannot install jpl_time must not declare `Time` in their
  SCHEMA; they continue to use the `datetime` path.

---

## References

- `src/tts_data_utils/core/data_frame.py` — TtsDataFrame / TtsRowSeries implementation
- `docs/adr/001-tts-data-frame-pivot.md` — DataContainer → TtsDataFrame pivot (jpl_time integration explicitly excludes DataContainer)
- `docs/roadmap.md` — roadmap item 8: jpl_time integration
- `nasa-jpl/jpl_time` PR #3 (branch `jpl-time-2.0`, Flora Ridenhour) — SPICE-free core
- `NASA-JPL-Teamtools-Studio/tts_data_utils` issue #16 (closed — superseded by this ADR)
- `teamtools_documentation/CONTEXT.md` — time system glossary (SCET, UTC, TAI, ET, SCLK, LMST, LTST, ERT, ETT, GPS, JD)
