import pytest

from app.db.models import ContentType
from app.ingestion.detect import detect_from_filename, detect_from_url
from app.ingestion.exceptions import UnsupportedContentError


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc123", ContentType.YOUTUBE),
        ("https://youtu.be/abc123", ContentType.YOUTUBE),
        ("https://example.com/some-article", ContentType.WEBSITE),
        ("http://example.com", ContentType.WEBSITE),
    ],
)
def test_detect_from_url(url, expected):
    assert detect_from_url(url) == expected


def test_detect_from_url_rejects_non_http():
    with pytest.raises(UnsupportedContentError):
        detect_from_url("ftp://example.com/file")


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("report.pdf", ContentType.PDF),
        ("notes.docx", ContentType.DOCX),
        ("budget.xlsx", ContentType.XLSX),
        ("deck.pptx", ContentType.PPTX),
        ("call.mp3", ContentType.AUDIO),
        ("meeting.wav", ContentType.AUDIO),
        ("clip.mp4", ContentType.VIDEO),
        ("clip.mkv", ContentType.VIDEO),
    ],
)
def test_detect_from_filename(filename, expected):
    assert detect_from_filename(filename) == expected


def test_detect_from_filename_rejects_unknown_extension():
    with pytest.raises(UnsupportedContentError):
        detect_from_filename("archive.zip")
