"""标题关键词匹配（AND/OR 分组）。"""
from __future__ import annotations

import re

_WORD_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """小写化，并把所有非字母数字字符替换为空格、压缩连续空白。

    例如 "Finite-Element\nMethod" -> "finite element method"。
    """
    return _WORD_RE.sub(" ", text.lower()).strip()


def match_groups(title: str, groups: list[list[str]]) -> list[list[str]]:
    """返回命中的关键词组。

    组内为 AND（标题需同时包含组内每个关键词），组间为 OR（命中任一组即收录）。
    匹配基于归一化后的子串，因此 "finite element" 可以命中 "Finite-Element"。
    """
    norm = " " + normalize(title) + " "
    matched: list[list[str]] = []
    for group in groups:
        kws = [normalize(k) for k in group if k and k.strip()]
        if kws and all(" " + kw + " " in norm for kw in kws):
            matched.append(group)
    return matched
