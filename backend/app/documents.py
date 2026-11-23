from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup


@dataclass
class ParsedDocument:
    title: str
    content: str
    metadata: dict[str, str]


def parse_document(path: str | Path) -> ParsedDocument:
    file_path = Path(path).expanduser().resolve()
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".log"}:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    elif suffix in {".html", ".htm"}:
        soup = BeautifulSoup(
            file_path.read_text(encoding="utf-8", errors="replace"), "html.parser"
        )
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        content = soup.get_text("\n", strip=True)
    elif suffix == ".json":
        content = json.dumps(
            json.loads(file_path.read_text(encoding="utf-8")),
            ensure_ascii=False,
            indent=2,
        )
    elif suffix == ".csv":
        with file_path.open(newline="", encoding="utf-8", errors="replace") as handle:
            content = "\n".join(" | ".join(row) for row in csv.reader(handle))
    elif suffix == ".pdf":
        try:
            import fitz  # type: ignore
        except ImportError as error:
            raise RuntimeError(
                "PDF parsing requires the optional PyMuPDF dependency"
            ) from error
        document = fitz.open(file_path)
        content = "\n\n".join(page.get_text("text") for page in document)
    elif suffix == ".docx":
        try:
            from docx import Document  # type: ignore
        except ImportError as error:
            raise RuntimeError(
                "DOCX parsing requires the optional python-docx dependency"
            ) from error
        document = Document(file_path)
        content = "\n".join(paragraph.text for paragraph in document.paragraphs)
    else:
        raise ValueError(f"Unsupported document type: {suffix or 'none'}")
    return ParsedDocument(
        title=file_path.stem.replace("_", " ").replace("-", " "),
        content=content.strip(),
        metadata={"path": str(file_path), "suffix": suffix},
    )


def chunk_document(
    content: str, max_chars: int = 1200, overlap: int = 120
) -> list[str]:
    """Chunk on paragraph boundaries and keep fenced code blocks intact when possible."""
    paragraphs = [
        part.strip()
        for part in content.replace("\r\n", "\n").split("\n\n")
        if part.strip()
    ]
    chunks: list[str] = []
    current = ""
    in_fence = False
    for paragraph in paragraphs:
        in_fence = in_fence ^ paragraph.count("```") % 2 == 1
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current and len(candidate) > max_chars and not in_fence:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
