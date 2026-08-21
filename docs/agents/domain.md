# Domain Documentation

## Multi-Context Layout

This repository is part of a larger ecosystem of ~25 interoperable repositories. Architectural documentation is centralized in the `teamtools_documentation` repository to avoid duplication and maintain consistency across the system.

### Context Structure

- **Central architecture** — `teamtools_documentation/CONTEXT.md` and `teamtools_documentation/docs/adr/`
  - System-wide design decisions
  - Shared vocabulary and domain model
  - Cross-cutting architectural patterns

- **Repository-specific context** — `CONTEXT.md` in each repository
  - How this repository fits into the larger system
  - Repository-specific design decisions and patterns
  - References to central architecture docs

### How Agents Use This

When using skills like `grill-me`, `improve-codebase-architecture`, or `diagnosing-bugs`:

1. **Start here** — Read `CONTEXT.md` in the current repository for repo-specific context
2. **Reference central docs** — Follow links to `teamtools_documentation` for architectural understanding
3. **Cross-repo navigation** — Agents can read and edit docs across multiple repositories as needed
4. **Edit in context** — Changes to architectural docs should go to `teamtools_documentation`; repo-specific changes stay local

### Finding Central Docs

The `teamtools_documentation` repository is located at:
```
../../../tts_core/teamtools_documentation
```

Or via GitHub: https://github.com/NASA-JPL-Teamtools-Studio/teamtools_documentation

### Adding to This Repository's Context

When documenting repo-specific decisions:
1. Create ADRs in `docs/adr/` for significant decisions
2. Update `CONTEXT.md` to summarize the repository's role and key patterns
3. Link to central architecture docs in `teamtools_documentation` for shared concepts
