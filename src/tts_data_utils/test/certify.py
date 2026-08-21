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
"""

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from tts_data_utils.test.core.inspection_utils import _normalize

TEST_FILES_DIR = Path(__file__).parent / "core" / "test_files"
STATUS_REPORT_PATH = TEST_FILES_DIR / "inspection_status.html"

_STATUS_CERTIFIED = "CERTIFIED"
_STATUS_STALE = "STALE"
_STATUS_UNCERTIFIED = "UNCERTIFIED"

_STATUS_BADGE = {
    _STATUS_CERTIFIED:   '<span class="badge certified">&#10003; CERTIFIED</span>',
    _STATUS_STALE:       '<span class="badge stale">&#9888; STALE</span>',
    _STATUS_UNCERTIFIED: '<span class="badge uncertified">&#9888; UNCERTIFIED</span>',
}

_STATUS_GUIDANCE = {
    _STATUS_CERTIFIED:   "Hash matches — no action needed.",
    _STATUS_STALE:       "Output changed since last approval. Open, review, then re-certify.",
    _STATUS_UNCERTIFIED: "Never reviewed. Open, verify, then certify.",
}


def _artifact_status(html_path: Path) -> str:
    """Return _STATUS_* for the given artifact."""
    hash_path = html_path.with_suffix(html_path.suffix + ".sha256")
    if not hash_path.exists():
        return _STATUS_UNCERTIFIED
    current = hashlib.sha256(_normalize(html_path.read_bytes())).hexdigest()
    committed = hash_path.read_text().strip().split()[0]
    return _STATUS_CERTIFIED if current == committed else _STATUS_STALE


def certify_file(html_path: Path) -> None:
    """Write a .sha256 sidecar file recording the current digest of html_path."""
    digest = hashlib.sha256(_normalize(html_path.read_bytes())).hexdigest()
    hash_path = html_path.with_suffix(html_path.suffix + ".sha256")
    hash_path.write_text(f"{digest}  {html_path.name}\n")
    print(f"  Certified: {html_path.name}  ({digest[:12]}...)")


def _render_status_report(artifacts: 'list[Path]') -> str:
    """Return a self-contained HTML status dashboard."""
    rows_html = ""
    for art in artifacts:
        status = _artifact_status(art)
        badge = _STATUS_BADGE[status]
        guidance = _STATUS_GUIDANCE[status]
        rows_html += (
            f"<tr>"
            f"<td>{badge}</td>"
            f'<td><a href="{art.name}" target="_blank">{art.name}</a></td>'
            f"<td>{guidance}</td>"
            f"</tr>\n"
        )

    counts = {s: sum(1 for a in artifacts if _artifact_status(a) == s)
              for s in (_STATUS_CERTIFIED, _STATUS_STALE, _STATUS_UNCERTIFIED)}
    needs_review = counts[_STATUS_STALE] + counts[_STATUS_UNCERTIFIED]
    summary_class = "ok" if needs_review == 0 else "warn"
    summary_msg = (
        "All artifacts have been certified by a human reviewer."
        if needs_review == 0
        else (
            f"{needs_review} artifact(s) need human review. "
            f"Open each linked file, verify it looks correct, then run "
            f"<code>python certify.py --certify</code>."
        )
    )
    certify_path = Path(__file__).resolve()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Inspection Artifact Review Status</title>
  <style>
    body {{ font-family: sans-serif; max-width: 960px; margin: 40px auto; padding: 0 20px; color: #333; }}
    h1 {{ font-size: 1.6em; }}
    .meta {{ color: #888; font-size: 0.9em; margin-bottom: 24px; }}
    .summary {{ padding: 14px 18px; border-radius: 6px; margin-bottom: 24px; font-size: 1em; }}
    .summary.ok   {{ background: #d4edda; border-left: 4px solid #28a745; }}
    .summary.warn {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
    th {{ background: #f1f3f5; padding: 10px 12px; text-align: left; border-bottom: 2px solid #dee2e6; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #dee2e6; vertical-align: top; }}
    a {{ color: #0066cc; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 0.85em; font-weight: bold; }}
    .badge.certified   {{ background: #28a745; color: white; }}
    .badge.stale       {{ background: #dc3545; color: white; }}
    .badge.uncertified {{ background: #ffc107; color: #333; }}
    .how-to {{ background: #f8f9fa; border-radius: 6px; padding: 18px 22px; }}
    .how-to h2 {{ margin-top: 0; font-size: 1.1em; }}
    .how-to ol {{ margin: 0; padding-left: 20px; }}
    .how-to li {{ margin-bottom: 6px; }}
    code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-size: 0.92em; }}
  </style>
</head>
<body>
  <h1>Inspection Artifact Review Status</h1>
  <p class="meta">Generated: {ts} &nbsp;|&nbsp;
     {counts[_STATUS_CERTIFIED]} certified &nbsp;|&nbsp;
     {counts[_STATUS_STALE]} stale &nbsp;|&nbsp;
     {counts[_STATUS_UNCERTIFIED]} uncertified &nbsp;|&nbsp;
     {len(artifacts)} total
  </p>

  <div class="summary {summary_class}">{summary_msg}</div>

  <table>
    <thead>
      <tr><th>Status</th><th>Artifact</th><th>Guidance</th></tr>
    </thead>
    <tbody>
{rows_html}    </tbody>
  </table>

  <div class="how-to">
    <h2>How to certify</h2>
    <ol>
      <li>Run the test suite to regenerate all HTML artifacts:<br>
          <code>pytest src/tts_data_utils/test/core/</code></li>
      <li>Click each UNCERTIFIED or STALE link above and verify the output in your browser.</li>
      <li>When satisfied, stamp your approval:<br>
          <code>python {certify_path}</code></li>
      <li>Commit the resulting <code>.sha256</code> files — they are the record of your review.</li>
    </ol>
    <p><strong>Never run <code>certify.py --certify</code> from CI or automated scripts.</strong>
       The .sha256 files are your personal stamp. Only update them after a human has looked.</p>
  </div>
</body>
</html>
"""


def status(artifacts: 'list[Path]') -> None:
    """Print a console summary and write the HTML status dashboard."""
    if not artifacts:
        print(f"No HTML artifacts found in {TEST_FILES_DIR}")
        return

    print("\nInspection Artifact Review Status\n" + "=" * 36)
    needs_review = 0
    for art in artifacts:
        s = _artifact_status(art)
        icon = {"CERTIFIED": "✓", "STALE": "✗", "UNCERTIFIED": "?"}[s]
        print(f"  {icon} [{s:12s}]  {art.name}")
        if s != _STATUS_CERTIFIED:
            needs_review += 1

    print()
    if needs_review:
        print(f"  {needs_review} artifact(s) need review.")
        print(f"  Open each file, verify it, then run: python {Path(__file__).resolve()} --certify")
    else:
        print("  All artifacts certified.")

    html = _render_status_report(artifacts)
    STATUS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"\n  Full dashboard: {STATUS_REPORT_PATH.resolve()}\n")


def certify(targets: 'list[Path]') -> None:
    """Stamp .sha256 approval files for each target artifact."""
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


def _inspection_artifacts() -> 'list[Path]':
    return sorted(
        p for p in TEST_FILES_DIR.glob("*.html")
        if p.name != STATUS_REPORT_PATH.name
    )


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
