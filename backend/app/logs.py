from __future__ import annotations

import hashlib
import re


FENCE_RE = re.compile(r"```(?:[\w+-]+)?\s*\n(?P<body>.*?)```", re.S)
ERROR_LINE_RE = re.compile(
    r"(?im)^.*(?:exception|error|traceback|failed|fatal|panic|status\s*[:=]\s*[45]\d\d).*$"
)
DIAGNOSTIC_RE = re.compile(
    r"(?i)(exception|error|traceback|failed|fatal|panic|status\s*[:=]\s*[45]\d\d|stack trace)"
)
SECRET_RE = re.compile(
    r"(?i)(bearer\s+|(?:token|password|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+"
)
PATH_RE = re.compile(r"(?i)([A-Z]:\\|/)(?:[^\s:]+[\\/])*[^\s:]+")
NUMBER_RE = re.compile(r"\b\d+\b")


def redact_log(text: str) -> str:
    redacted = SECRET_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", text or "")
    return PATH_RE.sub("<PATH>", redacted)


def extract_log_excerpts(text: str | None, max_items: int = 8) -> list[str]:
    """Extract likely diagnostic blocks without executing or interpreting them."""
    value = text or ""
    candidates = [match.group("body").strip() for match in FENCE_RE.finditer(value)]
    if not candidates:
        candidates = [match.group(0).strip() for match in ERROR_LINE_RE.finditer(value)]
    cleaned: list[str] = []
    for candidate in candidates:
        if "![" in candidate or not DIAGNOSTIC_RE.search(candidate):
            continue
        safe = redact_log(candidate)
        if len(safe) >= 12 and safe not in cleaned:
            cleaned.append(safe[:4000])
    return cleaned[:max_items]


def normalize_log_message(text: str) -> str:
    value = redact_log(" ".join((text or "").split()).lower())
    value = NUMBER_RE.sub("<n>", value)
    return value[:500]


def signature_for_log(text: str) -> str:
    normalized = normalize_log_message(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
