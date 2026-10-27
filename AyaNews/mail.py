"""邮件模块：构造并发送文献推送邮件（HTML 美化版 + 纯文本降级版）。"""
from __future__ import annotations

import html
import os
import smtplib
import ssl
import textwrap
import time
from datetime import date
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .appearance import (
    AppearanceConfig,
    Theme,
    banner_image_data_uri,
    find_banner_image,
    resolve_theme,
)
from .models import Paper


def build_body(papers: list[Paper], today: date) -> str:
    """构造纯文本邮件正文：文章名称 + 命中关键词 + 摘要。"""
    lines = [f"文々日报（{today.isoformat()}）· 共 {len(papers)} 篇命中关键词文献", ""]
    for i, p in enumerate(papers, 1):
        cat = f"（{', '.join(p.categories)}）" if p.categories else ""
        lines.append(f"{i}. {p.title}")
        lines.append(f"   作者：{p.authors_str or '（无作者信息）'}")
        lines.append(f"   来源：{p.source}{cat} | 日期：{p.published} | {p.url}")
        if p.matched_str:
            lines.append(f"   命中关键词：{p.matched_str}")
        if p.abstract:
            lines.append("   摘要：")
            lines.append(textwrap.indent(textwrap.fill(p.abstract, width=80), "     "))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML 美化版正文：季节主题配色、按来源分组、卡片式文献、摘要折叠展开
# ---------------------------------------------------------------------------

def _esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def _badge(text: str, bg: str, fg: str = "#ffffff") -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:11px;line-height:1.2;padding:3px 8px;border-radius:3px;'
        f'font-weight:600;vertical-align:middle;">{_esc(text)}</span>'
    )


def _kw_badge(text: str) -> str:
    return (
        f'<span style="display:inline-block;background:#e8f3ec;color:#1e7d46;'
        f'font-size:11px;line-height:1.2;padding:3px 9px;border-radius:10px;'
        f'margin:0 4px 4px 0;vertical-align:middle;">{_esc(text)}</span>'
    )


def _group_header(title: str, count: int, theme: Theme) -> str:
    return (
        f'<tr><td class="group" style="background:{theme.tint_bg};border-left:1px solid #e3e8ef;'
        'border-right:1px solid #e3e8ef;border-bottom:1px solid #e3e8ef;'
        f'padding:10px 32px;color:{theme.accent};font-size:13px;font-weight:700;">'
        f"{_esc(title)}（{count} 篇）</td></tr>"
    )


def _paper_card(index: int, p: Paper, theme: Theme) -> str:
    if p.source == "arXiv":
        badge = _badge("arXiv", "#b31b1b")
    else:
        badge = _badge(p.source, theme.bright)

    meta = []
    if p.categories:
        meta.append(" · ".join(p.categories))
    if p.published:
        meta.append(p.published.isoformat())
    meta_html = "&nbsp;·&nbsp;".join(_esc(m) for m in meta)

    authors = [a for a in p.authors if a]
    if len(authors) > 5:
        author_text = "，".join(authors[:5]) + f" 等 {len(authors)} 人"
    else:
        author_text = "，".join(authors)

    kw_html = "".join(_kw_badge(g) for g in p.matched_str.split("; ") if g)

    abstract_html = ""
    if p.abstract:
        # details/summary：支持的客户端可折叠；不支持的客户端会直接展开（可接受的降级）
        abstract_html = (
            '<details style="margin-top:2px;">'
            f'<summary style="cursor:pointer;color:{theme.accent};font-size:12px;'
            'font-weight:600;user-select:none;">📄 摘要（点击展开 / 收起）</summary>'
            f'<div style="margin-top:6px;color:#5b6572;font-size:12px;'
            f'line-height:1.7;">{_esc(p.abstract)}</div>'
            "</details>"
        )
    else:
        abstract_html = (
            '<div style="color:#8a94a6;font-size:12px;margin-top:2px;">'
            "📄 摘要：（暂缺，点击标题查看原文）</div>"
        )

    return (
        '<tr><td class="card" style="background:#ffffff;border-left:1px solid #e3e8ef;'
        'border-right:1px solid #e3e8ef;border-bottom:1px solid #e3e8ef;'
        'padding:16px 32px 18px 32px;">'
        f'<div style="margin-bottom:6px;">'
        f'<span style="color:#9aa7b8;font-size:13px;vertical-align:middle;'
        f'margin-right:6px;">{index}.</span>'
        f'<a href="{_esc(p.url)}" style="color:{theme.accent};font-size:15px;font-weight:700;'
        f'text-decoration:none;border-bottom:1px solid {theme.tint_border};">{_esc(p.title)}</a></div>'
        f'<div style="margin-bottom:6px;">{badge}'
        f'<span style="color:#8a94a6;font-size:12px;margin-left:8px;">{meta_html}</span></div>'
        f'<div style="color:#5b6572;font-size:12px;margin-bottom:6px;">'
        f'作者：{_esc(author_text) if author_text else "（无作者信息）"}</div>'
        f'<div style="margin-bottom:4px;">{kw_html}</div>'
        f"{abstract_html}"
        "</td></tr>"
    )


