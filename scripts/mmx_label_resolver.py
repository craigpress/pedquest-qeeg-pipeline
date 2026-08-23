"""Reconstruct Persyst CSV trend labels from an MMX, and match them to a CSV export.

Persyst composes the trend-row label for an instrument as:

  base instrument     : "{GraphTitle}[, {FreqMin} - {FreqMax} Hz][, {Channels}]"
                        (ratio instruments use "{num_lo}-{num_hi}/{den_lo}-{den_hi} Hz")
  derived instrument  : "{GraphTitle}, {label of the instrument named in Channels}"

`Channels` is a channel-set name for base instruments and a bracketed expression
referencing other instruments for derived ones. Resolving it recursively
reproduces the CSV label, which gives a name-based CSV↔MMX identity that does not
depend on panel ordering.

Usage:
    python scripts/mmx_label_resolver.py <csv> [--mmx PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_4290_1_columns import read_header_block

DEFAULT_MMX = Path(__file__).resolve().parents[1] / "Ref Files" / "PedQuEST_Pennsieve_V10_research.mmx"


def _num(x: str) -> str:
    f = float(x)
    return str(int(f)) if f == int(f) else str(f)


def load_instruments(mmx: Path) -> list[dict]:
    root = ET.parse(mmx).getroot()
    ins = root.find("Instruments")
    return [dict(e.attrib)
            for c in [ins] + list(ins.findall("Montage"))
            for e in c if e.tag == "Instrument"]


def build_labels(els: list[dict]) -> dict[int, set[str]]:
    """Return {index in els -> set of candidate CSV labels}."""
    by_name: dict[str, int] = {}
    for i, e in enumerate(els):
        by_name.setdefault(e.get("Name", ""), i)

    cache: dict[int, set[str]] = {}

    def freq_tokens(e: dict) -> list[str]:
        fmin, fmax = e.get("FreqMin"), e.get("FreqMax")
        dmin, dmax = e.get("FreqMinDenom"), e.get("FreqMaxDenom")
        if fmin is None or fmax is None:
            return []
        out = [f"{_num(fmin)} - {_num(fmax)} Hz"]
        if dmin is not None and dmax is not None:
            out.insert(0, f"{_num(fmin)}-{_num(fmax)}/{_num(dmin)}-{_num(dmax)} Hz")
        return out

    def compose(i: int, depth: int = 0) -> set[str]:
        if i in cache:
            return cache[i]
        if depth > 6:
            return set()
        cache[i] = set()          # cycle guard
        e = els[i]
        gt = e.get("GraphTitle", "") or e.get("Name", "")
        ch = e.get("Channels", "") or ""
        out: set[str] = {gt}

        # Some instruments (e.g. PeakEnvelope) carry no FreqMin/FreqMax attribute but
        # still show a band in the CSV label; the band is embedded in their Name
        # ("PeakEnvelope 2-20 All 10-20_avg").
        extra_freq: list[str] = []
        m = re.search(r"\b(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\b", e.get("Name", ""))
        if m and not freq_tokens(e):
            extra_freq.append(f"{_num(m.group(1))} - {_num(m.group(2))} Hz")

        if ch and not ch.lstrip().startswith("["):
            # Base instrument: Channels is a channel-set name.
            for fr in (freq_tokens(e) + extra_freq) or [None]:
                head = f"{gt}, {fr}" if fr else gt
                out.add(head)
                out.add(f"{head}, {ch}")
            out.add(f"{gt}, {ch}")
        else:
            # Derived: Channels references other instruments by Name in brackets.
            # Strip the OUTERMOST bracket first — parent names are themselves
            # bracketed ("[SumValues_Abs_0-0 [Rhythmicity … _avg]]"), so an
            # inner-bracket regex would resolve to the grandparent.
            refs: list[int] = []
            stripped = ch.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                inner = stripped[1:-1]
                if inner in by_name:
                    refs = [by_name[inner]]
            if not refs:
                refs = [by_name[nm] for nm in re.findall(r"\[([^\[\]]+)\]", ch)
                        if nm in by_name]
            # Only a single-parent reference reproduces the CSV's "child, parent" form.
            if len(set(refs)) == 1:
                for parent in compose(refs[0], depth + 1):
                    out.add(f"{gt}, {parent}")
            # Persyst sometimes appends the parent's *raw* Channels expression rather
            # than the parent's composed label (threshold / sleep-state chains).
            if ch:
                out.add(f"{gt}, {ch}")
                if len(set(refs)) == 1:
                    p = els[refs[0]]
                    p_gt = p.get("GraphTitle", "") or p.get("Name", "")
                    p_ch = p.get("Channels", "") or ""
                    if p_ch:
                        out.add(f"{gt}, {p_gt}, {p_ch}")
            for fr in freq_tokens(e) + extra_freq:
                out.add(f"{gt}, {fr}")
        cache[i] = {o for o in out if o}
        return cache[i]

    return {i: compose(i) for i in range(len(els))}


def match(csv_path: Path, mmx: Path) -> dict:
    hb = read_header_block(csv_path)
    groups: dict[int, str] = {}
    widths: dict[int, int] = {}
    for code, trend in hb["code_to_description"].items():
        m = re.fullmatch(r"I(\d+)_(\d+)", code)
        if not m:
            continue
        g, sub = int(m.group(1)), int(m.group(2))
        groups.setdefault(g, trend)
        widths[g] = max(widths.get(g, 0), sub)

    els = load_instruments(mmx)
    labels = build_labels(els)
    index: dict[str, list[int]] = defaultdict(list)
    for i, labs in labels.items():
        for lab in labs:
            index[lab].append(i)

    resolved, ambiguous, unmatched = {}, {}, {}
    for g in sorted(groups):
        hits = index.get(groups[g], [])
        if len(hits) == 1:
            resolved[g] = hits[0]
        elif hits:
            ambiguous[g] = hits
        else:
            unmatched[g] = groups[g]

    # Bijection check on the resolved subset.
    used = Counter(resolved.values())
    collisions = {i: c for i, c in used.items() if c > 1}

    return {
        "csv": csv_path.name,
        "mmx": str(mmx),
        "n_csv_instruments": len(groups),
        "n_mmx_instruments": len(els),
        "n_resolved_unique": len(resolved),
        "n_ambiguous": len(ambiguous),
        "n_unmatched": len(unmatched),
        "n_mmx_instruments_used": len(used),
        "one_to_one": not collisions and not ambiguous and not unmatched,
        "mmx_instruments_claimed_twice": [
            {"mmx_name": els[i].get("Name", "")[:90], "times": c,
             "i_groups": [f"I{g}" for g, j in resolved.items() if j == i]}
            for i, c in collisions.items()],
        "unmatched_detail": {f"I{g}": t for g, t in list(unmatched.items())[:40]},
        "ambiguous_detail": {
            f"I{g}": [els[i].get("Name", "")[:70] for i in hits]
            for g, hits in list(ambiguous.items())[:20]},
        "mapping": {
            f"I{g}": {
                "csv_trend_name": groups[g],
                "n_sub_columns": widths[g],
                "mmx_name": els[i].get("Name", ""),
                "mmx_graph_title": els[i].get("GraphTitle", ""),
                "mmx_channels": els[i].get("Channels", ""),
                "mmx_freq_min": els[i].get("FreqMin"),
                "mmx_freq_max": els[i].get("FreqMax"),
                "mmx_freq_min_denom": els[i].get("FreqMinDenom"),
                "mmx_freq_max_denom": els[i].get("FreqMaxDenom"),
                "mmx_cls_id": els[i].get("ClsId", ""),
            } for g, i in resolved.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--mmx", default=str(DEFAULT_MMX))
    ap.add_argument("--out")
    a = ap.parse_args()
    r = match(Path(a.csv), Path(a.mmx))
    print(json.dumps({k: v for k, v in r.items() if k != "mapping"}, indent=1)[:4000])
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(r, indent=2), encoding="utf-8")
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
