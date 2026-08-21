# ADR 001: Pivot from DataContainer/DataItem to TtsDataFrame

**Status:** Accepted — in progress  
**Date:** 2026

---

## Context

`tts_data_utils` originally provided `DataContainer` and `DataItem` as its primary abstractions for tabular data. `DataContainer` is a custom list-like class where each row is a `DataItem` — a "smart dictionary" with source/derived value separation. This pattern worked well and is still in use across many TTS-dependent repositories.

Over time, three pressure points emerged:

1. **Performance.** `DataContainer` works well up to roughly 1 million records. Beyond that, Python object overhead dominates. Some users (particularly in high-rate telemetry and long-baseline data analysis) need more.

2. **Math operations.** Derived value calculations that should be vectorized had to loop over `DataItem` objects. Once heavy math was needed, pandas was imported anyway — making `DataContainer` a thin and leaky abstraction.

3. **Ecosystem compatibility.** The pandas ecosystem (Dask, Plotly, statsmodels, etc.) operates on `pd.DataFrame`. `DataContainer` is invisible to these tools. Every integration required an explicit conversion step, and the converted plain DataFrame lost all custom metadata and methods. The `_constructor` hook and `_metadata` list preserve these attributes through standard pandas operations; subcontainers are intelligently pruned (not blindly copied) when the associated rows are no longer present after a filter or sort.

## Decision

Introduce `TtsDataFrame` as a subclass of `pd.DataFrame`. New data types in the TTS ecosystem should extend `TtsDataFrame` instead of `DataContainer`.

Key design choices:

- **`_metadata` list** propagates container-level attributes (`name`, `metadata`, `_subcontainers`) through pandas operations (`.copy()`, `.loc`, `.sort_values()`, etc.)
- **`_constructor` hook** ensures that pandas operations return the same subclass, not a plain DataFrame
- **`TtsRowSeries`** (subclass of `pd.Series`) provides row-level ergonomics equivalent to `DataItem`, without breaking vectorization
- **`SCHEMA`, `TIME_FORMATS`, `DEFAULT_TIME_LABEL`, `LABEL_COL`, `VALUE_COL`** are class-level contract attributes, carrying the documentation and display intent that `DataItem.DICT_VALID_KEYS` carried before

## Migration Strategy

`DataContainer` and `DataItem` are **not deprecated in a breaking way.** Existing projects using them are not required to migrate. They will be left in place and not actively maintained.

New data types should use `TtsDataFrame`. Existing `DataContainer`-based types may be migrated opportunistically when significant new features or performance work is needed.

The `multimission/` module is the first target for migration — `EhaContainer`/`EhaItem` → `AmpcsEhaFrame`, `EvrContainer`/`EvrItem` → `AmpcsEvrFrame`, in a new `multimission/ampcs/` subdirectory.

## Consequences

**Positive:**
- Higher performance ceiling — native NumPy/C backing
- Full pandas ecosystem compatibility out of the box
- Domain methods are tab-discoverable on the frame object
- Row-level ergonomics preserved via `TtsRowSeries`

**Negative / Watch items:**
- `_constructor` propagation is well-supported but requires care; some pandas internal operations may return plain `DataFrame` in edge cases — test thoroughly
- The `DataItem` source/derived separation (immutable source, writable derived layer) is not directly replicated in `TtsDataFrame` — derived values are just additional columns. This is simpler but loses the explicit audit trail of "what was raw vs. computed". **Note:** pandas v2+ introduced `DataFrame.attrs` and copy-on-write semantics that may offer a path to tracking column provenance without a custom abstraction — worth revisiting.
- `PowerTable` HTML display is not yet wired to `TtsDataFrame` — this is a roadmap item

## Subcontainers and Dispositions in __finalize__

Two `_metadata` attributes deserve special mention because they are not simple scalars:

**Subcontainers** (`_subcontainers`): A `dict` mapping row keys to nested frames or containers. Pandas operations that reduce rows (filter, sort, slice) trigger `__finalize__`, which prunes `_subcontainers` to only those keys still present in the live frame. This prevents orphaned subcontainers from accumulating after filtering. **Known limitation:** when `SUBCONTAINER_KEY = 'pandas_index'`, sort operations change the integer index values, which causes all subcontainers to be pruned even though no rows were removed. Workaround: set `SUBCONTAINER_KEY` to a stable data column. Long-term fix tracked in roadmap.

**Dispositions** (`_row_dispositions`): A `dict` mapping row index keys to lists of Dexter disposition stamps. `__finalize__` similarly prunes to live index keys, so dispositions on filtered-out rows are discarded. This is correct behavior for most operations but may be surprising if rows are temporarily excluded and re-included.

## References

- `src/tts_data_utils/core/data_frame.py` — TtsDataFrame implementation
- `src/tts_data_utils/core/data_container.py` — DataContainer (legacy)
- `docs/developer-guide.md` — how to extend TtsDataFrame
- `docs/roadmap.md` — pending migration work
