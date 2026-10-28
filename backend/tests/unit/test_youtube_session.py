"""Scoped authentication must not mutate browser/exported session files."""

from http.cookiejar import Cookie, MozillaCookieJar
from types import SimpleNamespace

import pytest

from src.youtube_session import YouTubeSessionError, youtube_dl


def cookie_file(path, domain=".youtube.com"):
    jar = MozillaCookieJar(str(path))
    jar.set_cookie(Cookie(
        0, "SID", "test-only-session", None, False, domain, True, True,
        "/", True, True, None, True, None, None, {}, False,
    ))
    jar.save(ignore_discard=True)


def test_scoped_session_stays_in_memory_and_export_is_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "cookies.txt"
    cookie_file(path)
    before = path.read_bytes()
    monkeypatch.setattr("src.youtube_session.get_config",
                        lambda: SimpleNamespace(youtube_cookie_file=str(path)))
    with youtube_dl({"quiet": True, "skip_download": True, "nocheckcertificate": True}) as client:
        assert "SID=test-only-session" in client.cookiejar.get_cookie_header("https://www.youtube.com/")
        assert not client.cookiejar.get_cookie_header("https://example.com/")
        assert client.cookiejar.filename is None
        assert client.params["nocheckcertificate"] is False
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["missing", "relative", "other_site", "empty", "malformed", "malformed_row"])
def test_invalid_or_unscoped_session_fails_without_leaking_details(tmp_path, monkeypatch, capsys, kind):
    path = tmp_path / "private-name.txt"
    if kind == "relative":
        path = type(path)("private-name.txt")
    elif kind == "other_site":
        cookie_file(path, ".example.com")
    elif kind == "empty":
        MozillaCookieJar(str(path)).save()
    elif kind == "malformed":
        path.write_text("sensitive-value")
    elif kind == "malformed_row":
        path.write_text("# Netscape HTTP Cookie File\n.youtube.com\tFALSE\t/\tTRUE\t0\tSID\tsensitive-value\n")
    monkeypatch.setattr("src.youtube_session.get_config",
                        lambda: SimpleNamespace(youtube_cookie_file=str(path)))
    with pytest.raises(YouTubeSessionError) as error:
        youtube_dl({"quiet": True})
    assert error.value.code == "youtube_session_invalid"
    assert "private-name" not in str(error.value)
    assert "sensitive-value" not in str(error.value)
    captured = capsys.readouterr()
    assert "sensitive-value" not in captured.out + captured.err


def test_browser_export_selects_only_youtube_without_changing_database(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlite3
    import time

    spec = importlib.util.spec_from_file_location(
        "windows_youtube_session",
        Path(__file__).resolve().parents[3] / "scripts/windows/youtube_session.py",
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    profile = tmp_path / "profile"
    profile.mkdir()
    database = profile / "cookies.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE moz_cookies(host,path,isSecure,expiry,name,value,isHttpOnly,originAttributes)")
        db.executemany("INSERT INTO moz_cookies VALUES(?,?,?,?,?,?,?,?)", [
            (".youtube.com", "/", 1, int(time.time()) + 600, "SID", "youtube-session", 1, ""),
            (".example.com", "/", 1, int(time.time()) + 600, "SID", "other-session", 1, ""),
            (".youtube.com", "/", 1, 1, "OLD", "expired", 1, ""),
            ("evil-youtube.com", "/", 1, int(time.time()) + 600, "BAD", "lookalike", 1, ""),
        ])
    before = database.read_bytes()
    target = tmp_path / "protected" / "cookies.txt"
    assert script.export_session(profile, target) == 1
    assert database.read_bytes() == before
    export = target.read_text()
    assert "youtube-session" in export
    assert not any(value in export for value in ["other-session", "expired", "lookalike"])


@pytest.mark.parametrize("limit", [3600, 5400])
async def test_cached_video_needs_no_online_session_but_keeps_duration_limit(tmp_path, monkeypatch, limit):
    from unittest.mock import AsyncMock
    from src.services.video_service import VideoService

    source = tmp_path / "full.mp4"
    source.write_bytes(b"fixture")
    monkeypatch.setattr("src.services.video_service.get_config", lambda: SimpleNamespace(
        max_video_duration=limit, youtube_download_max_bytes=2_000_000_000,
    ))
    monkeypatch.setattr("src.services.video_service.cached_full_media", lambda _: source)
    monkeypatch.setattr("src.services.video_service.ffprobe_duration", lambda _: 4690.0)
    metadata = AsyncMock(side_effect=AssertionError("No network request for cached source"))
    monkeypatch.setattr("src.services.video_service.async_get_youtube_video_info", metadata)
    monkeypatch.setattr("src.services.video_service.proxy_configured", lambda _: False)
    preparation = AsyncMock(side_effect=RuntimeError("reached media preparation"))
    monkeypatch.setattr(VideoService, "prepare_source", preparation)
    with pytest.raises(Exception, match="Video is too long" if limit < 4690 else "reached media preparation"):
        await VideoService.process_video_complete(
            "https://www.youtube.com/watch?v=abcdefghijk", "youtube",
        )
    metadata.assert_not_awaited()
    if limit < 4690:
        preparation.assert_not_awaited()
    else:
        preparation.assert_awaited_once_with(source)


def test_bad_local_session_does_not_fall_back_to_other_providers(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from src.config import Config, set_config_override
    from src.youtube_utils import download_youtube_video, get_youtube_video_info

    config = Config()
    config.temp_dir = str(tmp_path)
    config.youtube_metadata_provider = "yt_dlp"
    config.apify_api_token = "fixture"
    fallback = Mock()
    monkeypatch.setattr("src.youtube_utils._fetch_video_info_with_ytdlp", Mock(side_effect=YouTubeSessionError()))
    monkeypatch.setattr("src.youtube_utils._fetch_video_info_with_youtube_data_api", fallback)
    monkeypatch.setattr("src.youtube_utils.download_youtube_video_with_apify", fallback)
    set_config_override(config)
    try:
        with pytest.raises(YouTubeSessionError):
            get_youtube_video_info("https://www.youtube.com/watch?v=abcdefghijk")
        with pytest.raises(YouTubeSessionError):
            download_youtube_video("https://www.youtube.com/watch?v=abcdefghijk")
        fallback.assert_not_called()
    finally:
        set_config_override(None)
