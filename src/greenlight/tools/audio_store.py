"""Audio persistence: local disk or GCS bucket, switched by settings.gcs_bucket.

Local mode (gcs_bucket empty — dev + tests): WAVs live under AUDIO_DIR and URLs
are /generated_audio/<name>, served by the FastAPI static mount. Cloud mode:
WAVs upload to gs://<bucket>/audio/<name> and URLs are public object URLs
(bucket grants allUsers objectViewer) — Cloud Run's ephemeral filesystem can't
serve audio across restarts or instances.

Single owner of the URL shapes; tts_engine, stitcher, table_read, and assets
routes all go through here.
"""

import logging
from pathlib import Path

import httpx

from ..config import AUDIO_DIR, settings

logger = logging.getLogger(__name__)

_client = None
_bucket = None


def _get_bucket():
    """Lazily create the storage client (ADC: Cloud Run SA / gcloud login)."""
    global _client, _bucket
    if _bucket is None:
        from google.cloud import storage

        _client = storage.Client()
        _bucket = _client.bucket(settings.gcs_bucket)
    return _bucket


def is_cloud_url(audio_url: str) -> bool:
    return audio_url.startswith("https://")


def store_audio(local_path: str | Path) -> str:
    """Persist a local WAV and return its servable URL.

    The caller writes the file first (stitcher/tts_engine need it on disk for
    pydub anyway); this decides where it ultimately lives.
    """
    path = Path(local_path)
    if not settings.gcs_bucket:
        return f"/generated_audio/{path.name}"
    blob = _get_bucket().blob(f"audio/{path.name}")
    blob.upload_from_filename(str(path))
    url = blob.public_url
    logger.info(f"Uploaded {path.name} -> {url}")
    return url


def load_audio_bytes(audio_url: str | None) -> bytes | None:
    """Fetch WAV bytes from a local /generated_audio/ path or a https URL."""
    if not audio_url:
        return None
    if audio_url.startswith("/generated_audio/"):
        filepath = AUDIO_DIR / audio_url.split("/")[-1]
        if filepath.exists():
            try:
                return filepath.read_bytes()
            except OSError as e:
                logger.warning(f"Failed to read {filepath}: {e}")
        return None
    if is_cloud_url(audio_url):
        try:
            resp = httpx.get(audio_url, timeout=15, follow_redirects=True)
            if resp.status_code == 200:
                return resp.content
            logger.warning(f"Audio fetch {audio_url} -> HTTP {resp.status_code}")
        except httpx.HTTPError as e:
            logger.warning(f"Audio fetch failed {audio_url}: {e}")
    return None


def _blob_name_from_public_url(audio_url: str) -> str | None:
    """Extract <blob-name> from https://storage.googleapis.com/<bucket>/<name>.

    Only accepts URLs for the configured bucket — never delete arbitrary hosts.
    """
    marker = f"storage.googleapis.com/{settings.gcs_bucket}/"
    idx = audio_url.find(marker)
    if idx == -1:
        return None
    return audio_url[idx + len(marker) :]


def delete_audio(audio_url: str) -> bool:
    """Remove persisted audio. Returns True when something was removed."""
    if audio_url.startswith("/generated_audio/"):
        filepath = (AUDIO_DIR / audio_url.split("/")[-1]).resolve()
        if filepath.is_relative_to(AUDIO_DIR.resolve()) and filepath.exists():
            try:
                filepath.unlink()
                return True
            except OSError as e:
                logger.warning(f"Failed to delete {filepath}: {e}")
        return False
    if settings.gcs_bucket and is_cloud_url(audio_url):
        blob_name = _blob_name_from_public_url(audio_url)
        if not blob_name:
            return False
        try:
            _get_bucket().blob(blob_name).delete()
            return True
        except Exception as e:  # NotFound -> nothing to delete
            logger.warning(f"Bucket delete failed gs://{settings.gcs_bucket}/{blob_name}: {e}")
            return False
    return False
