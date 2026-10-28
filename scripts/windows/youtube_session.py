"""Export an explicitly selected Firefox profile's YouTube cookies only."""

import argparse
from http.cookiejar import Cookie, MozillaCookieJar
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
YOUTUBE_HOSTS = "(host='youtube.com' OR host='.youtube.com' OR host LIKE '%.youtube.com')"


def export_session(profile: Path, destination: Path) -> int:
    database = profile.resolve() / "cookies.sqlite"
    # Read in place through SQLite, including its WAL; do not copy other sites.
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        rows = db.execute(
            "SELECT host,path,isSecure,expiry,name,value,isHttpOnly "
            f"FROM moz_cookies WHERE {YOUTUBE_HOSTS} AND originAttributes='' "
            "AND (expiry=0 OR expiry>?)", (int(time.time()),)
        ).fetchall()
    if not rows:
        raise RuntimeError("No current YouTube session in the selected profile")
    jar = MozillaCookieJar()
    for host, path, secure, expiry, name, value, http_only in rows:
        jar.set_cookie(Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=host, domain_specified=host.startswith("."),
            domain_initial_dot=host.startswith("."), path=path,
            path_specified=True, secure=bool(secure), expires=expiry or None,
            discard=not expiry, comment=None, comment_url=None,
            rest={"HttpOnly": None} if http_only else {}, rfc2109=False,
        ))
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        # Apply a private ACL before writing any cookie values.
        identity = subprocess.check_output(["whoami"], text=True).strip()
        result = subprocess.run(
            ["icacls", str(destination.parent), "/inheritance:r", "/grant:r",
             identity + ":(OI)(CI)F"], capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise RuntimeError("Could not protect the local session directory")
    handle, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
    os.close(handle)
    try:
        jar.save(temporary, ignore_discard=True, ignore_expires=False)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return len(jar)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path,
                        help="Firefox profile directory chosen by the user")
    parser.add_argument("--remember", action="store_true",
                        help="Refresh this selected profile's YouTube session on app launch")
    args = parser.parse_args()
    if not (ROOT / "backend/.env").is_file():
        raise SystemExit("Install SupoClip first; no existing backend configuration found.")
    try:
        count = export_session(args.profile, ROOT / ".local/youtube/cookies.txt")
    except (OSError, sqlite3.Error, RuntimeError):
        raise SystemExit("Session export failed. Check the profile/login or close Firefox and retry.") from None
    from dotenv import set_key
    set_key(ROOT / "backend/.env", "YOUTUBE_COOKIE_FILE",
            str(ROOT / ".local/youtube/cookies.txt"))
    if args.remember:
        (ROOT / ".local/youtube/profile.json").write_text(
            json.dumps({"profile": str(args.profile.resolve()), "auto_refresh": True}),
            encoding="utf-8",
        )
    print(f"Exported {count} YouTube cookies to the protected local session file. No values logged.")
    print("For first-time setup, restart SupoClip when idle. Later refreshes need no restart.")


if __name__ == "__main__":
    main()
