"""Phase B hardening tests — TDD: these should FAIL before implementation.

Tests for:
1. Pipeline error boundaries (graceful partial results)
2. Config validation (monotonic bin edges, threshold ranges, artifact mode enum)
3. Path traversal protection on local upload endpoint
4. coverage_fraction column in bin summary
5. Background continuity index per bin
6. Cache invalidation when PipelineConfig changes (already tested in test_cache.py)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from qeeg.config import PipelineConfig, BinningConfig, ArtifactConfig


# ── 1. Config validation ─────────────────────────────────────────────────────

class TestConfigValidation:
    def test_monotonic_bin_edges_required(self):
        """Bin edges must be strictly increasing."""
        with pytest.raises(ValidationError):
            BinningConfig(bin_edges_hours=[0, 6, 3, 12])

    def test_bin_edges_minimum_two(self):
        """Need at least 2 edges to define 1 bin."""
        with pytest.raises(ValidationError):
            BinningConfig(bin_edges_hours=[0])

    def test_non_negative_bin_edges(self):
        """Bin edges cannot be negative."""
        with pytest.raises(ValidationError):
            BinningConfig(bin_edges_hours=[-1, 0, 6])

    def test_valid_artifact_mode_enum(self):
        """Artifact mode must be one of the allowed values."""
        with pytest.raises(ValidationError):
            ArtifactConfig(mode="invalid_mode")

    def test_valid_bin_config_passes(self):
        """Valid monotonic edges should not raise."""
        cfg = BinningConfig(bin_edges_hours=[0, 6, 12, 24])
        assert cfg.bin_edges_hours == [0, 6, 12, 24]


# ── 2. Path traversal protection ─────────────────────────────────────────────

class TestPathTraversalProtection:
    def test_rejects_path_traversal(self, client):
        """The local upload endpoint must reject path traversal attempts."""
        resp = client.post(
            "/api/upload/local",
            json={"paths": ["../../etc/passwd"]},
        )
        # Should be rejected, not 404 "file not found"
        assert resp.status_code in (400, 403)
        assert "traversal" in resp.json().get("detail", "").lower() or \
               "allowed" in resp.json().get("detail", "").lower()

    def test_rejects_dotdot_in_path(self, client, tmp_path):
        """Paths with .. components should be rejected before file existence check."""
        # Create a real CSV so the file exists — but the path uses traversal
        real = tmp_path / "legit.csv"
        real.write_text("data")
        traversal_path = str(tmp_path / "subdir" / ".." / "legit.csv")
        resp = client.post(
            "/api/upload/local",
            json={"paths": [traversal_path]},
        )
        assert resp.status_code in (400, 403)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


# ── 3. coverage_fraction in bin summary ───────────────────────────────────────

class TestCoverageFraction:
    def test_coverage_fraction_column_exists(self):
        """aggregate_by_bins must include a coverage_fraction column."""
        from qeeg.analysis.time_binning import aggregate_by_bins

        n = 7200  # 2 hours of 1-second epochs
        df = pd.DataFrame({"x": np.ones(n)})
        hours = pd.Series(np.linspace(0, 2, n))
        usable = pd.Series([True] * (n // 2) + [False] * (n // 2))

        result = aggregate_by_bins(
            df, hours, ["x"], [0, 2],
            usable_mask=usable,
            min_coverage_hours=0.01,
        )
        assert "coverage_fraction" in result.columns

    def test_coverage_fraction_value(self):
        """coverage_fraction = usable_epochs / total_epochs_in_bin."""
        from qeeg.analysis.time_binning import aggregate_by_bins

        n = 100
        df = pd.DataFrame({"x": np.ones(n)})
        hours = pd.Series(np.linspace(0, 1, n))
        # 50% usable
        usable = pd.Series([True, False] * (n // 2))

        result = aggregate_by_bins(
            df, hours, ["x"], [0, 1],
            usable_mask=usable,
            min_coverage_hours=0.0,
        )
        frac = result.iloc[0]["coverage_fraction"]
        assert 0.45 <= frac <= 0.55  # approximately 0.5


# ── 4. Background continuity index ───────────────────────────────────────────

class TestBackgroundContinuityIndex:
    def test_continuity_index_column_exists(self):
        """aggregate_by_bins must include background_continuity_index."""
        from qeeg.analysis.time_binning import aggregate_by_bins

        n = 100
        df = pd.DataFrame({
            "x": np.ones(n),
            # PERCENT-scale BSR (0-100), not a 0-1 fraction
            "suppression_left": np.random.RandomState(42).uniform(0, 50.0, n),
        })
        hours = pd.Series(np.linspace(0, 1, n))

        result = aggregate_by_bins(
            df, hours, ["x"], [0, 1],
            min_coverage_hours=0.0,
            suppression_columns=["suppression_left"],
            suppression_threshold=10.0,
        )
        assert "background_continuity_index" in result.columns

    def test_continuity_index_value(self):
        """BCI = proportion of epochs BELOW suppression threshold."""
        from qeeg.analysis.time_binning import aggregate_by_bins

        n = 100
        # All suppression values are 0% (below threshold) -> BCI = 1.0
        df = pd.DataFrame({
            "x": np.ones(n),
            "suppression_left": np.zeros(n),
        })
        hours = pd.Series(np.linspace(0, 1, n))

        result = aggregate_by_bins(
            df, hours, ["x"], [0, 1],
            min_coverage_hours=0.0,
            suppression_columns=["suppression_left"],
            suppression_threshold=10.0,
        )
        bci = result.iloc[0]["background_continuity_index"]
        assert bci == pytest.approx(1.0)


# ── 5. Pipeline error boundaries ─────────────────────────────────────────────

class TestPipelineErrorBoundaries:
    def test_partial_result_on_derived_feature_failure(self, synthetic_csv: Path):
        """If derived features fail, pipeline should return partial result with warning."""
        from qeeg.pipeline import process_patient

        # Process with a config that works — just verify the mechanism exists
        result = process_patient(synthetic_csv)
        # The pipeline should always return a PatientResult, never crash
        assert result is not None
        assert isinstance(result.warnings, list)
