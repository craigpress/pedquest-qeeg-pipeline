from __future__ import annotations

import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from qeeg.__version__ import __version__ as PIPELINE_VERSION

DEFAULT_COMPRESSION = "zstd"
DEFAULT_ROW_GROUP_SIZE = 100_000

# Columns that should be written as pd.CategoricalDtype for R/Arrow/Stata interop.
# Keys are column names (after _clean_column_name); values are ordered category lists.
_CATEGORICAL_COLUMNS: dict[str, list[str]] = {
    "missingness_flag": ["complete", "high_artifact", "moderate_artifact", "low_data", "no_data"],
    "n_effective_basis": ["fft_cadence_adjusted", "not_estimated"],
}

# Boolean/binary flag columns that should be categorical (True/False or 0/1).
_BOOLEAN_FLAG_COLUMNS: set[str] = {
    "meets_minimum",
    "has_status_epilepticus",
    "status_epilepticus_screen_flag",
}


def save_epochs(df: pd.DataFrame, path: Path, patient_id: str | None = None) -> Path:
    """Save processed epoch data as Parquet using robust analysis defaults."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_parquet(df, path, patient_id=patient_id)
    return path


def parquet_bytes(df: pd.DataFrame, patient_id: str | None = None) -> bytes:
    """Serialize a DataFrame to Parquet bytes with the standard schema metadata."""
    buf = io.BytesIO()
    _write_parquet(df, buf, patient_id=patient_id)
    return buf.getvalue()


def _restore_original_columns(df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    """Reverse _clean_column_name using the column_name_map stored in parquet metadata.

    _clean_column_name lowercases and sanitizes Persyst column names when writing
    the cache parquet. All downstream code (get_spectrogram_data, get_epochs_data,
    etc.) uses original Persyst names (entry.code) to look up columns, so we must
    restore them after loading.
    """
    col_map = metadata.get("column_name_map") if metadata else None
    if not col_map:
        return df
    reverse_map = {v: k for k, v in col_map.items()}
    df.columns = [reverse_map.get(c, c) for c in df.columns]
    return df


def load_epochs(path: Path) -> pd.DataFrame:
    """Load processed epoch data from Parquet and restore file metadata into attrs."""
    path = Path(path)
    table = pq.read_table(path)
    df = table.to_pandas(types_mapper=pd.ArrowDtype)
    metadata = _decode_metadata(table.schema.metadata)
    if metadata:
        df.attrs.update(metadata)
    df = _restore_original_columns(df, metadata)
    return df


def load_epochs_columns(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Load epoch data with optional column selection. Thread-safe.

    Uses pyarrow column pushdown so only requested columns are read from disk.
    Pass columns=None to load all columns (same as load_epochs).
    """
    path = Path(path)
    table = pq.read_table(path, columns=columns)
    df = table.to_pandas(types_mapper=pd.ArrowDtype)
    metadata = _decode_metadata(table.schema.metadata)
    if metadata:
        df.attrs.update(metadata)
    df = _restore_original_columns(df, metadata)
    return df


