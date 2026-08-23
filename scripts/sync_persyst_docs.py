"""Single source-of-truth sync for all *derived* Persyst documentation.

Anti-drift entrypoint. Code + the committed MMX are the source of truth; this
script regenerates every derived artifact from them so the GitHub docs, the
Obsidian vault, and the scripting can never silently diverge:

  docs/persyst_v10_catalog.json        – per-instrument catalog (from the MMX)
  docs/persyst_v10_panel_index.md      – per-panel instrument table (from the MMX)
  docs/persyst_families.generated.md  – family -> unit / engine / export-group /
                                        value-range table (from CODE registries)
  <vault>/Projects/qEEG Analysis Pipeline/Persyst Reference/persyst_families.generated.md
                                        – generated copy of the repo file

Usage:
  python scripts/sync_persyst_docs.py           # regenerate all artifacts in place
  python scripts/sync_persyst_docs.py --check    # exit 1 if any committed artifact
                                                 #   is stale (used by the drift test/CI)

The committed MMX at `Ref Files/PedQuEST_Pennsieve_V10_research.mmx` is the
canonical input (NOT the volatile C:\\ProgramData copy) so regeneration is
deterministic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qeeg.ingestion.mmx_parser import parse_mmx  # noqa: E402
from qeeg.ingestion.column_mapper import (  # noqa: E402
    classify_family, extract_hemisphere, extract_region, extract_electrode,
    extract_frequency_range, map_to_band, generate_common_name, ColumnEntry,
)
from qeeg.ingestion.cadence import FAMILY_ENGINE_MAP  # noqa: E402
from qeeg.storage.export import _FAMILY_UNITS, _GROUP_FAMILIES  # noqa: E402
from qeeg.validation.data_checks import FAMILY_VALUE_RANGES  # noqa: E402
from qeeg.constants import FEATURE_FAMILIES  # noqa: E402

MMX = ROOT / "Ref Files" / "PedQuEST_Pennsieve_V10_research.mmx"
DOCS = ROOT / "docs"
CATALOG_JSON = DOCS / "persyst_v10_catalog.json"
PANEL_INDEX_MD = DOCS / "persyst_v10_panel_index.md"
FAMILIES_MD = DOCS / "persyst_families.generated.md"

# Vault (outside the git repo). Keep a real generated copy: Syncthing does not
# replicate Windows symlinks to the NAS/OpenClaw vault copy.
VAULT_DIR = Path(r"E:/Craig_Vault/Projects/qEEG Analysis Pipeline/Persyst Reference")
VAULT_FAMILIES = VAULT_DIR / "persyst_families.generated.md"


# ---------------------------------------------------------------------------
# 1. Per-instrument catalog + panel index (from the MMX)
# ---------------------------------------------------------------------------

def _mmx_name_to_csv_desc(name: str, channels: str) -> str | None:
    ch = channels.strip()
    m = re.match(r"FFT_PowerRatio\s+(\d+-\d+)//(\d+-\d+)\s+", name)
    if m:
        return f"FFT PowerRatio, {m.group(1)}/{m.group(2)} Hz, {ch}"
    m = re.match(r"FFT_Power\s+(\d+)-(\d+)\s+", name)
    if m:
        return f"FFT Power, {m.group(1)} - {m.group(2)} Hz, {ch}"
    m = re.match(r"FFT_Edge\s+(\d+)\s+(\d+)-(\d+)\s+", name)
    if m:
        return f"SEF{m.group(1)}, {m.group(2)} - {m.group(3)} Hz, {ch}"
    if name.startswith("BSR "):
        return f"Suppression Ratio, {ch}"
    m = re.match(r"PeakEnvelope\s+(\d+)-(\d+)\s+", name)
    if m:
        return f"PeakEnvelope, {m.group(1)} - {m.group(2)} Hz, {ch}"
    return None


def _predicted_slug(name: str, channels: str) -> str | None:
    desc = _mmx_name_to_csv_desc(name, channels)
    if desc is None:
        return None
    fam = classify_family(desc)
    fmin, fmax = extract_frequency_range(desc)
    entry = ColumnEntry(
        col_index=0, code="I0_1", i_group=0, sub_index=1, trend_name=desc,
        family=fam, frequency_band=map_to_band(fmin, fmax) if fmin is not None else "",
        freq_min_hz=fmin, freq_max_hz=fmax, hemisphere=extract_hemisphere(desc),
        region=extract_region(desc), electrode=extract_electrode(desc),
    )
    return generate_common_name(entry)


def build_catalog(cfg) -> dict:
    fam = Counter(i.family for i in cfg.instruments.values())
    return {
        "mmx_version": cfg.mmx_version,
        "source": MMX.name,
        "description": "PedQuEST Pennsieve V10 research MMX - instrument catalog (generated)",
        "n_instruments": len(cfg.instruments),
        "n_panels": len(cfg.panels),
        "families": dict(sorted(fam.items())),
        "instruments": [
            {
                "name": i.name, "family": i.family, "channels": i.channels,
                "predicted_slug": _predicted_slug(i.name, i.channels),
                "panels": i.panels, "freq_min": i.freq_min, "freq_max": i.freq_max,
                "engine": i.engine.name if i.engine else None,
            }
            for i in sorted(cfg.instruments.values(), key=lambda x: x.name)
        ],
    }


def build_panel_index(cfg) -> str:
    lines = [
        "# Persyst V10 MMX - Panel x Instrument Index",
        "",
        f"<!-- GENERATED by scripts/sync_persyst_docs.py from {MMX.name} "
        f"(LTMPage Version {cfg.mmx_version}). Do not edit by hand. -->",
        "",
        "The template defines non-lateralized **Anterior**/**Posterior** channel sets, "
        "**relative band power** (`FFT PowerRatio {band}/1-30 Hz`), and Persyst-native "
        "**Status Epilepticus** / **Seizure Burden** metrics. See `PERSYST_V10_REFERENCE.md`.",
        "",
    ]
    for pname, panel in cfg.panels.items():
        lines.append(f"## {pname}  ({len(panel.instruments)} slots)")
        lines.append("")
        lines.append("| # | Instrument (Name) | Family | Channels | Predicted slug |")
        lines.append("|---:|---|---|---|---|")
        for k, inst in enumerate(panel.instruments, 1):
            slug = _predicted_slug(inst.name, inst.channels) or ""
            nm = inst.name if len(inst.name) <= 70 else inst.name[:67] + "..."
            lines.append(f"| {k} | `{nm}` | {inst.family} | `{inst.channels}` | `{slug}` |")
        lines.append("")
    return "\n".join(lines) + "\n"


def check_collisions(cfg) -> dict[str, list[str]]:
    slug_to_names: dict[str, list[str]] = defaultdict(list)
    for inst in cfg.instruments.values():
        slug = _predicted_slug(inst.name, inst.channels)
        if slug is not None:
            slug_to_names[slug].append(inst.name)
    return {s: sorted(set(ns)) for s, ns in slug_to_names.items() if len(set(ns)) > 1}


# ---------------------------------------------------------------------------
# 2. Family facts table (from CODE registries) - the cross-artifact contract
# ---------------------------------------------------------------------------

def all_families(cfg) -> list[str]:
    """The canonical family set = union across every code registry + the catalog."""
    fams: set[str] = set(_FAMILY_UNITS) | set(FAMILY_ENGINE_MAP) | set(FAMILY_VALUE_RANGES)
    for group in _GROUP_FAMILIES.values():
        fams |= set(group)
    fams |= set(FEATURE_FAMILIES)
    fams |= {i.family for i in cfg.instruments.values()}
    fams.discard("other")
    return sorted(fams)


def _group_of(family: str) -> str:
    for group, members in _GROUP_FAMILIES.items():
        if family in members:
            return group
    return "-"


def build_families_table(cfg) -> str:
    rows = []
    catalog_fams = {i.family for i in cfg.instruments.values()}
    for fam in all_families(cfg):
        rng = FAMILY_VALUE_RANGES.get(fam)
        rows.append((
            fam,
            _FAMILY_UNITS.get(fam, "-"),
            FAMILY_ENGINE_MAP.get(fam, "-"),
            _group_of(fam),
            f"{rng[0]}-{rng[1]}" if rng else "-",
            "yes" if fam in catalog_fams else "",
        ))
    md = [
        "| Family | Unit | Engine | Export group | Value range | In MMX |",
        "|---|---|---|---|---|:---:|",
    ]
    for fam, unit, eng, grp, rng, incat in rows:
        md.append(f"| `{fam}` | {unit} | `{eng}` | {grp} | {rng} | {incat} |")
    return "\n".join(md)


def build_families_md(cfg) -> str:
    return "\n".join([
        "# Persyst Feature Families - Generated Facts",
        "",
        "<!-- GENERATED by scripts/sync_persyst_docs.py from the code registries "
        "(constants.FEATURE_FAMILIES, cadence.FAMILY_ENGINE_MAP, export._FAMILY_UNITS / "
        "_GROUP_FAMILIES, data_checks.FAMILY_VALUE_RANGES) + the committed MMX. "
        "Do not edit by hand - run the script. -->",
        "",
        "This is the **machine-checkable contract** for Persyst feature families. The "
        "narrative docs (`PERSYST_V10_REFERENCE.md`, `DATA_DICTIONARY_v4.md`) and the "
        "Obsidian vault cite this table; they must not restate these values. A drift "
        "test (`tests/test_persyst_doc_sync.py`) fails if this file is stale vs the code.",
        "",
        build_families_table(cfg),
        "",
    ]) + "\n"


# ---------------------------------------------------------------------------
# 3. Orchestration: write or check
# ---------------------------------------------------------------------------

def generate_all():
    """Return ({path: desired_content}, cfg) for every repo artifact (no writes)."""
    cfg = parse_mmx(MMX)
    artifacts = {
        str(CATALOG_JSON): json.dumps(build_catalog(cfg), indent=2) + "\n",
        str(PANEL_INDEX_MD): build_panel_index(cfg),
        str(FAMILIES_MD): build_families_md(cfg),
    }
    return artifacts, cfg


def stale_artifacts() -> list[str]:
    artifacts, _ = generate_all()
    out = []
    for path, content in artifacts.items():
        p = Path(path)
        if not p.exists() or p.read_text(encoding="utf-8") != content:
            out.append(path)
    return out


def sync_vault_copy(repo_file: Path) -> None:
    """Write the generated families file as a real vault file for Syncthing."""
    if not VAULT_DIR.exists():
        print(f"(vault not mounted at {VAULT_DIR} - skipped)")
        return

    VAULT_FAMILIES.write_text(repo_file.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote vault copy: {VAULT_FAMILIES}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if any artifact is stale")
    args = ap.parse_args()

    artifacts, cfg = generate_all()
    collisions = check_collisions(cfg)
    stale = [p for p, c in artifacts.items()
             if not Path(p).exists() or Path(p).read_text(encoding="utf-8") != c]

    if args.check:
        ok = True
        if collisions:
            ok = False
            print(f"DRIFT CHECK FAILED: {len(collisions)} slug collisions:")
            for s, names in collisions.items():
                print(f"   {s}: {names}")
        if stale:
            ok = False
            print("DRIFT CHECK FAILED - stale (run: python scripts/sync_persyst_docs.py):")
            for p in stale:
                print(f"   {Path(p).relative_to(ROOT)}")
        if ok:
            print("Doc sync OK - all generated artifacts match code + MMX.")
        return 0 if ok else 1

    for path, content in artifacts.items():
        Path(path).write_text(content, encoding="utf-8")
        print(f"wrote {Path(path).relative_to(ROOT)}")

    sync_vault_copy(FAMILIES_MD)

    print(f"\n{MMX.name}: {len(cfg.instruments)} instruments, {len(cfg.panels)} panels, "
          f"{len(collisions)} collisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
