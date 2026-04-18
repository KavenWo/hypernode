const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function estimateRiskProfile(patient) {
  return {
    cardiovascular: patient.bloodThinners ? 72 : 28,
    fall: patient.mobilitySupport ? 78 : 22,
    respiratory: patient.conditions.length > 0 ? 24 : 12,
  };
}

export function normalizePatientProfile(profile) {
  const conditions = profile.chronic_conditions || [];
  const medications = profile.medications || [];
  const allergies = profile.allergies || [];
  const contacts = (profile.emergency_contacts || []).map((contact) => ({
    name: contact.name,
    relation: contact.relationship,
    phone: contact.phone,
  }));

  const normalized = {
    id: profile.patient_id,
    userId: profile.patient_id,
    patientId: profile.patient_id,
    sessionUid: profile.session_uid,
    name: profile.full_name || "Anonymous Patient",
    age: profile.age ?? "",
    bloodType: profile.blood_type || "Unknown",
    gender: "Unspecified",
    avatar: "🙂",
    scenarioLabel: "Session-owned profile",
    profileNote: profile.notes || "This profile belongs to the current anonymous session.",
    conditions,
    medications,
    allergies,
    contacts,
    bloodThinners: medications.some((item) => String(item).toLowerCase().includes("warfarin")),
    mobilitySupport: conditions.some((item) => {
      const value = String(item).toLowerCase();
      return value.includes("mobility") || value.includes("osteo") || value.includes("sarcopenia");
    }),
  };

  normalized.riskProfile = estimateRiskProfile(normalized);
  return normalized;
}

function humanizeAction(action) {
  const normalized = String(action || "").trim().toLowerCase();
  if (normalized === "call_ambulance") return "Call Ambulance";
  if (normalized === "call_family") return "Contact Family";
  if (normalized === "monitor") return "Monitor";
  if (!normalized) return "Noted";
  return normalized
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function humanizeEvent(eventType) {
  const normalized = String(eventType || "").trim().toLowerCase();
  if (normalized === "simulation") return "Fall Simulation";
  if (!normalized) return "Incident";
  return normalized
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function humanizeSeverity(severity) {
  const normalized = String(severity || "").trim().toLowerCase();
  if (normalized === "red") return "Critical";
  if (normalized === "amber") return "Medium";
  if (normalized === "yellow") return "Low";
  if (!normalized) return "Low";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function toBackendPayload(patient, sessionUid) {
  return {
    session_uid: sessionUid,
    full_name: patient.name,
    age: patient.age === "" ? null : Number(patient.age),
    blood_type: patient.bloodType || null,
    allergies: patient.allergies || [],
    medications: patient.medications || [],
    chronic_conditions: patient.conditions || [],
    emergency_contacts: (patient.contacts || []).map((contact, index) => ({
      contact_id: `contact_${index + 1}`,
      name: contact.name,
      phone: contact.phone,
      relationship: contact.relation || "emergency_contact",
      priority: index + 1,
    })),
    notes: patient.profileNote || "",
  };
}

export async function fetchSessionPatients(sessionUid) {
  const response = await fetch(`${API_BASE_URL}/api/v1/patients?session_uid=${encodeURIComponent(sessionUid)}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail || `Failed to fetch patients (${response.status})`);
  }
  return payload.map(normalizePatientProfile);
}

export async function fetchSessionHistory(sessionUid) {
  const response = await fetch(`${API_BASE_URL}/api/v1/history?session_uid=${encodeURIComponent(sessionUid)}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail || `Failed to fetch history (${response.status})`);
  }
  return payload.map((entry) => ({
    id: entry.history_id,
    incidentId: entry.incident_id,
    patientId: entry.patient_id,
    timestamp: new Date(entry.created_at).toLocaleString("en-MY", { hour12: false }).slice(0, 16),
    profile: entry.patient_name || entry.patient_id || "Unknown Patient",
    event: humanizeEvent(entry.event_type),
    severity: humanizeSeverity(entry.severity),
    action: humanizeAction(entry.action_taken),
    summary: entry.summary,
  }));
}

export async function saveSessionPatient(patient, sessionUid) {
  const response = await fetch(`${API_BASE_URL}/api/v1/patients/${patient.patientId}/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toBackendPayload(patient, sessionUid)),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail || `Failed to save patient profile (${response.status})`);
  }
  return normalizePatientProfile(payload);
}
