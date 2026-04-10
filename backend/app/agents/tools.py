"""
Mock tools for the Coordinator Agent.
These functions represent the actionable real-world integrations.
"""
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_twilio_call(contact_number: str, message: str) -> dict:
    """
    Mock function to simulate a Twilio API call to dispatch an ambulance or contact family.
    """
    logger.info(f"MOCK TWILIO CALL to {contact_number}: '{message}'")
    return {"status": "success", "action": "voice_call_dispatched", "contact": contact_number}

def get_nearest_hospital(lat: float, lon: float) -> dict:
    """
    Mock function to simulate Google Maps routing to the nearest healthcare facility.
    """
    logger.info(f"MOCK GOOGLE MAPS ROUTING for coordinates ({lat}, {lon})")
    return {
        "hospital_name": "Hospital Sultan Ismail",
        "eta_minutes": 14,
        "distance_km": 8.5
    }

def push_medical_profile_to_hospital(hospital_id: str, profile_data: dict) -> dict:
    """
    Mock function simulating a webhook to a local hospital system.
    """
    logger.info(f"MOCK HOSPITAL PUSH to {hospital_id} with profile {profile_data.get('user_id')}")
    return {"status": "received", "hospital": hospital_id}
