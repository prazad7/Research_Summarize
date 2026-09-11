"""Extractor interface + registry.

Every input type implements `BaseExtractor.extract()` and returns a single
normalized `ExtractedContent`. The CrewAI pipeline downstream never knows
or cares which extractor produced it -- this is the seam that makes adding
a new input type additive rather than invasive.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.db.models import ContentType, Job


class ExtractedContent(BaseModel):
    text: str
    title: str | None = None
    extra_metadata: dict = Field(default_factory=dict)
    raw_transcript: str | None = None  # populated only for audio/video


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, job: Job) -> ExtractedContent:
        """Turn a Job's source (URL or stored file) into normalized text."""
        raise NotImplementedError


def get_extractor(content_type: ContentType) -> BaseExtractor:
    # Local imports avoid pulling every extractor's (sometimes heavy)
    # dependencies until they're actually needed.
    from app.ingestion.audio_extractor import AudioExtractor
    from app.ingestion.docx_extractor import DocxExtractor
    from app.ingestion.excel_extractor import ExcelExtractor
    from app.ingestion.pdf_extractor import PdfExtractor
    from app.ingestion.pptx_extractor import PptxExtractor
    from app.ingestion.url_extractor import UrlExtractor
    from app.ingestion.video_extractor import VideoExtractor
    from app.ingestion.youtube_extractor import YoutubeExtractor

    registry: dict[ContentType, type[BaseExtractor]] = {
        ContentType.WEBSITE: UrlExtractor,
        ContentType.YOUTUBE: YoutubeExtractor,
        ContentType.PDF: PdfExtractor,
        ContentType.DOCX: DocxExtractor,
        ContentType.XLSX: ExcelExtractor,
        ContentType.PPTX: PptxExtractor,
        ContentType.AUDIO: AudioExtractor,
        ContentType.VIDEO: VideoExtractor,
    }
    extractor_cls = registry[content_type]
    return extractor_cls()
