from backend.app.search import tokenize


def test_tokenize_keeps_technical_tokens():
    tokens = tokenize("AUTH_ERROR in api/v1 after 401")
    assert "auth_error" in tokens
    assert "api/v1" in tokens
    assert "401" in tokens
