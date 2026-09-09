"""Tests for audio_store local-disk mode (gcs_bucket empty)."""

from greenlight.config import AUDIO_DIR
from greenlight.tools.audio_store import (
    delete_audio,
    is_cloud_url,
    load_audio_bytes,
    store_audio,
)


class TestLocalMode:
    def test_store_audio_returns_generated_path(self, tmp_path):
        wav = tmp_path / "turn_abc.wav"
        wav.write_bytes(b"RIFF")
        url = store_audio(wav)
        assert url == "/generated_audio/turn_abc.wav"

    def test_store_audio_local_does_not_copy(self, tmp_path):
        wav = tmp_path / "turn_abc.wav"
        wav.write_bytes(b"RIFF")
        store_audio(wav)
        assert not (AUDIO_DIR / "turn_abc.wav").exists()

    def test_load_audio_bytes_local_roundtrip(self):
        name = "audio_store_local_test.wav"
        filepath = AUDIO_DIR / name
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_bytes(b"RIFF-local")
        try:
            assert load_audio_bytes(f"/generated_audio/{name}") == b"RIFF-local"
        finally:
            filepath.unlink(missing_ok=True)

    def test_load_audio_bytes_missing_returns_none(self):
        assert load_audio_bytes("/generated_audio/no_such_file.wav") is None
        assert load_audio_bytes(None) is None

    def test_is_cloud_url(self):
        assert is_cloud_url("https://storage.googleapis.com/bucket/audio/x.wav")
        assert not is_cloud_url("/generated_audio/x.wav")

    def test_delete_audio_local(self):
        name = "audio_store_delete_test.wav"
        filepath = AUDIO_DIR / name
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_bytes(b"RIFF")
        assert delete_audio(f"/generated_audio/{name}") is True
        assert not filepath.exists()
        assert delete_audio(f"/generated_audio/{name}") is False

    def test_delete_audio_rejects_outside_dir(self):
        assert delete_audio("/generated_audio/../../etc/passwd") is False

    def test_delete_audio_https_without_bucket_is_noop(self):
        # local mode (gcs_bucket empty) must never touch https URLs
        assert delete_audio("https://storage.googleapis.com/some/audio/x.wav") is False
