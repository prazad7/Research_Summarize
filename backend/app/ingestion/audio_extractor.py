from __future__ import annotations

from pathlib import Path

from app.db.models import Job
from app.ingestion.audio_utils import transcribe_audio_file
from app.ingestion.base import BaseExtractor, ExtractedContent


class AudioExtractor(BaseExtractor):
    def extract(self, job: Job) -> ExtractedContent:
        path = Path(job.stored_file_path)
        transcript = transcribe_audio_file(path)
        return ExtractedContent(
            text=transcript,
            title=path.stem,
            raw_transcript=transcript,
            extra_metadata={"original_filename": job.source_reference},
        )
