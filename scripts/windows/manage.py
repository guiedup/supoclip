"""Start and stop only the processes owned by this local installation."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / '.local'
STATE = LOCAL / 'processes.json'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, creationflags=NO_WINDOW, **kwargs)


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            return True
    except OSError:
        return False


def wait_for(check, name, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    raise RuntimeError(f'{name} did not become ready; check .local/logs')


def start_postgres(config):
    args = [Path(config['pg_bin'])/'pg_ctl.exe', '-D', LOCAL/'postgres']
    status = subprocess.run([str(a) for a in [*args,'status']], capture_output=True, creationflags=NO_WINDOW)
    if status.returncode != 0:
        if listening(config['pg_port']):
            raise RuntimeError('The dedicated PostgreSQL port is already occupied by another process')
        run([*args,'-l',LOCAL/'logs/postgres.log','-w','start'])


def process_info(pid):
    command = f'Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}" | Select-Object ProcessId,CommandLine,CreationDate | ConvertTo-Json -Compress'
    result = run(['powershell.exe','-NoProfile','-Command',command], capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def alive(record):
    info = process_info(record['pid'])
    return bool(info and info.get('CreationDate') == record['created']
                and str(ROOT).lower() in (info.get('CommandLine') or '').lower())


def launch(name, args, cwd, env, state):
    if name in state and alive(state[name]):
        return
    with (LOCAL/f'logs/{name}.log').open('ab') as log:
        process = subprocess.Popen([str(a) for a in args], cwd=cwd, env=env,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=NO_WINDOW)
    info = process_info(process.pid)
    if info is None:
        raise RuntimeError(f'{name} exited during startup; check its log')
    state[name] = {'pid': process.pid, 'created': info['CreationDate']}
    STATE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def http_ok(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def start(config, no_browser):
    from dotenv import dotenv_values
    from redis import Redis
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    env = {**os.environ, 'PYTHONUTF8':'1', 'PYTHONUNBUFFERED':'1',
           'OMP_NUM_THREADS':'2', 'MKL_NUM_THREADS':'2',
           'NODE_OPTIONS':'--max-old-space-size=1536', 'NEXT_TELEMETRY_DISABLED':'1'}
    env.update({k:v for k,v in dotenv_values(ROOT/'backend/.env').items() if v is not None})
    tesseract = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Tesseract-OCR'
    if (tesseract/'tesseract.exe').exists():
        env['PATH'] = str(tesseract) + os.pathsep + env['PATH']
    if not http_ok(config['router_url'].rstrip('/') + '/models',
                   {'Authorization': 'Bearer ' + env.get('OPENAI_API_KEY', '')}):
        raise RuntimeError('Start your existing 9Router, then retry. Its settings are never changed.')
    start_postgres(config)
    if not ('redis' in state and alive(state['redis'])):
        if listening(config['redis_port']):
            raise RuntimeError('The dedicated Redis port is occupied by another process')
        redis_bin = next((LOCAL/'tools/redis').glob('**/redis-server.exe'))
        data = LOCAL/'redis-data'
        data.mkdir(exist_ok=True)
        launch('redis', [redis_bin, '--bind','127.0.0.1','--port',config['redis_port'],
                         '--maxmemory','128mb','--maxmemory-policy','noeviction',
                         '--appendonly','yes','--save',''], data, env, state)
    wait_for(lambda: listening(config['redis_port']), 'Redis', 20)
    with Redis(host='127.0.0.1',port=config['redis_port']) as redis:
        redis.ping()
    backend_env = {**env, 'SUPOCLIP_SERVICE':'api'}
    python = ROOT/'backend/.venv/Scripts/python.exe'
    if listening(config['api_port']) and not ('api' in state and alive(state['api'])):
        raise RuntimeError('The SupoClip API port is occupied by another process')
    launch('api', [python,'-m','uvicorn','src.main:app','--host','127.0.0.1','--port',config['api_port']], ROOT/'backend', backend_env, state)
    wait_for(lambda: http_ok(f"http://127.0.0.1:{config['api_port']}/health/db"), 'API/database')
    if not ('worker' in state and alive(state['worker'])):
        with Redis(host='127.0.0.1',port=config['redis_port']) as redis:
            redis.delete('supoclip_tasks:health-check')
    launch('worker', [python,'-m','src.workers.native'], ROOT/'backend', {**env,'SUPOCLIP_SERVICE':'worker'}, state)
    # The optional conversational AI editor uses a separate provider in upstream.
    # Do not start it until explicitly configured; standard clipping/export uses worker.
    def worker_ready():
        with Redis(host='127.0.0.1',port=config['redis_port']) as redis:
            return bool(redis.get('supoclip_tasks:health-check'))
    wait_for(worker_ready, 'Worker', 90)
    frontend_env = {**os.environ, 'NODE_OPTIONS':'--max-old-space-size=1536',
                    'NEXT_TELEMETRY_DISABLED':'1'}
    node = shutil.which('node')
    mode = 'start' if (ROOT/'frontend/.next/BUILD_ID').exists() else 'dev'
    if mode == 'dev':
        frontend_env['NEXT_BUILD_DIR'] = '.next-dev'
    if listening(config['frontend_port']) and not ('frontend' in state and alive(state['frontend'])):
        raise RuntimeError('The SupoClip frontend port is occupied by another process')
    launch('frontend', [node,ROOT/'frontend/node_modules/next/dist/bin/next',mode,
                        '--hostname','127.0.0.1','--port',config['frontend_port']], ROOT/'frontend', frontend_env, state)
    url = f"http://localhost:{config['frontend_port']}"
    wait_for(lambda: http_ok(url), 'Frontend', 180)
    print(f'SupoClip ready at {url}; Redis PING and ARQ heartbeat verified.')
    if not no_browser:
        webbrowser.open(url)


def stop(config):
    from redis import Redis
    # Do not interrupt active work or queued user jobs.
    if listening(config['redis_port']):
        with Redis(host='127.0.0.1',port=config['redis_port']) as redis:
            queued = redis.zrange('supoclip_tasks', 0, -1)
            running = list(redis.scan_iter('arq:in-progress:*', count=100))
            if (any(not job.startswith(b'cron:') for job in queued)
                    or any(not key.startswith(b'arq:in-progress:cron:') for key in running)):
                raise RuntimeError('Queued/running work exists. Wait for it before stopping.')
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    for name in ['frontend','worker','api']:
        record = state.get(name)
        if record and alive(record):
            run(['taskkill.exe','/PID',record['pid'],'/T','/F'], capture_output=True)
        state.pop(name, None)
    if 'redis' in state and alive(state['redis']):
        with Redis(host='127.0.0.1',port=config['redis_port']) as redis:
            redis.shutdown(save=True)
        state.pop('redis', None)
    pg_ctl = Path(config['pg_bin'])/'pg_ctl.exe'
    status = subprocess.run([str(pg_ctl),'-D',str(LOCAL/'postgres'),'status'], capture_output=True, creationflags=NO_WINDOW)
    if status.returncode == 0:
        run([pg_ctl,'-D',LOCAL/'postgres','-w','-m','fast','stop'])
    STATE.write_text(json.dumps(state), encoding='utf-8')
    print('Stopped this installation. Existing 9Router and other databases remain running.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start','stop'])
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    config = json.loads((LOCAL/'windows.json').read_text(encoding='utf-8'))
    if args.action == 'start':
        start(config, args.no_browser)
    else:
        stop(config)
