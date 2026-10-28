"""Optional local YouTube session; never read a browser profile implicitly."""

from http.cookiejar import MozillaCookieJar
from pathlib import Path
import shutil
import warnings

import yt_dlp

from .config import get_config


class YouTubeSessionError(RuntimeError):
    code = "youtube_session_invalid"

    def __init__(self):
        super().__init__(
            "The local YouTube session is unavailable or invalid. "
            "Refresh it with the Windows YouTube session setup script."
        )


def youtube_dl(options: dict):
    """Use only explicitly supplied YouTube cookies, without writing them back.

    yt-dlp normally saves a configured cookiefile on exit. Instead, load the
    scoped export into its in-memory jar so simultaneous metadata/download
    requests cannot rewrite the private session file or the browser database.
    """
    cookie_path = getattr(get_config(), "youtube_cookie_file", "")
    jar = None
    if cookie_path:
        try:
            path = Path(cookie_path)
            if not path.is_absolute() or not path.is_file():
                raise ValueError("Missing local session")
            jar = MozillaCookieJar()
            # CookieJar can emit the offending line in parser warnings.
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                jar.load(str(path), ignore_discard=True, ignore_expires=False)
            if not jar or any(
                cookie.domain.lstrip(".") != "youtube.com"
                and not cookie.domain.lstrip(".").endswith(".youtube.com")
                for cookie in jar
            ):
                raise ValueError("Only YouTube cookies are accepted")
        except (OSError, ValueError):
            raise YouTubeSessionError() from None

    opts = dict(options)
    if jar is not None:
        # Upstream download defaults disable certificate checks. Never send an
        # authenticated session over a connection without TLS verification.
        opts["nocheckcertificate"] = False
    if "js_runtimes" not in opts:
        if shutil.which("deno"):
            opts["js_runtimes"] = {"deno": {}}
        elif shutil.which("node"):
            opts["js_runtimes"] = {"node": {}}
    client = yt_dlp.YoutubeDL(opts)
    if jar is not None:
        for cookie in jar:
            client.cookiejar.set_cookie(cookie)
    return client
