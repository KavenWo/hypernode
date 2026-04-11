import logging

logger = logging.getLogger(__name__)


def send_twilio_call(contact_number: str, message: str) -> dict:
    logger.info("MOCK TWILIO CALL to %s: '%s'", contact_number, message)
    return {"status": "success", "action": "voice_call_dispatched", "contact": contact_number}


def get_nearest_hospital(lat: float, lon: float) -> dict:
    logger.info("MOCK GOOGLE MAPS ROUTING for coordinates (%s, %s)", lat, lon)
    return {
        "hospital_name": "Hospital Sultan Ismail",
        "eta_minutes": 14,
        "distance_km": 8.5,
    }


def dispatch_ambulance(lat: float, lon: float, contact_number: str, message: str) -> str:
    nearest = get_nearest_hospital(lat, lon)
    send_twilio_call(contact_number, message)
    return (
        f"Ambulance dispatched. Nearest hospital is {nearest['hospital_name']} "
        f"(ETA: {nearest['eta_minutes']} mins)."
    )
