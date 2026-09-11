from __future__ import annotations

import subprocess
from pathlib import Path

from app.db.models import Job
from app.ingestion.audio_utils import transcribe_audio_file
from app.ingestion.base import BaseExtractor, ExtractedContent
from app.ingestion.exceptions import CorruptFileError
from app.logging_config import get_logger

logger = get_logger(__name__)


class VideoExtractor(BaseExtractor):
    """Extracts the audio track (via ffmpeg) then reuses the Whisper pipeline."""

    def extract(self, job: Job) -> ExtractedContent:
        video_path = Path(job.stored_file_path)
        audio_path = video_path.with_suffix(".extracted.mp3")

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video_path),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                timeout=1800,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            logger.warning("ffmpeg_extract_failed", error=str(exc))
            raise CorruptFileError(
                "That video file couldn't be read -- it may be corrupt or in an "
                "unsupported format.",
                original=exc,
            ) from exc

        try:
            transcript = transcribe_audio_file(audio_path)
        finally:
            audio_path.unlink(missing_ok=True)

        return ExtractedContent(
            text=transcript,
            title=video_path.stem,
            raw_transcript=transcript,
            extra_metadata={"original_filename": job.source_reference},
        )
