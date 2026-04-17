"""Frontend patient, incident, dispatcher, and history API routes.

The actual route handlers live in `emergency.py` for this standalone backend.
This module restores the conventional `app.api.routes.patient_data` path and
exports the same router.
"""

from emergency import (  # noqa: F401
    ExecuteActionRequest,
    Incident,
    IncidentStatusUpdate,
    PatientProfile,
    PatientProfileUpdate,
    SmsRequest,
    SmsResult,
    StartIncidentRequest,
    SubmitAnswersRequest,
    api_router as router,
    execute_incident_action,
    fetch_history,
    get_current_profile,
    get_incident_result,
    get_lifecycle_incident,
    send_sms_message,
    start_incident,
    submit_triage_answers,
    submit_triage_answers_alias,
    update_current_profile,
    update_lifecycle_status,
)
