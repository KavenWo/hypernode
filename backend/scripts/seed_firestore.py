"""Seed Firestore with the sample patient profile used during local testing."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from db.firebase_client import seed_sample_patient


def main() -> None:
    profile = seed_sample_patient()
    print(f"Seeded patient profile for {profile.user_id} ({profile.full_name}).")


if __name__ == "__main__":
    main()
