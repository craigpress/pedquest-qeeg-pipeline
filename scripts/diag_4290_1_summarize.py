"""Summarize the JSON output from diag_4290_1_coverage.py."""
import json
import sys

import os
path = os.environ.get("DIAG_JSON", r"C:\Users\craig\AppData\Local\Temp\diag_4290_1.json")
with open(path) as f:
    d = json.load(f)

def pct(x):
    return "n/a" if x is None else f"{100*x:.1f}%"

print("=" * 80)
print("FAMILY SUMMARY: /api/patients/4290-1/epochs?families=<fam>")
print("=" * 80)
print(f"{'family':<22} {'cols':>5} {'early':>8} {'pre':>8} {'bnd':>8} {'late':>8} {'lost':>5} {'flip':>5}")
for fam, r in d["families"].items():
    if "error" in r:
        print(f"{fam:<22} ERROR: {r['error']}")
        continue
    agg = r["agg_nan_frac_per_window"]
    lost = len(r["cols_lost_at_boundary"])
    flip = len(r["cols_flipped_lo_to_hi_nan"])
    print(f"{fam:<22} {r['n_columns']:>5} "
          f"{pct(agg['early_0_30']['nan_frac']):>8} "
          f"{pct(agg['pre_30_35']['nan_frac']):>8} "
          f"{pct(agg['boundary_35_37']['nan_frac']):>8} "
          f"{pct(agg['late_37_44']['nan_frac']):>8} "
          f"{lost:>5} {flip:>5}")

print()
print("=" * 80)
print("SPECTROGRAM SUMMARY: /api/patients/4290-1/spectrogram/<type>")
print("=" * 80)
print(f"{'spec_type':<22} {'nfreq':>5} {'early NaN':>10} {'pre NaN':>10} {'bnd NaN':>10} {'late NaN':>10} | {'e pop':>6} {'l pop':>6}")
for spec, r in d["spectrograms"].items():
    if "error" in r:
        print(f"{spec:<22} ERROR: {r['error']}")
        continue
    ws = r["window_stats"]
    e_pop = ws["early_0_30"].get("mean_freqs_populated")
    l_pop = ws["late_37_44"].get("mean_freqs_populated")
    e_pop_s = f"{e_pop:.1f}" if e_pop is not None else "n/a"
    l_pop_s = f"{l_pop:.1f}" if l_pop is not None else "n/a"
    print(f"{spec:<22} {r['n_freq']:>5} "
          f"{pct(ws['early_0_30']['nan_frac']):>10} "
          f"{pct(ws['pre_30_35']['nan_frac']):>10} "
          f"{pct(ws['boundary_35_37']['nan_frac']):>10} "
          f"{pct(ws['late_37_44']['nan_frac']):>10} | "
          f"{e_pop_s:>6} {l_pop_s:>6}")

print()
print("=" * 80)
print("PER-FAMILY DETAIL")
print("=" * 80)
for fam, r in d["families"].items():
    if "error" in r:
        continue
    if r["cols_lost_at_boundary"] or r["cols_flipped_lo_to_hi_nan"] or r["range_shifts_2x"]:
        print(f"\n### {fam}")
        print(f"   n_columns={r['n_columns']}, populated_early={r['cols_populated_early']}, populated_late={r['cols_populated_late']}")
        if r["cols_lost_at_boundary"]:
            print(f"   COLS LOST at 36h ({len(r['cols_lost_at_boundary'])}): {r['cols_lost_at_boundary'][:10]}{'...' if len(r['cols_lost_at_boundary']) > 10 else ''}")
        if r["cols_flipped_lo_to_hi_nan"]:
            print(f"   FLIPPED <5% -> >80% NaN ({len(r['cols_flipped_lo_to_hi_nan'])}): {r['cols_flipped_lo_to_hi_nan'][:10]}{'...' if len(r['cols_flipped_lo_to_hi_nan']) > 10 else ''}")
        if r["cols_gained_at_boundary"]:
            print(f"   COLS GAINED late-only ({len(r['cols_gained_at_boundary'])}): {r['cols_gained_at_boundary'][:10]}")
        if r["range_shifts_2x"]:
            print(f"   VALUE RANGE SHIFT >=2x (early_mean -> late_mean):")
            for s in r["range_shifts_2x"][:10]:
                print(f"     {s['col']}: mean {s['early_mean']:.3f} -> {s['late_mean']:.3f} (ratio {s['ratio']:.20f}x), early_range={s['early_min_max']}, late_range={s['late_min_max']}")

print()
print("=" * 80)
print("SPIKE DENSITY DETAIL")
print("=" * 80)
if "spike_density" in d["families"] and "per_col" not in d["families"]["spike_density"].get("error", {}):
    sd = d["families"]["spike_density"]
    print(f"Columns in spike_density ({len(sd['per_col'])}):")
    for col, wins in sd["per_col"].items():
        e = wins["early_0_30"]
        p = wins["pre_30_35"]
        b = wins["boundary_35_37"]
        l = wins["late_37_44"]
        print(f"\n  {col}")
        for name, w in [("early_0_30", e), ("pre_30_35", p), ("boundary_35_37", b), ("late_37_44", l)]:
            mn = w["mean"]
            mn_s = f"{mn:.3f}" if mn is not None else "n/a"
            mx = w["max"]
            mx_s = f"{mx:.3f}" if mx is not None else "n/a"
            print(f"    {name:<18} n={w['n']:>4}  NaN={pct(w['nan_frac']):>7}  mean={mn_s:>8}  max={mx_s:>8}")
