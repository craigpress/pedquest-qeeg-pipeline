"""File upload and local path registration endpoints."""
from __future__ import annotations

import csv
import hashlib
import re
import uuid
from pathlib import Path
from io import StringIO

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from api.models.schemas import (
    UploadResponse, MmxUploadRequest, MmxUploadResponse, MmxConfigSummary,
    MmxEngineEntry,
)
from api.services.pipeline_service import ClinicalMetadata, EEGCorrection
from qeeg.ingestion.identity import derive_patient_id

router = APIRouter(prefix="/api", tags=["upload"])

MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
MAX_MMX_SIZE = 16 * 1024 * 1024  # 16 MB — MMX files are small XML configs


def get_service():
    """Lazy import to avoid circular deps — replaced at app startup."""
    from api.main import pipeline_service
    return pipeline_service


def _sanitize_filename(name: str) -> str:
    """Strip path components and dangerous characters from uploaded filename."""
    safe = Path(name).name
    safe = re.sub(r'[^\w\-.]', '_', safe)
    return safe or "upload.csv"


def _persyst_stem_from_bytes(header_bytes: bytes) -> str | None:
    """Extract the stem of the embedded .dat path from a Persyst CSV header.

    Persyst exports begin with metadata rows like:
        File,Z:/POCCA_Data/Final_EEG_Data\\2046\\2046_1.dat
    The uploaded CSV filename is often a Persyst-generated timestamp and
    cannot be relied on for patient identification. The embedded File path
    always reflects the original recording name (e.g. 2046_1).
    Returns the stem (e.g. '2046_1') or None if not found.
    """
    text = header_bytes.decode("utf-8", errors="replace")
    for line in text.splitlines():
        lower = line.lower()
        if lower.startswith("file,"):
            embedded = line.split(",", 1)[1].strip()
            if embedded:
                stem = Path(embedded.replace("\\", "/")).stem
                if stem:
                    return stem
    return None


def _stem_to_patient_id(stem: str) -> str:
    """Derive patient ID from a Persyst filename stem via the shared rule.

    Delegates to qeeg.ingestion.identity.derive_patient_id so upload, parser,
    quick_scan, and the grouper agree (the old leading-alphanumeric regex broke
    hyphenated POCCA IDs, collapsing '01-001_UUID_2' to '01'). Falls back to a
    random ID only when the stem yields nothing.

    '2046_1'        → '2046'
    '2046_1_2'      → '2046'
    '01-001_UUID_2' → '01-001'
    'SYNTH001_1'    → 'SYNTH001'
    """
    return derive_patient_id(stem) or uuid.uuid4().hex[:8]


class LocalPathRequest(BaseModel):
    paths: list[str]


@router.post("/upload/local", response_model=list[UploadResponse])
async def register_local_files(req: LocalPathRequest):
    """Register local file paths for processing (no upload needed).

    For a desktop app, files are already on the local machine.
    This just validates paths and returns file_ids that reference them directly.
    """
    service = get_service()
    results = []
    for path_str in req.paths:
        if ".." in path_str:
            raise HTTPException(400, f"Path traversal not allowed: {path_str}")
        if path_str.startswith("\\\\") or path_str.startswith("//"):
            raise HTTPException(status_code=400, detail="Network paths not allowed")
        try:
            Path(path_str).resolve()  # validate resolvable; not used further
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid path: {exc}") from exc

        p = Path(path_str)
        if not p.exists():
            raise HTTPException(404, f"File not found: {path_str}")
        if not p.suffix.lower() == ".csv":
            raise HTTPException(400, f"Only CSV files accepted: {p.name}")

        # file_id must be unique per CSV FILE across the whole cohort. The filename
        # stem alone is NOT unique: Persyst names trend exports by export timestamp
        # (e.g. "20260611_1323_.csv"), so two different patients exported in the same
        # minute collide — they write the same {stem}.ptr and the later registration
        # overwrites the earlier, so one patient's file resolves to the other's data
        # (observed: subject-13 seg3 resolving to subject-3's recording). Disambiguate with
        # a short hash of the absolute path so colliding filenames stay distinct.
        # Use .absolute(), NOT .resolve(): .resolve() rewrites a mapped network drive
        # (Y:\) to its UNC target (\\host\share\), and reading that UNC form can fail
        # for some files even when the Y:\ path reads fine — keep the drive the user
        # actually provided. The embedded stem is still used for patient_id derivation
        # (it strips the continuation suffix, e.g. "1002_TIMESTAMP_2" → "1002_TIMESTAMP").
        _full = p.absolute()
        with open(p, "rb") as _fh:
            header_bytes = _fh.read(1024)
        embedded_stem = _persyst_stem_from_bytes(header_bytes)
        _path_hash = hashlib.sha1(str(_full).encode("utf-8")).hexdigest()[:8]
        file_id = f"{p.stem}_{_path_hash}"  # unique per file even on filename collisions
        patient_id = _stem_to_patient_id(embedded_stem if embedded_stem else p.stem)

        # Write pointer file directly into upload_dir — never follow existing
        # pointers, which could resolve to the original CSV and overwrite it.
        ptr = service.upload_dir / f"{file_id}.ptr"
        ptr.write_text(str(_full), encoding="utf-8")

        results.append(UploadResponse(
            file_id=file_id,
            patient_id=patient_id,
            filename=p.name,
            size_bytes=p.stat().st_size,
        ))
    return results


