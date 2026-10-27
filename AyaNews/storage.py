"""去重状态存储：记录已推送过的文献标识。"""
from __future__ import annotations

import json
from pathlib import Path

MAX_KEEP = 5000  # 每种标识最多保留条数，防止状态文件无限膨胀


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {
                "arxiv_ids": list(data.get("arxiv_ids", [])),
                "dois": list(data.get("dois", [])),
            }
        except (ValueError, OSError):
            pass
    return {"arxiv_ids": [], "dois": []}


def filter_new(papers: list, state: dict) -> tuple[list, dict]:
    """过滤掉已见过的文献，并返回更新后的状态（由调用方决定何时保存）。"""
    arxiv_ids = set(state["arxiv_ids"])
    dois = set(state["dois"])
    new_papers = []
    for p in papers:
        if p.identifier in arxiv_ids or p.identifier in dois:
            continue
        new_papers.append(p)
        if p.source == "arXiv":
            arxiv_ids.add(p.identifier)
        else:
            dois.add(p.identifier)
    state["arxiv_ids"] = list(arxiv_ids)[-MAX_KEEP:]
    state["dois"] = list(dois)[-MAX_KEEP:]
    return new_papers, state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
