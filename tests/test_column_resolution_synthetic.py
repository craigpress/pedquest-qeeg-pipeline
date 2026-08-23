"""Ordinal resolution tested against a hand-built MMX, with no research share.

Every test that exercised `build_column_schema_with_mmx` previously required
`Y:` to be mounted. Off-share the whole remediation was untested, so a green
suite proved nothing about column identity — which is precisely the property all
of this work exists to protect.

These build a small `MMXConfig` in memory instead: three panels, a handful of
instruments, and the same shapes the real template uses — a panel-count
collision, Persyst's `Comment`/`Time` tail, instruments sharing one display
label, and the boolean expressions the laterality rules read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qeeg.ingestion.column_mapper import (  # noqa: E402
    build_column_schema_with_mmx,
    resolve_export_panel,
)
from qeeg.ingestion.mmx_parser import InstrumentDef, MMXConfig, PanelDef  # noqa: E402

# Persyst's real spike expressions, trimmed to the parts the rules read.
_L = "[>= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike C3]]"
_R = "[>= 3 <0> [EventDensity Spike F4 OR Spike Fp2 OR Spike C4]]"

_SPIKE_LABEL = "Spikes >=3 per ten seconds (blue=left, red=right, yellow=L&R)"


def _inst(name: str, channels: str = "", family: str = "other") -> InstrumentDef:
    return InstrumentDef(name=name, instance_id=name, channels=channels,
                         graph_title="", freq_min=None, freq_max=None,
                         engine="", family=family, panels=())


def _cfg() -> MMXConfig:
    """Three panels. 'Wide' and 'Decoy' deliberately share an instrument count."""
    wide = [
        _inst("FFT_Power 1-4 Left Hemisphere_avg", "Left Hemisphere", "fft_power"),
        _inst("FFT_Power 1-4 Right Hemisphere_avg", "Right Hemisphere", "fft_power"),
        _inst(f"{_L} AND {_R}", "", "spike_density"),          # bilateral
        _inst(f"{_L} AND NOT{_R}", "", "spike_density"),        # left only
        _inst(f"{_R} AND NOT{_L}", "", "spike_density"),        # right only
        _inst("= 0 <0> [SleepStages]", "", "sleep"),
        _inst("= 1 <0> [SleepStages]", "", "sleep"),
        _inst("SeizureProbabilityP14 Probability", "", "seizure_probability"),
        _inst("SeizureProbabilityP14 Detections", "", "seizure_probability"),
    ]
    decoy = [_inst(f"decoy {i}") for i in range(len(wide))]   # same count as `wide`
    narrow = [_inst("BSR All 10-20_avg", "All 10-20", "suppression_ratio")]
    panels = {
        "Wide": PanelDef(name="Wide", instruments=wide),
        "Decoy": PanelDef(name="Decoy", instruments=decoy),
        "Narrow": PanelDef(name="Narrow", instruments=narrow),
    }
    return MMXConfig(engines={}, engines_by_ref={},
                     instruments={i.name: i for p in panels.values() for i in p.instruments},
                     instance_index={}, panels=panels,
                     mmx_version="15", mmx_path=Path("synthetic.mmx"))


def _headers(labels: list[str], tail: bool = True) -> dict[str, str]:
    """Build a code->label map the way a Persyst CSV header does."""
    c2d = {f"I{k}_1": lab for k, lab in enumerate(labels, start=1)}
    if tail:
        n = len(labels)
        c2d[f"I{n + 1}_1"] = "Comment"
        c2d[f"I{n + 2}_1"] = "Time"
    return c2d


# --------------------------------------------------------------------------

def test_panel_is_identified_from_the_i_group_count():
    cfg = _cfg()
    assert resolve_export_panel(cfg, len(cfg.panels["Narrow"].instruments) + 2).name == "Narrow"


def test_colliding_instrument_counts_refuse_to_resolve():
    """`Wide` and `Decoy` are the same size, so the count cannot decide."""
    cfg = _cfg()
    assert resolve_export_panel(cfg, len(cfg.panels["Wide"].instruments) + 2) is None


def test_tail_columns_resolve_as_tail_not_as_instruments():
    cfg = _cfg()
    c2d = _headers(["Suppression Ratio, All 10-20"])
    entries = {e.code: e for e in build_column_schema_with_mmx(c2d, cfg)}
    assert entries["I1_1"].resolution == "ordinal"
    assert entries["I2_1"].resolution == "tail"     # Comment
    assert entries["I3_1"].resolution == "tail"     # Time


def test_resolution_degrades_to_regex_when_the_panel_is_ambiguous():
    """The guarantee must not be implied when it does not hold."""
    cfg = _cfg()
    c2d = _headers([_SPIKE_LABEL] * len(cfg.panels["Wide"].instruments))
    entries = build_column_schema_with_mmx(c2d, cfg)
    assert all(e.resolution == "regex" for e in entries), \
        sorted({e.resolution for e in entries})


def test_identical_labels_are_separated_by_position():
    """Three spike detectors share one display label; only ordinal splits them.

    This is the case that has broken twice — first as `spike_left` for all of
    them, then as `left` for the bilateral one.
    """
    cfg = _cfg()
    narrow = PanelDef(name="Solo", instruments=cfg.panels["Wide"].instruments[2:5])
    cfg.panels["Solo"] = narrow
    c2d = _headers([_SPIKE_LABEL, _SPIKE_LABEL, _SPIKE_LABEL])

    entries = {e.code: e for e in build_column_schema_with_mmx(c2d, cfg)}
    got = [entries[f"I{k}_1"].common_name for k in (1, 2, 3)]
    assert len(set(got)) == 3, got
    assert "bilateral" in got[0], got
    assert got[1].startswith("spike_left"), got
    assert got[2].startswith("spike_right"), got


def test_sleep_stages_take_their_number_from_the_expression():
    cfg = _cfg()
    cfg.panels["Sleep"] = PanelDef(name="Sleep",
                                   instruments=cfg.panels["Wide"].instruments[5:7])
    entries = {e.code: e for e in
               build_column_schema_with_mmx(_headers(["SleepStages"] * 2), cfg)}
    got = [entries["I1_1"].common_name, entries["I2_1"].common_name]
    assert got == ["sleep_stage_0", "sleep_stage_1"], got


def test_seizure_probability_and_detections_do_not_share_a_name():
    cfg = _cfg()
    cfg.panels["Sz"] = PanelDef(name="Sz",
                                instruments=cfg.panels["Wide"].instruments[7:9])
    label = "Seizure probability (black) and detections (red; hides probability)"
    entries = {e.code: e for e in
               build_column_schema_with_mmx(_headers([label] * 2), cfg)}
    a, bb = entries["I1_1"].common_name, entries["I2_1"].common_name
    assert a != bb, (a, bb)
    assert "probability" in a and "detections" in bb, (a, bb)


def test_no_identifier_embeds_an_i_code():
    """I-codes shift when the panel is edited, so they must not reach a name."""
    cfg = _cfg()
    cfg.panels["Solo"] = PanelDef(name="Solo", instruments=cfg.panels["Wide"].instruments[:3])
    c2d = _headers(["FFT Power, 1 - 4 Hz, Left Hemisphere",
                    "FFT Power, 1 - 4 Hz, Right Hemisphere",
                    _SPIKE_LABEL])
    for e in build_column_schema_with_mmx(c2d, cfg):
        if e.resolution == "tail":
            continue
        assert not any(tok in e.common_name for tok in ("i1s", "i2s", "i3s", "_d1", "_d2")), \
            f"{e.code}: {e.common_name}"
