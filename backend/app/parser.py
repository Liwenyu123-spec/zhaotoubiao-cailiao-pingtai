"""规则抽取测试版：不调用外部模型。低置信和无法读取的内容显式标出。"""

from __future__ import annotations

import re
from pathlib import Path

CATEGORIES = (
    ("资格", ("资格", "资质", "许可", "营业执照", "业绩", "财务", "信用", "社保", "纳税")),
    ("评分", ("评分", "得分", "分值", "评标办法", "综合评估")),
    ("签章", ("签字", "签章", "盖章", "印章", "法定代表人")),
    ("时间", ("截止", "开标", "递交时间", "投标截止", "有效期")),
    ("格式", ("格式", "装订", "密封", "正本", "副本", "电子版", "目录", "页码")),
    ("商务", ("付款", "交货", "交付", "质保", "保证金", "合同")),
    ("技术", ("技术", "参数", "规格", "性能", "实施方案")),
)

HEADING = re.compile(r"^(第[一二三四五六七八九十0-9]+[章节条]|[0-9]+(\.[0-9]+){0,3}|[（(][0-9一二三四五六七八九十]+[）)])")


def extract_text(path: Path) -> tuple[list[tuple[int, str]], str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return [(1, text)], "ok"
    if suffix == ".pdf":
        return _pdf(path)
    if suffix == ".docx":
        return _docx(path)
    return [], f"unsupported:{suffix or 'none'}"


def _pdf(path: Path) -> tuple[list[tuple[int, str]], str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], "missing-pypdf"
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    empty = 0
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            empty += 1
        pages.append((index, text))
    if not pages:
        return [], "empty-pdf"
    if empty == len(pages):
        return pages, "scan-unreadable"
    if empty:
        return pages, f"partial-empty:{empty}/{len(pages)}"
    return pages, "ok"


def _docx(path: Path) -> tuple[list[tuple[int, str]], str]:
    try:
        from docx import Document
    except ImportError:
        return [], "missing-python-docx"
    document = Document(str(path))
    lines = [p.text for p in document.paragraphs if p.text.strip()]
    if not lines:
        return [], "empty-docx"
    return [(1, "\n".join(lines))], "ok"


def extract_requirements(pages: list[tuple[int, str]], filename: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for page_no, text in pages:
        for raw in text.splitlines():
            line = raw.strip()
            if len(line) < 8 or len(line) > 400:
                continue
            category = _category(line)
            if category is None and not HEADING.match(line):
                continue
            if category is None:
                category = "其他"
            key = line[:80]
            if key in seen:
                continue
            seen.add(key)
            confidence = "high" if category != "其他" else "low"
            found.append(
                {
                    "category": category,
                    "content": line,
                    "source_file": filename,
                    "source_location": f"第 {page_no} 页",
                    "confidence": confidence,
                }
            )
            if len(found) >= 80:
                return found
    return found


def _category(line: str) -> str | None:
    for name, words in CATEGORIES:
        if any(word in line for word in words):
            return name
    return None
