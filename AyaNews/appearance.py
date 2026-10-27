"""外观定制中心：报头、字体、标题与「季节时段 → 主题参数」映射（来自 background.yaml）。

用法：项目根目录的 background.yaml 负责——
  - banner：背景图所在文件夹与文件名（不带扩展名，自动识别 png/jpg/jpeg/webp/gif）
  - title：报头标题文字、颜色、字号、阴影
  - fonts：邮件正文字体栈
  - seasonal.rules：季节时段规则（“在哪个时间段内使用哪套主题参数”）
  - seasonal.themes：各主题的文字配色参数

季节只是主题的名字，时段规则可自由增改；主题参数在 themes 里改。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


@dataclass(frozen=True)
class Theme:
    """一套主题的文字配色与横幅图。"""

    key: str
    label: str
    accent: str            # 标题链接 / 分组栏文字 / 统计数字主色
    bright: str            # 期刊徽章亮色
    tint_bg: str           # 分组栏浅色底
    tint_border: str       # 标题下划线浅色
    soft: str              # 横幅上的浅色小字
    banner_fallback: str   # 没有背景图时的横幅渐变
    image: str = ""        # 该主题的横幅图文件名（在 banner.image_dir 下）；空 = 用 banner.image_name


DEFAULT_THEMES: dict[str, Theme] = {
    "spring": Theme(
        "spring", "春季·浅绿",
        accent="#7cb342", bright="#9ccc65", tint_bg="#f1f8e9", tint_border="#d0e4b8",
        soft="#eaf6dd", banner_fallback="linear-gradient(135deg,#558b2f 0%,#9ccc65 100%)",
    ),
    "summer": Theme(
        "summer", "夏季·蓝",
        accent="#1565c0", bright="#1e88e5", tint_bg="#e3f2fd", tint_border="#bcd8f5",
        soft="#d8ebfa", banner_fallback="linear-gradient(135deg,#0d47a1 0%,#1e88e5 100%)",
    ),
    "autumn": Theme(
        "autumn", "秋季·橙",
        accent="#9a3412", bright="#ea580c", tint_bg="#fef3e7", tint_border="#f0d3b3",
        soft="#ffe8d6", banner_fallback="linear-gradient(135deg,#9a3412 0%,#ea580c 100%)",
    ),
    "winter": Theme(
        "winter", "冬季·紫",
        accent="#7b1fa2", bright="#ab47bc", tint_bg="#f3e5f5", tint_border="#d9c2e3",
        soft="#efddf3", banner_fallback="linear-gradient(135deg,#4a148c 0%,#ab47bc 100%)",
    ),
}

DEFAULT_RULES: list[dict] = [
    {"season": "spring", "start": "03-01", "end": "05-31"},
    {"season": "summer", "start": "06-01", "end": "08-31"},
    {"season": "autumn", "start": "09-01", "end": "11-30"},
    {"season": "winter", "start": "12-01", "end": "02-28"},
]


@dataclass(frozen=True)
class BannerConfig:
    image_dir: str = "background"
    image_name: str = "background"
    pc_width: str = "1000px"      # PC 端内容列宽度


@dataclass(frozen=True)
class TitleConfig:
    text: str = "🍁 AyaNews----Computation Mathematics"
    color: str = "#ffffff"
    font_size: str = "20px"
    shadow: str = "0 1px 3px rgba(0,0,0,0.4)"


@dataclass(frozen=True)
class FontConfig:
    body: str = "-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif"


@dataclass
class SeasonalRule:
    season: str
    start: str  # "MM-DD"
    end: str    # "MM-DD"；start > end 表示跨年（如 12-01 ~ 02-28）


@dataclass
class AppearanceConfig:
    banner: BannerConfig
    title: TitleConfig
    fonts: FontConfig
    seasonal_rules: list[SeasonalRule]
    themes: dict[str, Theme]


# ---------------------------------------------------------------------------
# 加载与解析
# ---------------------------------------------------------------------------

def default_appearance() -> AppearanceConfig:
    return AppearanceConfig(
        banner=BannerConfig(),
        title=TitleConfig(),
        fonts=FontConfig(),
        seasonal_rules=[SeasonalRule(**r) for r in DEFAULT_RULES],
        themes=dict(DEFAULT_THEMES),
    )


def load_appearance(path: Path) -> AppearanceConfig:
    """从 background.yaml 加载外观配置；文件缺失或字段缺失时用内置默认值。"""
    if not path.exists():
        print(f"[appearance] 未找到 {path}，使用内置默认外观。")
        return default_appearance()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        print(f"[appearance] {path} 内容无效，使用内置默认外观。")
        return default_appearance()

    banner = raw.get("banner") or {}
    title = raw.get("title") or {}
    fonts = raw.get("fonts") or {}
    seasonal = raw.get("seasonal") or {}

    rules = [
        SeasonalRule(
            season=str(r.get("season", "")),
            start=str(r.get("start", "")),
            end=str(r.get("end", "")),
        )
        for r in (seasonal.get("rules") or [])
        if isinstance(r, dict) and r.get("season")
    ]
    if not rules:
        rules = [SeasonalRule(**r) for r in DEFAULT_RULES]

    themes = dict(DEFAULT_THEMES)
    for key, t in (seasonal.get("themes") or {}).items():
        if not isinstance(t, dict):
            continue
        base = DEFAULT_THEMES.get(key)
        if base is None:
            continue
        themes[key] = Theme(
            key=key,
            label=str(t.get("label", base.label)),
            accent=str(t.get("accent", base.accent)),
            bright=str(t.get("bright", base.bright)),
            tint_bg=str(t.get("tint_bg", base.tint_bg)),
            tint_border=str(t.get("tint_border", base.tint_border)),
            soft=str(t.get("soft", base.soft)),
            banner_fallback=str(t.get("banner_fallback", base.banner_fallback)),
            image=str(t.get("image", base.image)),
        )

    return AppearanceConfig(
        banner=BannerConfig(
            image_dir=str(banner.get("image_dir", "background")),
            image_name=str(banner.get("image_name", "background")),
            pc_width=str(banner.get("pc_width", "1000px")),
        ),
        title=TitleConfig(
            text=str(title.get("text", "🍁 AyaNews----Computation Mathematics")),
            color=str(title.get("color", "#ffffff")),
            font_size=str(title.get("font_size", "20px")),
            shadow=str(title.get("shadow", "0 1px 3px rgba(0,0,0,0.4)")),
        ),
        fonts=FontConfig(
            body=str(fonts.get(
                "body",
                "-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif",
            )),
        ),
        seasonal_rules=rules,
        themes=themes,
    )


# ---------------------------------------------------------------------------
# 主题解析与横幅图查找
# ---------------------------------------------------------------------------

def _parse_md(text: str) -> tuple[int, int]:
    m, d = text.strip().split("-")[:2]
    return int(m), int(d)


def resolve_theme(appearance: AppearanceConfig, today: date, season: str | None = None) -> Theme:
    """按日期解析当前主题；season 可强制指定主题名（用于预览/测试）。"""
    if season is not None:
        theme = appearance.themes.get(season)
        if theme is None:
            raise KeyError(f"background.yaml 中没有名为 {season} 的主题")
        return theme

    md = (today.month, today.day)
    for rule in appearance.seasonal_rules:
        try:
            start = _parse_md(rule.start)
            end = _parse_md(rule.end)
        except (ValueError, IndexError):
            continue
        hit = (start <= md <= end) if start <= end else (md >= start or md <= end)
        if hit:
            return appearance.themes[rule.season]
    return appearance.themes[appearance.seasonal_rules[0].season]


def find_banner_image(
    appearance: AppearanceConfig, theme: Theme | None = None
) -> tuple[Path, str] | None:
    """查找横幅图，返回 (路径, MIME 子类型)；没有则 None。

    优先使用当前主题的 image 文件名（如 autumn.png），主题未指定时
    退回 banner.image_name；文件名不带扩展名时自动识别常见格式，
    同名多格式取最近修改（最新放入）的那张。
    """
    base = _PROJECT_ROOT / appearance.banner.image_dir
    if not base.is_dir():
        return None
    names: list[str] = []
    if theme and theme.image:
        names.append(theme.image)
    names.append(appearance.banner.image_name)
    for name in names:
        result = _match_image(base, name)
        if result:
            return result
    return None


def _match_image(base: Path, name: str) -> tuple[Path, str] | None:
    path = base / name
    if path.is_file():  # 带扩展名的完整文件名
        ext = path.suffix.lower()
        subtype = "jpeg" if ext in (".jpg", ".jpeg") else ext.lstrip(".")
        return path, subtype
    candidates: list[tuple[Path, str]] = []
    for ext in _IMAGE_EXTS:
        p = base / f"{name}{ext}"
        if p.is_file():
            subtype = "jpeg" if ext in (".jpg", ".jpeg") else ext.lstrip(".")
            candidates.append((p, subtype))
    if not candidates:
        return None
    return max(candidates, key=lambda c: c[0].stat().st_mtime)


def banner_image_data_uri(path: Path, subtype: str) -> str:
    """把图片转成 base64 data URI（浏览器预览用，cid: 在浏览器中无法显示）。"""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{subtype};base64,{data}"


def save_default_appearance(path: Path, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} 已存在（使用 --force 覆盖）")
    path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