def _banner(banner_src: str | None, today: date, theme: Theme, appearance: AppearanceConfig) -> str:
    """顶部横幅：图片以 <img> 原比例完整显示（不裁剪），标题条置于图片下方。

    标题条底色使用当前主题的无图渐变；没有图片时标题条兼作横幅主体。
    标题文字、颜色、字号、阴影均由 background.yaml 的 title 段控制。
    """
    img_html = ""
    if banner_src:
        img_html = (
            '<tr><td style="padding:0;line-height:0;">'
            f'<img class="banner-img" src="{banner_src}" alt="banner" width="600" '
            'style="display:block;width:100%;height:auto;border:0;'
            'border-radius:8px 8px 0 0;">'
            "</td></tr>"
        )
    radius = "border-radius:8px 8px 0 0;" if not banner_src else ""

    t = appearance.title
    return (
        img_html
        + f'<tr><td class="strip" style="background:{theme.banner_fallback};padding:18px 32px;{radius}">'
        f'<div class="title" style="color:{_esc(t.color)};font-size:{_esc(t.font_size)};'
        f'font-weight:700;letter-spacing:1px;text-shadow:{_esc(t.shadow)};">{_esc(t.text)}</div>'
        f'<div style="color:{theme.soft};font-size:12px;margin-top:4px;">{today.isoformat()}</div>'
        "</td></tr>"
    )


def _responsive_css() -> str:
    """响应式增强（部分邮件客户端会剥离 <style>，因此关键宽度与背景均使用内联样式兜底）。

    这里只做内边距与字号的客户端适配：PC 端加大内边距，移动端收紧。
    """
    return """
@media only screen and (min-width: 820px) {
  .card { padding: 18px 40px 20px 40px !important; }
  .strip { padding: 20px 40px !important; }
  .bar, .group, .foot { padding-left: 40px !important; padding-right: 40px !important; }
}
@media only screen and (max-width: 640px) {
  .container { width: 100% !important; }
  .card { padding: 14px 14px 16px 14px !important; }
  .strip { padding: 16px 14px !important; }
  .bar, .group, .foot { padding-left: 14px !important; padding-right: 14px !important; }
  .banner-img { border-radius: 0 !important; }
  .title { font-size: 17px !important; }
}
"""


def build_html_body(
    papers: list[Paper],
    today: date,
    appearance: AppearanceConfig,
    banner_src: str | None = None,
    season: str | None = None,
) -> str:
    """构造 HTML 邮件正文：期刊论文在前、arXiv 预印本在后，各自按日期倒序。

    appearance: 外观配置（background.yaml），决定报头、字体与季节主题。
    banner_src: 横幅图片地址——发送时为 "cid:background"（内嵌附件），
    浏览器预览时为 data URI；None 则用当前主题的渐变横幅。
    season: 强制主题名（如 spring/summer/autumn/winter），默认按日期与时段规则自动判断。
    """
    theme = resolve_theme(appearance, today, season)
    total = len(papers)
    n_arxiv = sum(1 for p in papers if p.source == "arXiv")
    n_journal = total - n_arxiv

    groups: list[tuple[str, list[Paper]]] = []
    journals = [p for p in papers if p.source != "arXiv"]
    arxiv = [p for p in papers if p.source == "arXiv"]
    if journals:
        groups.append(("期刊论文", journals))
    if arxiv:
        groups.append(("arXiv 预印本", arxiv))

    rows: list[str] = []
    index = 0
    for title, items in groups:
        rows.append(_group_header(title, len(items), theme))
        for p in items:
            index += 1
            rows.append(_paper_card(index, p, theme))

    stats = (
        f'<span style="color:#5b6572;font-size:13px;">'
        f'共 <b style="color:{theme.accent};">{total}</b> 篇'
        f'&nbsp;&nbsp;·&nbsp;&nbsp;期刊 <b style="color:{theme.accent};">{n_journal}</b> 篇'
        f'&nbsp;&nbsp;·&nbsp;&nbsp;arXiv <b style="color:{theme.accent};">{n_arxiv}</b> 篇</span>'
    )

    body_font = _esc(appearance.fonts.body)
    responsive = _responsive_css()
    pc_width = _esc(appearance.banner.pc_width)
    page_style = "background:#f4f6f9;"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文々日报</title>
<style>{responsive}</style>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:{body_font};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;">
<tr><td class="page" align="center" style="padding:24px 12px;{page_style}">
<table role="presentation" class="container" width="100%" cellpadding="0" cellspacing="0"
       style="width:100%;max-width:{pc_width};border-collapse:collapse;">

{_banner(banner_src, today, theme, appearance)}

