"""导出 Markdown 报告与 CSV 表格。"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from .models import Paper


def export(
    papers: list[Paper],
    out_dir: Path,
    prefix: str,
    include_abstract: bool,
    today: date,
) -> tuple[Path, Path]:
    """导出结果，返回 (markdown 路径, csv 路径)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = today.isoformat()
    md_path = out_dir / f"{prefix}_{stamp}.md"
    csv_path = out_dir / f"{prefix}_{stamp}.csv"

    by_source: dict[str, list[Paper]] = defaultdict(list)
    for p in papers:
        by_source[p.source].append(p)
    for lst in by_source.values():
        lst.sort(key=lambda p: p.published or date.min, reverse=True)

    _write_csv(csv_path, papers, include_abstract)
    _write_markdown(md_path, by_source, stamp, include_abstract)
    return md_path, csv_path


def _write_csv(path: Path, papers: list[Paper], include_abstract: bool) -> None:
    header = [
        "source", "published", "title", "authors",
        "journal_or_category", "matched_keywords", "doi", "url",
    ]
    if include_abstract:
        header.append("abstract")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for p in papers:
            row = [
                p.source,
                p.published.isoformat() if p.published else "",
                p.title,
                p.authors_str,
                ", ".join(p.categories) if p.categories else "",
                p.matched_str,
                p.doi,
                p.url,
            ]
            if include_abstract:
                row.append(p.abstract)
            writer.writerow(row)


def _write_markdown(
    path: Path, by_source: dict[str, list[Paper]], stamp: str, include_abstract: bool
) -> None:
    total = sum(len(v) for v in by_source.values())
    lines = [f"# 文献推送 {stamp}", "", f"共 **{total}** 篇。", ""]
    for source, papers in sorted(by_source.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {source}（{len(papers)} 篇）")
        lines.append("")
        by_date: dict[str, list[Paper]] = defaultdict(list)
        for p in papers:
            key = p.published.isoformat() if p.published else "日期未知"
            by_date[key].append(p)
        for d, lst in sorted(by_date.items(), reverse=True):
            lines.append(f"### {d}")
            lines.append("")
            for p in lst:
                hit = f" · 命中：{p.matched_str}" if p.matched_str else ""
                lines.append(f"- **{p.title}** — {p.authors_str or '（无作者信息）'}。 [链接]({p.url}){hit}")
                if include_abstract and p.abstract:
                    lines.append(f"  - 摘要：{p.abstract[:400]}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