@router.post("/upload", response_model=list[UploadResponse])
async def upload_files(files: list[UploadFile] = File(...)):
    """Upload one or more CSV files via HTTP multipart (for smaller files)."""
    service = get_service()
    results = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".csv"):
            raise HTTPException(400, f"Only CSV files accepted, got: {f.filename}")

        # Peek at first 1 KB to extract embedded Persyst filename from File row,
        # then stream the rest. Use the uploaded filename as file_id (unique per
        # file); use the embedded stem only for patient_id derivation so that
        # continuation segments (all embedding the same .dat name) don't collide.
        first_chunk = await f.read(1024)
        embedded_stem = _persyst_stem_from_bytes(first_chunk)
        file_id = Path(f.filename).stem  # unique per uploaded file
        patient_id = _stem_to_patient_id(embedded_stem if embedded_stem else Path(f.filename).stem)

        dest = service.upload_dir / file_id  # write directly, never via get_upload_path

        total = 0
        try:
            with open(dest, "wb") as out:
                out.write(first_chunk)
                total += len(first_chunk)
                while chunk := await f.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD_SIZE:
                        raise HTTPException(413, f"File too large (>{MAX_UPLOAD_SIZE // (1024*1024)} MB)")
                    out.write(chunk)
        except HTTPException:
            dest.unlink(missing_ok=True)
            raise
        except OSError as exc:
            dest.unlink(missing_ok=True)
            raise HTTPException(status_code=507, detail=f"Server storage error: {exc}") from exc

        results.append(UploadResponse(
            file_id=file_id,
            patient_id=patient_id,
            filename=f.filename,
            size_bytes=total,
        ))
    return results


def _parse_clinical_csv_from_path(path: Path) -> list["ClinicalMetadata"]:
    """Read a clinical CSV from a filesystem path and return parsed metadata list.

    Tolerates the known header typo 'rosc_timeage_at_arrest_days'.
    Raises ValueError on unrecoverable parse errors (caller wraps in HTTPException or logs).
    """
    import logging
    _log = logging.getLogger(__name__)

    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise ValueError(f"Could not decode {path} with any standard encoding")

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or "patient_id" not in [f.strip().lower() for f in reader.fieldnames]:
        raise ValueError("CSV must have 'patient_id' column")

    metadata_list = []
    for row_idx, row in enumerate(reader, start=2):
        try:
            result = _parse_clinical_row(row, row_idx)
            if result is not None:
                metadata_list.append(result)
        except HTTPException as exc:
            raise ValueError(str(exc.detail)) from exc

    if not metadata_list:
        raise ValueError("CSV contains no data rows")

    return metadata_list


