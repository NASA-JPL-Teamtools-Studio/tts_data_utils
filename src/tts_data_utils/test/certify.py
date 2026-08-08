"""Human certification script for inspection HTML artifacts.

Run this *after* you have visually verified that the inspection HTML files look
correct in a browser.  This records a SHA-256 digest of each artifact so the
test suite can detect future changes and prompt re-inspection.

IMPORTANT: This script is for humans to run — never call it from automated
tests or CI.  The point of the .sha256 sidecar files is that only a human
can stamp them as "reviewed and approved."

Usage
-----
Certify all artifacts in the default test_files/ directory:

    python certify.py

Certify a specific file:

    python certify.py path/to/file.html

Certify multiple specific files:

    python certify.py a.html b.html

After running, commit the resulting .sha256 files to record your approval.
"""

import hashlib
import sys
from pathlib import Path

from tts_data_utils.test.core.inspection_utils import _normalize

TEST_FILES_DIR = Path(__file__).parent / "core" / "test_files"


def certify_file(html_path: Path) -> None:
    """Write a .sha256 sidecar file recording the current digest of html_path.

    The digest is computed on UUID-normalized content so it remains stable
    across runs (PowerTable embeds a random UUID in each table id).
    """
    digest = hashlib.sha256(_normalize(html_path.read_bytes())).hexdigest()
    hash_path = html_path.with_suffix(html_path.suffix + ".sha256")
    hash_path.write_text(f"{digest}  {html_path.name}\n")
    print(f"  Certified: {html_path.name}  ({digest[:12]}...)")


def main() -> None:
    if len(sys.argv) > 1:
        targets = [Path(p) for p in sys.argv[1:]]
    else:
        targets = sorted(TEST_FILES_DIR.glob("*.html"))

    if not targets:
        print(f"No HTML artifacts found in {TEST_FILES_DIR}")
        return

    print("Certifying inspection artifacts:")
    for path in targets:
        if not path.exists():
            print(f"  SKIP (not found): {path}")
            continue
        certify_file(path)

    print(
        f"\nDone. {len(targets)} artifact(s) certified.\n"
        f"Commit the updated .sha256 files to record your approval."
    )


if __name__ == "__main__":
    main()
