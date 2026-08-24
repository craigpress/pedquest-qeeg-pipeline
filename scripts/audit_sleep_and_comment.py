"""Resolve what the SleepStages numeric codes mean, and what the Comment column carries.

Sleep: the MMX defines two palettes over the same 0-5 code space — `SleepStages`
(6 distinct colours) and `SleepWake` (codes 1-4 collapsed to one colour). The
Sleep-Wake *State* legend has exactly three categories, so the collapse pattern
identifies which codes are sleep stages and which is wake, without relying on
reading colour names.

Comment: the `.lay` [Comments] section holds the annotation text. This checks
whether the CSV Comment column carries any of it.

Writes output/audit_subject-1/sleep_and_comment.json.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import recording_dir  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MMX = ROOT / "Ref Files" / "PedQuEST_Pennsieve_V10_research.mmx"
OUT = ROOT / "output" / "audit_subject-1"
FULL_OUT = ROOT / "output" / "audit_fullpanel"
LAY3 = recording_dir("subject-1_rec") / "subject-1_rec-3.lay"


def palettes() -> dict:
    root = ET.parse(MMX).getroot()
    cp = root.find("CustomPaletteDefinitions")
    out = {}
    for e in (cp if cp is not None else []):
        name = e.get("Item")
        if name not in ("SleepStages", "SleepWake"):
            continue
        for ch in e:
            out[name] = [c.strip() for c in (ch.text or "").split(",") if c.strip()]
    return out


def sleep_instruments() -> dict:
    root = ET.parse(MMX).getroot()
    ins = root.find("Instruments")
    els = [dict(e.attrib) for c in [ins] + list(ins.findall("Montage"))
           for e in c if e.tag == "Instrument"]
    onehot, others = {}, []
    for e in els:
        nm = e.get("Name", "")
        m = re.fullmatch(r"= (\d+) <0> \[SleepStages\]", nm)
        if m:
            onehot[nm] = int(m.group(1))
        elif nm == "SleepStages" or nm == "ColorScaledBars":
            others.append({k: e.get(k) for k in ("Name", "GraphTitle", "Channels", "ClsId")})
    return {"equality_mask_codes": onehot, "related": others}


def comment_check() -> dict:
    txt = LAY3.read_text(errors="replace")
    sec = txt.split("[Comments]", 1)[1] if "[Comments]" in txt else ""
    comments = []
    for line in sec.splitlines():
        p = line.split(",", 4)
        if len(p) == 5:
            try:
                comments.append({"offset_s": float(p[0]), "text": p[4]})
            except ValueError:
                pass

    info = json.loads((FULL_OUT / "parquet_verification.json").read_text(encoding="utf-8"))
    df = pd.read_parquet(info["parquet_path"], columns=["ClockDateTime", "I368_1"])
    df = df.iloc[:44577]                      # block 0 == the -3.dat segment
    col = df["I368_1"]
    probed = []
    for c in comments:
        i = int(round(c["offset_s"]))
        if 0 <= i < len(col):
            probed.append({"offset_s": c["offset_s"], "row": i,
                           "comment_value": None if pd.isna(col.iloc[i]) else float(col.iloc[i]),
                           "text": c["text"][:70]})
    return {
        "lay_file": str(LAY3),
        "n_comments_in_lay": len(comments),
        "sample_comments": [c["text"][:70] for c in comments[:12]],
        "csv_comment_column": "I368_1 (full panel) / I231_1 (limited panel)",
        "csv_comment_distinct_values": sorted(
            {None if pd.isna(v) else float(v) for v in col.unique()},
            key=lambda x: (x is None, x)),
        "n_probed_offsets": len(probed),
        "n_nonzero_at_comment_offsets": sum(
            1 for p in probed if p["comment_value"] not in (0.0, None)),
        "probed": probed[:12],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pal = palettes()
    inst = sleep_instruments()

    # Group codes by the colour SleepWake assigns them.
    sw = pal.get("SleepWake", [])
    groups: dict[str, list[int]] = {}
    for code, colour in enumerate(sw):
        groups.setdefault(colour, []).append(code)

    result = {
        "palettes": pal,
        "sleepwake_colour_groups": groups,
        "sleep_instruments": inst,
        "deduction": {
            "code_0": "indeterminate — black (000000) in BOTH palettes; both legends say black = indeterminate",
            "codes_1_2_3_4": "the four sleep stages — collapsed to a single colour in SleepWake",
            "code_5": "wake — the singleton colour in SleepWake",
            "basis": ("AASM staging has exactly one wake state and four sleep stages "
                      "(N1/N2/N3/REM). SleepWake collapses 1-4 into one colour and keeps "
                      "5 separate, so the group of four must be the sleep stages."),
            "unresolved": "which of codes 1-4 is N1 vs N2 vs N3 vs REM",
            "conflict": ("The GraphTitle legend says 'yellow=wake', but B37400 (amber) is "
                         "the colour of codes 1-4 and 42E4F0 (cyan) is code 5. Read "
                         "literally that would make four codes 'wake' and one 'sleep', "
                         "which is not a valid staging scheme. The legend text is "
                         "user-authored (it contains the typo 'ornage'), so the palette "
                         "structure is trusted over the colour names."),
        },
        "comment": comment_check(),
    }
    (OUT / "sleep_and_comment.json").write_text(json.dumps(result, indent=2),
                                                encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "comment"}, indent=1))
    c = result["comment"]
    print(f"\ncomment: {c['n_comments_in_lay']} comments in .lay; CSV column distinct "
          f"values={c['csv_comment_distinct_values']}; non-zero at comment offsets="
          f"{c['n_nonzero_at_comment_offsets']} of {c['n_probed_offsets']}")
    print(f"\nwrote {OUT/'sleep_and_comment.json'}")


if __name__ == "__main__":
    main()
