"""Generate the complete V10 column map for review and for the metadata model.

Reads one exported Research-Trends CSV header + the V10 MMX, resolves every
column through the production path (``build_column_schema_with_mmx``), and
enriches each row with units, engine cadence, MMX power scale, and an evidence
tier per the release spec (§2.1).

Outputs:
  docs/COLUMN_MAP_V10.csv   — one row per exported column, machine-readable
  docs/COLUMN_MAP_V10.json  — same content plus a per-family rollup

Usage:
    python scripts/gen_column_map_v10.py [export.csv] [template.mmx]
"""
from __future__ import annotations

import csv
import importlib.util
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.disable(logging.WARNING)

from qeeg.ingestion.mmx_parser import parse_mmx  # noqa: E402
from qeeg.ingestion.column_mapper import build_column_schema_with_mmx  # noqa: E402
from qeeg.ingestion.cadence import FAMILY_ENGINE_MAP  # noqa: E402
from qeeg.storage.export import _FAMILY_UNITS  # noqa: E402

# No default subject. The path named one, and this script's outputs are
# published. Pass the export explicitly — any Research-Trends or Research
# panel CSV from the shipped template will do.
DEFAULT_CSV: Path | None = None
DEFAULT_MMX = Path(r"C:\ProgramData\Persyst\PedQuEST_Pennsieve_V10_research.mmx")

# Panel identity is derived from instrument count: the V10 template exports the
# 238-instrument Research-Trends panel and the 370-instrument Research panel,
# each plus the 2 Comment/Time tail instruments that are dropped at ingest.
PANELS = {240: ("Research Trends", "RESEARCH_TRENDS"),
          372: ("Full Research Panel", "FULL_RESEARCH_PANEL")}

# PowerType enum -> scale, confirmed against the Persyst UI Power Scale selector
# (Craig, 2026-08-21). Order in the dialog is uV^2, uV, dB, sqrt(uV).
POWER_TYPE = {"0": "uV^2", "1": "uV", "2": "dB", "3": "sqrt(uV)"}

# Evidence tier per release spec §2.1.
#   P-DOC  documented in the Persyst 15 help
#   P-COMM Persyst direct communication (Mike, 2026-08-20/21)
#   MMX    defined by the template only
#   EMP    inferred from exports; no vendor source
TIER = {
    "aeeg": ("P-COMM", "Mike 2026-08-20: Max, Min, Median, p75, p25"),
    "artifact_intensity": ("P-COMM", "Mike 2026-08-20: muscle uV, V-Eye/L-Eye prob 0-1"),
    "artifact_detector": ("P-COMM", "Mike 2026-08-20: 18 internal classifiers; discard"),
    "electrode_quality": ("P-COMM", "Mike 2026-08-20: 22 physical electrodes; >1.0 = disconnect"),
    "fft_spectrogram": ("P-DOC", "Trend Types Frequency.md; PowerType=3 sqrt(uV)"),
    "fft_power": ("P-DOC", "Trend Types Frequency.md; PowerType=1 uV"),
    "fft_power_ratio": ("P-DOC", "Trend Types Frequency.md; ratio of uV, Ratio Max 10"),
    "adr": ("P-DOC", "ratio of uV amplitude, NOT power; = sqrt of power-based ADR"),
    "relative_power": ("MMX", "band/1-30 Hz ratio of uV amplitude, not conventional rel power"),
    "alpha_variability": ("MMX", "RAV = 6-14/1-20 Hz ratio; absent from Persyst help"),
    "spectral_edge": ("P-DOC", "Trend Types Frequency.md; FFT Edge 0-32 Hz"),
    "peak_envelope": ("P-DOC", "Trend Type Peak Envelope.md; 10 s average"),
    "suppression_ratio": ("P-DOC", "Trend Type Suppression Ratio.md; 60 s running average"),
    "asymmetry": ("P-DOC", "Trend Types Asymmetry.md; EASI 0-100, REASI -100..+100"),
    "coherence_spectrogram": ("MMX", "Coherence appears in help only as a stored value"),
    "rhythmicity": ("P-COMM", "Mike 2026-08-21: bands 1-4, 4-9, 9-16, 16-25 Hz (fixed)"),
    "rda": ("P-COMM", "Mike 2026-08-21: binary; 'gen' = bilateral co-occurrence, NOT GRDA"),
    "rhythmic_delta": ("EMP", "MMX boolean logic: threshold on Rhythmicity delta band; NOT periodic discharges"),
    "sleep": ("P-DOC", "Trend Types Sleep-Wake.md; stage codes 0-5"),
    "spike_density": ("P-DOC", "Trend Types Spike Density.md; EventDensity 10 s epochs"),
    "seizure_detection": ("P-DOC", "Trend Types Seizure Detection.md; binary"),
    "seizure_probability": ("P-DOC", "Trend Types Seizure Probability.md; 0-1"),
    "seizure_notification": ("P-DOC", "Trend Panel Active Notifications.md"),
    "seizure_burden": ("MMX", "Persyst-native 5 min burden metric"),
    "status_epilepticus": ("MMX", "ESE: ACNS / Advanced / Combined x binary|percent"),
    "heart_rate": ("P-DOC", "Trend Types Heart Rate.md; BPM"),
    "annotation": ("P-DOC", "free-text comment"),
    "time_display": ("P-DOC", "elapsed-time display row"),
}


