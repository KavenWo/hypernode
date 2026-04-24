import { getFirebaseIdToken, signInAnonymouslyIfNeeded } from "./firebase.js";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function bootstrapAnonymousSession(patientId = null) {
  const user = await signInAnonymouslyIfNeeded();
  const idToken = await getFirebaseIdToken(true);

  if (!idToken) {
    throw new Error("Firebase did not return an ID token.");
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/session/bootstrap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_token: idToken,
        patient_id: patientId,
        create_profile: true,
      }),
    });
  } catch {
    throw new Error(
      `Failed to reach backend session bootstrap at ${API_BASE_URL}. Make sure the backend server is running and reachable.`,
    );
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(payload?.detail || `Session bootstrap failed (${response.status})`);
  }

  return {
    firebaseUser: user,
    backendSession: payload.session,
    patientId: payload.patient_id,
    profile: payload.profile,
    patients: payload.patients || [],
  };
}

export async function resolveExistingAnonymousSession() {
  const idToken = await getFirebaseIdToken();
  if (!idToken) {
    return null;
  }
  return bootstrapAnonymousSession(null);
}
