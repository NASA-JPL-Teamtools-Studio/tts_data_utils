# tts_data_utils Context

## Purpose

`tts_data_utils` is the central data abstraction layer for the Teamtools Studio (TTS) ecosystem. It solves three interconnected problems:

1. **Unified tabular abstraction** — a common data structure across 25+ interoperable repos, with extension hooks for custom behavior per data type
2. **Pandas interoperability** — leverages the full power of pandas while hiding obtuse syntax behind domain-friendly APIs for JPL developers
3. **Quality-of-life extensions** — common operations (filtering, display, diffing, lorem ipsum generation) in consistent ways across all projects

It is one of the central building blocks of the TTS ecosystem. If a tool in TTS works with tabular data, it either depends on this repo or produces a subclass of `TtsDataFrame`.

## Two Fundamental Data Types

The library is designed around two kinds of data:

1. **Tabular data** (`TtsDataFrame`) — the current fully-realized type. Any 2D data that could live in a spreadsheet belongs here.
2. **Infinitely-nestable structured data** — aspirational, not yet built. Intended for hierarchical data (think deeply nested JSON/YAML/XML) that doesn't fit neatly into a 2D table. See `docs/adr/002-infinitely-nestable-container.md` for the design direction.

## Architectural State: In Transition

This repo is in the middle of a deliberate architectural pivot. See `docs/adr/001-tts-data-frame-pivot.md` for the full decision record.

**Old pattern** (`DataContainer` / `DataItem`):
- Custom list-like container holding `DataItem` objects (one per row)
- Familiar iteration pattern, good for modest datasets (~1M rows max)
- Clunky interoperability with pandas-compatible tools
- Being left in place for existing projects; not actively maintained

**New pattern** (`TtsDataFrame`):
- Subclass of `pd.DataFrame` with metadata, schema, and domain-friendly methods
- Unlimited performance ceiling via native pandas/numpy (C under the hood)
- Full compatibility with pandas-compatible tools via the `_constructor` hook
- Row-level ergonomics available through `TtsRowSeries` (replaces `DataItem` iteration)

New data types should use `TtsDataFrame`. Existing `DataContainer`-based types will migrate over time but are not forced to.

## Key Modules

- **`core/data_frame.py`** — `TtsDataFrame`: the primary base class for all new data types. Extend this.
- **`core/data_container.py`** — `DataContainer`: the legacy base class. Leave in place; do not actively extend.
- **`core/data_item.py`** — `DataItem`: the legacy per-row class. Leave in place.
- **`core/expr_engines.py`** — Expression language for filter and math operations on DataFrames.
- **`core/diff.py`** / **`core/visual_diff.py`** — Diffing between containers. Visual diff not yet ported to TtsDataFrame (roadmap item).
- **`core/lorem_utils.py`** — Lorem ipsum data generation for prototyping and developer testing.
- **`multimission/ampcs/`** — AMPCS ground-system-specific data types (`AmpcsEhaFrame`, `AmpcsEvrFrame`). In progress; old flat files remain as DataContainers.
- **`invulnerable_data_manager/`** — Failure-resistant pipeline management. Uses an `@invulnerable` decorator pattern to swallow exceptions from malformed or missing data without halting the pipeline. Coordinates input/output data registries and logical batching (`Batcher`/`Batch`). Critical for spacecraft operations where a single bad record must not crash analysis.

## How This Connects to the Ecosystem

`tts_data_utils` is a **producer and consumer contract**. Other repos in the ecosystem interact with it in a defined pattern:

- **Query libraries** (e.g., `oco2_query`, `fss_query`) — read raw data from files or databases and return `TtsDataFrame` subclasses
- **Mission-specific data utils** (e.g., `oco2_data_utils`, `demosat_data_utils`) — define mission-specific `TtsDataFrame` subclasses with custom columns, methods, and display logic
- **tts_dexter** — consumes `TtsDataFrame` and adds disposition/review workflows via `TtsRowSeries.stamp()`
- **tts_dante** — channel derivation pipeline that produces new `TtsDataFrame` columns from existing ones; depends on the expression engine in this repo
- **tts_html_utils** — `PowerTable` renders `TtsDataFrame` as interactive HTML (connection not yet wired for TtsDataFrame; roadmap item)

