"""Extract and split the small set of document formats accepted by the RAG API."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


@dataclass(frozen=True, slots=True)
class SourceSection:
    """One extracted document section, optionally tied to a PDF page."""

    text: str
    page: int | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """One bounded piece of text sent to the embedding model."""

    text: str
    index: int
    page: int | None = None


def extract_sections(filename: str, content: bytes) -> list[SourceSection]:
    """Extract UTF text or PDF pages without retaining the uploaded binary."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("仅支持 .txt、.md 和 .pdf 文件")
    if suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(content))
            sections = []
            for index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    sections.append(SourceSection(text=text, page=index))
            return sections
        except Exception as error:
            raise ValueError("PDF 文件无法解析或已损坏") from error
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = content.decode(encoding).strip()
            return [SourceSection(text=text)] if text else []
        except UnicodeDecodeError:
            continue
    raise ValueError("文本文件必须使用 UTF-8 或 GB18030 编码")


def split_sections(
    sections: list[SourceSection],
    *,
    chunk_size: int,
    overlap: int,
) -> list[KnowledgeChunk]:
    """Split extracted text with overlap while preserving PDF page numbers."""
    if chunk_size < 100:
        raise ValueError("RAG_CHUNK_SIZE 不能小于 100")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("RAG_CHUNK_OVERLAP 必须大于等于 0 且小于 chunk size")
    chunks: list[KnowledgeChunk] = []
    step = chunk_size - overlap
    for section in sections:
        text = "\n".join(line.rstrip() for line in section.text.splitlines()).strip()
        for start in range(0, len(text), step):
            value = text[start : start + chunk_size].strip()
            if value:
                chunks.append(
                    KnowledgeChunk(text=value, index=len(chunks), page=section.page)
                )
            if start + chunk_size >= len(text):
                break
    return chunks