def _parse_clinical_row(row: dict, row_idx: int) -> "Optional[ClinicalMetadata]":
    """Parse a single CSV row into a ClinicalMetadata object.

    Required:
      - patient_id
      - rosc_time (HH:MM:SS — always needed)
      - rosc_date (non-date-shifted data) OR age_at_arrest_days/age_days (date-shifted data)

    Optional: sex, arrest_etiology, site, primary_outcome_pcpc, secondary_outcome_vabs, notes
    """
    patient_id = row.get("patient_id", "").strip()
    if not patient_id:
        raise HTTPException(400, f"Row {row_idx}: patient_id is required")

    # ROSC time is always required.
    # Tolerate the known header typo "rosc_timeage_at_arrest_days" (missing comma):
    # treat that column's value as rosc_time with a warning.
    rosc_time = row.get("rosc_time", "").strip() or None
    if not rosc_time:
        typo_val = row.get("rosc_timeage_at_arrest_days", "").strip()
        if typo_val:
            import logging
            logging.getLogger(__name__).warning(
                "Row %d: header typo 'rosc_timeage_at_arrest_days' detected — "
                "using value %r as rosc_time. Fix the CSV header to silence this.",
                row_idx, typo_val,
            )
            rosc_time = typo_val
    if not rosc_time:
        raise HTTPException(400, f"Row {row_idx}: rosc_time is required")

    # ROSC date — provided for non-date-shifted data
    rosc_date = row.get("rosc_date", "").strip() or None
    rosc_datetime = row.get("rosc_datetime", "").strip() or None
    if rosc_date and not rosc_datetime:
        rosc_datetime = f"{rosc_date} {rosc_time}"

    # Age — required for date-shifted data (omit when rosc_date is provided)
    age_str = row.get("age_at_arrest_days", "").strip() or row.get("age_days", "").strip()
    age_days: Optional[int] = None
    if age_str:
        try:
            age_days = int(age_str)
        except ValueError:
            raise HTTPException(400, f"Row {row_idx}: age must be an integer, got '{age_str}'")

    if not rosc_date and not rosc_datetime and age_days is None:
        import logging
        logging.getLogger(__name__).warning(
            "Row %d (patient %s): missing age_at_arrest_days and rosc_date — skipping row.",
            row_idx, patient_id,
        )
        return None  # caller must filter out None

    # Optional fields
    sex = row.get("sex", "").strip() or None
    arrest_etiology = row.get("arrest_etiology", "").strip() or None
    site = row.get("site", "").strip() or None
    notes = row.get("notes", "").strip() or None

    pcpc_str = row.get("primary_outcome_pcpc", "").strip()
    primary_outcome_pcpc = None
    if pcpc_str:
        try:
            primary_outcome_pcpc = int(pcpc_str)
        except ValueError:
            raise HTTPException(400, f"Row {row_idx}: primary_outcome_pcpc must be an integer, got '{pcpc_str}'")

    secondary_outcome_vabs = row.get("secondary_outcome_vabs", "").strip() or None

    return ClinicalMetadata(
        patient_id=patient_id,
        age_at_arrest_days=age_days,
        rosc_datetime=rosc_datetime,
        rosc_date=rosc_date,
        rosc_time=rosc_time,
        sex=sex,
        arrest_etiology=arrest_etiology,
        site=site,
        primary_outcome_pcpc=primary_outcome_pcpc,
        secondary_outcome_vabs=secondary_outcome_vabs,
        notes=notes,
    )