def _read_header_block(csv_path: Path) -> dict:
    spec = importlib.util.spec_from_file_location(
        "_audit", ROOT / "scripts" / "audit_4290_1_columns.py")
    audit = importlib.util.module_from_spec(spec)
    sys.modules["_audit"] = audit
    spec.loader.exec_module(audit)
    return audit.read_header_block(csv_path)


def _mmx_engine_stats(mmx_path: Path) -> dict[str, dict]:
    """Full <Engine> attributes keyed by EngineName.

    ``parse_mmx`` keeps only epoch duration/step; the raw tag also carries the
    sampling rate (``WaveformRate``), FFT window geometry, smoothing and filter
    settings — the statistical parameters needed to describe each measure.
    Back-reference tags carry no EpochDuration, so they are skipped.
    """
    text = mmx_path.read_text(errors="replace")
    out: dict[str, dict] = {}
    for tag in re.findall(r"<Engine\b[^>]*>", text):
        at = dict(re.findall(r'([A-Za-z0-9_]+)="([^"]*)"', tag))
        name = at.get("EngineName")
        if not name or "EpochDuration" not in at:
            continue
        rate = float(at["WaveformRate"]) if at.get("WaveformRate") else None
        pts = float(at["PtsPerWindow"]) if at.get("PtsPerWindow") else None
        out[name] = {
            "sampling_rate_hz": rate or "",
            "epoch_duration_s": at.get("EpochDuration", ""),
            "epoch_step_s": at.get("EpochStep", ""),
            "windows_per_epoch": at.get("WindowsPerEpoch", ""),
            "pts_per_window": at.get("PtsPerWindow", ""),
            "overlap_windows": at.get("OverlapWindows", ""),
            "smooth_factor": at.get("SmoothFactor", ""),
            # FFT bin width = sampling rate / points per window.
            "freq_resolution_hz": round(rate / pts, 4) if rate and pts else "",
            # Seconds of signal in one analysis window.
            "window_duration_s": round(pts / rate, 4) if rate and pts else "",
            "high_filter": at.get("HighFilter", ""),
            "low_filter": at.get("LowFilter", ""),
            "notch_filter": at.get("NotchFilter", ""),
            "epoch_centered": at.get("EpochDataIsCentered", ""),
            "freq_min_engine_hz": at.get("P2D2FreqMin", at.get("FreqMin", "")),
            "freq_max_engine_hz": at.get("P2D2FreqMax", at.get("FreqMax", "")),
        }
    return out


def _mmx_power_scale(mmx_path: Path) -> dict[str, str]:
    """Map instrument Name -> power scale string, read from the raw MMX."""
    text = mmx_path.read_text(errors="replace")
    out: dict[str, str] = {}
    for tag in re.finditer(r"<Instrument\b[^>]*>", text):
        s = tag.group(0)
        name = re.search(r'\bName="([^"]*)"', s)
        pt = re.search(r'\bPowerType="(\d)"', s)
        if name and pt:
            out[name.group(1)] = POWER_TYPE.get(pt.group(1), f"PowerType={pt.group(1)}")
    return out


