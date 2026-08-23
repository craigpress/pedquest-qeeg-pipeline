"""Verify a full-panel export end to end — the check QEEG-061 is blocked on.

The `Research-Trends` panel carries no spectrogram families, so nothing in the
local fixture set exercises the spectrogram path. Point this at a `Research` or
`Research-Spectrograms` export and it runs the checks that panel makes possible:

  1. Panel resolution — every column resolves by panel ordinal, not by regex.
  2. Naming — `common_name` is unique, a valid identifier, and carries no
     `__dupN` uniqueness-backstop suffix.
  3. Spectrogram families — bin counts and frequency axes for FFT (40),
     asymmetry (40), coherence (63) and rhythmicity (97, sqrt-scaled).
  4. NaN transport — AR-rejected values reach the API boundary as JSON `null`,
     never as a bare NaN (which is invalid JSON and would floor the render).

Usage:
    python scripts/verify_full_panel.py <export.csv> [template.mmx]
    python scripts/verify_full_panel.py --scan [dir]

`--scan` reports the panel width of every export under a directory and names
the widest, so you can tell at a glance whether a full-panel export has landed.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from qeeg.constants import SPECTROGRAM_FREQ_MAP  # noqa: E402
from qeeg.ingestion.mmx_parser import parse_mmx  # noqa: E402
from qeeg.pipeline import process_patient  # noqa: E402

DEFAULT_MMX = ROOT / "Ref Files" / "PedQuEST_Pennsieve_V10_research.mmx"
DEFAULT_SCAN = Path(r"C:\temp\cardiac_arrest\Test EEGs")

# spec_type -> (schema family, expected bins)
SPECTROGRAMS = {
    "fft_left":    ("fft_spectrogram", 40),
    "fft_right":   ("fft_spectrogram", 40),
    "asymmetry":   ("asymmetry", 40),
    "coherence":   ("coherence_spectrogram", 63),
    "rhythmicity": ("rhythmicity", 97),
}


def panel_width(csv_path: Path) -> int:
    """Column count of the I-code header row, or 0 if not found."""
    with csv_path.open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i > 120:
                break
            if line.startswith("ClockDateTime,"):
                return len(line.split(","))
    return 0


def scan(root: Path) -> int:
    files = sorted(root.rglob("2026*.csv")) or sorted(root.rglob("*.csv"))
    if not files:
        print(f"no exports under {root}")
        return 1
    widths: dict[int, list[Path]] = {}
    for f in files:
        widths.setdefault(panel_width(f), []).append(f)
    print(f"{len(files)} export(s) under {root}\n")
    for w in sorted(widths, reverse=True):
        print(f"  {w:6d} cols  x{len(widths[w]):<3d}  e.g. {widths[w][0].name}")
    widest = max(widths)
    print()
    if widest > 400:
        print(f"Full-panel export present ({widest} cols):")
        print(f"  {widths[widest][0]}")
        print("\nRun:")
        print(f'  python scripts/verify_full_panel.py "{widths[widest][0]}"')
        print(f'  python scripts/gen_column_map_v10.py "{widths[widest][0]}"')
    else:
        print(f"Widest is {widest} cols — still the Research-Trends panel.")
        print("A full-panel export is >400 columns (Research is ~4,100).")
    return 0


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    return ok


def verify(csv_path: Path, mmx_path: Path) -> int:
    width = panel_width(csv_path)
    print(f"export   : {csv_path}")
    print(f"template : {mmx_path.name}")
    print(f"width    : {width} columns\n")
    if width and width < 400:
        print("WARNING: this looks like the Research-Trends panel. It carries no")
        print("         spectrogram families, so section 3 below will find nothing.\n")

    mmx = parse_mmx(mmx_path)
    result = process_patient(csv_path, mmx=mmx, patient_id=csv_path.stem)
    schema = result.schema
    ok = True

    print("1. Panel resolution")
    methods: dict[str, int] = {}
    for e in schema:
        methods[getattr(e, "resolution", "?")] = methods.get(getattr(e, "resolution", "?"), 0) + 1
    non_ordinal = sum(n for m, n in methods.items() if m not in ("ordinal", "tail"))
    ok &= _check("every column resolves by panel ordinal", non_ordinal == 0,
                 f"{methods}")

    print("\n2. Naming")
    names = [e.common_name for e in schema if e.common_name]
    dupes = {n for n in names if names.count(n) > 1}
    ok &= _check("common_name is unique", not dupes, f"{sorted(dupes)[:5]}" if dupes else f"{len(names)} names")
    backstop = [n for n in names if "__dup" in n]
    ok &= _check("no __dupN backstop names", not backstop, f"{backstop[:5]}" if backstop else "")
    bad_id = [n for n in names if not n.isidentifier()]
    ok &= _check("all names are valid identifiers", not bad_id, f"{bad_id[:5]}" if bad_id else "")
    discarded = [e.code for e in schema if e.family == "artifact_detector"]
    ok &= _check("artifact_detector discarded", not discarded, f"{len(discarded)} leaked" if discarded else "")

    print("\n3. Spectrogram families")
    from api.services.pipeline_service import PipelineService
    svc = PipelineService.__new__(PipelineService)
    for spec_type, (family, expected) in SPECTROGRAMS.items():
        present = [e for e in schema if e.family == family]
        if not present:
            print(f"  [SKIP] {spec_type:12s} — family '{family}' absent from this panel")
            continue
        freqs, hours, matrix = svc.get_spectrogram_data(result, spec_type)
        ok &= _check(f"{spec_type:12s} bins == {expected}", len(freqs) == expected,
                     f"got {len(freqs)}")
        if freqs:
            info = SPECTROGRAM_FREQ_MAP.get(f"{family}_spectrogram" if not family.endswith("spectrogram") else family, {})
            lo, hi = info.get("freq_min"), info.get("freq_max")
            monotonic = all(a < b for a, b in zip(freqs, freqs[1:]))
            ok &= _check(f"{spec_type:12s} axis strictly increasing", monotonic,
                         f"{freqs[0]:.2f}..{freqs[-1]:.2f} Hz (expect {lo}..{hi})")
            leak = any(isinstance(v, float) and math.isnan(v) for r in matrix for v in r)
            ok &= _check(f"{spec_type:12s} no bare NaN in matrix", not leak)
            try:
                json.dumps(matrix[:2])
                ok &= _check(f"{spec_type:12s} JSON-serialisable", True)
            except (TypeError, ValueError) as exc:
                ok &= _check(f"{spec_type:12s} JSON-serialisable", False, str(exc))

    print("\n4. AR rejection transport")
    ar = result.ar_rejection
    empty = ar is not None and getattr(ar, "segment_empty", False)
    if empty:
        print("  [SKIP] AR found no analysable reference measure — see section 5")
    elif ar is None or not getattr(ar, "cells_nulled", 0):
        print("  [SKIP] no values were AR-rejected in this recording")
    else:
        nan_cols = [c for c in result.epochs.columns
                    if result.epochs[c].dtype.kind == "f" and result.epochs[c].isna().any()]
        ok &= _check("rejected values are NaN in the frame", bool(nan_cols),
                     f"{ar.cells_nulled} cells across {ar.columns_touched} columns")

    print("\n5. Data sanity")
    # A zero in a positive-definite family cannot be a measurement. If nearly
    # every one of them is zero the export carries no data, however well-formed
    # its header is — sections 1-4 cannot tell the difference, and AR
    # deliberately declines to null such a file rather than misreport an empty
    # segment as a heavily artifacted one.
    df = result.epochs
    zi_cols = [e.code for e in schema
               if e.family in ("fft_spectrogram", "fft_power", "aeeg", "peak_envelope")
               and e.code in df.columns][:200]
    if zi_cols:
        zero_rate = float((df[zi_cols] == 0).mean().mean()) * 100
        ok &= _check("positive-definite trends are not all zero", zero_rate < 90.0,
                     f"{zero_rate:.2f}% of sampled cells are exactly 0 "
                     f"across {len(zi_cols)} columns")
    ok &= _check("AR found an analysable reference measure", not empty,
                 "segment is empty, not artifacted" if empty else "")
    blocking = [w for w in result.warnings
                if "exclude from analysis" in w or "no analysable reference" in w]
    ok &= _check("no blocking pipeline warning", not blocking,
                 blocking[0] if blocking else
                 f"{len(result.warnings)} informational warning(s)")

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    if ok:
        print("\nNext: regenerate the full-panel column map from this export —")
        print(f'  python scripts/gen_column_map_v10.py "{csv_path}"')
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", help="export CSV to verify")
    ap.add_argument("mmx", nargs="?", default=str(DEFAULT_MMX))
    ap.add_argument("--scan", nargs="?", const=str(DEFAULT_SCAN), default=None,
                    metavar="DIR", help="report panel widths under DIR and exit")
    args = ap.parse_args()

    if args.scan is not None:
        return scan(Path(args.scan))
    if not args.csv:
        ap.error("give an export CSV, or --scan to look for one")
    return verify(Path(args.csv), Path(args.mmx))


if __name__ == "__main__":
    raise SystemExit(main())
