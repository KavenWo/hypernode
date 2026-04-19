"""Frontend-facing patient profile, incident lifecycle, and history routes."""

from fastapi import APIRouter, Query

from app.services.patient_incident_service import (
    ExecuteActionRequest,
    IncidentSummary,
    Incident,
    IncidentContextUpdate,
    IncidentStatusUpdate,
    PatientProfile,
    PatientProfileUpdate,
    SmsRequest,
    SmsResult,
    StartIncidentRequest,
    SubmitAnswersRequest,
    create_incident,
    execute_incident_action_once,
    get_incident_record,
    list_incident_summaries,
    list_patient_profiles,
    load_patient_profile,
    send_sms_message,
    submit_incident_answers,
    update_incident_context,
    update_incident_status,
    update_patient_profile,
)

router = APIRouter(prefix="/api/v1", tags=["Frontend API"])


@router.get("/patients/{patient_id}/profile", response_model=PatientProfile)
def get_current_profile(
    patient_id: str,
    session_uid: str | None = Query(default=None),
) -> PatientProfile:
    return load_patient_profile(patient_id, session_uid)


@router.get("/patients", response_model=list[PatientProfile])
def get_session_patients(
    session_uid: str = Query(...),
) -> list[PatientProfile]:
    return list_patient_profiles(session_uid)


@router.patch("/patients/{patient_id}/profile", response_model=PatientProfile)
def update_current_profile(
    patient_id: str,
    request: PatientProfileUpdate,
) -> PatientProfile:
    return update_patient_profile(patient_id, request.model_dump(exclude_unset=True))


@router.post("/incidents", response_model=Incident)
def start_incident(request: StartIncidentRequest) -> Incident:
    return create_incident(request)


@router.get("/incidents/summary", response_model=list[IncidentSummary])
def fetch_incident_summaries(
    session_uid: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[IncidentSummary]:
    return list_incident_summaries(session_uid=session_uid, patient_id=patient_id, limit=limit)


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_lifecycle_incident(
    incident_id: str,
    session_uid: str | None = Query(default=None),
) -> Incident:
    return get_incident_record(incident_id, session_uid)


@router.get("/incidents/{incident_id}/result", response_model=Incident)
def get_incident_result(
    incident_id: str,
    session_uid: str | None = Query(default=None),
) -> Incident:
    return get_incident_record(incident_id, session_uid)


@router.patch("/incidents/{incident_id}/status", response_model=Incident)
def update_lifecycle_status(
    incident_id: str,
    request: IncidentStatusUpdate,
) -> Incident:
    return update_incident_status(incident_id, request)


@router.post("/incidents/{incident_id}/answers", response_model=Incident)
def submit_triage_answers(
    incident_id: str,
    request: SubmitAnswersRequest,
) -> Incident:
    return submit_incident_answers(incident_id, request)


@router.post("/incidents/{incident_id}/triage", response_model=Incident)
def submit_triage_answers_alias(
    incident_id: str,
    request: SubmitAnswersRequest,
) -> Incident:
    return submit_incident_answers(incident_id, request)


@router.patch("/incidents/{incident_id}/context", response_model=Incident)
def patch_incident_context(
    incident_id: str,
    request: IncidentContextUpdate,
) -> Incident:
    return update_incident_context(incident_id, request)


@router.post("/incidents/{incident_id}/execute", response_model=Incident)
def execute_incident_action(
    incident_id: str,
    request: ExecuteActionRequest,
) -> Incident:
    return execute_incident_action_once(incident_id, request.action)


@router.post("/sms/send", response_model=SmsResult)
def send_sms_route(request: SmsRequest) -> SmsResult:
    return send_sms_message(request)
