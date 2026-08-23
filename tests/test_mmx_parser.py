"""Tests for MMX file parsing."""
from pathlib import Path
import pytest

from qeeg.ingestion.mmx_parser import parse_mmx, MMXConfig, EngineConfig, InstrumentDef


# Resolve fixtures relative to the repo root, not the (variable) pytest CWD, so the
# real-MMX tests actually run instead of silently skipping. The V5 MMX was archived
# under _archive/old-mmx/ during the V7→V8 migration; point at it there.
_REPO_ROOT = Path(__file__).resolve().parent.parent
MMX_V5 = _REPO_ROOT / "_archive" / "old-mmx" / "PedQuEST_Pennsieve_V5_research.mmx"
MMX_V3_REF = _REPO_ROOT / "Ref Files" / "PedQuEST_Pennsieve_V3_research.mmx"


def _skip_if_missing(path: Path):
    if not path.exists():
        pytest.skip(f"MMX file not available: {path}")


# ---------------------------------------------------------------------------
# EngineConfig backwards-compat tests
# ---------------------------------------------------------------------------

def test_engine_config_effective_independence():
    """EngineConfig.rows_per_independent_obs works (positional args unchanged)."""
    cfg = EngineConfig(name="FFTEngine01", epoch_duration=4.0, epoch_step=8.0)
    assert cfg.rows_per_independent_obs == 8

    cfg2 = EngineConfig(name="aEEG01", epoch_duration=1.0, epoch_step=1.0)
    assert cfg2.rows_per_independent_obs == 1

    cfg3 = EngineConfig(name="Amplitude01", epoch_duration=10.0, epoch_step=10.0)
    assert cfg3.rows_per_independent_obs == 10

    assert cfg.has_overlapping_windows is False     # 4 <= 8
    assert EngineConfig("R", 3.0, 2.0).has_overlapping_windows is True  # 3 > 2


# ---------------------------------------------------------------------------
# V5 MMX — full parse
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def v5_cfg() -> MMXConfig:
    _skip_if_missing(MMX_V5)
    return parse_mmx(MMX_V5)


def test_v5_engines(v5_cfg: MMXConfig):
    """Core engines are present with correct cadence."""
    eng = v5_cfg.engines
    assert "FFTEngine01" in eng
    assert eng["FFTEngine01"].epoch_duration == 4.0
    assert eng["FFTEngine01"].epoch_step == 8.0

    assert "RhythmicityEngine01" in eng
    assert eng["RhythmicityEngine01"].epoch_duration == 3.0
    assert eng["RhythmicityEngine01"].epoch_step == 2.0

    assert "aEEG01" in eng
    assert "Artifact01" in eng
    assert "SeizureProbabilityP1401" in eng


def test_v5_instruments_count(v5_cfg: MMXConfig):
    """A substantial number of Instruments are parsed."""
    assert len(v5_cfg.instruments) > 50, (
        f"Expected >50 instruments, got {len(v5_cfg.instruments)}"
    )


def test_v5_sef95_left_anterior(v5_cfg: MMXConfig):
    """FFT_Edge 95 Left Anterior resolves to spectral_edge family with correct channels."""
    name = "FFT_Edge 95 0-32 Left Anterior_avg"
    assert name in v5_cfg.instruments, f"Missing instrument: {name}"
    inst = v5_cfg.instruments[name]
    assert inst.channels == "Left Anterior"
    assert inst.family == "spectral_edge"
    assert inst.engine is not None
    assert inst.engine.name == "FFTEngine01"


def test_v5_rav_vs_adr_disambiguation(v5_cfg: MMXConfig):
    """RAV (6-14//1-20) and ADR (8-13//1-4) resolve to distinct families."""
    # Find any RAV instrument
    rav_names = [n for n in v5_cfg.instruments if "6-14//1-20" in n or "6-14/1-20" in n]
    adr_names = [n for n in v5_cfg.instruments if "8-13//1-4" in n or "8-13/1-4" in n]

    assert rav_names, "No RAV (6-14//1-20) instruments found"
    assert adr_names, "No ADR (8-13//1-4) instruments found"

    for n in rav_names:
        assert v5_cfg.instruments[n].family == "alpha_variability", (
            f"{n!r} → {v5_cfg.instruments[n].family!r}, expected alpha_variability"
        )
    for n in adr_names:
        assert v5_cfg.instruments[n].family == "adr", (
            f"{n!r} → {v5_cfg.instruments[n].family!r}, expected adr"
        )


def test_v5_panels(v5_cfg: MMXConfig):
    """Expected clinical panels exist."""
    for panel_name in [
        "Comprehensive", "aEEG", "Asymmetry",
        "Alpha-Delta Ratios (Quadrant)", "SEF and SR",
        "Power by Frequency Band", "Relative Alpha Variability (Quadrant)",
    ]:
        assert panel_name in v5_cfg.panels, f"Missing panel: {panel_name!r}"


