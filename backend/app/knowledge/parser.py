from dataclasses import dataclass
from pathlib import Path
from docx import Document
from pypdf import PdfReader


@dataclass
class Segment:
    text: str
    location: str


def parse(path: Path) -> list[Segment]:
    suffix = path.suffix.lower()
    blocks: list[tuple[str, str]] = []
    if suffix == ".pdf":
        blocks = [(page.extract_text() or "", f"第 {i + 1} 页") for i, page in enumerate(PdfReader(path).pages)]
    elif suffix == ".docx":
        doc = Document(path)
        blocks = [(p.text, f"第 {i + 1} 段") for i, p in enumerate(doc.paragraphs)]
        blocks += [("\n".join(" | ".join(c.text for c in row.cells) for row in table.rows), f"表格 {i + 1}") for i, table in enumerate(doc.tables)]
    elif suffix in {".md", ".txt"}:
        blocks = [(text, f"第 {i + 1} 段") for i, text in enumerate(path.read_text(encoding="utf-8-sig").split("\n\n"))]
    else:
        raise ValueError("仅支持 MD、TXT、PDF、DOCX")
    segments = [Segment(text[offset:offset + 700], f"{location} · 字符 {offset + 1}")
                for text, location in blocks if text.strip() for offset in range(0, len(text), 600)]
    if not segments:
        raise ValueError("未提取到文本；扫描 PDF 请先 OCR")
    if len(segments) > 5000:
        raise ValueError("文档片段超过 5000，请拆分后上传")
    return segments
