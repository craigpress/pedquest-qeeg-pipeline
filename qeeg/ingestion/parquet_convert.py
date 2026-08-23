"""One-time CSV→Parquet conversion for Persyst export files.

Parquet is stored in .qeeg_cache/parquet/ on local disk — never on the share.
Conversion reads the full CSV exactly once via parse_persyst_csv() (correct
header-skip and timestamp conversion), then saves to zstd-compressed Parquet.
All subsequent reads via parse_persyst_csv() use DuckDB against the local copy.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def convert_csv_to_parquet(csv_path: Path) -> Path:
    """Convert a Persyst CSV to Parquet and update the sidecar.

    Returns the path of the written Parquet file. Raises on conversion failure
    (caller should catch and mark sidecar as 'failed').

    ClockDateTime is stored as timestamps (not raw Excel serials) so the
    DuckDB read path produces output identical to the CSV slow path.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    from qeeg.ingestion.parser import parse_persyst_csv
    from qeeg.ingestion.sidecar import parquet_cache_path, read_sidecar, write_sidecar

    out_path = parquet_cache_path(csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("Converting %s → parquet (%s)", csv_path.name, out_path.name)
    try:
        parsed = parse_persyst_csv(csv_path)
        table = pa.Table.from_pandas(parsed.data, preserve_index=False)
        pq.write_table(table, out_path, compression="zstd")
        log.info(
            "Parquet ready: %s (%.1f MB)",
            out_path.name,
            out_path.stat().st_size / 1e6,
        )

        sidecar = read_sidecar(csv_path)
        if sidecar is not None:
            sidecar.parquet_status = "ready"
            sidecar.parquet_path = str(out_path)
            write_sidecar(csv_path, sidecar)

        return out_path

    except Exception:
        sidecar = read_sidecar(csv_path)
        if sidecar is not None:
            sidecar.parquet_status = "failed"
            write_sidecar(csv_path, sidecar)
        raise
