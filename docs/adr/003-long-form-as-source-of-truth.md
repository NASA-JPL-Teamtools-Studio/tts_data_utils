# ADR 003: Long-form as Source of Truth for TtsDataFrame

**Status:** Accepted  
**Date:** 2026

## Context

This decision was made as part of the broader architectural pivot from `DataContainer`/`DataItem` to `TtsDataFrame` (see ADR 001). As the team designed what the new pandas-backed data model should look like, the question of canonical data shape was directly tied to the question of which operations to support natively. The long-form vs. wide-form choice was one of the most contested parts of that discussion.

TTS data types built on `TtsDataFrame` can represent multi-label time-series data in two shapes:

- **Long-form**: one row per `(time, label, value)` triplet — the standard AMPCS telemetry output format. Metadata columns (alarm state, quality flag, source, etc.) ride along per row.
- **Wide-form**: one row per timestamp, one column per label. Metadata columns cannot be represented per-label without multi-indexing.

The team needed to decide which shape is the canonical internal representation.

This decision was contested. Some team members preferred wide-form because it makes certain operations — NaN-based filling, filtering on two labels simultaneously, NumPy math across columns — simpler to express and easier to explain to engineers who are comfortable with spreadsheet-style data.

## Decision

**Long-form is the source of truth.** Wide-form is a derived, read-only view obtained via `pivot_to_wide()`.

All methods that operate across multiple labels (`at_times_where`, `derive_values`, `moving_average`, `time_average`, `block_average`) expect long-form input. `pivot_to_wide()` produces a wide view for export, plotting, or downstream tools that require it.

## Rationale

### AMPCS cultural momentum

AMPCS (Advanced Multi-Mission Operations System), the dominant ground data system at JPL, delivers engineering telemetry in long-form. Engineers who have worked AMPCS missions arrive already fluent in the long-form mental model. Adopting long-form reduces onboarding friction for the primary audience. This may change in the future as JPL ground systems evolve, but it is the correct choice in 2026.

### Multi-index cost is prohibitive

Wide-form data with arbitrary per-row metadata columns (alarm state, quality flag, source, calibration version, etc.) requires a multi-level column index in pandas. Multi-indexed DataFrame filtering requires data copying that is disproportionately expensive — empirically, it erases the performance advantage of using pandas over a custom container. Multi-indexing was tested in an earlier version of `TtsDataFrame` and rejected for this reason.

### One set of logic to maintain

Supporting both shapes with equivalent capabilities (filtering, derivation, interpolation) doubles the implementation surface. Long-form as source of truth means one set of logic, one set of tests, and one mental model for contributors.

## Consequences

**Positive:**
- Long-form matches AMPCS output directly; no reshape step before loading data
- Metadata columns per row are first-class — no multi-index workarounds
- One implementation path for all cross-label operations

**Negative / Watch items:**
- Multi-label filtering (`at_times_where`) is harder to explain than the equivalent wide-form approach (`df[df['temp_1'] > 30]`). Engineers unfamiliar with long-form data find the concept unintuitive initially.
- `pivot_to_wide()` drops metadata columns — only `(time, value-per-label)` survives. Users who want wide-form lose TTS metadata. So far, the users who prefer wide-form have not needed the metadata after pivoting, but this assumption should be revisited if it changes.

## Rejected Alternatives

**Wide-form as source of truth**: Requires multi-indexing for metadata columns. Performance cost is too high.

**Dual support (accept both shapes)**: Would require every cross-label method to detect shape and branch. Doubles the implementation surface and test matrix. Rejected in favor of keeping the codebase tractable.

**ffill/bfill on wide-form as the interpolation story**: Simpler to explain, but not composable with per-label interpolation strategies (step for enumerations, linear for floats). `derive_values` with a configurable interpolator per label is more principled. The explanation gap is a documentation problem, not a design problem.

## References

- `src/tts_data_utils/core/data_frame.py` — `at_times_where`, `derive_values`, `pivot_to_wide`
- `docs/developer-guide.md` — Long-form vs. Wide-form Data section
- `docs/roadmap.md` — `at_times_where` inner join fix
