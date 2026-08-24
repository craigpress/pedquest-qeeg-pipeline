"""Render a column map as Markdown, so GitHub can display it.

GitHub serves `.html` from a repository as source, never as a page, and stops
rendering `.csv` once the file gets large — which is exactly the case for the
full Research panel. Markdown it renders natively at any size a reader will
tolerate, so this is the format that actually works in the browser.

Two shaping decisions, both about readability rather than file size:

  * **34 fields is not a table.** Only the columns needed to identify a column
    are shown; the CSV and JSON keep the full record and are linked at the top.
  * **Spectrogram families are summarised, not listed.** The full panel is 4,106
    rows, of which 3,770 are frequency bins — 97 rhythmicity bins per channel
    group, 40 FFT bins, and so on. Listing them individually produces pages
    nobody reads. Each bin family collapses to one row per instrument giving the
    bin count and the frequency range, which is the information a reader
    actually wants; the individual bin names are derivable from the slug rule
    and present in full in the CSV.

Usage:
    python scripts/gen_column_map_md.py [RESEARCH_TRENDS|FULL_RESEARCH_PANEL]
    python scripts/gen_column_map_md.py --all
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT))

# Read the discard list from the code rather than restating it, so the map
# cannot claim a family reaches the data when ingestion drops it.
from qeeg.constants import DISCARDED_FAMILIES  # noqa: E402

# Families that are one row per frequency bin. Summarised rather than listed.
BIN_FAMILIES = {"fft_spectrogram", "rhythmicity", "asymmetry",
                "coherence_spectrogram"}

# The fields a reader needs to identify a column, in display order.
CORE = [("variable_name", "Column"), ("i_code", "I-code"),
        ("units", "Units"), ("csv_header", "CSV header"),
        ("mmx_instrument", "MMX instrument"), ("evidence_tier", "Tier")]

TIER_NOTE = {
    "P-DOC":  "vendor-documented",
    "P-COMM": "direct Persyst communication",
    "MMX":    "read from the template",
    "EMP":    "empirical / inferred — provisional",
}


def _esc(s: str) -> str:
    """Escape what would otherwise break a Markdown table cell."""
    return (s or "").replace("|", r"\|").replace("\n", " ").strip()


def _bin_summary(rows: list[dict]) -> list[tuple[str, str, str, str]]:
    """One entry per instrument: (stem, n bins, frequency range, tier)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        # Strip the trailing frequency token to recover the instrument stem.
        groups[re.sub(r"_\d+_\d+hz$", "", r["variable_name"])].append(r)
    out = []
    for stem, rs in sorted(groups.items()):
        freqs = []
        for r in rs:
            m = re.search(r"_(\d+)_(\d+)hz$", r["variable_name"])
            if m:
                freqs.append(float(f"{m.group(1)}.{m.group(2)}"))
        span = f"{min(freqs):g}–{max(freqs):g} Hz" if freqs else "—"
        out.append((stem, str(len(rs)), span, rs[0].get("evidence_tier", "")))
    return out


def render(slug: str) -> str:
    src = DOCS / f"COLUMN_MAP_V10_{slug}.csv"
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    by_family: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_family[r["family"] or "(unassigned)"].append(r)

    panel = slug.replace("_", " ").title()
    L: list[str] = [
        f"# Column map — {panel}",
        "",
        f"**{len(rows):,} columns** across {len(by_family)} families, generated "
        f"from the shipped template through the production resolution path, so "
        f"it cannot drift from what ingestion does.",
        "",
        f"Full record (all 34 fields per column): "
        f"[`COLUMN_MAP_V10_{slug}.csv`](COLUMN_MAP_V10_{slug}.csv) · "
        f"[`.json`](COLUMN_MAP_V10_{slug}.json). "
        f"The `.html` alongside them is a richer browser view, but GitHub will "
        f"not render it — clone the repo and open it locally.",
        "",
        "## Evidence tiers",
        "",
        "Every column carries one. Read it before relying on the column.",
        "",
        "| Tier | Meaning | Count |",
        "|---|---|---:|",
    ]
    tiers = Counter(r.get("evidence_tier", "") for r in rows)
    for tier, n in tiers.most_common():
        L.append(f"| `{tier or '—'}` | {TIER_NOTE.get(tier, '')} | {n:,} |")

    L += ["", "## Families", "",
          "| Family | Columns | Units |", "|---|---:|---|"]
    for fam in sorted(by_family):
        rs = by_family[fam]
        units = _esc(rs[0].get("units", ""))
        if len(units) > 60:
            units = units[:57] + "…"
        if fam in DISCARDED_FAMILIES:
            note = " **— discarded at ingestion, never exported**"
        elif fam in BIN_FAMILIES:
            note = " *(bins summarised below)*"
        else:
            note = ""
        L.append(f"| [`{fam}`](#{fam.replace('_', '-')}) | {len(rs):,} | {units}{note} |")

    for fam in sorted(by_family):
        rs = by_family[fam]
        L += ["", f"### {fam}", ""]
        units = _esc(rs[0].get("units", ""))
        if units:
            L += [f"**Units:** {units}", ""]

        if fam in DISCARDED_FAMILIES:
            # Listing the individual columns would invite exactly the misuse the
            # discard exists to prevent: their names are positional placeholders,
            # not identities read from the export.
            note = _esc(rs[0].get("evidence_note", ""))
            L += [
                f"> **These {len(rs)} columns are present in the export and "
                f"deliberately dropped at ingestion.** They never reach the "
                f"dataframe, the schema, or any output.",
                ">",
                f"> {note}" if note else ">",
                ">",
                "> Their `variable_name` values here are positional placeholders, "
                "not identities read from the export — which is part of why the "
                "family is discarded. See `docs/ARTIFACT_EXCLUSION.md`.",
                "",
            ]
            continue

        if fam in BIN_FAMILIES:
            summary = _bin_summary(rs)
            L += [
                f"{len(rs):,} columns — one per frequency bin, across "
                f"{len(summary)} instruments. Bin names follow "
                f"`<stem>_<centre-frequency>hz` with the decimal written as `_`, "
                f"so the frequency is readable from the slug. Listed by "
                f"instrument; the individual bins are in the CSV.",
                "",
                "| Instrument | Bins | Frequency range | Tier |",
                "|---|---:|---|---|",
            ]
            for stem, n, span, tier in summary:
                L.append(f"| `{stem}` | {n} | {span} | `{tier}` |")
            continue

        L += ["| " + " | ".join(h for _, h in CORE) + " |",
              "|" + "---|" * len(CORE)]
        for r in sorted(rs, key=lambda x: x["variable_name"]):
            cells = []
            for key, _ in CORE:
                v = _esc(r.get(key, ""))
                if len(v) > 70:
                    v = v[:67] + "…"
                cells.append(f"`{v}`" if key in ("variable_name", "i_code") else v)
            L.append("| " + " | ".join(cells) + " |")

    L += ["", "---", "",
          "*Generated by `scripts/gen_column_map_md.py` from the CSV. "
          "Regenerate both with `gen_column_map_v10.py` first.*", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?", default="RESEARCH_TRENDS")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    slugs = ["RESEARCH_TRENDS", "FULL_RESEARCH_PANEL"] if a.all else [a.slug]
    for slug in slugs:
        if not (DOCS / f"COLUMN_MAP_V10_{slug}.csv").exists():
            print(f"  skip {slug}: no CSV")
            continue
        out = DOCS / f"COLUMN_MAP_V10_{slug}.md"
        text = render(slug)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}  "
              f"({len(text) // 1024} KB, {text.count(chr(10)):,} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
