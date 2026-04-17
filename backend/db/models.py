"""Shared backend data models.

The standalone backend currently keeps the canonical model definitions in
`emergency.py`. This module restores the conventional `db.models` import path
and re-exports those models for other backend files.
"""

from emergency import (  # noqa: F401
    AIDecisionSummary,
    EmergencyContact,
    ExecuteActionRequest,
    HistoryEntry,
    Incident,
    IncidentStatus,
    IncidentStatusUpdate,
    Location,
    PatientProfile,
    PatientProfileUpdate,
    SeverityLevel,
    SmsRequest,
    SmsResult,
    StartIncidentRequest,
    SubmitAnswersRequest,
    VitalsSnapshot,
)
