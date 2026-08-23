"""Pipeline execution and status endpoints."""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.models.schemas import (
    PipelineRunRequest, PipelineRunResponse,
    BatchRunRequest, BatchRunResponse,
    ReprocessRequest,
)
from qeeg.config import PipelineConfig, ArtifactConfig, SeizureConfig, BinningConfig

router = APIRouter(prefix="/api", tags=["pipeline"])

JOB_TIMEOUT_SECONDS = 3600  # 1 hour max


def get_service():
    from api.main import pipeline_service
    return pipeline_service


def _build_config(req: PipelineRunRequest) -> PipelineConfig:
    return PipelineConfig(
        artifact=ArtifactConfig(
            mode=req.artifact_mode,
            intensity_threshold=req.artifact_intensity_threshold,
            quality_threshold=req.artifact_quality_threshold,
        ),
        seizure=SeizureConfig(
            exclusion_mode=req.seizure_mode,
            probability_threshold=req.seizure_probability_threshold,
        ),
        binning=BinningConfig(
            bin_edges_hours=req.bin_edges_hours,
            min_coverage_hours=req.min_coverage_hours,
        ),
        rosc_time=req.rosc_time,
    )


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def run_pipeline(req: PipelineRunRequest):
    """Start pipeline processing for a single patient."""
    service = get_service()
    config = _build_config(req)
    patient_id = req.patient_id or req.file_ids[0]

    status = service.run_pipeline(
        file_ids=req.file_ids,
        patient_id=patient_id,
        config=config,
        rosc_time_str=req.rosc_time,
        mmx_study=req.mmx_study,
        study_name=req.study_name,
    )
    return PipelineRunResponse(job_id=status.job_id, patient_id=patient_id)


@router.get("/pipeline/status/{job_id}")
async def pipeline_status(job_id: str):
    """SSE stream of pipeline progress."""
    service = get_service()
    status = service.get_job(job_id)
    if not status:
        raise HTTPException(404, f"Job {job_id} not found")

    async def event_generator():
        while True:
            with status._lock:  # read snapshot atomically
                snapshot = {
                    "job_id": status.job_id,
                    "patient_id": status.patient_id,
                    "stage": status.stage,
                    "progress": status.progress,
                    "message": status.message,
                    "complete": status.complete,
                    "error": status.error,
                }

            # Enforce timeout
            elapsed = time.time() - status.started_at
            if not snapshot["complete"] and elapsed > JOB_TIMEOUT_SECONDS:
                with status._lock:
                    status.complete = True
                    status.error = "Job timed out after 1 hour. Check server logs."
                snapshot["complete"] = True
                snapshot["error"] = status.error

            yield {"event": "progress", "data": json.dumps(snapshot)}

            if snapshot["complete"]:
                break
            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@router.post("/pipeline/reprocess/{patient_id}", response_model=PipelineRunResponse)
async def reprocess_patient(patient_id: str, req: ReprocessRequest):
    """Re-run pipeline for an existing patient with updated config settings."""
    service = get_service()
    config = PipelineConfig(
        artifact=ArtifactConfig(
            mode=req.artifact_mode,
            intensity_threshold=req.artifact_intensity_threshold,
            quality_threshold=req.artifact_quality_threshold,
        ),
        seizure=SeizureConfig(
            exclusion_mode=req.seizure_mode,
            probability_threshold=req.seizure_probability_threshold,
        ),
        binning=BinningConfig(
            bin_edges_hours=req.bin_edges_hours,
            min_coverage_hours=req.min_coverage_hours,
        ),
    )
    try:
        status = service.reprocess_patient(
            patient_id=patient_id,
            config=config,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    return PipelineRunResponse(job_id=status.job_id, patient_id=patient_id)


@router.post("/batch/run", response_model=BatchRunResponse)
async def run_batch(req: BatchRunRequest):
    """Start batch pipeline for multiple patients."""
    service = get_service()
    patients = []
    for p in req.patients:
        patients.append({
            "file_ids": p.file_ids,
            "patient_id": p.patient_id,
            "rosc_time": p.rosc_time,
            "artifact_mode": p.artifact_mode,
            "artifact_intensity_threshold": p.artifact_intensity_threshold,
            "artifact_quality_threshold": p.artifact_quality_threshold,
            "seizure_mode": p.seizure_mode,
            "seizure_probability_threshold": p.seizure_probability_threshold,
            "bin_edges_hours": p.bin_edges_hours,
            "min_coverage_hours": p.min_coverage_hours,
            "mmx_study": p.mmx_study,
            "study_name": p.study_name,
        })

    batch_id, jobs = service.run_batch(patients)
    return BatchRunResponse(
        batch_id=batch_id,
        jobs=[PipelineRunResponse(job_id=j.job_id, patient_id=j.patient_id) for j in jobs],
    )


@router.get("/batch/status/{batch_id}")
async def batch_status(batch_id: str):
    """SSE stream of batch progress (all jobs)."""
    service = get_service()

    # Find all jobs (batch_id isn't stored on jobs, so stream all active jobs)
    async def event_generator():
        while True:
            all_complete = True
            for jid, status in list(service._jobs.items()):
                data = {
                    "job_id": status.job_id,
                    "patient_id": status.patient_id,
                    "stage": status.stage,
                    "progress": status.progress,
                    "complete": status.complete,
                    "error": status.error,
                }
                yield {"event": "progress", "data": json.dumps(data)}
                if not status.complete:
                    all_complete = False

            if all_complete:
                yield {"event": "batch_complete", "data": json.dumps({"batch_id": batch_id})}
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
