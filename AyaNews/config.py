"""配置文件加载与默认配置生成。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ArxivConfig:
    enabled: bool = True
    categories: list[str] = field(default_factory=lambda: ["math.NA", "math.OC"])
    days: int = 14
    max_results: int = 100


@dataclass
class Journal:
    name: str = ""
    issn: str = ""


@dataclass
class CrossrefConfig:
    enabled: bool = True
    journals: list[Journal] = field(default_factory=list)
    days: int = 30
    max_results: int = 200
    mailto: str = ""  # 建议填写邮箱，加入 Crossref 礼貌池


@dataclass
class OutputConfig:
    dir: str = "output"
    include_abstract: bool = True


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    use_ssl: bool = True
    username: str = ""
    password_env: str = "CMATH_EMAIL_PASSWORD"
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)
    subject: str = "最新文献推送"


@dataclass
class AppConfig:
    keywords: list[list[str]] = field(default_factory=list)
    arxiv: ArxivConfig = field(default_factory=ArxivConfig)
    crossref: CrossrefConfig = field(default_factory=CrossrefConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    state_file: str = "state.json"
    appearance_file: str = "background.yaml"  # 报头/字体/季节主题定制


def _get(data: dict, key: str, default):
    """从 dict 取值，data 为空时返回默认值。"""
    if isinstance(data, dict):
        return data.get(key, default)
    return default


def load_config(path: Path) -> AppConfig:
    """从 YAML 文件加载配置；缺省字段使用默认值。"""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("配置文件顶层必须是 YAML 映射（dict）")

    # 关键词：支持嵌套列表，也兼容逗号分隔的单行写法
    kw_raw = raw.get("keywords", [])
    if isinstance(kw_raw, str):
        kw_raw = [[s.strip()] for s in kw_raw.split(",") if s.strip()]
    keywords: list[list[str]] = []
    for group in kw_raw or []:
        if isinstance(group, (list, tuple)):
            ks = [str(k).strip() for k in group if str(k).strip()]
        else:
            ks = [str(group).strip()]
        if ks:
            keywords.append(ks)

    arxiv = _get(raw, "arxiv", {}) or {}
    cr = _get(raw, "crossref", {}) or {}
    out = _get(raw, "output", {}) or {}
    em = _get(raw, "email", {}) or {}

    journals = []
    for j in _get(cr, "journals", []) or []:
        if isinstance(j, dict):
            journals.append(
                Journal(name=str(j.get("name", "")), issn=str(j.get("issn", "")))
            )

    return AppConfig(
        keywords=keywords,
        arxiv=ArxivConfig(
            enabled=bool(_get(arxiv, "enabled", True)),
            categories=[str(c) for c in (_get(arxiv, "categories", []) or [])],
            days=int(_get(arxiv, "days", 14)),
            max_results=int(_get(arxiv, "max_results", 100)),
        ),
        crossref=CrossrefConfig(
            enabled=bool(_get(cr, "enabled", True)),
            journals=journals,
            days=int(_get(cr, "days", 30)),
            max_results=int(_get(cr, "max_results", 200)),
            mailto=str(_get(cr, "mailto", "")),
        ),
        output=OutputConfig(
            dir=str(_get(out, "dir", "output")),
            include_abstract=bool(_get(out, "include_abstract", True)),
        ),
        email=EmailConfig(
            enabled=bool(_get(em, "enabled", False)),
            smtp_host=str(_get(em, "smtp_host", "")),
            smtp_port=int(_get(em, "smtp_port", 465)),
            use_ssl=bool(_get(em, "use_ssl", True)),
            username=str(_get(em, "username", "")),
            password_env=str(_get(em, "password_env", "CMATH_EMAIL_PASSWORD")),
            from_addr=str(_get(em, "from_addr", "")),
            to_addrs=[str(a) for a in (_get(em, "to_addrs", []) or [])],
            subject=str(_get(em, "subject", "最新文献推送")),
        ),
        state_file=str(raw.get("state_file", "state.json")),
        appearance_file=str(raw.get("appearance_file", "background.yaml")),
    )


DEFAULT_TEMPLATE = """\
# AyaNews 配置文件
# keywords: 关键词分组。组内为 AND（标题需同时包含），组间为 OR（命中任一组即收录）。
keywords:
  - ["finite element", "adaptive"]        # 标题同时包含 finite element 与 adaptive
  - ["spectral method", "stability"]      # 或同时包含 spectral method 与 stability
  - ["machine learning", "pde"]           # 或同时包含 machine learning 与 pde

arxiv:
  enabled: true
  # arXiv 学科分类（留空表示不限）。常用：math.NA 数值分析 / math.OC 优化 / math.AP 偏微分方程
  categories: ["math.NA", "math.OC", "math.AP"]
  days: 14           # 只看最近 N 天
  max_results: 100   # 单次查询最大条数（arXiv 上限 2000）

crossref:
  enabled: true
  # 要关注的期刊：name 仅用于显示，issn 用于定位（Crossref 按 ISSN 查询期刊）
  journals:
    - name: "SIAM Journal on Numerical Analysis"
      issn: "0036-1429"
    - name: "Mathematics of Computation"
      issn: "0025-5718"
    - name: "SIAM Journal on Scientific Computing"
      issn: "1064-8275"
  days: 30
  max_results: 200
  mailto: ""           # 建议填写你的邮箱，Crossref 礼貌池凭此识别请求方

output:
  dir: "output"           # 输出目录
  include_abstract: true  # Markdown 报告中是否包含摘要

# 邮件通知（可选）。密码不写入文件，通过环境变量 CMATH_EMAIL_PASSWORD 提供。
email:
  enabled: false
  smtp_host: "smtp.example.com"
  smtp_port: 465
  use_ssl: true           # true = SSL/SMTPS；false = STARTTLS
  username: "you@example.com"
  password_env: "CMATH_EMAIL_PASSWORD"
  from_addr: "you@example.com"
  to_addrs: ["you@example.com"]
  subject: "最新文献推送"

# 去重状态文件（记录已推送的文献，配合 --new-only 使用）
state_file: "state.json"

# 外观定制文件：报头背景图/字体/标题/季节时段主题（详见 background.yaml）
appearance_file: "background.yaml"
"""


def save_default_config(path: Path, force: bool = False) -> None:
    """在 path 生成默认配置；已存在且未指定 force 时抛出 FileExistsError。"""
    if path.exists() and not force:
        raise FileExistsError(f"{path} 已存在（使用 --force 覆盖）")
    path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