def test_v5_panel_membership_raf_quadrant(v5_cfg: MMXConfig):
    """Relative Alpha Variability (Quadrant) panel members are all alpha_variability family."""
    panel = v5_cfg.panels.get("Relative Alpha Variability (Quadrant)")
    assert panel is not None

    rav_members = [i for i in panel.instruments if "6-14" in i.name]
    assert rav_members, "No RAV instruments in RAV Quadrant panel"
    for inst in rav_members:
        assert inst.family == "alpha_variability", (
            f"Panel member {inst.name!r} → family {inst.family!r}"
        )


def test_v5_panel_adr_quadrant(v5_cfg: MMXConfig):
    """Alpha-Delta Ratios (Quadrant) panel contains adr-family instruments."""
    panel = v5_cfg.panels.get("Alpha-Delta Ratios (Quadrant)")
    assert panel is not None

    adr_members = [i for i in panel.instruments if "8-13" in i.name]
    assert adr_members, "No ADR instruments in ADR panel"
    for inst in adr_members:
        assert inst.family == "adr", (
            f"Panel member {inst.name!r} → family {inst.family!r}"
        )


def test_v5_instance_index(v5_cfg: MMXConfig):
    """InstanceID index resolves the same objects as the name index."""
    for name, inst in list(v5_cfg.instruments.items())[:20]:
        resolved = v5_cfg.instance_index.get(inst.instance_id)
        assert resolved is not None, f"InstanceID {inst.instance_id!r} missing from index"
        # Same object or at least same name
        assert resolved.name == name or resolved.instance_id == inst.instance_id


def test_v5_aeeg_family(v5_cfg: MMXConfig):
    """aEEG instruments resolve to aeeg family."""
    aeeg_names = [n for n in v5_cfg.instruments if n.startswith("aEEG ")]
    assert aeeg_names, "No aEEG instruments found"
    for n in aeeg_names:
        assert v5_cfg.instruments[n].family == "aeeg", (
            f"{n!r} → {v5_cfg.instruments[n].family!r}"
        )


def test_v5_bsr_suppression_ratio(v5_cfg: MMXConfig):
    """BSR instruments resolve to suppression_ratio family."""
    bsr_names = [n for n in v5_cfg.instruments if n.startswith("BSR ")]
    assert bsr_names, "No BSR instruments found"
    for n in bsr_names:
        assert v5_cfg.instruments[n].family == "suppression_ratio"


def test_v5_seizure_probability(v5_cfg: MMXConfig):
    """SeizureProbabilityP14 instruments resolve to seizure_probability / seizure_detection."""
    prob = [n for n in v5_cfg.instruments if "SeizureProbabilityP14 Probability" in n]
    det = [n for n in v5_cfg.instruments if "SeizureProbabilityP14 Detections" in n]
    assert prob
    assert det
    for n in prob:
        assert v5_cfg.instruments[n].family == "seizure_probability"
    for n in det:
        assert v5_cfg.instruments[n].family == "seizure_detection"


def test_v5_spike_density(v5_cfg: MMXConfig):
    """EventDensity Spike instruments resolve to spike_density family."""
    spike_names = [n for n in v5_cfg.instruments if n.startswith("EventDensity Spike")]
    assert spike_names, "No EventDensity Spike instruments found"
    for n in spike_names:
        assert v5_cfg.instruments[n].family == "spike_density"


def test_v5_comprehensive_panel_members(v5_cfg: MMXConfig):
    """Comprehensive panel has expected instruments (matching Trend panels.md)."""
    panel = v5_cfg.panels["Comprehensive"]
    names = {i.name for i in panel.instruments}

    expected_present = {
        "ArtifactIntensity",
        "SeizureProbabilityP14 Probability",
        "SeizureProbabilityP14 Detections",
        "FFT_Spectrogram 0-20 Left Hemisphere_avg",
        "FFT_Spectrogram 0-20 Right Hemisphere_avg",
        "aEEG Left Hemisphere_avg",
        "aEEG Right Hemisphere_avg",
        "BSR Left Hemisphere_avg",
        "BSR Right Hemisphere_avg",
    }
    missing = expected_present - names
    assert not missing, f"Comprehensive panel missing instruments: {missing}"


# ---------------------------------------------------------------------------
# V3 ref MMX (backwards compat)
# ---------------------------------------------------------------------------

def test_v3_ref_parses(tmp_path):
    """V3 ref MMX still parses (engine configs intact)."""
    _skip_if_missing(MMX_V3_REF)
    cfg = parse_mmx(MMX_V3_REF)
    assert "FFTEngine01" in cfg.engines
    assert cfg.engines["FFTEngine01"].epoch_step == 8.0
