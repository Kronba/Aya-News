"""arXiv API 数据源：按学科分类 + 标题关键词检索最新论文。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

import requests

from ..models import Paper
from .http import get_with_retry

API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(
    keywords: list[list[str]],
    categories: list[str],
    window_start: date,
    max_results: int = 100,
) -> list[Paper]:
    """抓取 window_start 之后、标题匹配关键词的 arXiv 论文。"""
    params = {
        "search_query": _build_query(keywords, categories),
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    try:
        resp = get_with_retry(API, params, label="arxiv")
    except requests.RequestException as exc:
        print(f"[arxiv] 请求失败：{exc}")
        return []

    root = ET.fromstring(resp.text)
    papers = [
        p for p in (_parse_entry(e, window_start) for e in root.findall(f"{ATOM}entry"))
        if p is not None
    ]
    print(f"[arxiv] 获取 {len(papers)} 条（窗口内）")
    return papers


def _build_query(keywords: list[list[str]], categories: list[str]) -> str:
    """构造 search_query：分类之间 OR，关键词组内 AND、组间 OR。"""
    parts: list[str] = []
    kw_parts = []
    for group in keywords:
        terms = [k.strip().replace('"', "") for k in group if k.strip()]
        if terms:
            kw_parts.append("(" + " AND ".join(f'ti:"{t}"' for t in terms) + ")")
    if kw_parts:
        parts.append("(" + " OR ".join(kw_parts) + ")")
    if categories:
        parts.append("(" + " OR ".join(f"cat:{c}" for c in categories) + ")")
    return " AND ".join(parts) if parts else "all:*"


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_entry(entry: ET.Element, window_start: date) -> Paper | None:
    """解析单条 Atom entry；不在时间窗口内的返回 None。"""
    aid = _clean(entry.findtext(f"{ATOM}id"))
    arxiv_id = re.sub(r"v\d+$", "", aid.rsplit("/abs/", 1)[-1])

    published = None
    try:
        published = date.fromisoformat(_clean(entry.findtext(f"{ATOM}published"))[:10])
    except ValueError:
        pass
    if published and published < window_start:
        return None

    authors = [_clean(a.findtext(f"{ATOM}name")) for a in entry.findall(f"{ATOM}author")]
    return Paper(
        source="arXiv",
        title=_clean(entry.findtext(f"{ATOM}title")),
        authors=[a for a in authors if a],
        abstract=_clean(entry.findtext(f"{ATOM}summary")),
        url=f"https://arxiv.org/abs/{arxiv_id}",
        doi="",
        published=published,
        identifier=arxiv_id,
        categories=[c.get("term", "") for c in entry.findall(f"{ATOM}category")],
    )
