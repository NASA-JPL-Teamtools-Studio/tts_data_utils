# ADR 002: Infinitely-Nestable Structured Data Container

**Status:** Proposed — not yet implemented  
**Date:** 2026

---

## Context

`tts_data_utils` handles 2D tabular data well via `TtsDataFrame`. But systems engineering regularly produces a second class of data that does not fit neatly into rows and columns:

- Spacecraft subsystem configuration trees
- Alarm gumball displays with categorization of systems
- Nested telemetry packet structures
- Hierarchical JSON/XML payloads from ground system APIs (AMPCS, MGSS, etc.)
- Planning products where a top-level plan contains activities, which may themselves include activities to arbitrary depths.

Today, the library handles this with a `subcontainers` dictionary — each `DataItem` or `TtsDataFrame` row can carry a dict of nested `DataContainer`s. This works, and the `PowerTable` row-expansion feature in `tts_html_utils` uses it effectively. But it is clunky for deep nesting and does not serialize cleanly.

## Decision (Proposed)

Introduce a second fundamental data type — provisionally called `TtsDataNode` — alongside `TtsDataFrame`. This type would handle hierarchical data with the same quality-of-life intent.

Design goals:

- **Arbitrary depth.** Any node can be a leaf (scalar value) or a parent (containing child nodes, lists of nodes, or `TtsDataFrame`s).
- **Pythonic access.** `node.subsystem.power.voltage` instead of `node['subsystem']['power']['voltage']`.
- **Serializable.** Round-trip serialization to/from JSON, YAML, and XML without loss of structure or type information.
- **Typed.** Nodes should carry type hints and optional schema declarations, similar to `SCHEMA` on `TtsDataFrame`.
- **Visualizable.** Nodes should support hierarchy diagrams. Nodes that carry `start_time` / `end_time` should support nested Gantt chart rendering. Note: `TtsDataNode` is not a table — `PowerTable` is not the right renderer here.
- **Extensible by customer projects.** Must be a class-based design that missions can subclass, consistent with TTS's brick-not-tool philosophy.

**Open question — SemanticDictionary connection:** `tts_dictionary_interface` provides a base interface for spacecraft dictionaries (channel mnemonics, command definitions, etc.). There may be value in connecting `TtsDataNode` to this interface so that node fields can be looked up against a `SemanticDictionary` for validation or metadata enrichment. This is an open design question — evaluate when both pieces are better defined.

## Options Considered

**Option A: Python dataclasses**  
Python `dataclass` with nested dataclasses provides attribute-style access and is familiar. Limitation: does not support dynamic schemas (unknown keys at definition time), and JSON/XML serialization requires manual effort.

**Option B: Pydantic models**  
Pydantic provides schema validation, attribute access, and JSON serialization out of the box. It is the strongest option for typed, validated nested data. Limitation: adds a dependency and a learning curve; may be heavier than needed for simple use cases.

**Option C: Custom recursive class**  
A lightweight custom class with `__getattr__` delegation, similar in spirit to `DataItem`, but recursive. More control over serialization; more implementation work.

## Current Thinking

No decision has been made. The primary question is whether the use cases require runtime-dynamic schemas (unknown keys, variable structure) or whether compile-time-known schemas (like Pydantic) are sufficient.

For now, the `subcontainers` dict pattern remains in use where needed. New code that requires deep nesting should document the structure clearly and plan for migration once this is resolved.

## Next Steps

1. Survey existing `subcontainers` usages across TTS repos to understand the range of structures needed
2. Build a prototype (`demosat_data_utils` is the right sandbox) using Pydantic and a custom recursive class side-by-side
3. Evaluate based on: serialization ergonomics, IDE support, runtime flexibility, and `PowerTable` integration cost
4. Return to this ADR with a decision

## References

- `src/tts_data_utils/core/data_item.py` — current `subcontainers` pattern
- `src/tts_data_utils/core/data_frame.py` — `_subcontainers` in `_metadata`
- `docs/developer-guide.md` — Section 10: Looking Ahead
- `tts_html_utils` — `PowerTable` row expansion (the primary consumer of nested data today)
