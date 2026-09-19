"""Inspection artifact review dashboard and certification tool.

IMPORTANT: This script is for humans only — never call it from automated
tests or CI.  The .sha256 sidecar files are the human stamp of approval.

Workflow
--------
1. Run tests to generate the HTML artifacts (they will fail if uncertified).
2. Run this script with no arguments to see what needs review:

       python certify.py

   Opens (or prints the path to) an HTML status dashboard listing every
   artifact and its current review state.

3. Open each UNCERTIFIED or STALE artifact in a browser and verify it looks
   correct.

4. Stamp your approval:

       python certify.py --certify             # certify all artifacts
       python certify.py --certify file.html   # certify one specific file

5. Commit the resulting .sha256 files to record your approval.

Internals delegate to ``tts_utilities.inspection`` (the shared, generalized
implementation); this script only owns the repo-specific artifact location
and CLI surface.
"""

import sys
from pathlib import Path

from tts_utilities.inspection import (
    certify,
    print_status,
    render_status_report,
)

TEST_FILES_DIR = Path(__file__).parent / "core" / "test_files"
STATUS_REPORT_PATH = TEST_FILES_DIR / "inspection_status.html"


def _inspection_artifacts() -> 'list[Path]':
    return sorted(
        p for p in TEST_FILES_DIR.glob("*.html")
        if p.name != STATUS_REPORT_PATH.name
    )


def status(artifacts: 'list[Path]') -> None:
    """Print a console summary and write the HTML status dashboard."""
    if not artifacts:
        print(f"No HTML artifacts found in {TEST_FILES_DIR}")
        return
    certify_cmd = f"python {Path(__file__).resolve()} --certify"
    print_status(artifacts, certify_cmd)
    STATUS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_REPORT_PATH.write_text(
        render_status_report(artifacts, certify_cmd), encoding="utf-8")
    print(f"\n  Full dashboard: {STATUS_REPORT_PATH.resolve()}\n")


def main() -> None:
    args = sys.argv[1:]
    if "--certify" in args:
        explicit = [Path(p) for p in args if p != "--certify"]
        targets = explicit if explicit else _inspection_artifacts()
        certify(targets)
    else:
        status(_inspection_artifacts())


if __name__ == "__main__":
    main()
