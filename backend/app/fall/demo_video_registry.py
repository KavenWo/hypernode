"""Registry for controlled fall-demo videos used by the dashboard MVP."""

from __future__ import annotations

from pathlib import Path


DEMO_VIDEO_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "sample_videos"


def _label_from_filename(filename: str, index: int) -> str:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    if stem.lower().startswith("clip"):
        return stem.title()
    return f"Clip {index}"


def _build_demo_video_registry() -> dict[str, dict[str, object]]:
    registry: dict[str, dict[str, object]] = {}
    video_files = sorted(DEMO_VIDEO_DIRECTORY.glob("*.mp4"))
    print(f"[DemoRegistry] Scanning {DEMO_VIDEO_DIRECTORY} -> Found: {[f.name for f in video_files]}")
    for index, video_path in enumerate(video_files, start=1):
        video_id = video_path.stem
        registry[video_id] = {
            "id": video_id,
            "label": _label_from_filename(video_path.name, index),
            "filename": video_path.name,
            "motion_state": "unknown",
            "confidence_score": 0.0,
            "fall_detected": None,
            "summary": "Gemini will analyze this clip at session start.",
            "severity_hint": "unknown",
            "description": "Preset local clip for AI fall analysis during the dashboard session start flow.",
            "source_type": "local_demo_video",
        }
    return registry


def get_demo_video_registry() -> dict[str, dict[str, object]]:
    """Build and return the demo video registry dynamically."""
    return _build_demo_video_registry()


def get_demo_video(video_id: str | None) -> dict[str, object] | None:
    """Return the configured metadata for a known demo video."""

    if not video_id:
        return None
    return get_demo_video_registry().get(video_id)


def get_demo_video_path(video_id: str | None) -> Path | None:
    """Resolve a demo video path if the configured asset exists locally."""

    metadata = get_demo_video(video_id)
    if metadata is None:
        return None
    path = DEMO_VIDEO_DIRECTORY / str(metadata["filename"])
    if not path.exists():
        return None
    return path


def list_demo_videos() -> list[dict[str, object]]:
    """Return frontend-safe metadata for the available preset demo videos."""

    items: list[dict[str, object]] = []
    registry = get_demo_video_registry()
    for metadata in registry.values():
        path = get_demo_video_path(str(metadata["id"]))
        items.append(
            {
                "id": metadata["id"],
                "label": metadata["label"],
                "description": metadata["description"],
                "motion_state": metadata["motion_state"],
                "confidence_score": metadata["confidence_score"],
                "fall_detected": metadata["fall_detected"],
                "summary": metadata["summary"],
                "source_type": metadata["source_type"],
                "available": path is not None,
                "video_url": f"/api/v1/events/fall/demo-videos/{metadata['id']}/file",
            }
        )
    return items
