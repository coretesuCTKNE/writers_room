import logging
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_genai_use_vertexai: str = "TRUE"
    google_cloud_project: str = ""
    google_api_key: str = ""
    google_cloud_location: str = "global"
    tts_cloud_location: str = "us-central1"

    clickhouse_url: str = "http://localhost:8123"
    clickhouse_db: str = "greenlight"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    lt_url: str = "http://localhost:8010"
    port: int = 8000
    api_host: str = "127.0.0.1"
    opencode_url: str = "http://localhost:4096"

    otel_exporter_otlp_endpoint: str = ""
    grafana_stack_url: str = ""
    grafana_service_token: str = ""
    grafana_clickhouse_uid: str = ""  # pre-baked datasource UID saves a tool hop
    grafana_public_dashboard_url: str = ""  # externally shared Story Ops dashboard
    ingest_drive_folder_id: str = ""

    enable_proto: bool = False

    agent_model: str = "gemini-3.6-flash"
    tts_model: str = "gemini-3.1-flash-tts-preview"
    coverage_model: str = "gemini-3.6-flash"
    dictation_model: str = "gemini-3.5-transcribe-live-preview"

    scripts_dir: str = "uploads"
    audio_dir: str = "generated_audio"
    gcs_bucket: str = ""  # empty = local disk mode; bucket name = upload audio to GCS
    firebase_project_id: str = ""  # empty = auth off (principal "local")

    # Preview models are global-endpoint only (no regional pinning until GA)
    dictation_cloud_location: str = "global"
    dictation_vad_silence_ms: int = 800
    dictation_vad_prefix_padding_ms: int = 20
    dictation_session_warn_seconds: int = 480  # 8 min
    dictation_session_max_seconds: int = 600  # 10 min
    dictation_shortlist_size: int = 9  # hold-key character count (keys 1–9)

    table_read_take_limit: int = 10  # 0 = unlimited; keep N newest takes per principal
    table_read_max_turns: int = 50  # 0 = unlimited; reject longer scenes for table-read
    tts_call_timeout_seconds: int = 60  # 0 = no timeout; per-turn TTS call deadline

    @field_validator("table_read_take_limit", "table_read_max_turns", "tts_call_timeout_seconds")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"limit must be >= 0, got {v}")
        return v

    @field_validator("port")
    @classmethod
    def _port_range(cls, v: int) -> int:
        if not (1024 <= v <= 65535):
            raise ValueError(f"port must be 1024-65535, got {v}")
        return v


settings = Settings()


SCRIPTS_DIR = Path(settings.scripts_dir)
SCRIPTS_DIR.mkdir(exist_ok=True)

AUDIO_DIR = Path(settings.audio_dir)
AUDIO_DIR.mkdir(exist_ok=True)


def validate_runtime() -> list[str]:
    """Surface misconfig at startup. Returns list of warnings (non-fatal)."""
    warnings: list[str] = []
    has_api_key = bool(settings.google_api_key)
    has_vertex = settings.google_genai_use_vertexai.upper() == "TRUE" and bool(
        settings.google_cloud_project
    )
    if not has_api_key and not has_vertex:
        warnings.append(
            "No GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT — /coverage, /table-read, "
            "/rewrite, /bible-check will return 503."
        )
    if settings.google_cloud_project and settings.google_genai_use_vertexai.upper() != "TRUE":
        warnings.append(
            "GOOGLE_CLOUD_PROJECT set but GOOGLE_GENAI_USE_VERTEXAI!=TRUE. "
            "Vertex endpoints will not authenticate."
        )
    if not settings.clickhouse_url:
        warnings.append("CLICKHOUSE_URL unset — DB queries will fail.")
    for w in warnings:
        logger.warning(f"[greenlight startup] {w}")
    return warnings
