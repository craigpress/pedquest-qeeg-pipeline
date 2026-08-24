"""Tests for qeeg.storage.result_cache — hashing, save/load, invalidation."""

from __future__ import annotations

from pathlib import Path

import pytest

from qeeg.storage.result_cache import (
    _cache_key,
    cache_size_bytes,
    clear_cache,
    content_hash_file,
    content_hash_files,
    list_cached_patients,
    load_result,
    save_result,
)


class TestContentHashFile:
    def test_deterministic(self, synthetic_csv: Path):
        h1 = content_hash_file(synthetic_csv)
        h2 = content_hash_file(synthetic_csv)
        assert h1 == h2

    def test_different_files_different_hash(self, tmp_path: Path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_text("content A")
        f2.write_text("content B")
        assert content_hash_file(f1) != content_hash_file(f2)

    def test_same_file_same_hash(self, tmp_path: Path):
        # hash = name|size|mtime — same path called twice must be identical
        f = tmp_path / "a.csv"
        f.write_text("identical")
        assert content_hash_file(f) == content_hash_file(f)

    def test_different_names_different_hash(self, tmp_path: Path):
        # name is included in hash, so a.csv != b.csv even with same content
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_text("identical")
        f2.write_text("identical")
        assert content_hash_file(f1) != content_hash_file(f2)

    def test_returns_hex_string(self, synthetic_csv: Path):
        h = content_hash_file(synthetic_csv)
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)


class TestContentHashFiles:
    def test_order_independent(self, tmp_path: Path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_text("content A")
        f2.write_text("content B")
        h1 = content_hash_files([f1, f2])
        h2 = content_hash_files([f2, f1])
        assert h1 == h2  # sorted by name

    def test_single_file(self, synthetic_csv: Path):
        h = content_hash_files([synthetic_csv])
        assert len(h) == 64


class TestCacheKey:
    def test_deterministic(self):
        k1 = _cache_key("abc123", {"mode": "combined"})
        k2 = _cache_key("abc123", {"mode": "combined"})
        assert k1 == k2

    def test_different_config_different_key(self):
        k1 = _cache_key("abc123", {"mode": "combined"})
        k2 = _cache_key("abc123", {"mode": "intensity"})
        assert k1 != k2

    def test_different_hash_different_key(self):
        k1 = _cache_key("abc123", {"mode": "combined"})
        k2 = _cache_key("def456", {"mode": "combined"})
        assert k1 != k2

    def test_length(self):
        k = _cache_key("abc", {})
        assert len(k) == 16


class TestSaveAndLoadResult:
    def test_round_trip(self, synthetic_csv: Path, cache_dir: Path):
        from qeeg.pipeline import process_patient

        result = process_patient(synthetic_csv)
        config_dict = {"artifact": {"mode": "combined"}}
        content_hash = content_hash_file(synthetic_csv)

        save_result(result, config_dict, content_hash, [str(synthetic_csv)], cache_dir)

        loaded = load_result(content_hash, config_dict, cache_dir)
        assert loaded is not None
        assert "epochs" in loaded
        assert "bin_summary" in loaded
        assert "schema" in loaded
        assert "meta" in loaded
        assert loaded["meta"]["patient_id"] == result.patient_id
        assert loaded["epochs"].shape == result.epochs.shape

    def test_cache_miss_returns_none(self, cache_dir: Path):
        loaded = load_result("nonexistent_hash", {}, cache_dir)
        assert loaded is None

    def test_config_change_invalidates(self, synthetic_csv: Path, cache_dir: Path):
        from qeeg.pipeline import process_patient

        result = process_patient(synthetic_csv)
        content_hash = content_hash_file(synthetic_csv)
        config1 = {"artifact": {"mode": "combined"}}
        config2 = {"artifact": {"mode": "intensity"}}

        save_result(result, config1, content_hash, [str(synthetic_csv)], cache_dir)

        # Same content hash but different config -> miss
        loaded = load_result(content_hash, config2, cache_dir)
        assert loaded is None

    def test_schema_preserved(self, synthetic_csv: Path, cache_dir: Path):
        from qeeg.pipeline import process_patient

        result = process_patient(synthetic_csv)
        config_dict = {}
        content_hash = content_hash_file(synthetic_csv)

        save_result(result, config_dict, content_hash, [str(synthetic_csv)], cache_dir)
        loaded = load_result(content_hash, config_dict, cache_dir)

        assert len(loaded["schema"]) == len(result.schema)
        assert loaded["schema"][0]["code"] == result.schema[0].code


class TestListCachedPatients:
    def test_empty_cache(self, cache_dir: Path):
        assert list_cached_patients(cache_dir) == []

    def test_lists_after_save(self, synthetic_csv: Path, cache_dir: Path):
        from qeeg.pipeline import process_patient

        result = process_patient(synthetic_csv)
        content_hash = content_hash_file(synthetic_csv)
        save_result(result, {}, content_hash, [str(synthetic_csv)], cache_dir)

        patients = list_cached_patients(cache_dir)
        assert len(patients) == 1
        assert patients[0]["patient_id"] == result.patient_id

    def test_nonexistent_dir(self, tmp_path: Path):
        assert list_cached_patients(tmp_path / "nonexistent") == []


class TestClearCache:
    def test_clears_patient(self, synthetic_csv: Path, cache_dir: Path):
        from qeeg.pipeline import process_patient

        result = process_patient(synthetic_csv)
        content_hash = content_hash_file(synthetic_csv)
        save_result(result, {}, content_hash, [str(synthetic_csv)], cache_dir)

        assert clear_cache(result.patient_id, cache_dir) is True
        assert list_cached_patients(cache_dir) == []

    def test_returns_false_when_nothing_to_clear(self, cache_dir: Path):
        assert clear_cache("nonexistent", cache_dir) is False

    def test_exact_patient_id_does_not_clear_prefix_match(self, cache_dir: Path):
        """Regression: clearing subject-1 must not delete subject-10."""
        d1 = cache_dir / "aaa_subject-1"
        d2 = cache_dir / "bbb_subject-10"
        d1.mkdir(parents=True)
        d2.mkdir(parents=True)
        (d1 / "meta.json").write_text('{"patient_id": "subject-1"}', encoding="utf-8")
        (d2 / "meta.json").write_text('{"patient_id": "subject-10"}', encoding="utf-8")

        assert clear_cache("subject-1", cache_dir) is True
        assert not d1.exists()
        assert d2.exists()


class TestCacheSizeBytes:
    def test_empty_cache(self, cache_dir: Path):
        assert cache_size_bytes(cache_dir) == 0

    def test_nonzero_after_save(self, synthetic_csv: Path, cache_dir: Path):
        from qeeg.pipeline import process_patient

        result = process_patient(synthetic_csv)
        content_hash = content_hash_file(synthetic_csv)
        save_result(result, {}, content_hash, [str(synthetic_csv)], cache_dir)

        assert cache_size_bytes(cache_dir) > 0
