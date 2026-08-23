"""Study management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models.schemas import StudyResponse, CreateStudyRequest

router = APIRouter(prefix="/api", tags=["studies"])


def get_service():
    from api.main import pipeline_service
    return pipeline_service


@router.get("/studies", response_model=list[StudyResponse])
async def list_studies():
    service = get_service()
    studies = service.list_studies()
    result = []
    for s in studies:
        patient_count = len(service.list_patients_by_study(s.name))
        result.append(StudyResponse(
            name=s.name,
            mmx_study=s.mmx_study,
            created_at=s.created_at,
            patient_count=patient_count,
            date_shifted=s.date_shifted,
        ))
    return result


@router.post("/studies", response_model=StudyResponse)
async def create_study(req: CreateStudyRequest):
    service = get_service()
    study = service.create_study(req.name, req.mmx_study, req.date_shifted)
    patient_count = len(service.list_patients_by_study(study.name))
    return StudyResponse(
        name=study.name,
        mmx_study=study.mmx_study,
        created_at=study.created_at,
        patient_count=patient_count,
        date_shifted=study.date_shifted,
    )


@router.post("/studies/{study_name}/assign")
async def assign_patients(study_name: str, patient_ids: list[str]):
    service = get_service()
    if not service.get_study(study_name):
        raise HTTPException(404, f"Study '{study_name}' not found")
    service.assign_patients_to_study(patient_ids, study_name)
    return {"status": "ok", "count": len(patient_ids)}


@router.delete("/studies/{study_name}")
async def delete_study(study_name: str):
    """Delete a study and unassign every patient previously in it.

    Does NOT delete patient data itself — patients still exist, they just
    have no study assignment. Use DELETE /api/patients/{pid} for that.
    """
    service = get_service()
    if not service.get_study(study_name):
        raise HTTPException(404, f"Study '{study_name}' not found")
    unassigned = service.delete_study(study_name)
    return {"deleted": study_name, "patients_unassigned": unassigned}
