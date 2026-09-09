"""Shared genai client factory. Replaces per-module _get_client singletons."""

import logging
import os
from pathlib import Path
from threading import Lock

from google import genai

from ..config import settings

logger = logging.getLogger(__name__)

_clients: dict[str, genai.Client] = {}
_lock = Lock()
_adc_cached: bool | None = None


def get_genai_client(
    *,
    location: str | None = None,
    use_vertex: bool | None = None,
    key: str = "default",
) -> genai.Client:
    """Lazily create and cache genai.Client instances.

    Args:
        location: Vertex region override (defaults to settings.google_cloud_location).
        use_vertex: Force Vertex mode (defaults to settings.google_genai_use_vertexai).
        key: Cache key for sharing client across callers.
    """
    cache_key = f"{key}:{location or settings.google_cloud_location}"
    with _lock:
        if cache_key in _clients:
            return _clients[cache_key]

        vertex = (
            use_vertex
            if use_vertex is not None
            else settings.google_genai_use_vertexai.upper() == "TRUE"
        )
        client = genai.Client(
            vertexai=vertex,
            project=settings.google_cloud_project or None,
            location=location or settings.google_cloud_location,
        )
        _clients[cache_key] = client
        return client


def is_llm_available() -> bool:
    """Returns True if either API key or Vertex project is configured.

    Centralized probe — replaces is_coverage_available + is_tts_available with
    a single source of truth.
    """
    if settings.google_api_key:
        return True
    if settings.google_genai_use_vertexai.upper() == "TRUE" and settings.google_cloud_project:
        return True
    return False


def is_dictation_available() -> bool:
    """Returns True if dictation (Gemini 3.5 Transcribe Live) can be used.

    Requires the same LLM credentials as other Gemini endpoints.
    The transcribe-live model must be accessible via the configured location.
    """
    return is_llm_available()


def has_vertex_credentials() -> bool:
    """Vertex-mode extra check: SA json, gcloud ADC file, or cloud metadata server.

    Cloud Run authenticates via the metadata server — no ADC file exists at
    the well-known path — so fall back to google.auth.default().
    """
    global _adc_cached
    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if sa_path:
        return Path(sa_path).exists()
    adc = Path.home() / ".config/gcloud/application_default_credentials.json"
    if adc.exists():
        return True
    if _adc_cached is None:
        try:
            import google.auth

            creds, _ = google.auth.default()
            _adc_cached = creds is not None
        except Exception:
            _adc_cached = False
    return _adc_cached


def get_dictation_client() -> genai.Client:
    """Client for Gemini 3.5 Transcribe Live (Live API).

    Uses dictation_cloud_location (default us-central1) — separate from the
    main client pool so dictation traffic doesn't evict LLM/TTS clients.
    """
    return get_genai_client(location=settings.dictation_cloud_location, key="dictation")


def reset_clients() -> None:
    """For tests: drop cached clients so next call re-instantiates."""
    with _lock:
        _clients.clear()
