from unittest.mock import Mock

import pytest
from yt_dlp.utils import DownloadError

from src.config import Config, set_config_override
from src.youtube_errors import YouTubeAccessRequired, requires_youtube_verification
from src.youtube_utils import download_youtube_video, get_youtube_video_info


@pytest.mark.parametrize("message", [
    "Sign in to confirm you're not a bot. Use --cookies",
    "ERROR: Sign in to confirm you’re not a bot.",
    "CAPTCHA verification required",
])
def test_recognizes_human_verification(message):
    assert requires_youtube_verification(DownloadError(message))


@pytest.mark.parametrize("message", ["HTTP Error 403: Forbidden", "timeout", "Video unavailable"])
def test_does_not_reclassify_unrelated_errors(message):
    assert not requires_youtube_verification(DownloadError(message))


def test_download_metadata_stops_before_fallback_and_returns_safe_error(monkeypatch):
    config = Config()
    config.youtube_metadata_provider = "yt_dlp"
    set_config_override(config)
    fallback = Mock()
    monkeypatch.setattr("src.youtube_utils._fetch_video_info_with_ytdlp", Mock(side_effect=
        DownloadError("Sign in to confirm you're not a bot: https://user:private@example.com/signed?token=secret")))
    monkeypatch.setattr("src.youtube_utils._fetch_video_info_with_youtube_data_api", fallback)
    try:
        with pytest.raises(YouTubeAccessRequired) as error:
            get_youtube_video_info("https://www.youtube.com/watch?v=abcdefghijk", raise_on_access_error=True)
        assert "private" not in str(error.value)
        assert "token=" not in str(error.value)
        fallback.assert_not_called()
    finally:
        set_config_override(None)


async def test_video_service_preserves_the_access_error_code(monkeypatch):
    from src.services.video_service import VideoService

    monkeypatch.setattr("src.services.video_service.resolve_full_youtube_download",
                        Mock(side_effect=YouTubeAccessRequired()))
    with pytest.raises(YouTubeAccessRequired) as error:
        await VideoService.download_video("https://www.youtube.com/watch?v=abcdefghijk")
    assert error.value.code == "youtube_access_required"


def test_full_download_does_not_try_another_provider_after_verification(monkeypatch, tmp_path):
    config = Config()
    config.temp_dir = str(tmp_path)
    config.apify_api_token = "test-fixture"
    set_config_override(config)
    fallback = Mock()
    monkeypatch.setattr("src.youtube_utils._download_youtube_video_with_ytdlp", Mock(side_effect=YouTubeAccessRequired()))
    monkeypatch.setattr("src.youtube_utils.download_youtube_video_with_apify", fallback)
    monkeypatch.setattr("src.youtube_utils._provider_order", lambda *a, **k: ["yt_dlp", "apify"])
    try:
        with pytest.raises(YouTubeAccessRequired):
            download_youtube_video("https://www.youtube.com/watch?v=abcdefghijk")
        fallback.assert_not_called()
    finally:
        set_config_override(None)
