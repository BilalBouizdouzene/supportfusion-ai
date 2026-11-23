from backend.app.github import (
    GitHubClient,
    _incident_payload,
    content_hash,
    extract_error_codes,
    sanitize_text,
)


def test_error_codes_are_normalized_and_deduplicated():
    assert extract_error_codes("HTTP 401 then AUTH_ERROR and HTTP 401") == [
        "401",
        "AUTH_ERROR",
    ]


def test_secrets_are_redacted():
    assert "super-secret" not in sanitize_text("token=super-secret")
    assert "[REDACTED]" in sanitize_text("token=super-secret")


def test_content_hash_is_stable():
    assert content_hash({"b": 2, "a": 1}) == content_hash({"a": 1, "b": 2})


def test_incremental_cursor_is_sent_to_github(monkeypatch):
    client = GitHubClient()
    seen = []
    monkeypatch.setattr(client, "get", lambda url: seen.append(url) or [])
    client.fetch_issues("acme/product", 10, since="2026-11-03T10:00:00Z")
    assert "since=2026-11-03T10%3A00%3A00Z" in seen[0]


def test_issue_structuring_extracts_component_version_and_pr():
    payload = _incident_payload(
        {
            "id": 1,
            "title": "API fails on v1.2.3",
            "body": "component: auth\nSee https://github.com/acme/product/pull/42",
            "labels": [{"name": "component: identity"}],
            "html_url": "https://github.com/acme/product/issues/1",
            "state": "open",
            "created_at": None,
            "updated_at": None,
            "user": {"login": "user"},
        },
        "acme/product",
    )
    assert payload["affected_component"] == "identity"
    assert payload["affected_version"] == "v1.2.3"
    assert payload["pull_requests"] == ["https://github.com/acme/product/pull/42"]