def main() -> None:
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    elif DEFAULT_CSV is not None:
        csv_path = Path(DEFAULT_CSV)
    else:
        sys.exit("usage: python scripts/gen_column_map_v10.py <export.csv> "
                 "[template.mmx]")
    mmx_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MMX

    mmx = parse_mmx(mmx_path)
    hb = _read_header_block(csv_path)
    entries = build_column_schema_with_mmx(hb["code_to_description"], mmx)
    power = _mmx_power_scale(mmx_path)

    engines = {e.name: e for e in mmx.engines.values()}
    estats = _mmx_engine_stats(mmx_path)

    # Families whose values Persyst suppresses to 0 for an entire FFT epoch when
    # artifact is high (empirical, see release spec). Zeros are NOT measurements.
    SUPPRESSED = {"fft_power", "fft_power_ratio", "adr", "relative_power",
                  "alpha_variability", "fft_spectrogram", "spectral_edge",
                  "asymmetry", "coherence_spectrogram"}

    rows = []
    for e in entries:
        fam = e.family or ""
        eng_name = FAMILY_ENGINE_MAP.get(fam, "")
        eng = engines.get(eng_name)
        st = estats.get(eng_name, {})
        tier, tier_note = TIER.get(fam, ("EMP", "no vendor source identified"))
        rows.append({
            "sampling_rate_hz": st.get("sampling_rate_hz", ""),
            "freq_resolution_hz": st.get("freq_resolution_hz", ""),
            "window_duration_s": st.get("window_duration_s", ""),
            "windows_per_epoch": st.get("windows_per_epoch", ""),
            "pts_per_window": st.get("pts_per_window", ""),
            "smooth_factor": st.get("smooth_factor", ""),
            "high_filter": st.get("high_filter", ""),
            "low_filter": st.get("low_filter", ""),
            "notch_filter": st.get("notch_filter", ""),
            "zero_means_suppressed": "yes" if fam in SUPPRESSED else "",
            "col_index": e.col_index,
            "i_code": e.code,
            "i_group": e.i_group,
            "sub_index": e.sub_index,
            "csv_header": e.trend_name,
            "mmx_instrument": e.mmx_name or "",
            "variable_name": e.common_name or "",
            "family": fam,
            "sub_column": e.sub_column_name or "",
            "units": _FAMILY_UNITS.get(fam, ""),
            "power_scale": power.get(e.mmx_name or "", ""),
            "freq_band": e.frequency_band or "",
            "freq_min_hz": e.freq_min_hz if e.freq_min_hz is not None else "",
            "freq_max_hz": e.freq_max_hz if e.freq_max_hz is not None else "",
            "hemisphere": e.hemisphere or "",
            "region": e.region or "",
            "electrode": e.electrode or "",
            "engine": eng_name,
            "epoch_duration_s": getattr(eng, "epoch_duration", "") if eng else "",
            "epoch_step_s": getattr(eng, "epoch_step", "") if eng else "",
            "rows_per_obs": getattr(eng, "rows_per_independent_obs", "") if eng else "",
            "resolution": e.resolution or "",
            "evidence_tier": tier,
            "evidence_note": tier_note,
        })

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)

    fields = list(rows[0].keys())
    # Highest instrument ordinal in the export == panel size incl. the 2 tail
    # instruments, which is the number PANELS is keyed on.
    n_instr = max(r["i_group"] for r in rows)
    panel_label, slug = PANELS.get(n_instr, (f"Panel ({n_instr} instruments)", f"PANEL_{n_instr}"))
    out_csv = docs / f"COLUMN_MAP_V10_{slug}.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    fam_rollup: dict[str, dict] = {}
    for r in rows:
        f = r["family"] or "(unassigned)"
        d = fam_rollup.setdefault(f, {
            "columns": 0, "instruments": set(), "units": r["units"],
            "engine": r["engine"], "evidence_tier": r["evidence_tier"],
            "evidence_note": r["evidence_note"],
        })
        d["columns"] += 1
        d["instruments"].add(r["i_group"])
    for d in fam_rollup.values():
        d["instruments"] = len(d["instruments"])

    out_json = docs / f"COLUMN_MAP_V10_{slug}.json"
    out_json.write_text(json.dumps({
        "panel": panel_label,
        # Basename only: the parent directory is the subject/recording
        # identifier, and this file is published. The timestamped filename
        # still says which export the map came from.
        "source_export": csv_path.name,
        "source_template": mmx_path.name,
        "n_columns": len(rows),
        "n_distinct_variable_names": len({r["variable_name"] for r in rows if r["variable_name"]}),
        "families": fam_rollup,
        "columns": rows,
    }, indent=2), encoding="utf-8")

    print(f"wrote {out_csv}  ({len(rows)} columns)")
    print(f"wrote {out_json}  ({len(fam_rollup)} families)")


if __name__ == "__main__":
    main()
