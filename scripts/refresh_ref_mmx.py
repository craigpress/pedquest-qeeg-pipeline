"""Refresh the committed Persyst MMX templates in `Ref Files/` from the live install.

Why this exists
---------------
`Ref Files/*.mmx` is the *canonical* input for every downstream artifact
(`sync_persyst_docs.py`, the column audits, `mmx_label_resolver.py`). Persyst
edits its own copies under ``C:\\ProgramData\\Persyst`` in place, so the committed
copies drift silently as soon as a template is edited in Persyst.

That drift caused a real defect: the committed V8 was a 2026-06-10 draft while the
exports were produced from the 2026-06-11 template. The two differ by 8 removed
spectrogram instruments and one renamed instrument, which shifted every recorded
panel position from 27 onward by 8.

Usage
-----
    python scripts/refresh_ref_mmx.py --check    # exit 1 if any committed copy is stale
    python scripts/refresh_ref_mmx.py            # copy live -> Ref Files, report what changed

`--check` is the CI/drift-test entry point; run it before trusting any generated
column documentation.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_DIR = ROOT / "Ref Files"
LIVE_DIR = Path(r"C:\ProgramData\Persyst")

# Templates tracked in the repo. V8 is the current source of truth for column
# naming; V7 is kept for provenance, V9 because it is the newest template Persyst
# holds (instrument-identical to V8 — it differs only in engine serialisation
# order and the description string).
TEMPLATES = (
    "PedQuEST_Pennsieve_V7_research.mmx",
    "PedQuEST_Pennsieve_V10_research.mmx",
    "PedQuEST_Pennsieve_V9_research.mmx",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit 1 if stale; copy nothing")
    args = ap.parse_args()

    stale: list[str] = []
    missing: list[str] = []

    for name in TEMPLATES:
        live, ref = LIVE_DIR / name, REF_DIR / name
        if not live.exists():
            missing.append(name)
            print(f"  ??  {name}: not present in {LIVE_DIR}")
            continue

        live_hash = _sha256(live)
        ref_hash = _sha256(ref) if ref.exists() else None

        if ref_hash == live_hash:
            print(f"  ok  {name}")
            continue

        stale.append(name)
        if args.check:
            what = "MISSING from Ref Files" if ref_hash is None else "STALE"
            print(f"  !!  {name}: {what} "
                  f"(live {live.stat().st_size} b, committed "
                  f"{ref.stat().st_size if ref.exists() else 0} b)")
        else:
            shutil.copy2(live, ref)
            assert _sha256(ref) == live_hash, f"copy verification failed for {name}"
            print(f"  ->  {name}: refreshed ({live.stat().st_size} b)")

    if missing:
        print(f"\n{len(missing)} template(s) not found in the live install — "
              f"is Persyst installed on this machine?")

    if args.check and missing:
        # Exiting 0 here would make --check green-and-blind on any machine
        # without Persyst installed -- i.e. on CI, which is the one place it is
        # meant to run. Absence of the live install is an inconclusive check,
        # not a passing one.
        print(f"\n{len(missing)} template(s) could not be checked: no live "
              f"install at {LIVE_DIR}. Drift is UNVERIFIED, not absent.")
        return 2

    if args.check and stale:
        print(f"\n{len(stale)} committed template(s) are stale. "
              f"Run `python scripts/refresh_ref_mmx.py`, then regenerate the "
              f"derived docs with `python scripts/sync_persyst_docs.py`.")
        return 1

    if stale and not args.check:
        print(f"\nRefreshed {len(stale)} template(s). Regenerate derived docs with "
              f"`python scripts/sync_persyst_docs.py` — committed artifacts are now stale.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
