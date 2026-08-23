"""Anti-drift guard: derived Persyst docs must match code + the committed MMX.

This is the enforcement mechanism for the single-source-of-truth contract
documented in docs/INDEX.md ("Anti-drift"). Code (the family registries) and
the committed MMX are the source of truth; `scripts/sync_persyst_docs.py`
regenerates every derived artifact. If anyone edits code/MMX without
regenerating, these tests fail loudly.

Run `python scripts/sync_persyst_docs.py` to fix a failure here.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "sync_persyst_docs.py"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_persyst_docs", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync = _load_sync()


def test_generated_artifacts_are_fresh():
    """Catalog JSON, panel index, and families table must equal a fresh regen."""
    stale = sync.stale_artifacts()
    rel = [str(Path(p).relative_to(ROOT)) for p in stale]
    assert not stale, (
        "Derived Persyst docs are STALE vs code/MMX:\n  "
        + "\n  ".join(rel)
        + "\nRun: python scripts/sync_persyst_docs.py"
    )


def test_no_slug_collisions_in_v8_mmx():
    """No two distinct V8 instruments may map to the same backend slug."""
    cfg = sync.parse_mmx(sync.MMX)
    collisions = sync.check_collisions(cfg)
    assert not collisions, f"Unintended slug collisions: {collisions}"


def test_every_family_has_a_unit():
    """Every family produced by the MMX/classifier must carry a unit string."""
    cfg = sync.parse_mmx(sync.MMX)
    catalog_fams = {i.family for i in cfg.instruments.values()} - {"other", "display"}
    missing = sorted(f for f in catalog_fams if f not in sync._FAMILY_UNITS)
    assert not missing, (
        f"Families in the V8 MMX with no unit in export._FAMILY_UNITS: {missing}"
    )


def test_engine_families_have_units():
    """Every family in FAMILY_ENGINE_MAP must also have a unit (registry consistency)."""
    missing = sorted(f for f in sync.FAMILY_ENGINE_MAP if f not in sync._FAMILY_UNITS)
    assert not missing, (
        f"Families in cadence.FAMILY_ENGINE_MAP missing from export._FAMILY_UNITS: {missing}"
    )


def test_value_range_families_are_known():
    """Every family with a validation range must be a real family (unit or engine)."""
    known = set(sync._FAMILY_UNITS) | set(sync.FAMILY_ENGINE_MAP)
    orphan = sorted(f for f in sync.FAMILY_VALUE_RANGES if f not in known)
    assert not orphan, (
        f"data_checks.FAMILY_VALUE_RANGES has families unknown to units/engine map: {orphan}"
    )


def test_core_export_families_have_units():
    """Every family routed to an export group must have a unit."""
    grouped = set().union(*sync._GROUP_FAMILIES.values())
    missing = sorted(f for f in grouped if f not in sync._FAMILY_UNITS)
    assert not missing, (
        f"Families in export._GROUP_FAMILIES missing a unit: {missing}"
    )