<tr><td class="bar" style="background:#ffffff;border-left:1px solid #e3e8ef;border-right:1px solid #e3e8ef;border-bottom:1px solid #e3e8ef;padding:12px 32px;">
{stats}
</td></tr>

{''.join(rows)}

<tr><td class="foot" style="background:#f0f3f7;border:1px solid #e3e8ef;border-radius:0 0 8px 8px;padding:14px 32px;text-align:center;color:#8a94a6;font-size:11px;">
由 AyaNews 生成 · 点击文章标题可直接查看原文
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


def _read_env_file() -> dict[str, str]:
    """读取项目根目录 .env 中的键值对（环境变量未设置时兜底用）。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    data: dict[str, str] = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip("'\"")
    return data


def send_email(
    cfg,
    papers: list[Paper],
    today: date,
    appearance: AppearanceConfig,
    season: str | None = None,
) -> bool:
    """按配置发送邮件，返回是否成功。

    未启用邮箱或无文献视为成功（无需发送）；发送失败返回 False，
    调用方可据此决定是否更新去重状态（避免失败后被标记为已推送）。
    """
    if not cfg.enabled or not papers:
        return True
    password = os.environ.get(cfg.password_env or "", "")
    if not password:
        password = _read_env_file().get(cfg.password_env, "")
        if password:
            print(f"[email] 未检测到环境变量 {cfg.password_env}，已自动读取项目根目录 .env。")
        else:
            print(
                f"[email] 未找到授权码：请设置环境变量 {cfg.password_env}，"
                f"或在项目根目录 .env 中写入 {cfg.password_env}='你的授权码'。"
            )
            return False
    theme = resolve_theme(appearance, today, season)
    banner_info = find_banner_image(appearance, theme)
    if banner_info:
        print(f"[email] 当前主题：{theme.label}，横幅图：{banner_info[0].name}")
    else:
        print(f"[email] 当前主题：{theme.label}，未找到横幅图，使用主题渐变背景。")

    text_body = build_body(papers, today)
    html_body = build_html_body(
        papers, today, appearance,
        "cid:background" if banner_info else None, season,
    )

    # 结构：multipart/alternative{ text/plain, multipart/related{ text/html, 横幅图(cid) } }
    images = []
    if banner_info:
        images.append((banner_info[0], banner_info[1], "background"))

    root = MIMEMultipart("alternative")
    root["Subject"] = f"{cfg.subject}（{today.isoformat()}）· {len(papers)} 篇"
    root["From"] = cfg.from_addr or cfg.username
    root["To"] = ", ".join(cfg.to_addrs)
    root.attach(MIMEText(text_body, "plain", "utf-8"))
    if images:
        related = MIMEMultipart("related")
        related.attach(MIMEText(html_body, "html", "utf-8"))
        for img_path, subtype, cid in images:
            image = MIMEImage(img_path.read_bytes(), _subtype=subtype)
            image.add_header("Content-ID", f"<{cid}>")
            image.add_header("Content-Disposition", "inline", filename=img_path.name)
            related.attach(image)
        root.attach(related)
    else:
        root.attach(MIMEText(html_body, "html", "utf-8"))

    def _deliver() -> None:
        """按配置的主通道发送（SSL 或 STARTTLS）。"""
        if cfg.use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ctx, timeout=120) as s:
                if cfg.username:
                    s.login(cfg.username, password)
                s.send_message(root)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=120) as s:
                s.starttls(context=ssl.create_default_context())
                if cfg.username:
                    s.login(cfg.username, password)
                s.send_message(root)

    def _deliver_fallback() -> None:
        """主通道失败后换另一条通道再试：SSL 走 587 STARTTLS，STARTTLS 走 465 SSL。"""
        if cfg.use_ssl:
            with smtplib.SMTP(cfg.smtp_host, 587, timeout=120) as s:
                s.starttls(context=ssl.create_default_context())
                if cfg.username:
                    s.login(cfg.username, password)
                s.send_message(root)
        else:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.smtp_host, 465, context=ctx, timeout=120) as s:
                if cfg.username:
                    s.login(cfg.username, password)
                s.send_message(root)

    # 网络抖动或服务器临时断开时：主通道重试一次，再尝试备用通道
    attempts = [
        ("第 1 次", _deliver),
        ("第 2 次", _deliver),
        ("备用通道", _deliver_fallback),
    ]
    for index, (label, deliver) in enumerate(attempts, start=1):
        try:
            deliver()
            print(f"[email] 已发送 {len(papers)} 篇到 {', '.join(cfg.to_addrs)}")
            return True
        except (smtplib.SMTPException, OSError) as exc:
            if index < len(attempts):
                wait = 5 if index == 1 else 15
                print(f"[email] 第 {index} 次发送失败：{exc}，{wait} 秒后改用{'备用通道' if index == 2 else '主通道'}重试…")
                time.sleep(wait)
            else:
                print(f"[email] 发送失败：{exc}")
                return False
    return False
