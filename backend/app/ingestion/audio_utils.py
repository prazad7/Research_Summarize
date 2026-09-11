"""Shared Whisper transcription helper, used by the audio and video
extractors (and the YouTube no-captions fallback).

OpenAI's transcription endpoint caps request size at 25MB, so long
recordings are split into chunks with pydub/ffmpeg and transcribed
sequentially, then stitched back together. This is the seam to revisit if
you ever swap providers (e.g. local Whisper) -- everything else calls only
`transcribe_audio_file()`.
"""
from __future__ import annotations

import math
from pathlib import Path

from openai import OpenAI
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from app.config import settings
from app.ingestion.exceptions import CorruptFileError, MediaTooLongError, TranscriptionError
from app.logging_config import get_logger

logger = get_logger(__name__)

_MAX_CHUNK_MS = 10 * 60 * 1000  # 10 minutes per chunk, safely under the 25MB API limit
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def transcribe_audio_file(path: Path) -> str:
    try:
        audio = AudioSegment.from_file(str(path))
    except CouldntDecodeError as exc:
        raise CorruptFileError(
            "That audio/video file couldn't be decoded -- it may be corrupt or in an "
            "unsupported codec.",
            original=exc,
        ) from exc

    duration_minutes = len(audio) / 1000 / 60
    if duration_minutes > settings.MAX_MEDIA_DURATION_MINUTES:
        raise MediaTooLongError()

    chunk_count = max(1, math.ceil(len(audio) / _MAX_CHUNK_MS))
    transcripts: list[str] = []
    client = _get_client()

    for i in range(chunk_count):
        chunk = audio[i * _MAX_CHUNK_MS : (i + 1) * _MAX_CHUNK_MS]
        chunk_path = path.with_name(f"{path.stem}_chunk{i}.mp3")
        try:
            chunk.export(str(chunk_path), format="mp3")
            with open(chunk_path, "rb") as fh:
                result = client.audio.transcriptions.create(model="whisper-1", file=fh)
            transcripts.append(result.text.strip())
        except Exception as exc:
            logger.warning("whisper_chunk_failed", chunk=i, error=str(exc))
            raise TranscriptionError(original=exc) from exc
        finally:
            chunk_path.unlink(missing_ok=True)

    full_transcript = " ".join(t for t in transcripts if t)
    if not full_transcript.strip():
        raise TranscriptionError("Transcription completed but produced no text.")

    return full_transcript
