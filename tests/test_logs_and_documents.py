from backend.app.documents import chunk_document
from backend.app.logs import (
    extract_log_excerpts,
    normalize_log_message,
    signature_for_log,
)


def test_log_extraction_redacts_secrets():
    excerpts = extract_log_excerpts(
        "```\nTraceback: AUTH_ERROR\ntoken=secret-value\n```"
    )
    assert excerpts and "secret-value" not in excerpts[0]
    assert "[REDACTED]" in excerpts[0]


def test_log_signature_normalizes_numbers():
    assert normalize_log_message("HTTP 401 for user 42") == "http <n> for user <n>"
    assert signature_for_log("HTTP 401 for user 42") == signature_for_log(
        "HTTP 500 for user 17"
    )


def test_document_chunking_preserves_content():
    chunks = chunk_document(
        "# Heading\n\nParagraph one.\n\n```\nAUTH_ERROR\n```", max_chars=30, overlap=0
    )
    assert any("AUTH_ERROR" in chunk for chunk in chunks)
