# Developer Guide: Working with TtsDataFrame

This guide is for developers who want to:
- Understand the intent and design of `tts_data_utils`
- Create a new data type for their project by extending `TtsDataFrame` or work on an existing extension
- Use the features built into the framework (filtering, display, diffing, lorem ipsum)

If you are looking for API reference docs, see the auto-generated API reference in `docs/` (built with Sphinx). This guide covers the *why* and *how* at the design level.

---

## 1. Why TtsDataFrame?

### The problem with raw pandas

Pandas is one of the most powerful data analysis libraries in Python, and it is a core dependency of `tts_data_utils`. But for a team of systems engineers, a few things about raw pandas are painful:

- **Discovery is hard.** `df.loc[:, 'my_col'] > threshold` works, but `df.gt('my_col', threshold)` is much easier to find and understand, especially when quickly reviewing large amounts of work written by another engineer, an AI agent, or even yourself during a previous workday.
- **No shared vocabulary.** Different people write the same operation ten different ways. Across 25 repos, this compounds quickly.
- **No metadata.** A raw `DataFrame` doesn't know its name, where it came from, or what its columns mean.
- **No display contract.** Printing a DataFrame in a Jupyter notebook is functional but unstyled. Engineering reports need tables with color-coded rows, expandable sub-tables, and consistent formatting.

### Why not a custom container?

The predecessor to `TtsDataFrame` was `DataContainer` — a custom list-like class that held one `DataItem` per row. It solved the discovery and vocabulary problems well, but at a cost:

- **Performance ceiling** around ~1 million rows, after which Python object overhead dominates
- **Math is slow** — derive operations that should be vectorized had to loop over rows
- **Poor interoperability** — third-party pandas-compatible tools don't know what to do with a `DataContainer`

### Why TtsDataFrame works

`TtsDataFrame` is a *subclass* of `pd.DataFrame`. This means:

- Every pandas method works on it out of the box
- The `_constructor` hook ensures that operations like `.copy()`, `.loc[]`, and `.sort_values()` return the same subclass, not a plain DataFrame
- NumPy-backed math operations run in C, not Python — orders of magnitude faster than looping
- Domain methods live right on the object, discoverable via tab-completion

