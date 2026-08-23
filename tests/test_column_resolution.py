"""Tests for the MMX column-resolution path.

Before these, `build_column_schema_with_mmx`, `resolve_export_panel`,
`ensure_unique_common_names` and `_spike_laterality` had zero occurrences across
the whole test suite, and `tests/fixtures/column_identity_v2.json` was read by no
test at all -- so a full green run proved nothing about column identity.

The fixture test is the important one: it rebuilds the schema from the real
4290-1 headers and asserts every `common_name` still matches the frozen
baseline. That is what catches a silent identifier regression, which is
otherwise invisible until someone's analysis script stops joining.

Fixture tests skip when the research share is not mounted; the pure-logic tests
always run.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qeeg.__version__ import COLUMN_SCHEMA_VERSION  # noqa: E402
from qeeg.ingestion.column_mapper import (  # noqa: E402
    ColumnEntry,
    _spike_laterality,
    build_column_schema_with_mmx,
    canonical_family,
    classify_family,
    ensure_unique_common_names,
    resolve_export_panel,
)
from qeeg.ingestion.mmx_parser import parse_mmx  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / f"column_identity_v{COLUMN_SCHEMA_VERSION}.json"
PATIENT_DIR = Path(r"Y:\cardiac_arrest\4290-1_1684730")
REF_MMX = ROOT / "Ref Files" / "PedQuEST_Pennsieve_V10_research.mmx"

_share = pytest.mark.skipif(
    not PATIENT_DIR.exists() or not FIXTURE.exists(),
    reason="research share or identity fixture unavailable",
)


def _entry(code: str, name: str, i_group: int = 1) -> ColumnEntry:
    e = ColumnEntry(0, code, i_group, 1, "", "", "", None, None, "", "", "")
    e.common_name = name
    return e


# --------------------------------------------------------------------------
# Identifier stability — the regression guard
# --------------------------------------------------------------------------

@_share
def test_common_names_match_frozen_fixture():
    """Every common_name still matches the frozen baseline for this schema version.

    A failure means column identity drifted. If intentional, bump
    COLUMN_SCHEMA_VERSION, regenerate the fixture, and publish an updated
    crosswalk -- renaming a column silently is the failure mode this guards.
    """
    spec = importlib.util.spec_from_file_location(
        "_audit", ROOT / "scripts" / "audit_4290_1_columns.py")
    audit = importlib.util.module_from_spec(spec)
    sys.modules["_audit"] = audit
    spec.loader.exec_module(audit)

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mmx = parse_mmx(sorted(PATIENT_DIR.glob("*.mg2.mmx"))[0])

    checked = 0
    for csv_name, exp in fixture["exports"].items():
        csv_path = PATIENT_DIR / csv_name
        if not csv_path.exists():
            continue
        hb = audit.read_header_block(csv_path)
        built = {e.code: e for e in
                 build_column_schema_with_mmx(hb["code_to_description"], mmx)}
        for code, expected in exp["identifiers"].items():
            assert code in built, f"{csv_name}: {code} no longer emitted"
            assert built[code].common_name == expected["common_name"], (
                f"{csv_name} {code}: common_name changed "
                f"{expected['common_name']!r} -> {built[code].common_name!r}"
            )
            checked += 1
    assert checked > 4000, f"only {checked} columns checked — fixture not loaded?"


@_share
def test_every_real_column_resolves_by_ordinal():
    """No real column falls back to name or regex resolution.

    Name lookup resolves ~0.3% of columns; a fallback means the export is being
    classified from trend-name text alone, which cannot separate instruments
    Persyst ships under one display label.
    """
    spec = importlib.util.spec_from_file_location(
        "_audit", ROOT / "scripts" / "audit_4290_1_columns.py")
    audit = importlib.util.module_from_spec(spec)
    sys.modules["_audit"] = audit
    spec.loader.exec_module(audit)

    mmx = parse_mmx(sorted(PATIENT_DIR.glob("*.mg2.mmx"))[0])
    for csv_path in sorted(PATIENT_DIR.glob("2026*.csv")):
        hb = audit.read_header_block(csv_path)
        entries = build_column_schema_with_mmx(hb["code_to_description"], mmx)
        bad = [e.code for e in entries if e.resolution not in ("ordinal", "tail")]
        assert not bad, f"{csv_path.name}: {len(bad)} column(s) not ordinal: {bad[:5]}"


@_share
def test_common_names_unique_per_export():
    spec = importlib.util.spec_from_file_location(
        "_audit", ROOT / "scripts" / "audit_4290_1_columns.py")
    audit = importlib.util.module_from_spec(spec)
    sys.modules["_audit"] = audit
    spec.loader.exec_module(audit)

    mmx = parse_mmx(sorted(PATIENT_DIR.glob("*.mg2.mmx"))[0])
    for csv_path in sorted(PATIENT_DIR.glob("2026*.csv")):
        hb = audit.read_header_block(csv_path)
        names = [e.common_name for e in
                 build_column_schema_with_mmx(hb["code_to_description"], mmx)
                 if e.common_name]
        assert len(names) == len(set(names)), f"{csv_path.name}: duplicate common_name"


# --------------------------------------------------------------------------
# Panel resolution
# --------------------------------------------------------------------------

def test_resolve_export_panel_uses_the_ordinal_invariant():
    """len(panel) + 2 == max(i_group); the +2 is Persyst's Comment/Time tail."""
    mmx = parse_mmx(REF_MMX)
    assert resolve_export_panel(mmx, 240).name == "Research-Trends"   # 238 + 2
    assert resolve_export_panel(mmx, 372).name == "Research"          # 370 + 2


