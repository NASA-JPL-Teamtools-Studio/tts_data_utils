# Roadmap

Prioritized list of features and architectural work for `tts_data_utils`. Items are ordered by impact.

---

## 1. PowerTable → TtsDataFrame (High Priority)

**What:** Wire `tts_html_utils.PowerTable` to work with `TtsDataFrame` subclasses, providing:
- Styled HTML table rendering with color-coded rows (driven by domain logic on `TtsRowSeries`)
- Expandable sub-table rows for nested data
- Auto-generation of `_repr_html_()` using `PowerTable` (currently uses plain pandas HTML)

**Why:** Quick, formatted HTML display in Jupyter notebooks and HTML reports is a core promise of this library. The `DataContainer` era had this; `TtsDataFrame` does not yet.

**Entry points:**
- `TtsDataFrame._repr_html_()` — override to delegate to `PowerTable`
- `TtsRowSeries` — row-level color/style logic lives here (analogous to `DataItem.default_html_row_style`)
- `TtsDataFrame.SUBCONTAINER_KEY` — already exists; drives which column holds nested frame references for row expansion

---

## 2. Visual Diff → TtsDataFrame (High Priority)

**What:** Port the visual diff feature from `DataContainer` to `TtsDataFrame`. Produce a side-by-side HTML diff of two frames, highlighting changed, added, and removed rows.

**Why:** Diffing tabular data (expected vs. actual, version A vs. B) is one of the most common analysis tasks in operations. The `DataContainer` era had this; it is missing in the new architecture.

**Entry points:**
- `src/tts_data_utils/core/diff.py` — basic diff logic (assess what exists here)
- `src/tts_data_utils/core/visual_diff.py` — visual diff (assess what exists here)

---

## 3. AmpcsEha / AmpcsEvr Migration (Medium Priority)

**What:** Migrate `multimission/eha.py` and `multimission/evr.py` from `DataContainer`/`DataItem` to `TtsDataFrame`. Place the new classes in `multimission/ampcs/` as `AmpcsEhaFrame` and `AmpcsEvrFrame`.

**Why:** The multimission EHA/EVR types are the most widely used data types in the ecosystem. Renaming to `Ampcs*` also clarifies that these are specific to the AMPCS ground system, reducing confusion for users on other ground systems (MGSS, FPrime, etc.).

**Notes:**
- Leave `EhaContainer`/`EvrContainer` in place for backward compatibility — do not delete
- The `multimission/ampcs/` subdirectory establishes a pattern for future ground system groupings (`multimission/fprime/`, `multimission/yamcs/`, etc.)
- `demosat_data_utils` should be updated to use the new `Ampcs*Frame` types as reference implementation

---

## 4. Vectorized Interpolation (Medium Priority)

**What:** The current interpolation implementation in `tts_dante` (step and linear interpolators) is not vectorized — it operates element-by-element in Python rather than using NumPy operations. This should be replaced or wrapped with a vectorized implementation.

**Why:** Interpolation is used to align time-series channels to a common time grid and to query values at arbitrary timestamps. At high data volumes this becomes a bottleneck.

**Notes:**
- The `interpolation.py` stub in `tts_data_utils/core/` is empty and should either be removed or used as the home for a proper implementation
- `tts_dante` has the current interpolators (`interpolators/interpolators.py`) — the question is whether to port them here, fix them in place, or use `scipy.interpolate` directly
- No gap detection is in scope (the interpolators make no attempt to distinguish real data gaps from sparse sampling)

---

## 5. Lorem Ipsum → TtsDataFrame (Low Priority)

**What:** Ensure `lorem_utils` can generate realistic dummy data for `TtsDataFrame` subclasses, using `SCHEMA` to infer column types.

**Why:** Lorem ipsum generation is a quality-of-life feature for developers building new data types — they can get a populated frame without needing real data. Currently tied to the `DataContainer` era.

**Entry points:**
- `src/tts_data_utils/core/lorem_utils.py`

---

## 6. Infinitely-Nestable Container (`TtsDataNode`) (Long-term)

**What:** Design and implement a second fundamental data type for hierarchical structured data — the complement to `TtsDataFrame` for non-tabular data. Must be serializable to/from JSON, YAML, and XML.

**Why:** Systems engineering data is not always tabular. Configuration trees, packet structures, and nested planning products need a first-class representation.

**See:** `docs/adr/002-infinitely-nestable-container.md` for design options and open questions.

---

## 7. IDM / tts_events Interoperability (Medium Priority)

**What:** Allow `InvulnerableDataManager` batches to accept `TtsEvent` subclasses from `tts_events` as inputs, in addition to `TtsDataFrame`-based data sources. This would unify the failure-resistant pipeline pattern across both tabular and event-driven data.

**Why:** Currently IDM is designed around registering data sources that produce `DataContainer` or `TtsDataFrame` output. `tts_events` uses a separate `TtsEvent` dataclass hierarchy. Bridging these would let a single pipeline coordinator handle all data types in a failure-resistant way.

**Entry points:**
- `src/tts_data_utils/invulnerable_data_manager/` — IDM and Batch/Batcher base classes
- `tts_events/src/tts_events/core/event.py` — `TtsEvent` base class

---

## 8. jpl_time Integration (Low Priority)

**What:** `jpl_time` is listed as a dependency but `datetime` and `pd.Timestamp` are used in practice throughout the codebase. Decide: either remove `jpl_time` as a dependency, or properly integrate it so that `TIME_FORMATS` and time-aware methods can accept `jpl_time.Time` objects natively.

**Why:** The stated dependency creates a false contract. Either the dependency should be honored (proper integration) or removed (honest contract).

---

## 9. Sort-Safe Subcontainers (Low Priority)

**What:** When `SUBCONTAINER_KEY = 'pandas_index'`, any sort operation resets the integer index, causing all subcontainers to be pruned by `__finalize__` even though no rows were removed. Make `__finalize__` smarter for this case so that subcontainers survive sorts.

**Why:** The current workaround (set `SUBCONTAINER_KEY` to a stable data column) is not always possible and is not well-documented. The behavior is surprising and hard to debug.

**Entry points:**
- `src/tts_data_utils/core/data_frame.py` — `__finalize__` method

---

## 10. Python Version Deprecation (Low Priority)

**What:** `tts_data_utils` currently supports Python back to 3.6.8 for compatibility with older mission deployments. As newer language features become desirable (e.g., `match` statements, `|` union types in type hints, `tomllib`), plan and communicate a timeline for dropping Python 3.6/3.7/3.8 support.

**Why:** Supporting old Python versions constrains the code style and prevents use of useful standard library features. The deprecation should be deliberate and well-signaled to dependent projects.

**Notes:**
- `pyproject.toml` is the source of truth for supported Python versions
- `tts_utilities` provides compat shims for some Python version differences; coordinate with that repo
