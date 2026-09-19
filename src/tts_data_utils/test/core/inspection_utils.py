"""Utilities for human-certification of inspection HTML artifacts.

Delegates to ``tts_utilities.inspection``, the shared implementation
generalized from this module. Kept so existing imports and error-message
conventions continue to work unchanged.

See ``test/certify.py`` for the script that humans run to record approval.
See ``teamtools_documentation/CONTEXT.md`` (Human-inspectable test artifacts)
for the full design directive.
"""

from pathlib import Path

from tts_utilities.inspection import (
    certify_file,
    check_inspection_hash as _check_inspection_hash,
    normalize_uuids,
)


def _normalize(html_bytes):
    """Backward-compatible alias: UUID placeholder normalization.

    Preserved for the prototype's import surface; identical semantics to
    ``tts_utilities.inspection.normalize_uuids``.
    """
    return normalize_uuids(html_bytes)


def check_inspection_hash(html_path: Path) -> None:
    """Assert that the generated HTML matches the committed human-certification hash.

    This enforces the pattern: any change in rendered output requires a human to
    open the file, verify it looks correct, and re-run ``certify.py`` before the
    test suite will pass again.

    Parameters
    ----------
    html_path : Path
        Path to the generated ``.html`` artifact.  A ``.sha256`` sidecar file
        must exist alongside it containing the committed digest.

    Raises
    ------
    AssertionError
        If no sidecar hash exists (first run — human review needed before
        certifying) or if the current content hash does not match the committed
        one (output has changed — re-inspection required).
    """
    _check_inspection_hash(
        html_path,
        certify_hint='python %s' % (
            Path(__file__).parent.parent / 'certify.py'
        ).resolve(),
    )


__all__ = ['check_inspection_hash', 'certify_file']
