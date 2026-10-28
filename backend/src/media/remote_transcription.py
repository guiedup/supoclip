"""Strict word-timing adapter for OpenAI-compatible STT, including 9Router.

Chat compatibility is deliberately independent from transcription compatibility.
Never synthesize timings from text or silently send media to another provider.
"""

import math
from pathlib import Path

import httpx


def normalize_word_transcript(payload: dict) -> dict:
    words = payload.get("words")
    if not words:
        words = [word for segment in payload.get("segments") or []
                 for word in segment.get("words") or []]
    if not words:
        raise RuntimeError(
            "STT returned no word timestamps. Select an STT model supporting "
            "verbose_json with word timings; chat and text-only STT are insufficient."
        )
    normalized = []
    previous_start = -1.0
    for word in words:
        text = str(word.get("word", word.get("text", ""))).strip()
        # Some providers include non-spoken spacing tokens.
        if not text:
            continue
        try:
            start, end = float(word["start"]), float(word["end"])
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("STT returned a word without numeric timestamps") from None
        if (not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or end <= start or start < previous_start):
            raise RuntimeError("STT returned invalid or unordered word timestamps")
        normalized.append({"word": text, "start": start, "end": end})
        previous_start = start
    if not normalized:
        raise RuntimeError("STT returned no spoken words with timestamps")
    # Group real timed words into analysis lines, without inventing timing.
    segments, group = [], []
    for word in normalized:
        group.append(word)
        if len(group) >= 18 or word["word"].endswith((".", "!", "?")):
            segments.append(_segment(group))
            group = []
    if group:
        segments.append(_segment(group))
    return {
        "text": payload.get("text") or " ".join(w["word"] for w in normalized),
        "language": payload.get("language"),
        "segments": segments,
    }


def _segment(words: list[dict]) -> dict:
    return {"start": words[0]["start"], "end": words[-1]["end"],
            "text": " ".join(w["word"] for w in words), "words": words}


def transcribe_openai_compatible(audio_path: Path, config) -> dict:
    if not config.stt_base_url or not config.stt_model:
        raise RuntimeError("STT_BASE_URL and STT_MODEL are required for remote STT")
    if audio_path.stat().st_size > 24 * 1024 * 1024:
        raise RuntimeError("Remote STT audio exceeds 24 MiB; use a shorter source")
    headers = {"Authorization": f"Bearer {config.stt_api_key}"} if config.stt_api_key else {}
    data = {"model": config.stt_model, "response_format": "verbose_json",
            "timestamp_granularities[]": "word", "timestamps_granularity": "word"}
    if config.transcription_language:
        data["language"] = config.transcription_language.split("_", 1)[0]
    with audio_path.open("rb") as audio:
        with httpx.Client(timeout=config.stt_timeout_seconds) as client:
            response = client.post(
                config.stt_base_url.rstrip("/") + "/audio/transcriptions",
                headers=headers, data=data,
                files={"file": (audio_path.name, audio, "audio/mpeg")},
            )
    if response.is_error:
        # Provider bodies may contain credentials or account details.
        raise RuntimeError(f"Remote STT failed (HTTP {response.status_code}); check 9Router STT configuration")
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError("STT did not return verbose JSON with word timestamps") from None
    if not isinstance(payload, dict):
        raise RuntimeError("STT returned an invalid JSON document")
    return normalize_word_transcript(payload)
