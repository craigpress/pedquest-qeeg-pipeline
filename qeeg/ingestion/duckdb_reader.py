"""DuckDB-based read path for Parquet-cached Persyst data.

Reconstructs a ParsedExport from local Parquet + sidecar metadata.
The returned object is identical to what parse_persyst_csv() returns via the
CSV slow path: same column names, same mappings, same timestamp type.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qeeg.ingestion.parser import ParsedExport
    from qeeg.ingestion.sidecar import SidecarMeta

log = logging.getLogger(__name__)


def load_from_parquet(parquet_path: Path, sidecar: "SidecarMeta") -> "ParsedExport":
    """Read Parquet via DuckDB and return a fully-populated ParsedExport.

    DuckDB reads only the columns requested (default: all) from the local
    .qeeg_cache/parquet/ copy without touching the network share.
    """
    import duckdb

    from qeeg.ingestion.parser import ExportMetadata, ParsedExport

    log.debug("DuckDB read: %s", parquet_path.name)
    df = duckdb.execute(
        "SELECT * FROM read_parquet(?)", [str(parquet_path)]
    ).df()

    metadata = ExportMetadata(
        file_path=sidecar.source_csv,
        patient_id=sidecar.patient_id,
        test_date=sidecar.test_date,
        test_time=sidecar.test_time,
        source_path=sidecar.source_csv,
        persyst_version=sidecar.persyst_version,
    )
    return ParsedExport(
        data=df,
        code_to_description=sidecar.code_to_description,
        description_to_codes=sidecar.description_to_codes,
        metadata=metadata,
        code_row_index=sidecar.code_row_index,
        trend_row_index=sidecar.trend_row_index,
    )
