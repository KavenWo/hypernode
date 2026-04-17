"""FastAPI entrypoint for the standalone backend files."""

from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore

from app.api.routes.patient_data import router as api_router
from emergency import router as emergency_router
from vitals import router as vitals_router


app = FastAPI(title="Hypernode Emergency Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> dict:
    return {
        "status": "ok",
        "routes": [
            "/api/v1/patients/{patient_id}/profile",
            "/api/v1/incidents",
            "/api/v1/history",
            "/vitals",
            "/emergency",
        ],
    }


app.include_router(api_router)
app.include_router(emergency_router)
app.include_router(vitals_router)
