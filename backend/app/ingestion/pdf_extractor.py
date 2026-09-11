from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings
from app.db.models import Job
from app.ingestion.base import BaseExtractor, ExtractedContent
from app.ingestion.exceptions import CorruptFileError, NoExtractableTextError
from app.logging_config import get_logger

logger = get_logger(__name__)


class PdfExtractor(BaseExtractor):
    def extract(self, job: Job) -> ExtractedContent:
        path = Path(job.stored_file_path)

        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    raise CorruptFileError(
                        "That PDF is password-protected, so we couldn't open it."
                    )
            pages_text = [page.extract_text() or "" for page in reader.pages]
        except PdfReadError as exc:
            raise CorruptFileError(original=exc) from exc

        text = "\n\n".join(p.strip() for p in pages_text if p.strip())

        if not text.strip():
            if settings.ENABLE_OCR_FALLBACK:
                text = self._try_ocr(path)
            if not text or not text.strip():
                raise NoExtractableTextError()

        title = reader.metadata.title if reader.metadata and reader.metadata.title else path.stem
        return ExtractedContent(
            text=text.strip(),
            title=title,
            extra_metadata={"page_count": len(reader.pages)},
        )

    def _try_ocr(self, path: Path) -> str:
        """Best-effort OCR fallback for image-only (scanned) PDFs."""
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError:
            logger.warning("ocr_dependencies_missing")
            return ""

        try:
            images = convert_from_path(str(path))
            ocr_text = "\n\n".join(pytesseract.image_to_string(img) for img in images)
            return ocr_text
        except Exception as exc:
            logger.warning("ocr_fallback_failed", error=str(exc))
            return ""
