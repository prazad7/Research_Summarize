from __future__ import annotations

import requests
import trafilatura

from app.config import settings
from app.db.models import Job
from app.ingestion.base import BaseExtractor, ExtractedContent
from app.ingestion.exceptions import IngestionError, UnreachableSourceError
from app.logging_config import get_logger

logger = get_logger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchSummarizeBot/1.0)"}
_TIMEOUT_SECONDS = 20


class UrlExtractor(BaseExtractor):
    """Fetches a webpage and extracts its main readable content."""

    def extract(self, job: Job) -> ExtractedContent:
        url = job.source_reference
        try:
            response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.warning("url_fetch_failed", url=url, error=str(exc))
            raise UnreachableSourceError(original=exc) from exc

        downloaded = response.text
        extracted_text = trafilatura.extract(
            downloaded, include_comments=False, include_tables=True, favor_recall=True
        )

        if not extracted_text or not extracted_text.strip():
            raise IngestionError(
                "We reached that page but couldn't find any readable article content on it "
                "(it may be mostly images, a login wall, or a web app)."
            )

        metadata = trafilatura.extract_metadata(downloaded)
        title = metadata.title if metadata and metadata.title else url

        return ExtractedContent(
            text=extracted_text.strip(),
            title=title,
            extra_metadata={"url": url},
        )
