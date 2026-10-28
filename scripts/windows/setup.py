"""Provision isolated Windows services. Never modify the 9Router database."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local"
REDIS_URL = "https://github.com/redis-windows/redis-windows/releases/download/8.10.3/Redis-8.10.3-Windows-x64-msys2.zip"
REDIS_SHA256 = "af16df340525b431e9ec8dabfd625d5e7a233f82805b5418819904ea909c447f"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, creationflags=NO_WINDOW, **kwargs)


def read_router():
    """The active SQLite store supersedes the obsolete db.json migration file."""
    path = Path(os.environ["APPDATA"]) / "9router/db/data.sqlite"
    if not path.exists():
        raise RuntimeError("9Router active SQLite store not found; configure .env manually")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        if not db.execute("SELECT 1 FROM combos WHERE name='MyCombo'").fetchone():
            raise RuntimeError("MyCombo does not exist in the active 9Router configuration")
        row = db.execute("SELECT key FROM apiKeys WHERE isActive=1 AND COALESCE(accessRestricted,0)=0 LIMIT 1").fetchone()
        if not row:
            raise RuntimeError("No unrestricted active 9Router API key; supply a suitable key privately")
        return row[0]


def router_url():
    # Match the exact local 9Router process and its listening port, not any Node app.
    command = "$p=Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'node.exe' -and $_.CommandLine -match '9router[\\\\/]app[\\\\/]custom-server.js'}; Get-NetTCPConnection -State Listen | Where-Object {$_.OwningProcess -in $p.ProcessId} | Select-Object -ExpandProperty LocalPort -Unique"
    result = run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True)
    ports = [int(v) for v in result.stdout.split() if v.isdigit()]
    if len(ports) != 1:
        raise RuntimeError("Cannot uniquely discover 9Router port; pass -RouterUrl http://127.0.0.1:PORT/v1")
    return f"http://127.0.0.1:{ports[0]}/v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--router-url")
    parser.add_argument("--stt-model")
    parser.add_argument("--local-whisper", action="store_true")
    args = parser.parse_args()
    LOCAL.mkdir(exist_ok=True)
    config_file = LOCAL / "windows.json"
    if config_file.exists():
        print("Existing configuration preserved. Starting its isolated database if necessary.")
        config = json.loads(config_file.read_text(encoding="utf-8"))
    else:
        # Reuse installed executables but never attach to or modify existing databases.
        candidates = sorted(Path(os.environ.get("ProgramFiles", "C:/Program Files")).glob("PostgreSQL/*/bin/pg_ctl.exe"), reverse=True)
        if not candidates:
            raise RuntimeError("Install PostgreSQL Windows binaries first; see docs/windows-native.md")
        pg_bin = candidates[0].parent
        url = args.router_url or router_url()
        if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise RuntimeError("This installer only integrates a local 9Router")
        key = read_router()
        with urllib.request.urlopen(urllib.request.Request(url.rstrip('/') + '/models', headers={"Authorization": "Bearer " + key}), timeout=10) as response:
            if "MyCombo" not in [m["id"] for m in json.load(response).get("data", [])]:
                raise RuntimeError("The discovered 9Router does not advertise MyCombo")
        config = {"pg_bin": str(pg_bin), "pg_port": 55432, "redis_port": 56379,
                  "api_port": 8000, "frontend_port": 3107, "router_url": url,
                  "pg_password": secrets.token_hex(24)}
        # Refuse to overwrite an existing app environment.
        if (ROOT / 'backend/.env').exists() or (ROOT / 'frontend/.env.local').exists():
            raise RuntimeError("Existing application .env found; review it before provisioning")
        backend_url = f"postgresql+asyncpg://supoclip:{config['pg_password']}@127.0.0.1:55432/supoclip"
        frontend_url = backend_url.replace("postgresql+asyncpg:", "postgresql:")
        auth_secret = secrets.token_hex(32)
        common = {"BACKEND_AUTH_SECRET": auth_secret, "SELF_HOST": "true"}
        backend = {**common, "DATABASE_URL": backend_url, "OPENAI_BASE_URL": url,
                   "OPENAI_API_KEY": key, "LLM": "openai:MyCombo", "RERANK_LLM": "openai:MyCombo",
                   "STT_BASE_URL": url, "STT_API_KEY": key, "STT_MODEL": args.stt_model or "groq/whisper-large-v3",
                   "TRANSCRIPTION_PROVIDER": "whisper" if args.local_whisper else "openai_compatible",
                   "WHISPER_MODEL_SIZE": "tiny", "WHISPER_CPU_THREADS": "2",
                   "REDIS_HOST": "127.0.0.1", "REDIS_PORT": "56379", "WORKER_MAX_JOBS": "1",
                   "MAX_CLIPS": "2", "FAST_MODE_MAX_CLIPS": "2", "DEFAULT_PROCESSING_MODE": "fast",
                   "TEMP_DIR": str(LOCAL / 'uploads'), "OUTPUT_DIR": str(LOCAL / 'clips'),
                   "CORS_ORIGINS": "http://localhost:3107", "NEXT_PUBLIC_APP_URL": "http://localhost:3107",
                   "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "FFMPEG_THREADS": "2"}
        frontend = {**common, "DATABASE_URL": frontend_url, "BETTER_AUTH_SECRET": secrets.token_hex(32),
                    "BETTER_AUTH_URL": "http://localhost:3107", "NEXT_PUBLIC_SELF_HOST": "true",
                    "NEXT_PUBLIC_APP_URL": "http://localhost:3107", "NEXT_PUBLIC_API_URL": "http://127.0.0.1:8000",
                    "BACKEND_URL": "http://127.0.0.1:8000", "API_URL": "http://127.0.0.1:8000"}
        for file, values in [(ROOT/'backend/.env', backend), (ROOT/'frontend/.env.local', frontend)]:
            file.write_text(''.join(k + '=' + json.dumps(v) + '\n' for k,v in values.items()), encoding='utf-8')
        config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    # Redis port retains its bundled licenses and DLLs. Check the published digest.
    redis_dir = LOCAL / "tools/redis"
    if not list(redis_dir.glob("**/redis-server.exe")):
        redis_dir.mkdir(parents=True, exist_ok=True)
        archive = LOCAL / "tools/redis.zip"
        urllib.request.urlretrieve(REDIS_URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != REDIS_SHA256:
            raise RuntimeError("Redis archive SHA256 mismatch")
        with zipfile.ZipFile(archive) as z:
            z.extractall(redis_dir)
    # Only this repository's private new cluster is initialized.
    pg_data = LOCAL / "postgres"
    if not (pg_data / "PG_VERSION").exists():
        pwfile = LOCAL / "initdb-password.tmp"
        try:
            pwfile.write_text(config["pg_password"], encoding="utf-8")
            run([Path(config['pg_bin'])/'initdb.exe', '-D', pg_data, '-U', 'supoclip',
                 '-A', 'scram-sha-256', '--encoding=UTF8', '--locale=C', '--pwfile', pwfile])
        finally:
            pwfile.unlink(missing_ok=True)
        with (pg_data/'postgresql.conf').open('a', encoding='utf-8') as out:
            out.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\nshared_buffers = '64MB'\nmax_connections = 40\nwork_mem = '4MB'\n")
    sys.path.insert(0, str(Path(__file__).parent))
    from manage import start_postgres
    start_postgres(config)
    env = {**os.environ, "PGPASSWORD": config["pg_password"]}
    psql = [Path(config['pg_bin'])/'psql.exe', '-h','127.0.0.1','-p','55432','-U','supoclip','-v','ON_ERROR_STOP=1']
    exists = run([*psql, '-d', 'postgres', '-tAc', "SELECT 1 FROM pg_database WHERE datname='supoclip'"], env=env, capture_output=True, text=True)
    if not exists.stdout.strip():
        run([*psql,'-d','postgres','-c','CREATE DATABASE supoclip'], env=env)
        run([*psql,'-d','supoclip','-f',ROOT/'init.sql'], env=env)
    print("Windows services provisioned. Credentials saved only in ignored local files.")


if __name__ == '__main__':
    main()
