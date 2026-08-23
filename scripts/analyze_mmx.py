"""One-off: review V8 MMX for errors/duplications and diff against V7.

Read-only analysis. Prints a structured report; makes no changes.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from qeeg.ingestion.mmx_parser import parse_mmx  # noqa: E402

# Both read from the committed Ref Files copies — NOT the volatile C:\ProgramData
# originals — so this analysis is deterministic and reproducible from the repo alone.
# (Refresh the committed copies with scripts/refresh_ref_mmx.py.)
_REF = Path(__file__).resolve().parents[1] / "Ref Files"
V7 = _REF / "PedQuEST_Pennsieve_V7_research.mmx"
V8 = _REF / "PedQuEST_Pennsieve_V10_research.mmx"


def raw_scan(path: Path) -> dict:
    """Raw XML scan — catches duplicate InstanceIDs the parser dedupes away."""
    tree = ET.parse(path)
    root = tree.getroot()
    out = {}
    out["version_desc"] = root.get("Description", "")
    out["version"] = root.get("Version", "")

    # All <Channels> defs (top-level montage channel sets)
    chan_defs = []
    for ch in root.findall(".//Channels"):
        chan_defs.append({k: ch.get(k) for k in ch.keys()})
    out["channel_defs"] = chan_defs

    # All Instrument elements anywhere, with their channels + instanceid
    insts = []
    for el in root.iter("Instrument"):
        insts.append({
            "name": el.get("Name", ""),
            "iid": el.get("InstanceID", ""),
            "channels": el.get("Channels", ""),
            "graph": el.get("GraphTitle", ""),
            "has_inline_engine": el.find("Engine") is not None,
            "freqmin": el.get("FreqMin"),
            "freqmax": el.get("FreqMax"),
        })
    out["instruments_raw"] = insts

    # Panels
    panels = []
    for p in root.findall("Panel"):
        members = [(i.get("Name", ""), i.get("InstanceID", "")) for i in p.findall("Instrument")]
        panels.append({"name": p.get("Name", ""), "n": len(members), "members": members})
    out["panels_raw"] = panels

    # Distinct Channels= values across all instruments
    out["channel_values"] = Counter(i["channels"] for i in insts if i["channels"])
    return out


def find_channel_set_definitions(path: Path) -> list[dict]:
    """Find ChannelSet / named channel-group definitions in the MMX.

    Persyst stores reusable channel groups; the exact tag varies. Scan for any
    element whose tag or attributes reference channel-set naming.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    found = []
    for el in root.iter():
        tag = el.tag
        if "Channel" in tag and tag != "Channels":
            found.append({"tag": tag, "attrs": dict(el.attrib)})
    return found


