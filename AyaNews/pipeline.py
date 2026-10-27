"""核心流水线：抓取 → 关键词过滤 → 跨来源去重 → 历史去重。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .config import AppConfig
from .filters import match_groups
from .models import Paper
from .providers import fetch_arxiv, fetch_crossref
from .storage import filter_new, load_state


@dataclass
class CollectResult:
    """一次采集的结果。state 仅在 new_only 时非 None（由调用方决定是否保存）。"""

    papers: list[Paper]
    state: dict | None
    today: date
    fetched: int   # 数据源返回的原始条数（过滤前）
    matched: int   # 命中标题关键词的条数（去重前）


def collect(cfg: AppConfig, *, new_only: bool = False) -> CollectResult:
    """按配置执行采集与过滤，打印各阶段数量统计。"""
    today = date.today()
    papers: list[Paper] = []
    if cfg.arxiv.enabled:
        start = today - timedelta(days=cfg.arxiv.days)
        papers += fetch_arxiv(cfg.keywords, cfg.arxiv.categories, start, cfg.arxiv.max_results)
    if cfg.crossref.enabled:
        start = today - timedelta(days=cfg.crossref.days)
        papers += fetch_crossref(
            cfg.crossref.journals, start, cfg.crossref.max_results, cfg.crossref.mailto
        )

    fetched = len(papers)
    matched_papers = _filter_by_keywords(papers, cfg.keywords)
    print(f"共抓取 {fetched} 条 → 标题命中关键词 {len(matched_papers)} 条")

    papers = _dedupe_cross_source(matched_papers)
    if len(matched_papers) > len(papers):
        print(f"跨来源去重后剩余 {len(papers)} 条")

    state = None
    if new_only:
        state = load_state(Path(cfg.state_file))
        before = len(papers)
        papers, state = filter_new(papers, state)
        print(f"过滤已推送文献后剩余 {len(papers)} 条新文献（已推送过 {before - len(papers)} 条）")

    return CollectResult(
        papers=papers, state=state, today=today,
        fetched=fetched, matched=len(matched_papers),
    )


def _filter_by_keywords(papers: list[Paper], keywords: list[list[str]]) -> list[Paper]:
    """标题关键词过滤（AND/OR 分组），并在每篇上记录命中组。"""
    matched_papers: list[Paper] = []
    for p in papers:
        groups = match_groups(p.title, keywords)
        if groups:
            p.matched_groups = groups
            matched_papers.append(p)
    return matched_papers


def _dedupe_cross_source(papers: list[Paper]) -> list[Paper]:
    """跨来源去重（优先 DOI，其次来源标识），返回按日期倒序的列表。"""
    unique: dict[str, Paper] = {}
    for p in papers:
        unique.setdefault(p.doi or p.identifier, p)
    return sorted(unique.values(), key=lambda p: p.published or date.min, reverse=True)