def _codebook_hash() -> str:
    """Compute a stable SHA-256 hash of the structural data dictionary."""
    from qeeg.storage.export import build_data_dictionary

    entries = build_data_dictionary(schema=None, engines=None)
    canonical = json.dumps(entries, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_parquet(
    df: pd.DataFrame,
    destination: Path | BinaryIO,
    patient_id: str | None = None,
) -> None:
    """Write Parquet with stable typing, metadata, compression, and statistics."""
    prepared, metadata = _prepare_dataframe_for_parquet(df, patient_id=patient_id)
    metadata["codebook_hash"] = _codebook_hash()
    table = pa.Table.from_pandas(prepared, preserve_index=False)
    table = table.replace_schema_metadata(_merge_metadata(table.schema.metadata, metadata))

    pq.write_table(
        table,
        destination,
        compression=DEFAULT_COMPRESSION,
        use_dictionary=True,
        write_statistics=True,
        data_page_version="2.0",
        version="2.6",
        row_group_size=_row_group_size(len(prepared)),
    )


def _prepare_dataframe_for_parquet(
    df: pd.DataFrame,
    patient_id: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normalize dtypes and build metadata for robust Parquet interchange."""
    original_columns = list(df.columns)
    prepared = df.copy()
    prepared.columns = [_clean_column_name(c) for c in prepared.columns]
    prepared = prepared.convert_dtypes(dtype_backend="pyarrow")

    for col in prepared.columns:
        series = prepared[col]
        if isinstance(series.dtype, pd.DatetimeTZDtype):
            prepared[col] = series.dt.tz_convert("UTC")
        elif pd.api.types.is_object_dtype(series.dtype):
            prepared[col] = series.astype("string[pyarrow]")

    # Cast known categorical columns to ordered CategoricalDtype
    for col, categories in _CATEGORICAL_COLUMNS.items():
        if col in prepared.columns:
            cat_dtype = pd.CategoricalDtype(categories=categories, ordered=True)
            prepared[col] = prepared[col].astype("object").astype(cat_dtype)

    # Cast boolean flag columns to categorical (False, True)
    for col in _BOOLEAN_FLAG_COLUMNS:
        if col in prepared.columns:
            cat_dtype = pd.CategoricalDtype(categories=[False, True], ordered=False)
            prepared[col] = prepared[col].astype("object").astype(cat_dtype)

    metadata = {
        "qeeg_pipeline_version": PIPELINE_VERSION,
        "export_created_utc": datetime.now(timezone.utc).isoformat(),
        "export_format": "parquet",
        "parquet_compression": DEFAULT_COMPRESSION,
        "missing_value_policy": {
            "numeric": "null/NaN",
            "categorical": "null",
            "sentinel_codes_used": False,
        },
        "row_count": int(len(prepared)),
        "column_count": int(prepared.shape[1]),
        "patient_id": patient_id or "",
        "column_name_map": dict(zip(original_columns, prepared.columns)),
        "column_dtypes": {col: str(dtype) for col, dtype in prepared.dtypes.items()},
        "null_counts": {col: _safe_int(prepared[col].isna().sum()) for col in prepared.columns},
        "data_dictionary_hint": "See export codebook/data dictionary for semantic definitions and categorical domains.",
    }
    if patient_id:
        prepared.attrs["patient_id"] = patient_id
    prepared.attrs.update(metadata)
    return prepared, metadata


def _merge_metadata(
    existing: dict[bytes, bytes] | None,
    extra: dict[str, Any],
) -> dict[bytes, bytes]:
    merged: dict[bytes, bytes] = dict(existing or {})
    for key, value in extra.items():
        merged[str(key).encode("utf-8")] = json.dumps(value, default=str).encode("utf-8")
    return merged


def _decode_metadata(metadata: dict[bytes, bytes] | None) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for raw_key, raw_value in (metadata or {}).items():
        key = raw_key.decode("utf-8")
        try:
            decoded[key] = json.loads(raw_value.decode("utf-8"))
        except Exception:
            decoded[key] = raw_value.decode("utf-8", errors="replace")
    return decoded


def _row_group_size(row_count: int) -> int:
    if row_count <= 0:
        return DEFAULT_ROW_GROUP_SIZE
    return max(10_000, min(DEFAULT_ROW_GROUP_SIZE, row_count))


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, float) and math.isnan(value):
        return 0
    return int(value)


def _clean_column_name(name: str) -> str:
    """Convert Persyst trend names to valid Parquet/R/Python identifiers."""
    name = name.replace(", ", "_").replace(",", "_")
    name = name.replace(" - ", "_").replace(" ", "_")
    name = name.replace("(", "").replace(")", "")
    name = name.replace("/", "_over_").replace(".", "_")
    name = name.replace("Hz", "hz").replace("%", "pct")
    name = name.replace("<", "lt").replace(">", "gt")
    name = name.replace(">=", "gte").replace("<=", "lte")
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)
    if name and name[0].isdigit():
        name = "x" + name
    return name.lower().rstrip("_")