def report():
    print("=" * 78)
    print("V8 MMX REVIEW — read-only")
    print("=" * 78)

    rv7 = raw_scan(V7)
    rv8 = raw_scan(V8)
    cfg7 = parse_mmx(V7)
    cfg8 = parse_mmx(V8)

    print(f"\nV7 Description: {rv7['version_desc']!r}  LTMPage Version={rv7['version']}")
    print(f"V8 Description: {rv8['version_desc']!r}  LTMPage Version={rv8['version']}")

    # ---- 1. Channel set definitions ----
    print("\n" + "-" * 78)
    print("1. TOP-LEVEL <Channels> MONTAGE DEFS")
    print("-" * 78)
    for tag, defs in (("V7", rv7["channel_defs"]), ("V8", rv8["channel_defs"])):
        print(f"  {tag}: {len(defs)} <Channels> def(s)")
        for d in defs:
            print(f"     {d.get('Name')!r}  filters: low={d.get('LowFilter')} high={d.get('HighFilter')} notch={d.get('NotchFilter')}")

    # ---- 2. Distinct Channels= values (the channel *sets* used by instruments) ----
    print("\n" + "-" * 78)
    print("2. DISTINCT Channels= VALUES ON INSTRUMENTS  (V7 vs V8)")
    print("-" * 78)
    c7 = set(rv7["channel_values"])
    c8 = set(rv8["channel_values"])
    added = sorted(c8 - c7)
    removed = sorted(c7 - c8)
    print(f"  NEW in V8 ({len(added)}):")
    for c in added:
        print(f"     + {c!r}   (used by {rv8['channel_values'][c]} instruments)")
    print(f"  REMOVED from V7 ({len(removed)}):")
    for c in removed:
        print(f"     - {c!r}")
    print(f"  Total distinct channel values: V7={len(c7)}  V8={len(c8)}")

    # ---- 3. Duplicate InstanceIDs (raw, pre-dedupe) ----
    print("\n" + "-" * 78)
    print("3. DUPLICATE InstanceIDs  (raw XML, pre-parser-dedupe)")
    print("-" * 78)
    for tag, raw in (("V7", rv7), ("V8", rv8)):
        iid_counts = Counter(i["iid"] for i in raw["instruments_raw"] if i["iid"])
        dups = {iid: n for iid, n in iid_counts.items() if n > 1}
        # Distinguish: same iid with same name (panel refs are NOT in instruments_raw
        # because we iter all Instrument elements incl panel refs). Filter to
        # definitions that carry channels/graph (real defs, not bare refs).
        defs_only = [i for i in raw["instruments_raw"] if i["channels"] or i["graph"] or i["has_inline_engine"]]
        def_iid_counts = Counter(i["iid"] for i in defs_only if i["iid"])
        def_dups = {iid: n for iid, n in def_iid_counts.items() if n > 1}
        print(f"  {tag}: {len(raw['instruments_raw'])} total <Instrument> elements (defs+panel refs)")
        print(f"      {len(defs_only)} are full definitions (carry Channels/GraphTitle/Engine)")
        print(f"      duplicate InstanceIDs among full defs: {len(def_dups)}")
        for iid, n in list(def_dups.items())[:25]:
            names = sorted({i["name"] for i in defs_only if i["iid"] == iid})
            print(f"         {iid}  x{n}  names={names}")

    # ---- 4. Duplicate Instrument NAMES among definitions ----
    print("\n" + "-" * 78)
    print("4. DUPLICATE Instrument NAMES among full definitions (V8)")
    print("-" * 78)
    defs8 = [i for i in rv8["instruments_raw"] if i["channels"] or i["graph"] or i["has_inline_engine"]]
    name_counts = Counter(i["name"] for i in defs8 if i["name"])
    name_dups = {n: c for n, c in name_counts.items() if c > 1}
    print(f"  {len(name_dups)} names defined more than once:")
    for nm, c in sorted(name_dups.items(), key=lambda kv: -kv[1])[:40]:
        chans = sorted({i["channels"] for i in defs8 if i["name"] == nm})
        iids = sorted({i["iid"] for i in defs8 if i["name"] == nm})
        flag = "  <-- DIFFERENT CHANNELS" if len(chans) > 1 else ""
        print(f"     {nm!r}  x{c}  channels={chans}  iids={len(iids)}{flag}")

    # ---- 5. Parsed instruments + families diff ----
    print("\n" + "-" * 78)
    print("5. PARSED INSTRUMENT COUNT + FAMILY DIFF")
    print("-" * 78)
    print(f"  V7: {len(cfg7.instruments)} instruments, {len(cfg7.panels)} panels, {len(cfg7.engines)} engines")
    print(f"  V8: {len(cfg8.instruments)} instruments, {len(cfg8.panels)} panels, {len(cfg8.engines)} engines")
    fam7 = Counter(i.family for i in cfg7.instruments.values())
    fam8 = Counter(i.family for i in cfg8.instruments.values())
    allfams = sorted(set(fam7) | set(fam8))
    print(f"  {'family':<26}{'V7':>5}{'V8':>5}  delta")
    for f in allfams:
        d = fam8[f] - fam7[f]
        mark = "  <==" if d else ""
        print(f"  {f:<26}{fam7[f]:>5}{fam8[f]:>5}  {d:+d}{mark}")

    # ---- 6. 'other' family instruments (possible misclassification) ----
    print("\n" + "-" * 78)
    print("6. V8 INSTRUMENTS CLASSIFIED 'other' (parser didn't recognize)")
    print("-" * 78)
    others = [i for i in cfg8.instruments.values() if i.family == "other"]
    print(f"  {len(others)} instruments:")
    for i in sorted(others, key=lambda x: x.name)[:50]:
        print(f"     {i.name!r}  channels={i.channels!r}")

    # ---- 7. NEW instrument NAMES in V8 (not in V7) ----
    print("\n" + "-" * 78)
    print("7. NEW INSTRUMENT NAMES IN V8 (not present in V7)")
    print("-" * 78)
    new_names = sorted(set(cfg8.instruments) - set(cfg7.instruments))
    print(f"  {len(new_names)} new instrument names:")
    for nm in new_names:
        i = cfg8.instruments[nm]
        print(f"     [{i.family}] {nm!r}  ch={i.channels!r}")

    # ---- 8. REMOVED instrument names ----
    print("\n" + "-" * 78)
    print("8. INSTRUMENT NAMES IN V7 BUT NOT V8 (removed/renamed)")
    print("-" * 78)
    gone = sorted(set(cfg7.instruments) - set(cfg8.instruments))
    print(f"  {len(gone)} removed:")
    for nm in gone:
        print(f"     [{cfg7.instruments[nm].family}] {nm!r}")

    # ---- 9. Panel diff ----
    print("\n" + "-" * 78)
    print("9. PANEL DIFF (membership counts)")
    print("-" * 78)
    p7 = {p.name: len(p.instruments) for p in cfg7.panels.values()}
    p8 = {p.name: len(p.instruments) for p in cfg8.panels.values()}
    allp = sorted(set(p7) | set(p8))
    for p in allp:
        a, b = p7.get(p), p8.get(p)
        if a is None:
            print(f"     + NEW PANEL {p!r}: {b} instruments")
        elif b is None:
            print(f"     - REMOVED PANEL {p!r} (had {a})")
        elif a != b:
            print(f"     ~ {p!r}: {a} -> {b}  ({b-a:+d})")
        else:
            print(f"       {p!r}: {a} (unchanged)")

    # ---- 10. Relative power detection ----
    print("\n" + "-" * 78)
    print("10. RELATIVE POWER TRENDS (newly added per user)")
    print("-" * 78)
    relpow = [i for i in cfg8.instruments.values()
              if "rel" in i.name.lower() and "power" in i.name.lower()
              or "relative" in i.name.lower() and "power" in i.name.lower()
              or "FFT_RelPower" in i.name or "RelPower" in i.name]
    print(f"  {len(relpow)} candidate relative-power instruments:")
    for i in sorted(relpow, key=lambda x: x.name):
        print(f"     {i.name!r}  ch={i.channels!r} freq=({i.freq_min},{i.freq_max})")


if __name__ == "__main__":
    report()
