"""Render docs/COLUMN_MAP_V10.json as a reviewable HTML page.

Adds review flags: rows where the generated metadata is known to disagree with
a vendor statement, or where identity is still positional/unresolved. Run
gen_column_map_v10.py first.

Usage:  python scripts/gen_column_map_page.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys as _s
SLUG = _s.argv[1] if len(_s.argv) > 1 else "RESEARCH_TRENDS"
SRC = ROOT / "docs" / f"COLUMN_MAP_V10_{SLUG}.json"
OUT = ROOT / "docs" / f"COLUMN_MAP_V10_{SLUG}.html"

# Known disagreements between what the pipeline currently emits and what the
# vendor has stated. Each entry: family -> (flag id, what to verify).
FLAGS: dict[str, tuple[str, str]] = {
    "artifact_intensity": ("verify", "Muscle sub-column units unconfirmed: Mike says uV, the Persyst help says average power (uV^2). V-Eye/L-Eye are probability 0.0-1.0 (settled)."),
    "other": ("unresolved", "No family assigned; name is positional. This is the tail Time column."),
}
ROW_FLAGS: dict[str, tuple[str, str]] = {
    # Confirmed in the raw CSV across 16 real exports (7 patients), 2026-08-23.
    # See docs/DATA_DICTIONARY_v4.md and the batch-verification diagnostic.
    "status_epilepticus_persyst_advanced_percent": (
        "verify",
        "Floors at 0.050331 and NEVER reaches 0, so `> 0` fires on every epoch of "
        "every recording -- threshold above the floor, not at zero. Also identical "
        "on every row to status_epilepticus_persyst_combined_percent: one variable, "
        "two names. Do not model both."),
    "status_epilepticus_persyst_combined_percent": (
        "verify",
        "Identical on every row to status_epilepticus_persyst_advanced_percent, and "
        "floors at 0.050331 rather than 0. See that column's note."),
    "status_epilepticus_persyst_acns_percent": (
        "unresolved",
        "Exactly 0 in all 16 exports examined. Either ACNS-criterion ESE did not "
        "occur in this cohort or the variant does not populate -- a zero here is "
        "not yet evidence of absence."),
    "heart_rate_2": (
        "unresolved",
        "Second heart-rate instrument (MMX 'Heart Rate01', CSV header 'Heart Rate 2'). "
        "Whether it carries a signal distinct from heart_rate is unconfirmed."),
}
# Families where Persyst writes 0 for a whole FFT epoch when artifact is high.
SUPPRESSED_NOTE = ("suppressed-zeros",
                   "0 does not mean zero - Artifact Reduction rejected this channel for this epoch. "
                   "Suppression is PER-CHANNEL (2.2%-51.9% by derivation on the recording it was measured on), not global. "
                   "Treat as MISSING, not zero.")

CSS = """
:root{
  --ground:#f7f8fa; --surface:#ffffff; --surface-2:#eef1f5; --line:#d8dee7;
  --ink:#161a20; --ink-2:#4a5462; --ink-3:#78838f;
  --left:#2b4a8b; --right:#a8322c; --gen:#2f6b4f;
  --accent:#2b4a8b; --accent-soft:#e5ebf6;
  --t-pdoc:#1f6b4a; --t-pdoc-bg:#e2f0e9;
  --t-pcomm:#2b4a8b; --t-pcomm-bg:#e5ebf6;
  --t-mmx:#8a5a12; --t-mmx-bg:#f6ecda;
  --t-emp:#a8322c; --t-emp-bg:#f7e4e2;
  --flag:#a8322c; --flag-bg:#fdf0ee;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#12151a; --surface:#181c23; --surface-2:#20252e; --line:#2e3540;
    --ink:#e8ecf1; --ink-2:#a8b2be; --ink-3:#78838f;
    --left:#7ea2e0; --right:#e08b85; --gen:#6fb593;
    --accent:#7ea2e0; --accent-soft:#1e2836;
    --t-pdoc:#7fc7a4; --t-pdoc-bg:#16281f;
    --t-pcomm:#7ea2e0; --t-pcomm-bg:#182231;
    --t-mmx:#d6a75c; --t-mmx-bg:#2a2216;
    --t-emp:#e08b85; --t-emp-bg:#2c1a19;
    --flag:#e08b85; --flag-bg:#2a1a19;
  }
}
:root[data-theme="dark"]{
  --ground:#12151a; --surface:#181c23; --surface-2:#20252e; --line:#2e3540;
  --ink:#e8ecf1; --ink-2:#a8b2be; --ink-3:#78838f;
  --left:#7ea2e0; --right:#e08b85; --gen:#6fb593;
  --accent:#7ea2e0; --accent-soft:#1e2836;
  --t-pdoc:#7fc7a4; --t-pdoc-bg:#16281f;
  --t-pcomm:#7ea2e0; --t-pcomm-bg:#182231;
  --t-mmx:#d6a75c; --t-mmx-bg:#2a2216;
  --t-emp:#e08b85; --t-emp-bg:#2c1a19;
  --flag:#e08b85; --flag-bg:#2a1a19;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:14px; line-height:1.5;
}
.wrap{max-width:1500px; margin:0 auto; padding:28px 22px 64px}
header.masthead{display:flex; flex-direction:column; gap:6px; margin-bottom:22px}
h1{
  font-family:"IBM Plex Serif",Georgia,serif; font-weight:600;
  font-size:clamp(24px,3.2vw,34px); margin:0; letter-spacing:-.015em; text-wrap:balance;
}
.sub{color:var(--ink-2); max-width:68ch}
.prov{
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:11.5px;
  color:var(--ink-3); margin-top:4px; word-break:break-all;
}
.stats{display:flex; flex-wrap:wrap; gap:10px; margin:20px 0 6px}
.stat{
  background:var(--surface); border:1px solid var(--line); border-radius:3px;
  padding:10px 14px; min-width:120px;
}
.stat .n{
  font-family:"IBM Plex Mono",monospace; font-size:21px; font-weight:600;
  font-variant-numeric:tabular-nums; display:block; line-height:1.2;
}
.stat .k{font-size:10.5px; text-transform:uppercase; letter-spacing:.09em; color:var(--ink-3)}
.stat.good .n{color:var(--t-pdoc)}
.stat.warn .n{color:var(--flag)}
.controls{
  display:flex; flex-wrap:wrap; gap:10px; align-items:center;
  position:sticky; top:0; z-index:5; padding:12px 0;
  background:var(--ground); border-bottom:1px solid var(--line); margin-bottom:0;
}
input[type=search],select{
  font:inherit; padding:7px 10px; border:1px solid var(--line);
  border-radius:3px; background:var(--surface); color:var(--ink);
}
input[type=search]{min-width:260px; flex:1 1 260px}
input[type=search]:focus-visible,select:focus-visible,button:focus-visible{
  outline:2px solid var(--accent); outline-offset:1px;
}
button.toggle{
  font:inherit; padding:7px 12px; border:1px solid var(--line); border-radius:3px;
  background:var(--surface); color:var(--ink-2); cursor:pointer;
}
button.toggle[aria-pressed="true"]{
  background:var(--flag-bg); border-color:var(--flag); color:var(--flag); font-weight:600;
}
.count{color:var(--ink-3); font-size:12.5px; font-variant-numeric:tabular-nums; margin-left:auto}
.tablewrap{overflow-x:auto; border:1px solid var(--line); border-radius:3px; background:var(--surface); margin-top:14px}
table{border-collapse:collapse; width:100%; font-size:12.5px}
thead th{
  position:sticky; top:0; background:var(--surface-2); text-align:left;
  padding:9px 10px; font-size:10.5px; text-transform:uppercase; letter-spacing:.07em;
  color:var(--ink-2); border-bottom:1px solid var(--line); white-space:nowrap; cursor:pointer;
}
thead th:hover{color:var(--ink)}
tbody td{padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top}
tbody tr:hover{background:var(--surface-2)}
tr.flagged td:first-child{box-shadow:inset 3px 0 0 var(--flag)}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums}
.var{font-family:"IBM Plex Mono",monospace; font-weight:500; color:var(--accent); word-break:break-all}
.hdr{max-width:30ch}
.dim{color:var(--ink-3)}
.tier{
  display:inline-block; padding:1px 7px; border-radius:2px; font-size:10px;
  font-weight:600; letter-spacing:.05em; white-space:nowrap;
}
.tier.PDOC{color:var(--t-pdoc); background:var(--t-pdoc-bg)}
.tier.PCOMM{color:var(--t-pcomm); background:var(--t-pcomm-bg)}
.tier.MMX{color:var(--t-mmx); background:var(--t-mmx-bg)}
.tier.EMP{color:var(--t-emp); background:var(--t-emp-bg)}
.flagchip{
  display:inline-block; padding:1px 6px; border-radius:2px; font-size:10px;
  font-weight:600; letter-spacing:.04em; color:var(--flag); background:var(--flag-bg);
  white-space:nowrap;
}
.reviewlist{display:grid; gap:8px; margin-top:6px}
.reviewitem{
  background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--flag);
  border-radius:3px; padding:10px 12px;
}
.reviewitem .rh{display:flex; gap:8px; align-items:baseline; flex-wrap:wrap}
.reviewitem .rn{font-family:"IBM Plex Mono",monospace; font-size:12px; font-weight:600}
.reviewitem .rc{font-size:11px; color:var(--ink-3); font-variant-numeric:tabular-nums}
.reviewitem p{margin:4px 0 0; font-size:12.5px; color:var(--ink-2); max-width:88ch}
.flagnote{
  display:block; margin-top:3px; font-size:11px; color:var(--flag);
  background:var(--flag-bg); padding:3px 6px; border-radius:2px; max-width:46ch;
}
h2{
  font-family:"IBM Plex Serif",Georgia,serif; font-size:17px; margin:34px 0 10px;
  font-weight:600; letter-spacing:-.01em;
}
.callout{
  margin:22px 0 4px; padding:14px 16px; background:var(--flag-bg);
  border:1px solid var(--flag); border-left-width:3px; border-radius:3px;
}
.callout h3{
  font-family:"IBM Plex Serif",Georgia,serif; font-size:15px; margin:0 0 6px;
  font-weight:600; color:var(--flag);
}
.callout p{margin:0 0 6px; max-width:82ch; font-size:13px}
.callout p:last-child{margin-bottom:0}
.famgrid{display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:8px}
.fam{background:var(--surface); border:1px solid var(--line); border-radius:3px; padding:9px 11px}
.fam .fn{font-family:"IBM Plex Mono",monospace; font-size:12px; font-weight:600}
.fam .fm{font-size:11px; color:var(--ink-3); font-variant-numeric:tabular-nums; margin-top:2px}
.legend{display:flex; flex-wrap:wrap; gap:14px; font-size:11.5px; color:var(--ink-2); margin-top:8px}
.legend span{display:flex; align-items:center; gap:5px}
footer{margin-top:38px; padding-top:16px; border-top:1px solid var(--line); color:var(--ink-3); font-size:11.5px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""


def main() -> None:
    if not SRC.exists():
        sys.exit(f"missing {SRC} - run gen_column_map_v10.py first")
    d = json.loads(SRC.read_text(encoding="utf-8"))
    cols = d["columns"]

    for c in cols:
        fam = c.get("family") or ""
        # Suppression is conveyed by its own "0=NA" column; repeating it as a
        # per-row note buried the genuine review flags under 1,900 duplicates.
        flag = ROW_FLAGS.get(c.get("variable_name") or "") or FLAGS.get(fam)
        c["flag"] = flag[0] if flag else ""
        c["flag_note"] = flag[1] if flag else ""

    n_flag = sum(1 for c in cols if c["flag"])
    fams = d["families"]

    fam_html = "".join(
        f'<div class="fam"><div class="fn">{k}</div>'
        f'<div class="fm">{v["columns"]} cols &middot; {v["instruments"]} instr &middot; '
        f'<span class="tier {v["evidence_tier"].replace("-","")}">{v["evidence_tier"]}</span></div></div>'
        for k, v in sorted(fams.items(), key=lambda x: -x[1]["columns"])
    )
    fam_opts = "".join(f'<option value="{k}">{k}</option>'
                       for k in sorted(fams.keys()))

    # Review items live in their own section, not repeated on every row.
    seen: dict[str, tuple[str, int]] = {}
    for c in cols:
        if c["flag"]:
            key = (c["flag"], c["flag_note"])
            n, _ = seen.get(key, (0, 0))
            seen[key] = (n + 1, 0)
    review_html = "".join(
        f'<div class="reviewitem"><div class="rh"><span class="flagchip">{fl}</span>'
        f'<span class="rc">{n} column{"s" if n != 1 else ""}</span></div>'
        f'<p>{note}</p></div>'
        for (fl, note), (n, _) in sorted(seen.items(), key=lambda x: -x[1][0]))

    html = f"""<title>{d.get("panel","V10")} Column Map</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="masthead">
  <h1>PedQuEST V10 &mdash; {d.get("panel","Column Map")}</h1>
  <p class="sub">Every column in a Persyst Research-Trends export, resolved to its variable name
  with the metadata attached to it. Flagged rows are where the generated metadata disagrees with a
  vendor statement, or where identity is still positional &mdash; verify these before this becomes
  the extraction contract.</p>
  <p class="prov">generated from export {d["source_export"]}<br>template: {d["source_template"]}</p>
</header>

<div class="stats">
  <div class="stat"><span class="n">{d["n_columns"]}</span><span class="k">Columns</span></div>
  <div class="stat good"><span class="n">{d["n_distinct_variable_names"]}</span><span class="k">Unique names</span></div>
  <div class="stat good"><span class="n">0</span><span class="k">Collisions</span></div>
  <div class="stat"><span class="n">{len(fams)}</span><span class="k">Families</span></div>
  <div class="stat warn"><span class="n">{n_flag}</span><span class="k">Need review</span></div>
</div>

<div class="callout">
  <h3>Zeros are Artifact-Reduction rejections, and they are per-channel</h3>
  <p>Artifact Reduction writes <span class="mono">0</span> rather than a blank when it cannot clean
  a channel for an epoch. Proven by toggling AR on one recording, same panel: with AR
  <b>off</b> every derivation is zero exactly <b>0.12%</b> of the time &mdash; identical across all
  25, because that is one real 37&nbsp;s recording gap. With AR <b>on</b>, zero rates range from
  <b>2.2%</b> (Right Anterior) to <b>51.9%</b> (T4&#8209;T6). Only <b>1.7%</b> of AR&#8209;on zeros
  are also zero without AR, so <b>98.3% are AR rejections, not gaps</b>.</p>
  <p>Because rejection is channel-selective, null <em>per channel</em>, not per row: all 25
  derivations are zero together in only 1.6% of rows, while 61% are partial. A uniform all-channel
  zero indicates a recording gap; a partial pattern indicates AR. Runs are quantised to the
  8&nbsp;s <span class="mono">EpochStep</span>. Columns affected are marked
  <span class="mono">0=NA</span> below.</p>
</div>

<h2>Families</h2>
<div class="famgrid">{fam_html}</div>
<div class="legend">
  <span><span class="tier PDOC">P-DOC</span> Persyst 15 help</span>
  <span><span class="tier PCOMM">P-COMM</span> Persyst direct (Mike)</span>
  <span><span class="tier MMX">MMX</span> template only</span>
  <span><span class="tier EMP">EMP</span> inferred from exports</span>
</div>

<h2>Review items</h2>
<div class="reviewlist">{review_html}</div>

<h2>Columns</h2>
<div class="controls">
  <input type="search" id="q" placeholder="Search name, header, i-code, family&hellip;" aria-label="Search columns">
  <select id="fam" aria-label="Filter by family"><option value="">All families</option>{fam_opts}</select>
  <select id="tier" aria-label="Filter by evidence tier">
    <option value="">All tiers</option><option>P-DOC</option><option>P-COMM</option><option>MMX</option><option>EMP</option>
  </select>
  <button class="toggle" id="onlyflag" aria-pressed="false">Needs review only</button>
  <span class="count" id="count"></span>
</div>
<div class="tablewrap">
  <table>
    <thead><tr>
      <th data-k="col_index">#</th><th data-k="i_code">I-code</th>
      <th data-k="csv_header">CSV header (row 7)</th><th data-k="sub_index">Sub</th>
      <th data-k="variable_name">Variable name</th><th data-k="flag">Flag</th>
      <th data-k="family">Family</th>
      <th data-k="units">Units</th><th data-k="power_scale">Scale</th>
      <th data-k="freq_band">Band</th><th data-k="hemisphere">Hemi</th>
      <th data-k="region">Region</th><th data-k="electrode">Electrode</th>
      <th data-k="engine">Engine</th>
      <th data-k="sampling_rate_hz">Rate Hz</th><th data-k="epoch_duration_s">Epoch s</th>
      <th data-k="epoch_step_s">Step s</th><th data-k="freq_resolution_hz">Res Hz</th>
      <th data-k="window_duration_s">Win s</th><th data-k="smooth_factor">Smooth</th>
      <th data-k="rows_per_obs">Rows/obs</th><th data-k="zero_means_suppressed">0=NA</th>
      <th data-k="evidence_tier">Tier</th>
    </tr></thead>
    <tbody id="tb"></tbody>
  </table>
</div>

<footer>
  Generated from the production resolver (<span class="mono">build_column_schema_with_mmx</span>),
  ordinal-primary against the V10 panel. Regenerate with
  <span class="mono">scripts/gen_column_map_v10.py</span> then
  <span class="mono">scripts/gen_column_map_page.py</span>.
  Machine-readable equivalents: <span class="mono">docs/COLUMN_MAP_V10.csv</span> /
  <span class="mono">.json</span>.
</footer>
</div>
<script>
const DATA = {json.dumps(cols)};
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
const tb = document.getElementById("tb"), cnt = document.getElementById("count");
const q = document.getElementById("q"), famSel = document.getElementById("fam"),
      tierSel = document.getElementById("tier"), onlyFlag = document.getElementById("onlyflag");
let sortKey = "col_index", sortAsc = true, flagOnly = false;

function rows() {{
  const t = q.value.trim().toLowerCase(), f = famSel.value, tr = tierSel.value;
  let r = DATA.filter(c =>
    (!f || c.family === f) && (!tr || c.evidence_tier === tr) && (!flagOnly || c.flag) &&
    (!t || [c.variable_name, c.csv_header, c.i_code, c.family, c.units, c.mmx_instrument]
      .some(v => String(v ?? "").toLowerCase().includes(t))));
  r.sort((a, b) => {{
    let x = a[sortKey], y = b[sortKey];
    if (typeof x === "number" && typeof y === "number") return sortAsc ? x - y : y - x;
    x = String(x ?? ""); y = String(y ?? "");
    return sortAsc ? x.localeCompare(y) : y.localeCompare(x);
  }});
  return r;
}}
function render() {{
  const r = rows();
  cnt.textContent = r.length + " of " + DATA.length + " columns";
  tb.innerHTML = r.map(c => `<tr class="${{c.flag ? "flagged" : ""}}">
    <td class="mono dim">${{c.col_index}}</td>
    <td class="mono">${{esc(c.i_code)}}</td>
    <td class="hdr">${{esc(c.csv_header)}}</td>
    <td class="mono dim">${{c.sub_index}}</td>
    <td><span class="var">${{esc(c.variable_name)}}</span></td>
    <td>${{c.flag ? `<span class="flagchip">${{esc(c.flag)}}</span>` : ""}}</td>
    <td class="mono">${{esc(c.family)}}</td>
    <td class="dim">${{esc(c.units)}}</td>
    <td class="mono">${{esc(c.power_scale)}}</td>
    <td class="mono">${{esc(c.freq_band)}}</td>
    <td>${{esc(c.hemisphere)}}</td>
    <td>${{esc(c.region)}}</td>
    <td class="mono">${{esc(c.electrode)}}</td>
    <td class="mono dim">${{esc(c.engine)}}</td>
    <td class="mono">${{esc(c.sampling_rate_hz)}}</td>
    <td class="mono">${{esc(c.epoch_duration_s)}}</td>
    <td class="mono">${{esc(c.epoch_step_s)}}</td>
    <td class="mono">${{esc(c.freq_resolution_hz)}}</td>
    <td class="mono">${{esc(c.window_duration_s)}}</td>
    <td class="mono dim">${{esc(c.smooth_factor)}}</td>
    <td class="mono dim">${{esc(c.rows_per_obs)}}</td>
    <td class="mono">${{c.zero_means_suppressed ? '<b>yes</b>' : ''}}</td>
    <td><span class="tier ${{String(c.evidence_tier).replace("-","")}}">${{esc(c.evidence_tier)}}</span></td>
  </tr>`).join("");
}}
document.querySelectorAll("thead th").forEach(th => th.addEventListener("click", () => {{
  const k = th.dataset.k; if (!k) return;
  if (sortKey === k) sortAsc = !sortAsc; else {{ sortKey = k; sortAsc = true; }}
  render();
}}));
onlyFlag.addEventListener("click", () => {{
  flagOnly = !flagOnly; onlyFlag.setAttribute("aria-pressed", String(flagOnly)); render();
}});
[q, famSel, tierSel].forEach(el => el.addEventListener("input", render));
render();
</script>
"""
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({len(cols)} rows, {n_flag} flagged)")


if __name__ == "__main__":
    main()
