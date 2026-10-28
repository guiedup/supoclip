"""Contracts that must hold on Windows, including real subprocess locks."""

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import httpx
import pytest

from src import file_lock
from src.media.remote_transcription import normalize_word_transcript, transcribe_openai_compatible


def test_remote_word_timestamps_remain_in_seconds_until_cache_conversion():
    from src.media.transcription import _whisper_result_to_transcript_data
    result = normalize_word_transcript({"text":"Olá mundo.", "language":"pt", "words":[
        {"word":"Olá", "start":1.25,"end":1.6},
        {"text":"mundo.", "start":1.7,"end":2.2},
    ]})
    cached = _whisper_result_to_transcript_data(result)
    assert cached['words'][0]['start'] == 1250
    assert cached['words'][1]['end'] == 2200
    assert cached['language_code'] == 'pt'


@pytest.mark.parametrize('payload', [
    {'text':'Only text'}, {'segments':[{'start':0,'end':3,'text':'Only segment'}]},
    {'words':[{'word':'missing', 'start':0}]},
    {'words':[{'word':'bad', 'start':float('nan'), 'end':1}]},
    {'words':[{'word':'bad', 'start':1,'end':0}]},
    {'words':[{'word':'one','start':2,'end':3},{'word':'two','start':1,'end':2}]},
])
def test_never_invent_word_timestamps(payload):
    with pytest.raises(RuntimeError):
        normalize_word_transcript(payload)


def test_remote_error_does_not_expose_provider_response(monkeypatch, tmp_path):
    import src.media.remote_transcription as module
    def respond(request):
        assert request.url.path == '/v1/audio/transcriptions'
        assert b'timestamp_granularities[]' in request.content
        return httpx.Response(401, json={'error':'secret-key-must-not-appear'})
    real_client = httpx.Client
    monkeypatch.setattr(module.httpx, 'Client', lambda **kwargs: real_client(
        transport=httpx.MockTransport(respond), **kwargs))
    audio = tmp_path/'audio.mp3'
    audio.write_bytes(b'audio fixture')
    config = SimpleNamespace(stt_base_url='http://localhost:20128/v1',stt_api_key='private',
        stt_model='groq/whisper-large-v3',stt_timeout_seconds=5,transcription_language='pt')
    with pytest.raises(RuntimeError, match=r'HTTP 401') as error:
        transcribe_openai_compatible(audio,config)
    assert 'secret-key' not in str(error.value)


def test_process_lock_keeps_shared_readers_and_excludes_writers(tmp_path):
    lock_path = tmp_path/'media.lease'
    script = '''
import sys
from src import file_lock as lock
with open(sys.argv[1], 'a') as handle:
    try:
        lock.flock(handle, int(sys.argv[2]) | lock.LOCK_NB)
    except BlockingIOError:
        sys.exit(23)
'''
    with lock_path.open('a') as handle:
        file_lock.flock(handle, file_lock.LOCK_SH)
        shared = subprocess.run([sys.executable,'-c',script,str(lock_path),str(int(file_lock.LOCK_SH))])
        exclusive = subprocess.run([sys.executable,'-c',script,str(lock_path),str(int(file_lock.LOCK_EX))])
        assert shared.returncode == 0
        assert exclusive.returncode == 23
        file_lock.flock(handle, file_lock.LOCK_UN)
    released = subprocess.run([sys.executable,'-c',script,str(lock_path),str(int(file_lock.LOCK_EX))])
    assert released.returncode == 0


def test_remote_pipeline_import_does_not_load_torch():
    result = subprocess.run([sys.executable,'-c',
        "import sys; import src.main; assert 'torch' not in sys.modules"], capture_output=True,text=True)
    assert result.returncode == 0, result.stderr


def test_chat_uses_explicit_local_endpoint(monkeypatch):
    from src.config import Config
    from src.ai import _build_transcript_model
    monkeypatch.setenv('OPENAI_BASE_URL','http://127.0.0.1:20128/v1')
    monkeypatch.setenv('OPENAI_API_KEY','local-fixture')
    model = _build_transcript_model(Config(), 'openai:MyCombo')
    assert model.model_name == 'MyCombo'
    assert str(model.client.base_url) == 'http://127.0.0.1:20128/v1/'
