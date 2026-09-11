from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.db.models import Job
from app.ingestion.base import BaseExtractor, ExtractedContent
from app.ingestion.exceptions import CorruptFileError, NoExtractableTextError

_MAX_ROWS_PER_SHEET = 500  # keeps huge spreadsheets from blowing the LLM context


class ExcelExtractor(BaseExtractor):
    def extract(self, job: Job) -> ExtractedContent:
        path = Path(job.stored_file_path)
        try:
            workbook = load_workbook(str(path), read_only=True, data_only=True)
        except (InvalidFileException, KeyError, OSError) as exc:
            raise CorruptFileError(original=exc) from exc

        sections: list[str] = []
        for sheet in workbook.worksheets:
            lines = [f"## Sheet: {sheet.title}"]
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                if i >= _MAX_ROWS_PER_SHEET:
                    lines.append(f"... ({sheet.max_row - _MAX_ROWS_PER_SHEET} more rows truncated)")
                    break
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append(" | ".join(cells))
            if len(lines) > 1:
                sections.append("\n".join(lines))

        text = "\n\n".join(sections)
        if not text.strip():
            raise NoExtractableTextError()

        return ExtractedContent(
            text=text.strip(),
            title=path.stem,
            extra_metadata={"sheet_count": len(workbook.worksheets)},
        )
