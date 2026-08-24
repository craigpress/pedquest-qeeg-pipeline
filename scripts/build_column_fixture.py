"""Freeze the column-identity ground truth from the real subject-1 Persyst exports.

Why this exists
---------------
`build_column_schema_with_mmx()` has never had test coverage, and the column
identifiers it emits (`common_name`, `sub_column_name`) are the column names in
analysis datasets that have already been produced. Any change to resolution
renames columns silently.

This script freezes two things before any mapper change:

1. **The ordinal invariant.** Persyst serialises the export panel in order and
   appends two trailing pseudo-columns, so for every export::

       i_group == panel ordinal + 1        (1-based)
       len(panel) + {Comment, Time} == max(i_group)

   The fixture records the resolved MMX instrument for every I-group so a
   regression can be detected per column rather than in aggregate.

2. **The v1 `common_name` baseline** — what the mapper emits *today*. Downstream
   work must diff against this and ship an old->new crosswalk; a renamed column
   is indistinguishable from a broken join in an analysis script.

Resolution prefers the per-recording ``.mg2.mmx`` snapshot (the template Persyst
actually processed that recording with) and falls back to the committed template,
recording which applied.

Usage
-----
    python scripts/build_column_fixture.py            # write the fixture
    python scripts/build_column_fixture.py --check    # exit 1 if it drifted
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util

_spec = importlib.util.spec_from_file_location("_audit", ROOT / "scripts" / "audit_columns.py")
_audit = importlib.util.module_from_spec(_spec)
sys.modules["_audit"] = _audit
_spec.loader.exec_module(_audit)

from qeeg.ingestion.column_mapper import build_column_schema_with_mmx  # noqa: E402
from qeeg.ingestion.mmx_parser import parse_mmx  # noqa: E402

from qeeg.__version__ import COLUMN_SCHEMA_VERSION  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import recording_dir  # noqa: E402

# One fixture per column-vocabulary version. Older ones stay frozen: they are
# the historical record the crosswalk is generated against, so they must never
# be rewritten in place.
FIXTURE = ROOT / "tests" / "fixtures" / f"column_identity_v{COLUMN_SCHEMA_VERSION}.json"

PATIENT_DIR = recording_dir("subject-1_rec")
FALLBACK_MMX = ROOT / "Ref Files" / "PedQuEST_Pennsieve_V10_research.mmx"

# Trailing pseudo-columns Persyst appends after the panel's instruments. They have
# no MMX instrument and are expected to be unresolvable — an allowlist, not a bug.
TAIL_PSEUDO_COLUMNS = ("Comment", "Time")

# export CSV -> (source .dat stem, export panel)
EXPORTS = {
    "20260707_1358_.csv": "Research-Trends",
    "20260707_1413_.csv": "Research-Trends",
    "20260707_1449_.csv": "Research-Trends",
    "20260708_1400_.csv": "Research",
}


def _mmx_for(csv_name: str) -> tuple[Path, str]:
    """Prefer the snapshot for THIS recording; fall back to the template.

    The .dat stem in the CSV's own header names the recording, and each
    recording has its own .mg2.mmx. Taking sorted(...)[0] regardless -- the
    previous behaviour -- silently resolved every export against one
    recording's template while the docstring claimed otherwise. Harmless
    while the snapshots agree; wrong the moment they do not.
    """
    snaps = sorted(PATIENT_DIR.glob("*.mg2.mmx"))
    if not snaps:
        return FALLBACK_MMX, "committed Ref Files template"

    try:
        hb = _audit.read_header_block(PATIENT_DIR / csv_name)
        dat = Path(getattr(hb["metadata"], "source_file", "") or "").stem
    except Exception:
        dat = ""
    if dat:
        for s in snaps:
            if s.name.startswith(dat):
                return s, f"per-recording .mg2.mmx ({s.name})"
    return snaps[0], f"per-recording .mg2.mmx ({snaps[0].name}, stem unmatched)"


def build() -> dict:
    out: dict = {"schema_version": COLUMN_SCHEMA_VERSION, "exports": {}}

    for csv_name, panel_name in EXPORTS.items():
        csv_path = PATIENT_DIR / csv_name
        if not csv_path.exists():
            print(f"  --  {csv_name}: not on the share, skipped")
            continue

        mmx_path, provenance = _mmx_for(csv_name)
        hb = _audit.read_header_block(csv_path)
        c2d: dict[str, str] = hb["code_to_description"]

        # Use the parser's panel view, not audit._load_export_panel(). The latter
        # reads raw XML and counts Montage-nested duplicates, which inflates the
        # Research panel to 385; the parser's deduplicated ordering (367) is what
        # Persyst actually serialises. The two agree on Research-Trends (230).
        mmx_cfg = parse_mmx(mmx_path)
        panel_instruments = mmx_cfg.panels[panel_name].instruments
        kept = [{"Name": i.name} for i in panel_instruments]

        # i_group -> first trend name seen for it (sub-columns share a group)
        groups: dict[int, str] = {}
        for code, trend in c2d.items():
            if not code.startswith("I") or "_" not in code:
                continue
            head, _, _tail = code[1:].partition("_")
            if head.isdigit():
                groups.setdefault(int(head), trend)

        max_ig = max(groups) if groups else 0
        columns = {}
        violations = []
        for ig in sorted(groups):
            ordinal = ig - 1  # 0-based index into the panel
            if ordinal < len(kept):
                inst = kept[ordinal].get("Name", "")
                kind = "instrument"
            else:
                inst = ""
                kind = "tail_pseudo_column"
                if groups[ig] not in TAIL_PSEUDO_COLUMNS:
                    violations.append(
                        {"i_group": ig, "trend": groups[ig],
                         "why": "past end of panel but not an allowlisted pseudo-column"}
                    )
            columns[str(ig)] = {
                "trend_name": groups[ig],
                "mmx_instrument": inst,
                "resolved_by": kind,
            }

        # The invariant the whole ordinal scheme rests on.
        expected_max = len(kept) + len(TAIL_PSEUDO_COLUMNS)
        invariant_ok = (max_ig == expected_max)

        # v1 identifier baseline, straight from today's mapper.
        entries = build_column_schema_with_mmx(c2d, mmx_cfg)
        # `resolution` is frozen too: a silent flip from ordinal to regex is
        # exactly the regression the field was added to expose, and without it
        # here the golden test cannot see it.
        identifiers = {
            e.code: {"common_name": e.common_name,
                     "sub_column_name": e.sub_column_name,
                     "family": e.family,
                     "resolution": e.resolution}
            for e in entries
        }

        out["exports"][csv_name] = {
            "panel": panel_name,
            "mmx": mmx_path.name,
            "mmx_provenance": provenance,
            "panel_instruments": len(kept),
            "max_i_group": max_ig,
            "ordinal_invariant_holds": invariant_ok,
            "expected_max_i_group": expected_max,
            "violations": violations,
            "n_columns": len(identifiers),
            "columns": columns,
            "identifiers": identifiers,
        }

        flag = "ok " if invariant_ok and not violations else "!! "
        print(f"  {flag} {csv_name}: panel={len(kept)} +{len(TAIL_PSEUDO_COLUMNS)} tail "
              f"-> max I{max_ig} (expected I{expected_max}), "
              f"{len(identifiers)} columns, {len(violations)} violations")

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="compare against the committed fixture; exit 1 on drift")
    args = ap.parse_args()

    fresh = build()
    if not fresh["exports"]:
        print("No exports readable — is the Y: research share mounted?")
        return 1

    if args.check:
        if not FIXTURE.exists():
            print(f"{FIXTURE} does not exist yet — run without --check first.")
            return 1
        committed = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if committed == fresh:
            print("\nfixture matches — column identity unchanged")
            return 0
        for name, exp in fresh["exports"].items():
            old = committed.get("exports", {}).get(name)
            if old is None:
                print(f"  NEW export in fixture: {name}")
                continue
            changed = [c for c, v in exp["identifiers"].items()
                       if old["identifiers"].get(c) != v]
            if changed:
                print(f"  {name}: {len(changed)} identifier(s) changed, e.g. {changed[:5]}")
        print("\nColumn identity DRIFTED. If intentional, ship a crosswalk and "
              "bump schema_version before regenerating the fixture.")
        return 1

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(fresh, indent=1, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {FIXTURE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
