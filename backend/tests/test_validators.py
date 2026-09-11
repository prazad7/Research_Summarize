from types import SimpleNamespace

import pytest

from app.config import settings
from app.ingestion.exceptions import FileTooLargeError
from app.utils.validators import validate_upload_size


def test_validate_upload_size_passes_under_limit():
    upload = SimpleNamespace(size=1024)
    validate_upload_size(upload)  # should not raise


def test_validate_upload_size_rejects_over_limit():
    upload = SimpleNamespace(size=settings.max_file_size_bytes + 1)
    with pytest.raises(FileTooLargeError):
        validate_upload_size(upload)


def test_validate_upload_size_allows_unknown_size():
    upload = SimpleNamespace(size=None)
    validate_upload_size(upload)  # no Content-Length header -- can't pre-check, shouldn't raise
