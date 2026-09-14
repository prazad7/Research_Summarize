"""Regression coverage for a real reported bug: youtube-transcript-api 1.x
rewrote its API (YouTubeTranscriptApi.list_transcripts(video_id), a
classmethod, became YouTubeTranscriptApi().list(video_id), an instance
method; transcript entries went from dict-subscriptable to attribute-only
objects). The old unbounded ">=0.6.2" pin let that breaking upgrade slip
in silently and broke every YouTube job. These tests mock the library at
the shape the currently-pinned version (1.x) actually has, so a future
regression back to the old dict/classmethod shape fails loudly here
instead of only in production.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

from app.db.models import ContentType, Job, JobStatus
from app.ingestion.exceptions import NoTranscriptAvailableError, UnreachableSourceError
from app.ingestion.youtube_extractor import YoutubeExtractor, _extract_video_id


def _make_job(url: str) -> Job:
    return Job(
        id="test-job",
        status=JobStatus.PENDING,
        content_type=ContentType.YOUTUBE,
        source_type="url",
        source_reference=url,
    )


def _snippet(text: str) -> SimpleNamespace:
    """Mimics youtube_transcript_api 1.x's FetchedTranscriptSnippet: an
    object with a `.text` attribute, NOT a dict with a ["text"] key."""
    return SimpleNamespace(text=text)


@pytest.mark.parametrize(
    "url,expected_id",
    [
        ("https://www.youtube.com/watch?v=abc12345678", "abc12345678"),
        ("https://youtu.be/abc12345678", "abc12345678"),
        ("https://www.youtube.com/embed/abc12345678", "abc12345678"),
        ("https://www.youtube.com/shorts/abc12345678", "abc12345678"),
        ("https://example.com/not-youtube", None),
    ],
)
def test_extract_video_id(url, expected_id):
    assert _extract_video_id(url) == expected_id


def test_youtube_extractor_reads_transcript_via_instance_api(mocker):
    from app.ingestion import youtube_extractor

    fake_transcript = mocker.MagicMock()
    fake_transcript.fetch.return_value = [_snippet("Hello "), _snippet(""), _snippet("world.")]

    fake_transcript_list = mocker.MagicMock()
    fake_transcript_list.find_transcript.return_value = fake_transcript

    fake_api_instance = mocker.MagicMock()
    fake_api_instance.list.return_value = fake_transcript_list
    mocker.patch.object(youtube_extractor, "YouTubeTranscriptApi", return_value=fake_api_instance)

    job = _make_job("https://www.youtube.com/watch?v=abc12345678")
    extracted = YoutubeExtractor().extract(job)

    # list() (instance method), not list_transcripts() (the removed classmethod).
    fake_api_instance.list.assert_called_once_with("abc12345678")
    # Entries read via .text (attribute), not ["text"] (dict-style) -- and
    # a blank entry is skipped rather than producing a stray double space.
    assert extracted.text == "Hello world."
    assert extracted.extra_metadata["transcript_source"] == "captions"


def test_youtube_extractor_falls_back_to_translated_transcript(mocker):
    from app.ingestion import youtube_extractor

    translated = mocker.MagicMock()
    translated.fetch.return_value = [_snippet("Bonjour translated.")]

    original_language = mocker.MagicMock(is_translatable=True)
    original_language.translate.return_value = translated

    fake_transcript_list = mocker.MagicMock()
    fake_transcript_list.find_transcript.side_effect = NoTranscriptFound(
        "abc12345678", ["en"], {}
    )
    fake_transcript_list.__iter__.return_value = iter([original_language])

    fake_api_instance = mocker.MagicMock()
    fake_api_instance.list.return_value = fake_transcript_list
    mocker.patch.object(youtube_extractor, "YouTubeTranscriptApi", return_value=fake_api_instance)

    job = _make_job("https://www.youtube.com/watch?v=abc12345678")
    extracted = YoutubeExtractor().extract(job)

    original_language.translate.assert_called_once_with("en")
    assert extracted.text == "Bonjour translated."


def test_youtube_extractor_raises_on_invalid_url():
    job = _make_job("https://example.com/not-a-video")
    with pytest.raises(UnreachableSourceError):
        YoutubeExtractor().extract(job)


def test_youtube_extractor_raises_friendly_error_on_unavailable_video(mocker):
    from app.ingestion import youtube_extractor

    fake_api_instance = mocker.MagicMock()
    fake_api_instance.list.side_effect = VideoUnavailable("abc12345678")
    mocker.patch.object(youtube_extractor, "YouTubeTranscriptApi", return_value=fake_api_instance)

    job = _make_job("https://www.youtube.com/watch?v=abc12345678")
    with pytest.raises(UnreachableSourceError):
        YoutubeExtractor().extract(job)


def test_youtube_extractor_raises_when_no_captions_and_fallback_disabled(mocker, monkeypatch):
    from app.ingestion import youtube_extractor

    monkeypatch.setattr(youtube_extractor.settings, "ENABLE_YOUTUBE_AUDIO_FALLBACK", False)

    fake_api_instance = mocker.MagicMock()
    fake_api_instance.list.side_effect = TranscriptsDisabled("abc12345678")
    mocker.patch.object(youtube_extractor, "YouTubeTranscriptApi", return_value=fake_api_instance)

    job = _make_job("https://www.youtube.com/watch?v=abc12345678")
    with pytest.raises(NoTranscriptAvailableError):
        YoutubeExtractor().extract(job)
