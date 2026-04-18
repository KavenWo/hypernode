from db.firebase_client import load_patient_profile


def test_load_patient_profile_falls_back_to_sample_when_firestore_errors(monkeypatch):
    class ExplodingDocument:
        @property
        def exists(self):
            return False

    class ExplodingCollection:
        def document(self, _user_id):
            raise RuntimeError("Firestore database is not available")

    class ExplodingClient:
        def collection(self, _name):
            return ExplodingCollection()

    monkeypatch.setattr("db.firebase_client.get_firestore_client", lambda: ExplodingClient())

    profile = load_patient_profile("user_001")

    assert profile.user_id == "user_001"
    assert profile.full_name == "Amina Rahman"


def test_load_patient_profile_uses_default_sample_for_unknown_user(monkeypatch):
    monkeypatch.setattr("db.firebase_client.get_firestore_client", lambda: None)

    profile = load_patient_profile("unknown_user")

    assert profile.user_id == "unknown_user"
    assert profile.full_name == "Amina Rahman"
