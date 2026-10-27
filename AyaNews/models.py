"""文献数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Paper:
    """一篇文献的元数据。"""

    source: str                       # 来源："arXiv" 或期刊名
    title: str
    authors: list[str]
    abstract: str
    url: str
    doi: str                          # 无 DOI 时为空字符串
    published: date | None
    identifier: str                   # 去重标识：arXiv ID 或 DOI
    categories: list[str] = field(default_factory=list)
    matched_groups: list[list[str]] = field(default_factory=list)

    @property
    def authors_str(self) -> str:
        return ", ".join(self.authors)

    @property
    def matched_str(self) -> str:
        return "; ".join(" + ".join(g) for g in self.matched_groups)