def test_resolve_export_panel_refuses_when_ambiguous():
    """Several panels share an instrument count, so the count alone cannot decide.

    Returning None is correct -- it must not guess. Callers fall back to
    name/regex resolution and the entries record that in `resolution`.
    """
    mmx = parse_mmx(REF_MMX)
    sizes = [len(p.instruments) for p in mmx.panels.values()]
    ambiguous = next(n for n in sizes if sizes.count(n) > 1)
    assert resolve_export_panel(mmx, ambiguous + 2) is None


def test_resolve_export_panel_returns_none_when_nothing_fits():
    assert resolve_export_panel(parse_mmx(REF_MMX), 99999) is None


# --------------------------------------------------------------------------
# Uniqueness backstop
# --------------------------------------------------------------------------

def test_backstop_does_not_steal_a_naturally_occurring_name():
    """The instrument Persyst named `foo_2` must still answer to `foo_2`.

    Suffixing in one pass let a synthesised `foo_2` claim that name and push
    the real holder to `foo_2_2` -- an identity swap, silent and type-correct,
    and worse for a downstream join than the collision it was fixing. The
    earlier version of this test asserted only uniqueness, so it passed while
    the swap happened.
    """
    entries = [_entry("a", "seizure_detection"),
               _entry("b", "seizure_detection"),
               _entry("c", "seizure_detection_2")]
    ensure_unique_common_names(entries)
    names = [e.common_name for e in entries]
    assert len(names) == len(set(names)), names
    assert names[0] == "seizure_detection"
    assert names[2] == "seizure_detection_2", (
        "the natural _2 was displaced: " + repr(names))
    assert "__dup" in names[1]


def test_backstop_survives_a_natural_name_appearing_after_the_duplicate():
    entries = [_entry("a", "x"), _entry("b", "x"), _entry("c", "x_2")]
    ensure_unique_common_names(entries)
    names = [e.common_name for e in entries]
    assert names[2] == "x_2"
    assert len(names) == len(set(names)), names


def test_backstop_preserves_first_occurrence_and_reports():
    entries = [_entry("a", "dup"), _entry("b", "dup"), _entry("c", "dup")]
    renamed = ensure_unique_common_names(entries)
    names = [e.common_name for e in entries]
    assert names[0] == "dup"
    assert len(names) == len(set(names))
    assert len(renamed) == 2


def test_backstop_ignores_empty_names():
    entries = [_entry("a", ""), _entry("b", "")]
    assert ensure_unique_common_names(entries) == []


# --------------------------------------------------------------------------
# Laterality and classification
# --------------------------------------------------------------------------

@pytest.mark.parametrize("expr,expected", [
    ("[>= 3 <0> [EventDensity Spike F3 OR Spike Fp1 OR Spike C3 OR Spike P3]]", "left"),
    ("[>= 3 <0> [EventDensity Spike F4 OR Spike Fp2 OR Spike C4 OR Spike P4]]", "right"),
    ("EventDensity SpikeGen <Detector,Count_epoch>01", "generalized"),
    ("[EventDensity Spike F3] AND NOT[EventDensity Spike F4]", "left"),
    ("[EventDensity Spike F4] AND NOT[EventDensity Spike F3]", "right"),
    # The case the previous parametrize list omitted, and the one that broke:
    # a plain symmetric conjunction is the BILATERAL detector. Splitting on the
    # first " AND " made this unreachable and returned "left" for I166.
    ("[EventDensity Spike F3 OR Spike C3] AND [EventDensity Spike F4 OR Spike C4]",
     "bilateral"),
    ("no electrodes here", ""),
])
def test_spike_laterality_reads_the_electrode_set(expr, expected):
    """Laterality comes from the expression: the display label names both sides.

    I166/I167 both read "Spikes >=3 per ten seconds (blue=left, red=right)" while
    selecting opposite hemispheres, and both were once named spike_left.
    """
    assert _spike_laterality(expr) == expected


@pytest.mark.parametrize("trend,expected", [
    ("Relative Alpha, 8-13/1-30 Hz, All 10-20", "relative_power"),
    ("Relative Theta, 4-8/1-30 Hz, Anterior", "relative_power"),
    ("Relative Delta, 1-4/1-30 Hz, Left Hemisphere", "relative_power"),
    ("FFT PowerRatio, 6-14/1-20 Hz, All 10-20", "alpha_variability"),
    ("Alpha Delta Ratio, 8-13/1-4 Hz, Left Hemisphere", "adr"),
])
def test_ratios_classify_by_denominator_not_label(trend, expected):
    """//1-30 is relative power; //1-20 is RAV; //1-4 is ADR.

    RAV means Relative Alpha VARIABILITY and Persyst pins it to 6-14/1-20 -- the
    panels named "Relative Alpha Variability" contain only that ratio.
    Alpha-over-broadband is a power measure and must not land there.
    """
    assert classify_family(trend) == expected


def test_mmx_family_aliases_reach_the_spectrogram_branches():
    """The MMX emits schema slugs; this module's branches key off shorter names.

    Unaliased, these miss every spectrogram branch, lose their bin-centre
    frequency, and fall to a generic slug that embeds the volatile I-code.
    """
    assert canonical_family("rhythmicity_spectrogram") == "rhythmicity"
    assert canonical_family("asymmetry_spectrogram") == "asymmetry"
    assert canonical_family("fft_power") == "fft_power"
