from app.ingestion.exceptions import CorruptFileError, NoExtractableTextError
from app.tasks.errors import GENERIC_ERROR_MESSAGE, friendly_message


def test_friendly_message_uses_ingestion_error_user_message():
    exc = NoExtractableTextError()
    assert friendly_message(exc) == exc.user_message
    assert "OCR" in exc.user_message


def test_friendly_message_uses_custom_override():
    exc = CorruptFileError("Custom explanation shown to the user.")
    assert friendly_message(exc) == "Custom explanation shown to the user."


def test_friendly_message_falls_back_for_unknown_exceptions():
    assert friendly_message(RuntimeError("some internal detail")) == GENERIC_ERROR_MESSAGE
