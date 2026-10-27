"""Crossref API 数据源：按期刊 ISSN 抓取最新期刊论文。"""
from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import date

import requests

from ..models import Paper
from .http import get_with_retry

API = "https://api.crossref.org"
S2_API = "https://api.semanticscholar.org/graph/v1/paper"
SLEEP_BETWEEN_JOURNALS = 1.0   # 对 Crossref 保持礼貌的请求间隔
SLEEP_AFTER_S2 = 1.2           # Semantic Scholar 无密钥限速（~1 req/s）


def fetch_crossref(
    journals,
    window_start: date,
    max_results: int = 200,
    mailto: str = "",
) -> list[Paper]:
    """逐个期刊抓取 window_start 之后发表的期刊论文（type=journal-article）。"""
    params = {
        "filter": f"from-pub-date:{window_start.isoformat()},type:journal-article",
        "rows": max_results,
        "sort": "published",
        "order": "desc",
        "select": "DOI,title,author,container-title,published,URL,abstract",
    }
    if mailto:
        params["mailto"] = mailto

    papers: list[Paper] = []
    enriched = 0
    for jr in journals:
        issn = (jr.issn or "").strip()
        name = (jr.name or "").strip() or issn
        if not issn:
            print(f"[crossref] 跳过没有 ISSN 的期刊：{name or jr}")
            continue

        items = _fetch_journal_items(name, issn, params)
        for item in items:
            paper = _parse_item(name, item, window_start)
            if paper is None:
                continue
            if not paper.abstract and paper.doi:
                filled = _s2_abstract(paper.doi)
                if filled:
                    paper.abstract = filled
                    enriched += 1
                time.sleep(SLEEP_AFTER_S2)
            papers.append(paper)

        print(f"[crossref] {name}：{len(items)} 条")
        time.sleep(SLEEP_BETWEEN_JOURNALS)

    if enriched:
        print(f"[crossref] 通过 Semantic Scholar 补全摘要 {enriched} 篇")
    return papers


def _fetch_journal_items(name: str, issn: str, params: dict) -> list[dict]:
    try:
        resp = get_with_retry(f"{API}/journals/{issn}/works", params, label="crossref")
        return (resp.json().get("message") or {}).get("items") or []
    except (requests.RequestException, ValueError) as exc:
        print(f"[crossref] 期刊 {name}（{issn}）请求失败：{exc}")
        return []


def _parse_item(source: str, item: dict, window_start: date) -> Paper | None:
    """把 Crossref works 条目解析为 Paper；标题/链接缺失或超窗时返回 None。"""
    title = (item.get("title") or [""])[0].strip()
    doi = item.get("DOI") or ""
    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
    if not title or (not doi and not url):
        return None

    published = _parse_date(item)
    if published is not None and published < window_start:
        return None

    authors = [
        " ".join(x for x in (au.get("given"), au.get("family")) if x)
        for au in (item.get("author") or [])
        if au.get("given") or au.get("family")
    ]
    return Paper(
        source=source,
        title=title,
        authors=authors,
        abstract=_clean_abstract(item.get("abstract") or ""),
        url=url,
        doi=doi,
        published=published,
        identifier=doi or url,
    )


def _parse_date(item: dict) -> date | None:
    dp = (item.get("published") or {}).get("date-parts") or []
    if not (dp and dp[0]):
        return None
    y, m, d = (list(dp[0]) + [None, None, None])[:3]
    try:
        return date(int(y), int(m or 1), int(d or 1))
    except (TypeError, ValueError):
        return None


def _clean_abstract(text: str) -> str:
    """清洗摘要：剥掉 JATS 标签（<jats:p> 等）、还原实体、压缩空白、去掉开头的 Abstract.。"""
    if not text:
        return ""
    s = text.strip()
    if s.startswith("<"):
        try:
            root = ET.fromstring(s)
            s = " ".join(t.strip() for t in root.itertext() if t.strip())
        except ET.ParseError:
            s = re.sub(r"<[^>]*>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"^abstract[.:\s]+", "", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _s2_abstract(doi: str) -> str:
    """Crossref 缺失摘要时用 Semantic Scholar 按 DOI 补全；失败静默返回空串。"""
    try:
        resp = requests.get(
            f"{S2_API}/DOI:{doi}", params={"fields": "abstract"}, timeout=20
        )
        if resp.status_code == 200:
            return _clean_abstract(resp.json().get("abstract") or "")
    except (requests.RequestException, ValueError):
        pass
    return ""
