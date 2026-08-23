"""Tests for the publication audit bundle writer."""
from __future__ import annotations

import json
from pathlib import Path

from qeeg.storage.audit_bundle import build_audit_bundle, write_audit_bundle


def test_audit_bundle_captures_raw_and_export_hashes(tmp_path: Path):
    raw = tmp_path / "raw.csv"
    raw.write_bytes(b"id,val\n1,2\n")
    export = tmp_path / "out.parquet"
    export.write_bytes(b"placeholder")

    bundle = build_audit_bundle(
        patient_id="P-001",
        config={"artifact": {"mode": "quality"}},
        raw_inputs=[raw],
        generated_exports=[export],
        stage_row_counts={"parsed": 10, "usable": 7, "binned": 2},
    )

    assert bundle["patient_id"] == "P-001"
    assert bundle["audit_bundle_version"] == 1
    assert bundle["config"]["artifact"]["mode"] == "quality"
    assert bundle["stage_row_counts"]["parsed"] == 10

    raw_entry = bundle["inputs"]["raw"][0]
    assert raw_entry["path"] == str(raw)
    assert raw_entry["sha256"] and len(raw_entry["sha256"]) == 64
    assert raw_entry["size_bytes"] == raw.stat().st_size

    assert len(bundle["exports"]) == 1
    assert bundle["exports"][0]["sha256"]

    # git info should be captured (best-effort; may be None when not in a repo)
    assert "git" in bundle and set(bundle["git"]) == {"commit", "branch", "dirty"}

    # dependencies digest should be a sha256 hex string or None (no pip)
    assert "dependencies" in bundle


def test_audit_bundle_handles_missing_files_gracefully(tmp_path: Path):
    bundle = build_audit_bundle(
        patient_id="ghost",
        config=None,
        raw_inputs=[tmp_path / "nonexistent.csv"],
    )
    # Missing input gets None hash + None size — doesn't raise
    entry = bundle["inputs"]["raw"][0]
    assert entry["sha256"] is None
    assert entry["size_bytes"] is None


def test_audit_bundle_roundtrip(tmp_path: Path):
    bundle = build_audit_bundle(
        patient_id="P-42",
        config={"binning": {"bin_edges_hours": [0, 6, 12]}},
    )
    out = write_audit_bundle(bundle, tmp_path / "audit_bundle.json")
    assert out.exists()
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded["patient_id"] == "P-42"
    assert reloaded["config"]["binning"]["bin_edges_hours"] == [0, 6, 12]