@router.post("/upload/clinical")
async def upload_clinical_data(file: UploadFile = File(...)):
    """Upload clinical metadata CSV.

    Accepted columns:
      - patient_id (required)
      - age_at_arrest_days or age_days (required, integer)
      - rosc_datetime OR rosc_date + rosc_time (optional)
      - sex, arrest_etiology, site, primary_outcome_pcpc, secondary_outcome_vabs, notes (optional)

    Example (new format):
        patient_id,age_at_arrest_days,rosc_date,rosc_time,sex,arrest_etiology,site
        3848,4380,2024-01-15,08:30:00,M,cardiac,CHOP

    Example (legacy format):
        patient_id,age_days,rosc_datetime,notes
        3848,4380,2024-01-15 08:30,
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files accepted")

    service = get_service()
    try:
        content = await file.read()
        text = content.decode("utf-8")
        reader = csv.DictReader(StringIO(text))

        if not reader.fieldnames or "patient_id" not in reader.fieldnames:
            raise HTTPException(400, "CSV must have 'patient_id' column")

        metadata_list = []
        for row_idx, row in enumerate(reader, start=2):  # start=2 because header is row 1
            result = _parse_clinical_row(row, row_idx)
            if result is not None:
                metadata_list.append(result)

        if not metadata_list:
            raise HTTPException(400, "CSV contains no data rows")

        service.store_clinical_metadata(metadata_list)
        return {
            "status": "success",
            "count": len(metadata_list),
            "patients": [m.patient_id for m in metadata_list],
        }

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(400, "File encoding error — ensure UTF-8")
    except Exception as e:
        raise HTTPException(400, f"CSV parsing error: {str(e)}")


@router.post("/upload/eeg-corrections")
async def upload_eeg_corrections(file: UploadFile = File(...)):
    """Upload EEG date correction CSV for de-identified PedQuEST recordings.

    Expected columns: new_name, age_in_days_at_time_of_eeg, eeg_start_time,
                      eeg_duration, date_of_csv_creation (optional)
    Example:
        new_name,age_in_days_at_time_of_eeg,eeg_start_time,eeg_duration,date_of_csv_creation
        subject-1_rec,6050,07:00:34,07:52:31,2025-09-26 10:07:43.964550
        subject-1_rec_2,6049,07:00:31,22:19:31,2025-09-26 10:08:44.345235
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files accepted")

    service = get_service()
    try:
        content = await file.read()
        text = content.decode("utf-8")
        reader = csv.DictReader(StringIO(text))

        required = {"new_name", "age_in_days_at_time_of_eeg", "eeg_start_time", "eeg_duration"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            missing = required - set(reader.fieldnames or [])
            raise HTTPException(400, f"CSV missing required columns: {', '.join(sorted(missing))}")

        corrections = []
        for row_idx, row in enumerate(reader, start=2):
            new_name = row.get("new_name", "").strip()
            age_str = row.get("age_in_days_at_time_of_eeg", "").strip()
            eeg_start = row.get("eeg_start_time", "").strip()
            eeg_dur = row.get("eeg_duration", "").strip()
            date_created = row.get("date_of_csv_creation", "").strip() or None

            if not new_name:
                raise HTTPException(400, f"Row {row_idx}: new_name is required")
            if not age_str:
                raise HTTPException(400, f"Row {row_idx}: age_in_days_at_time_of_eeg is required")
            try:
                age_days = int(age_str)
            except ValueError:
                raise HTTPException(
                    400, f"Row {row_idx}: age_in_days_at_time_of_eeg must be an integer, got '{age_str}'"
                )

            corrections.append(EEGCorrection(
                new_name=new_name,
                age_in_days_at_time_of_eeg=age_days,
                eeg_start_time=eeg_start,
                eeg_duration=eeg_dur,
                date_of_csv_creation=date_created,
            ))

        if not corrections:
            raise HTTPException(400, "CSV contains no data rows")

        service.store_eeg_corrections(corrections)
        return {
            "status": "success",
            "count": len(corrections),
            "files": [c.new_name for c in corrections],
        }

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(400, "File encoding error — ensure UTF-8")
    except Exception as e:
        raise HTTPException(400, f"CSV parsing error: {str(e)}")


# ---------------------------------------------------------------------------
# Path-based companion uploads (used by folder scan / manifest flow)
# ---------------------------------------------------------------------------

class PathUploadRequest(BaseModel):
    path: str


def _validate_file_path(path_str: str) -> Path:
    """Validate a file path — reject traversal and UNC paths."""
    if ".." in path_str:
        raise HTTPException(400, "Path traversal not allowed")
    if path_str.startswith("\\\\") or path_str.startswith("//"):
        raise HTTPException(400, "Network paths not allowed")
    p = Path(path_str)
    if not p.exists():
        raise HTTPException(404, f"File not found: {path_str}")
    if p.suffix.lower() != ".csv":
        raise HTTPException(400, "Only CSV files accepted")
    return p


@router.post("/upload/clinical-path")
async def upload_clinical_by_path(req: PathUploadRequest):
    """Load clinical metadata CSV from a local file path (scan/manifest flow).

    Accepts same column formats as /upload/clinical — see that endpoint's docstring.
    """
    p = _validate_file_path(req.path)

    service = get_service()
    try:
        text = p.read_text(encoding="utf-8")
        reader = csv.DictReader(StringIO(text))

        if not reader.fieldnames or "patient_id" not in reader.fieldnames:
            raise HTTPException(400, "CSV must have 'patient_id' column")

        metadata_list = []
        for row_idx, row in enumerate(reader, start=2):
            result = _parse_clinical_row(row, row_idx)
            if result is not None:
                metadata_list.append(result)

        if not metadata_list:
            raise HTTPException(400, "CSV contains no data rows")

        service.store_clinical_metadata(metadata_list)
        return {"status": "success", "count": len(metadata_list), "patients": [m.patient_id for m in metadata_list]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"CSV parsing error: {str(e)}")


@router.post("/upload/corrections-path")
async def upload_corrections_by_path(req: PathUploadRequest):
    """Load EEG corrections CSV from a local file path (scan/manifest flow)."""
    p = _validate_file_path(req.path)

    service = get_service()
    try:
        text = p.read_text(encoding="utf-8")
        reader = csv.DictReader(StringIO(text))

        required = {"new_name", "age_in_days_at_time_of_eeg", "eeg_start_time", "eeg_duration"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            missing = required - set(reader.fieldnames or [])
            raise HTTPException(400, f"CSV missing required columns: {', '.join(sorted(missing))}")

        corrections = []
        for row_idx, row in enumerate(reader, start=2):
            new_name = row.get("new_name", "").strip()
            age_str = row.get("age_in_days_at_time_of_eeg", "").strip()
            eeg_start = row.get("eeg_start_time", "").strip()
            eeg_dur = row.get("eeg_duration", "").strip()
            date_created = row.get("date_of_csv_creation", "").strip() or None

            if not new_name:
                raise HTTPException(400, f"Row {row_idx}: new_name is required")
            if not age_str:
                raise HTTPException(400, f"Row {row_idx}: age_in_days_at_time_of_eeg is required")
            try:
                age_days = int(age_str)
            except ValueError:
                raise HTTPException(400, f"Row {row_idx}: age_in_days_at_time_of_eeg must be an integer, got '{age_str}'")

            corrections.append(EEGCorrection(
                new_name=new_name, age_in_days_at_time_of_eeg=age_days,
                eeg_start_time=eeg_start, eeg_duration=eeg_dur,
                date_of_csv_creation=date_created,
            ))

        if not corrections:
            raise HTTPException(400, "CSV contains no data rows")

        service.store_eeg_corrections(corrections)
        return {"status": "success", "count": len(corrections), "files": [c.new_name for c in corrections]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"CSV parsing error: {str(e)}")


# ---------------------------------------------------------------------------
# MMX configuration upload (S7)
# ---------------------------------------------------------------------------


def _ingest_mmx(source: Path, study_name: str) -> MmxUploadResponse:
    """Parse *source*, fingerprint it, and store the config under *study_name*.

    Shared by the path-based and multipart upload endpoints.
    """
    from qeeg.ingestion.mmx_parser import parse_mmx

    try:
        mmx_cfg = parse_mmx(source)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse MMX file: {e}")

    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()

    # Store in service (pass engines dict for backwards-compat storage)
    service = get_service()
    service.store_mmx_config(study_name, mmx_cfg.engines, fingerprint, str(source))

    engine_entries = [
        MmxEngineEntry(
            name=ec.name,
            epoch_duration=ec.epoch_duration,
            epoch_step=ec.epoch_step,
            rows_per_independent_obs=ec.rows_per_independent_obs,
        )
        for ec in mmx_cfg.engines.values()
    ]
    return MmxUploadResponse(
        study_name=study_name,
        fingerprint=fingerprint,
        engines=engine_entries,
    )


@router.post("/upload/mmx", response_model=MmxUploadResponse)
async def upload_mmx(req: MmxUploadRequest):
    """Upload an MMX file by local path and associate with a study name.

    Parses engine configurations and computes a SHA-256 fingerprint for
    provenance tracking. The MMX config persists across sessions.
    """
    path_str = req.path
    study_name = req.study_name.strip()
    if not study_name:
        raise HTTPException(400, "study_name is required")

    # Validate path
    if ".." in path_str:
        raise HTTPException(400, "Path traversal not allowed")
    p = Path(path_str)
    if path_str.startswith("\\\\") or path_str.startswith("//"):
        raise HTTPException(400, "Network paths not allowed")
    if not p.exists():
        raise HTTPException(404, f"File not found: {path_str}")
    if not p.suffix.lower() == ".mmx":
        raise HTTPException(400, f"Only .mmx files accepted, got: {p.name}")

    return _ingest_mmx(p.resolve(), study_name)


@router.post("/upload/mmx/file", response_model=MmxUploadResponse)
async def upload_mmx_file(
    file: UploadFile = File(...),
    study_name: str = Form(...),
):
    """Upload an MMX file via HTTP multipart and associate with a study name.

    The browser never exposes a real local path for a picked file, so the
    path-based endpoint above cannot serve a file picker. The bytes are
    persisted under the service upload dir so ``source_path`` stays
    resolvable across restarts.
    """
    study_name = study_name.strip()
    if not study_name:
        raise HTTPException(400, "study_name is required")
    if not file.filename or not file.filename.lower().endswith(".mmx"):
        raise HTTPException(400, f"Only .mmx files accepted, got: {file.filename}")

    body = await file.read(MAX_MMX_SIZE + 1)
    if len(body) > MAX_MMX_SIZE:
        raise HTTPException(413, f"MMX file too large (>{MAX_MMX_SIZE // (1024 * 1024)} MB)")

    service = get_service()
    mmx_dir = service.upload_dir / "mmx"
    mmx_dir.mkdir(parents=True, exist_ok=True)
    dest = mmx_dir / _sanitize_filename(file.filename)
    try:
        dest.write_bytes(body)
    except OSError as exc:
        raise HTTPException(status_code=507, detail=f"Server storage error: {exc}") from exc

    try:
        return _ingest_mmx(dest, study_name)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise


@router.get("/mmx/configs", response_model=list[MmxConfigSummary])
async def list_mmx_configs():
    """List all ingested MMX configurations by study name."""
    service = get_service()
    return service.list_mmx_configs()