## Developer Guide

See `docs/developer-guide.md` for a step-by-step guide on how to create a new `TtsDataFrame` subclass for a specific data type.

## Roadmap

See `docs/roadmap.md` for the prioritized list of features and architectural work.

## System Architecture

For the broader TTS ecosystem architecture, see the central documentation:

**Central docs**: `teamtools_documentation/CONTEXT.md` and `teamtools_documentation/docs/adr/`

## Development

- **Python versioning** defined in `pyproject.toml`; `tts_utilities` provides compatibility shims for older Python versions
- **pytest** for testing (`src/tts_data_utils/test/`)
- **Sphinx** for reference docs (`docs/`)
- `demosat_data_utils` is the canonical sandbox/example repo for the full TTS ecosystem

## Dependencies

- `tts-utilities` — shared utilities, logging, Python compat shims
- `tts-html-utils` — `PowerTable` and HTML rendering primitives
- `pandas` — core data engine
- `plotly` — visualization
- `jpl_time` — listed as a dependency but not actively used; `datetime` and `pd.Timestamp` are used in practice. See roadmap for planned proper integration.
- `lark` — expression language grammar parsing

---

## Language

Canonical terms for concepts specific to this repository. For ecosystem-wide terms see `teamtools_documentation/CONTEXT.md`.

**TtsDataFrame**:
A `pd.DataFrame` subclass that is the primary base class for all tabular data types in the TTS ecosystem. Carries a name, metadata, schema contract, and domain methods. Preserves its subclass type across pandas operations via `_constructor`.
_Avoid_: "DataFrame," "container," "data frame" (lowercase)

**DataContainer**:
The legacy list-like tabular abstraction, now in maintenance-only mode. Held `DataItem` objects one per row. Still in use in older repos; new code should use `TtsDataFrame`.
_Avoid_: "container" (ambiguous), "DC"

**DataItem**:
The legacy per-row class used with `DataContainer`. A "smart dictionary" separating source data from derived values. Row-level ergonomics are now provided by `TtsRowSeries` instead.
_Avoid_: "item," "row object," "record"

**TtsRowSeries**:
A `pd.Series` subclass returned when accessing a single row of a `TtsDataFrame`. The place to attach row-level domain methods (e.g., computed properties, display logic). The successor to `DataItem` for row-level ergonomics.
_Avoid_: "row," "item," "DataItem"

**TtsColumnSeries**:
A `pd.Series` subclass returned when accessing a single column of a `TtsDataFrame`.
_Avoid_: "column," "series"

**Schema**:
The `SCHEMA` class variable on a `TtsDataFrame` subclass — a list of `(column_name, type)` tuples declaring the frame's expected columns and their types. Serves as the machine-readable contract between data producers and consumers.
_Avoid_: "column spec," "validation spec," "column list"

**TIME_FORMATS**:
A class variable mapping column names to `strptime` format strings. Tells the framework how to parse mission-specific timestamp strings (e.g., year-day-of-year format) into `datetime` objects.
_Avoid_: "date format," "timestamp format dict"

**DEFAULT_TIME_LABEL**:
The class variable naming the primary timestamp column for a `TtsDataFrame` subclass. Used by time-aware operations (interpolation, windowed filtering, plotting) so callers don't need to specify the column each time, though callers should all include a temporary override for cases of multiple time columns in the saem TtsDataFrame.
_Avoid_: "time column," "timestamp column"

**LABEL_COL / VALUE_COL**:
Class variables marking which column names a row (LABEL_COL) and which holds the primary measurement (VALUE_COL). Used by display and diff tools to make formatting decisions without per-type configuration. All methods that use these defaults should also accept explicit `label_col` and `value_col` keyword arguments so individual call sites can override them.
_Avoid_: "label column," "value column" (as prose — these are the canonical terms)

