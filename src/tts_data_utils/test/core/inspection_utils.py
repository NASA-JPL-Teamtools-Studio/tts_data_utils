"""Utilities for human-certification of inspection HTML artifacts.

See ``test/certify.py`` for the script that humans run to record approval.
See ``teamtools_documentation/CONTEXT.md`` (Human-inspectable test artifacts)
for the full design directive.
"""

import hashlib
import re
from pathlib import Path

_UUID_RE = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE,
)
_UUID_PLACEHOLDER = '00000000-0000-0000-0000-000000000000'


def _normalize(html_bytes: bytes) -> bytes:
    """Replace runtime-generated UUIDs with a stable placeholder.

    PowerTable embeds a UUID in each table's ``id`` attribute.  Normalizing
    these ensures the hash is stable across runs even though the UUID changes.
    """
    text = html_bytes.decode('utf-8', errors='replace')
    text = _UUID_RE.sub(_UUID_PLACEHOLDER, text)
    return text.encode('utf-8')


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
    hash_path = html_path.with_suffix(html_path.suffix + ".sha256")
    certify_cmd = (
        f"python {(Path(__file__).parent.parent / 'certify.py').resolve()}"
    )

    current_hash = hashlib.sha256(_normalize(html_path.read_bytes())).hexdigest()

    if not hash_path.exists():
        raise AssertionError(
            f"\nNo certification hash found for: {html_path.name}\n"
            f"\n  Steps to certify:"
            f"\n    1. Open in browser: {html_path.resolve()}"
            f"\n    2. Verify the output looks correct."
            f"\n    3. Run: {certify_cmd}"
            f"\n    4. Commit the resulting .sha256 file.\n"
        )

    committed_hash = hash_path.read_text().strip().split()[0]
    if current_hash != committed_hash:
        raise AssertionError(
            f"\nHTML output has changed since last human certification: {html_path.name}\n"
            f"\n  Steps to re-certify:"
            f"\n    1. Open in browser: {html_path.resolve()}"
            f"\n    2. Verify the changes are intentional and look correct."
            f"\n    3. Run: {certify_cmd}"
            f"\n    4. Commit the updated .sha256 file.\n"
        )