> **A note on vectorization**: When you write `self[self['col'] > value]`, pandas translates this into a NumPy boolean mask operation that runs in compiled C code. This is orders of magnitude faster than looping over rows in Python. The reason: Python executes one object at a time, with interpreter overhead on every step. NumPy hands a typed array directly to a C loop, with no per-element Python overhead. The rule of thumb: express operations as masks, aggregations, or `.apply()` with a scalar function — not as explicit `for row in df` loops. Only iterate over rows as a last resort. See the [pandas user guide on indexing](https://pandas.pydata.org/docs/user_guide/indexing.html) and [enhancing performance](https://pandas.pydata.org/docs/user_guide/enhancingperf.html) for background.

> **The mental model**: `TtsDataFrame` is a pandas DataFrame that also knows what kind of data it is, has a name, knows which column is "the time" and which is "the value," and can render itself as a styled HTML table.

---

## 2. How to Create a New Data Type

The pattern is: define a class that inherits from `TtsDataFrame` and set a handful of class-level attributes. Here is the minimal example:

```python
from tts_data_utils.core.data_frame import TtsDataFrame
from datetime import datetime
import pandas as pd

class CommWindowFrame(TtsDataFrame):
    SCHEMA = [
        ('station', str),
        ('start_time', (datetime, pd.Timestamp)),
        ('end_time', (datetime, pd.Timestamp)),
        ('max_elevation_deg', float),
    ]
    TIME_FORMATS = {
        'start_time': '%Y-%jT%H:%M:%S.%f',
        'end_time':   '%Y-%jT%H:%M:%S.%f',
    }
    DEFAULT_TIME_LABEL = 'start_time'
    LABEL_COL = 'station'
    VALUE_COL = 'max_elevation_deg'
```

That's it. You now have a named, schema-aware, time-aware data type. Here is what each class variable does and **why it exists**:

### `SCHEMA`

```python
SCHEMA = [('column_name', type_or_tuple_of_types), ...]
```

**Why:** Documents the expected columns and their types. This is a contract between the producer of the data (e.g., a query library) and the consumer. It can be used for validation on construction (configurable) and coercion. Even when not enforced strictly, it is the primary machine-readable documentation for what columns this frame expects — agents, linters, and future tooling can read this.

Critically, `SCHEMA` also enables **loss-free CSV deserialization**. Without it, pandas infers column types from the data — turning timestamps into strings, integers into floats, and booleans into objects. With `SCHEMA`, the framework knows to parse each column into the correct Python type, so loading a CSV produces the same typed frame as constructing one from live data.

Tip: Use a tuple of types when a column can be multiple types: `('scet', (datetime, pd.Timestamp, str))`.

### `TIME_FORMATS`

```python
TIME_FORMATS = {'column_name': 'strptime_format_string'}
```

**Why:** Spacecraft data sources frequently deliver timestamps as strings in non-standard formats (e.g., `2026-219T14:32:00.000` — year-day-of-year format). `TIME_FORMATS` tells the framework how to parse these strings into `datetime` objects. Without this, every consumer would need to know the format themselves.

The value is a dict so you can declare formats for **as many time columns as your data type has**. Spacecraft data commonly carries multiple time systems simultaneously — for example:

```python
TIME_FORMATS = {
    'scet':  '%Y-%jT%H:%M:%S.%f',  # Spacecraft Event Time (UTC)
    'sclk':  '%d-%f',              # Spacecraft Clock (ticks)
    'ert':   '%Y-%jT%H:%M:%S.%f',  # Earth Receive Time
    'lmst':  'Sol-%jM%H:%M:%S',    # Local Mean Solar Time (surface missions)
}
```

Each entry is independent — you only need to include the columns your data type actually has.

### `DEFAULT_TIME_LABEL`

```python
DEFAULT_TIME_LABEL = 'scet'
```

**Why:** Many operations — interpolation, filtering by time window, plotting — need to know "which column is the primary timestamp." Rather than passing the column name every time, you declare it once here and all time-aware methods use it automatically.

All time-aware methods should accept an explicit column override so individual call sites can use a different column when needed — `time_col` on the averaging methods (`moving_average`, `time_average`, `block_average`), and `index_col` on `at_times_where`. **Note:** the claim that *every* time-aware method supports this override has not been verified exhaustively — confirm for any method you rely on before documenting it as a guarantee. More importantly, because `DEFAULT_TIME_LABEL` is a class attribute, it can be changed for an **entire project at once**. Consider a Mars surface mission: during cruise, time is tracked in SCET (spacecraft event time). After landing, the operations team switches to LMST (local mean solar time). With `TtsDataFrame`, you update `DEFAULT_TIME_LABEL = 'lmst'` in one place and every downstream tool, report, and method in the entire TTS stack switches automatically — no hunting through individual call sites.

### `LABEL_COL` and `VALUE_COL`

```python
LABEL_COL = 'station'     # The column that names or identifies a row
VALUE_COL = 'max_elevation_deg'  # The column that is the primary measurement
```

**Why:** These are semantic markers. Display tools like `PowerTable` use them to make smart formatting decisions (bold the label, highlight the value). Diffing uses them to match rows across two frames. Having a standard vocabulary for "what is the label" and "what is the value" means tools don't need to be told for each data type.

Setting `LABEL_COL` and `VALUE_COL` to non-`None` also signals that this frame type uses **long-form** data — see [Long-form vs. Wide-form Data](#long-form-vs-wide-form-data) below for what that means and when it matters for filtering and derivation.

---

## 3. Adding Domain Methods

The real payoff of subclassing is attaching methods that speak the domain's language. This is not just a convenience — it is a deliberate strategy for reducing cognitive load.

Operations engineers work under pressure through reams of code, procedures, data, and technical writing. Every unnecessary mental burden — decoding a pandas expression, remembering which column holds the primary value, translating between raw indexing and engineering intent — is another straw on the camel's back. Domain methods written in natural, mission-specific language reduce that overhead. A method named `comm_windows.above_elevation(30.0)` or `evrs.warning_and_above()` communicates intent immediately to anyone reading the code, regardless of their pandas fluency. The goal is code that reads like the engineer thinks, not like pandas works. This also allows key stake holders with less code fluency (like Team Chiefs and Mission Managers) to inspect code themselves and actually understand it.

### Container-level methods (vectorized — prefer these)

Add methods directly to the frame class. These operate on the whole DataFrame at once and are fast because pandas/numpy does the work in C, not Python loops.

```python
class CommWindowFrame(TtsDataFrame):
    # ... (SCHEMA, etc. as above)

    def above_elevation(self, min_deg):
        """Return only windows where the spacecraft is above min_deg elevation."""
        return self[self['max_elevation_deg'] >= min_deg]

    def for_station(self, station_name):
        """Return only windows for a specific ground station."""
        return self[self['station'] == station_name]

    @property
    def dsn_windows(self):
        """Shorthand for DSN stations."""
        return self.for_station(['Goldstone', 'Madrid', 'Canberra'])
```

Usage:

```python
windows = CommWindowFrame(raw_data)
high_el = windows.above_elevation(30.0).dsn_windows
```

See the vectorization note in Section 1 for the performance rationale.

### Row-level methods (via TtsRowSeries)

Sometimes you need to act on a single row — for example, to apply custom logic to one record at a time. `TtsRowSeries` is the row class returned when you access a single row via `.loc[]`. Subclass it to attach row-level methods.

```python
from tts_data_utils.core.data_frame import TtsDataFrame, TtsRowSeries

class CommWindowRow(TtsRowSeries):
    @property
    def duration_minutes(self):
        return (self['end_time'] - self['start_time']).total_seconds() / 60.0

    def is_high_elevation(self, threshold=30.0):
        return self['max_elevation_deg'] >= threshold


class CommWindowFrame(TtsDataFrame):
    ROW_SERIES_CLASS = CommWindowRow
    # ... rest of class
```

Usage:

```python
row = windows.loc[0]          # Returns a CommWindowRow
row.duration_minutes          # -> float
row.is_high_elevation(45.0)   # -> bool
```

> **When to use row methods vs. container methods**: Prefer container methods for anything you'd apply to the whole dataset — they are vectorized and scale without limit. Use row methods for logic that only makes sense on a single row: custom display styling, row-level Dexter disposition decisions, or computed properties that mix several columns in ways that are awkward to vectorize. The performance distinction matters most at scale (>1M rows) or when an operation runs repeatedly in a loop; for small, one-off calls on a modest dataset the difference is negligible. When in doubt, start with a container method and drop to a row method only when you find a compelling reason.

---

## 4. Lifecycle of a TtsDataFrame Subclass

The pattern across the TTS ecosystem is:

```
tts_data_utils/           ← base classes only; multimission data types
<mission>_data_utils/     ← mission-specific subclasses (e.g., oco2_data_utils)
<mission>_query/          ← reads raw files/DBs and returns <Mission>Frame instances
```

Your mission's data types live in `<mission>_data_utils`. The query library for your mission reads raw data and hands back instances of those types. From there, the frame can be passed to any combination of downstream tools:

- **`tts_dexter`** (optional) — operators stamp individual rows via `TtsRowSeries` to record disposition, review status, or acknowledgment
- **`tts_dtat`** (optional) — plot the frame's data with mission-appropriate axes and styling
- **`tts_html_utils.PowerTable`** (optional) — render the frame as a styled HTML report with color-coded rows and expandable sub-tables
- **CSV / Excel export** — because `TtsDataFrame` is a pandas DataFrame, `.to_csv()` and `.to_excel()` work natively

For a worked example of this full lifecycle end-to-end, see [`demosat_data_utils`](https://github.com/NASA-JPL-TTS-Demosat/demosat_data_utils). Demosat is a fictional satellite that is an amalgamation of real Earth orbiters, purpose-built as a sandbox for TTS development and demonstration.

---

## 5. CSV Construction

`TtsDataFrame` supports direct construction from a CSV file:

```python
windows = CommWindowFrame(csv_path='comm_windows.csv')
```

Column names are matched against `SCHEMA`, and `TIME_FORMATS` are applied automatically to timestamp columns during loading. This means timestamp strings in mission-specific formats are parsed into `datetime` objects, and column types are coerced to match `SCHEMA` — so the resulting frame is indistinguishable from one constructed from live data. You do not lose type information by round-tripping through CSV.

---

## 6. HTML Display and Jupyter Integration

A key goal of this library is **quick, formatted data display** — in Jupyter notebooks during analysis, and in HTML reports for operations teams.

`TtsDataFrame` implements `_repr_html_()` so that Jupyter automatically renders a styled table when a frame is the last expression in a cell.

For full HTML report generation (styled tables, color-coded rows, expandable sub-tables), `tts_html_utils.PowerTable` is the tool. **Note:** direct wiring between `TtsDataFrame` and `PowerTable` is currently on the roadmap. In the meantime, see the existing `DataContainer` integration for patterns to follow.

Example of what a styled table output looks like (from `DataContainer`-era tools — the TtsDataFrame version will match this):

- Column headers with configurable background colors
- Rows color-coded by domain-specific rules (e.g., EVR severity level)
- Expandable sub-tables per row (for nested data like alarm records per telemetry point)

Because `TtsDataFrame` is a pandas `DataFrame` under the hood, it also supports writing to other formats out of the box:

```python
frame.to_csv('output.csv')
frame.to_excel('output.xlsx')
```

`to_csv()` is overridden to apply `TIME_FORMATS` so timestamp columns are written in the correct mission-specific string format, preserving round-trip fidelity.

---

## 7. Filtering and Value Derivation

### Long-form vs. Wide-form Data

All TTS frame types use **long-form** (sometimes called "tidy" or "narrow") data. Understanding this is essential for using `at_times_where` and `derive_values`.

**Long-form**: one row per `(time, label, value)` triplet. A frame with 3 channels sampled at 100 Hz for one hour has 3 × 360,000 = 1,080,000 rows. Each row carries the timestamp in `DEFAULT_TIME_LABEL`, the channel name in `LABEL_COL`, and the reading in `VALUE_COL`. Any extra columns (quality flags, metadata, alarm state) ride along per row.

```
time                label       value   alarm_state
2026-01-01T00:00    temp_1      23.4    GREEN
2026-01-01T00:00    temp_2      19.1    GREEN
2026-01-01T00:00    pressure    101.3   GREEN
2026-01-01T00:01    temp_1      23.5    GREEN
...
```

**Wide-form**: one row per timestamp, one column per label. The same data as above has 360,000 rows and 3 value columns.

```
time                temp_1   temp_2   pressure
2026-01-01T00:00    23.4     19.1     101.3
2026-01-01T00:01    23.5     ...
```

Long-form is the **source of truth** for TTS. Wide-form is a derived view. Methods that operate across labels (`at_times_where`, `derive_values`, the averaging methods) all expect long-form input. Use `pivot_to_wide()` to get a wide view for export, plotting, or downstream tools that require it — but note that `pivot_to_wide` drops metadata columns (only `time` and the `value` for each label survive).

**Why long-form?**
- Long-form is how AMPCS delivers telemetry — the dominant ground system at JPL. There is strong cultural momentum from engineers who have worked AMPCS missions.
- Wide-form with arbitrary per-row metadata columns would require multi-index DataFrames. Multi-indexing was attempted and rejected: filtering on multi-indexed frames requires expensive data copying that erases the performance advantage of using pandas in the first place.
- One set of filtering and derivation logic to maintain, not two.

See `docs/adr/003-long-form-as-source-of-truth.md` for the full decision record.

---

### Quality-of-life filter methods

`TtsDataFrame` ships a family of built-in filter methods. These are the first and best way to filter for most cases — they handle the pandas mask boilerplate and support optional count constraints:

```python
# Comparison
evrs.eq('level', 'WARNING')           # column == value
chalvals.gt('eu', 30)                 # column > value
chalvals.lt('eu', 30)                 # column < value
chalvals.gte('eu', 30)                # column >= value
chalvals.lte('eu', 30)                # column <= value
chalvals.between('eu', 20, 40)        # lower <= column <= upper

# Membership
evrs.isin('level', ['WARNING_HI', 'FATAL'])
evrs.notin('level', ['DIAGNOSTIC'])

# String
evrs.contains('message', 'timeout')
evrs.doesnotcontain('message', 'expected')
evrs.matches('message', r'^\[FAULT\]')   # regex

# Time window (uses DEFAULT_TIME_LABEL)
evrs.before(t_end)
evrs.after(t_start)
evrs.after(t_start, inclusive=True)

# Dict-valued column (e.g. extracted EVR arguments)
evrs.dict_key_eq('arguments', 'port', 8080)
```

All of these accept optional `minimum`, `maximum`, and `exactly` keyword arguments to assert the result count — useful for defensive scripting in ops pipelines:

```python
# Raises if fewer than 1 row matches
root_cause = evrs.eq('message_id', 0x4A2F, minimum=1)

# Raises if not exactly 1 row
launch_evr = evrs.eq('message_id', 0x0001, exactly=1)
```

Domain methods defined on the frame subclass (Section 3) layer mission vocabulary on top of these and are a great complement:

```python
critical = evrs.warning_and_above()   # wraps .isin('level', ['WARNING', 'ERROR'])
high_el = comm_windows.above_elevation(30.0)  # wraps .gt('max_elevation_deg', 30)
```

For plain pandas boolean indexing — also fine for ad-hoc analysis:

```python
warm = eha_frame[eha_frame['eu'] > 30]
alarms = eha_frame[eha_frame['alarm_state'] != 'GREEN']
```

### Filtering across labels in long-form data: `at_times_where`

With long-form data (see the section above), `sensor_001` is not a column — it is a *value* in the `label` column. A condition like "give me all records at times when sensor_001 is above 0.7" cannot be expressed as plain pandas boolean indexing or `filter_expr`. `at_times_where` is designed for exactly this case:

```python
# Long-form: each row is (time, label, value)
# Returns ALL rows (all labels) at timestamps where sensor_001 > 0.7
result = eha_frame.at_times_where('sensor_001 > 0.7')

# Multi-label condition — times where both labels satisfy their conditions simultaneously
result = eha_frame.at_times_where('sensor_001 > 0.7 and sensor_002 < 0.5')

# With tolerance: also include rows within 5 seconds of a qualifying timestamp
result = eha_frame.at_times_where('sensor_001 > 0.7', tolerance=5)
```

Internally, `at_times_where` pivots a temporary wide view using an inner join on timestamps: the expression is evaluated only at timestamps where ALL referenced labels have a sample. `tolerance` then widens the output — any row whose timestamp falls within `tolerance` seconds of a qualifying timestamp is included.

### The expression engine: `filter_expr`

`filter_expr()` filters rows using a string boolean expression where identifiers are column names:

```python
warm_alarms = eha_frame.filter_expr('eu > 30 and alarm_state != "GREEN"')

# Supports: >, >=, <, <=, ==, !=, is, is not, and, or, not, in, not in, parentheses
# String literals in single or double quotes; None/null/none match NaN
```

`filter_expr` and `at_times_where` share the same boolean expression engine (lark-based, `core/expr_engines.py`). `derive_values` uses a separate math expression engine that supports arithmetic and functions.

Note that `filter_expr` operates on column names — it is a wide-form style filter. Since long-form is first-class in TTS, `filter_expr` is not the primary recommended approach. Its main use case is filter rules written by non-programmers and stored in YAML or CSV configuration files, where expressing the condition as a Python boolean mask is impractical.

### Deriving new values

`derive_values()` computes a new label from a math expression over existing labels in a long-form frame. The output is a new long-form frame containing only the derived label.

**Output timestamps** depend on the `timeout` argument:
- `timeout=0` (default): timestamps = **intersection** of all referenced labels — only times when every label has an actual sample. No interpolation is called; this is the fast path.
- `timeout>0`: timestamps = **union** of all label timestamps. At each union timestamp, each label's value is filled by its interpolator (step by default; override `get_interpolator()` to choose per label). Timestamps where any label cannot be interpolated within `timeout` seconds are silently skipped.

Labels are aligned by time using interpolation before the expression is evaluated:

```python
# Assignment syntax: 'new_label = expression'
result = eha_frame.derive_values('temp_delta = temp_1 - abs(temp_2)')

# Supports: +, -, *, /, **, unary -, parentheses
# Functions: abs, sqrt, sin, cos, tan, log, log10, exp, floor, ceil

# Force a specific interpolator for all labels:
from tts_dante.interpolators.interpolators import LinearInterpolator
result = eha_frame.derive_values(
    'smoothed = channel_a + channel_b',
    interpolator=LinearInterpolator(),
    timeout=5,
)
```

The interpolation step is where `tts_dante` connects to `tts_data_utils`. When labels are sampled at different rates or timestamps, `derive_values()` calls `get_interpolator(label)` to determine how to align each label's values to a common time base. The base implementation returns a `StepInterpolator`; subclasses override `get_interpolator()` to choose interpolation strategy per label (e.g., step for enumerations, linear for floats, clamped-linear for integers).

---

## 8. Diffing

`TtsDataFrame` supports diffing two frames — useful for comparing as-run results against expceted unit test values.

```python
from tts_data_utils.core.diff import diff

changes = diff(old_frame, new_frame)
```

Visual diff (HTML side-by-side) is planned for TtsDataFrame but not yet implemented. See `docs/roadmap.md`.

---

## 9. Lorem Ipsum Data Generation

For prototyping and testing, `lorem_utils` can generate a frame populated with semi-realistic dummy data:

```python
from tts_data_utils.core.lorem_utils import lorem_frame

sample = lorem_frame(CommWindowFrame, n=50)
```

This generates `n` rows with random but type-correct values, respecting the `SCHEMA` definition.

---

## 10. The Two Architectural Elements of tts_data_utils

`tts_data_utils` is built around two fundamental data types. Only one is fully realized today:

### Element 1: TtsDataFrame (fully implemented)

The `TtsDataFrame` + `TtsRowSeries` hierarchy is the primary abstraction. It handles any data that fits in rows and columns — telemetry channels, event records, contact windows, ephemeris, planning products, test results.

### Element 2: TtsDataNode (aspirational, not yet built)

A second class of systems engineering data does not fit neatly into 2D tables: deeply hierarchical structures with arbitrary depth — spacecraft subsystem state trees, alarm gumball categorizations, planning products where activities contain sub-activities to arbitrary depth, hierarchical JSON/XML from ground system APIs.

A future `TtsDataNode` class is intended as the peer to `TtsDataFrame` for this data. Design goals:
- Pythonic attribute-style access (`node.subsystem.power.voltage`)
- Serializable/deserializable to/from JSON, YAML, and XML
- Typed, with optional schema declarations per node
- Nestable to arbitrary depth as a proper class hierarchy (not the current `subcontainers` dict workaround)
- Visualization via hierarchy diagrams and nested Gantt charts for nodes with start/end times

This is a class-based design that customer projects can extend — consistent with TTS's core philosophy of providing extensible bricks rather than fixed tools.

See `docs/adr/002-infinitely-nestable-container.md` for design options and open questions. This feature does not exist yet — contributions welcome.
