from unittest.mock import MagicMock

import pytest

from app.db.models import ContentType, Job, JobStatus
from app.ingestion.exceptions import NoExtractableTextError


def _make_job(path: str = "fake.pdf") -> Job:
    return Job(
        id="test-job",
        status=JobStatus.PENDING,
        content_type=ContentType.PDF,
        source_type="file",
        source_reference="fake.pdf",
        stored_file_path=path,
    )


def test_pdf_extractor_reads_text_pages(mocker):
    from app.ingestion import pdf_extractor

    fake_page = MagicMock()
    fake_page.extract_text.return_value = "Hello from page one."
    fake_reader = MagicMock(is_encrypted=False, pages=[fake_page])
    fake_reader.metadata.title = "My PDF"
    mocker.patch.object(pdf_extractor, "PdfReader", return_value=fake_reader)

    result = pdf_extractor.PdfExtractor().extract(_make_job())

    assert "Hello from page one." in result.text
    assert result.title == "My PDF"
    assert result.extra_metadata["page_count"] == 1


def test_pdf_extractor_raises_when_no_text_and_ocr_disabled(mocker, monkeypatch):
    from app.ingestion import pdf_extractor

    monkeypatch.setattr(pdf_extractor.settings, "ENABLE_OCR_FALLBACK", False)

    fake_page = MagicMock()
    fake_page.extract_text.return_value = ""
    fake_reader = MagicMock(is_encrypted=False, pages=[fake_page])
    fake_reader.metadata.title = None
    mocker.patch.object(pdf_extractor, "PdfReader", return_value=fake_reader)

    with pytest.raises(NoExtractableTextError):
        pdf_extractor.PdfExtractor().extract(_make_job())
