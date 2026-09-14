from __future__ import annotations

import re

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

from app.config import settings
from app.db.models import Job
from app.ingestion.base import BaseExtractor, ExtractedContent
from app.ingestion.exceptions import NoTranscriptAvailableError, UnreachableSourceError
from app.logging_config import get_logger

logger = get_logger(__name__)

_ID_PATTERNS = [
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/embed/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
]


def _extract_video_id(url: str) -> str | None:
    for pattern in _ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


class YoutubeExtractor(BaseExtractor):
    """Primary path: fetch existing captions/transcript (fast, free, reliable).

    Fallback (if enabled): download audio with yt-dlp and transcribe with
    Whisper, for videos that have no captions at all.
    """

    def extract(self, job: Job) -> ExtractedContent:
        url = job.source_reference
        video_id = _extract_video_id(url)
        if not video_id:
            raise UnreachableSourceError("That doesn't look like a valid YouTube link.")

        try:
            transcript_text, title = self._fetch_transcript(video_id)
            return ExtractedContent(
                text=transcript_text,
                title=title,
                extra_metadata={"url": url, "video_id": video_id, "transcript_source": "captions"},
            )
        except (TranscriptsDisabled, NoTranscriptFound):
            logger.info("youtube_no_captions", video_id=video_id)
            if settings.ENABLE_YOUTUBE_AUDIO_FALLBACK:
                return self._fallback_audio_transcription(job, url, video_id)
            raise NoTranscriptAvailableError() from None
        except VideoUnavailable as exc:
            raise UnreachableSourceError(
                "That YouTube video is unavailable (private, deleted, or region-locked).",
                original=exc,
            ) from exc

    def _fetch_transcript(self, video_id: str) -> tuple[str, str]:
        # youtube-transcript-api 1.x rewrote this as an instance API (the
        # old YouTubeTranscriptApi.list_transcripts(video_id) classmethod
        # is gone -- requirements.txt pins ">=0.6.2" with no upper bound,
        # so a fresh install pulls this breaking rewrite straight in).
        transcript_list = YouTubeTranscriptApi().list(video_id)
        try:
            transcript = transcript_list.find_transcript(["en"])
        except NoTranscriptFound:
            transcript = next(iter(transcript_list))  # first available language
            if transcript.is_translatable:
                transcript = transcript.translate("en")

        entries = transcript.fetch()
        # Same 1.x rewrite: each entry is now a FetchedTranscriptSnippet
        # (attribute access), not the old dict (which supported ["text"]).
        text = " ".join(entry.text.strip() for entry in entries if entry.text.strip())
        return text, f"YouTube video {video_id}"

    def _fallback_audio_transcription(self, job: Job, url: str, video_id: str) -> ExtractedContent:
        from app.ingestion.audio_utils import transcribe_audio_file

        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover
            raise NoTranscriptAvailableError() from exc

        download_path = settings.upload_dir_path / f"{job.id}_youtube_audio.mp3"
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(download_path.with_suffix("")),
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}
            ],
            "quiet": True,
            "noplaylist": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", f"YouTube video {video_id}")
        except Exception as exc:
            logger.warning("youtube_audio_fallback_failed", video_id=video_id, error=str(exc))
            raise NoTranscriptAvailableError() from exc

        transcript_text = transcribe_audio_file(download_path)
        return ExtractedContent(
            text=transcript_text,
            title=title,
            raw_transcript=transcript_text,
            extra_metadata={"url": url, "video_id": video_id, "transcript_source": "whisper_fallback"},
        )