**InvulnerableDataManager (IDM)**:
The pipeline coordinator in `invulnerable_data_manager/`. Registers data sources, initializes them with `@invulnerable` to swallow per-source errors, and organizes data into named logical groups via `Batcher`/`Batch`. A notional future integration would allow `Batch` inputs to include `TtsEvent` subclasses from `tts_events`, enabling the same failure-resistant pipeline pattern for event-driven data (see roadmap).
_Avoid_: "data manager," "pipeline manager," "IDM" on first use (spell out first)

**Batcher**:
An abstract base class in `invulnerable_data_manager/` that sorts input data into named logical subsets (`Batch` objects) before processing.
_Avoid_: "grouper," "sorter," "partitioner"

**Expression engine**:
The `lark`-based filter and math language exposed on `TtsDataFrame`. Three entry points:
- `frame.filter_expr('eu > 30 and alarm_state != "GREEN"')` — filter rows by expression over column names (wide-form style, identifiers = columns)
- `frame.at_times_where('sensor_001 > 0.7 and sensor_002 < 0.5')` — return all rows at timestamps where a cross-label condition holds (long-form; identifiers = label values, pivoted internally). Includes a tolerance kwarg for returning values close to the times a condition holds, but not necessarily exactly at them.
- `frame.derive_values('delta = channel_a - abs(channel_b)')` — compute a new label from existing labels (long-form). The output timestamps depend on the `timeout` argument: with `timeout=0` (default fast path), output timestamps are the **intersection** of timestamps across all referenced labels — only times where every label has an actual sample. With `timeout>0`, output timestamps are the **union** of all label timestamps; each label's value at a given time is filled by its interpolator, and timestamps where any label cannot be interpolated within `timeout` are silently skipped.

Useful for rule configurations written by non-programmers or stored in YAML/CSV files.
_Avoid_: "expression language," "filter engine," "DSL"

**Multimission data type**:
A `TtsDataFrame` subclass that represents a data format common across multiple missions (e.g., AMPCS EHA telemetry). Lives in `multimission/` and is intended to be extended by mission-specific data utils repos.
_Avoid_: "generic frame," "shared frame"

**AmpcsEhaFrame**:
The AMPCS-specific `TtsDataFrame` subclass for Engineering Health and Alarms telemetry. Lives in `multimission/ampcs/`.
_Avoid_: "EhaFrame," "EhaContainer," "EHA frame" (lowercase)

**AmpcsEvrFrame**:
The AMPCS-specific `TtsDataFrame` subclass for Event/EVent Records. Lives in `multimission/ampcs/`.
_Avoid_: "EvrFrame," "EvrContainer," "EVR frame" (lowercase)

**Subcontainers**:
A dictionary of nested `DataContainer` or `TtsDataFrame` objects stored as metadata on a row or frame, enabling hierarchical data within a tabular structure. Used by `PowerTable` for row expansion. A recognized workaround — the long-term replacement is `TtsDataNode`.
_Avoid_: "nested containers," "child containers"

**TtsDataNode**:
The aspirational second fundamental data type for infinitely-nestable structured data (hierarchical JSON/YAML/XML). Not yet implemented. See `docs/adr/002-infinitely-nestable-container.md`.
_Avoid_: "nested container," "tree node," "JSON wrapper"

**Visual diff**:
A side-by-side HTML comparison of two `TtsDataFrame` instances, highlighting changed, added, and removed rows. Implemented for `DataContainer`; not yet ported to `TtsDataFrame` (roadmap item #2).
_Avoid_: "diff," "comparison view"

**Lorem**:
The fake-data generation utilities in `core/lorem_utils.py` that produce `TtsDataFrame` instances populated with type-correct dummy data from `SCHEMA`. Used for prototyping and developer testing.
_Avoid_: "lorem ipsum," "dummy data generator," "test data factory"
