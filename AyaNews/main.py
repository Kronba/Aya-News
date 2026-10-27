"""命令行入口：按标题关键词爬取特定领域刊物的最新文献。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .appearance import (
    banner_image_data_uri,
    find_banner_image,
    load_appearance,
    resolve_theme,
)
from .config import AppConfig, load_config, save_default_config
from .export import export
from .mail import build_html_body, send_email
from .pipeline import CollectResult, collect
from .storage import save_state


def run(
    cfg: AppConfig, appearance, *, new_only: bool, send: bool, season: str | None = None
) -> None:
    """执行一次完整流程：采集 → 导出 → 邮件推送 → 更新去重状态。"""
    result: CollectResult = collect(cfg, new_only=new_only)
    if not result.papers:
        print("\n没有新文献 → 本次不发邮件、不导出。")
        return

    _print_summary(result.papers, result.today)

    md_path, csv_path = export(
        result.papers, Path(cfg.output.dir), "papers",
        cfg.output.include_abstract, result.today,
    )
    print(f"已导出：\n  Markdown: {md_path}\n  CSV:      {csv_path}")

    email_ok = True  # 未要求发邮件视为成功
    if send:
        if not cfg.email.enabled:
            print("[email] 邮箱未启用（config.yaml 中 email.enabled: false），跳过发送。")
        else:
            email_ok = send_email(cfg.email, result.papers, result.today, appearance, season)

    if new_only:
        if email_ok:
            save_state(Path(cfg.state_file), result.state)
            print(f"去重状态已更新：{Path(cfg.state_file)}")
        else:
            print("[email] 发送失败，本次不更新去重状态（下次运行会重试这些文献）。")


def preview_email(cfg: AppConfig, appearance, out_path: Path, season: str | None = None) -> None:
    """只生成 HTML 邮件预览文件，不发送、不影响去重状态。"""
    result = collect(cfg, new_only=False)
    theme = resolve_theme(appearance, result.today, season)
    banner_src = None
    banner_info = find_banner_image(appearance, theme)
    if banner_info:
        img_path, subtype = banner_info
        banner_src = banner_image_data_uri(img_path, subtype)
        print(f"当前主题：{theme.label}，横幅图：{img_path.name}")
    else:
        print(f"当前主题：{theme.label}，未找到横幅图，使用主题渐变背景。")

    html_text = build_html_body(
        result.papers, result.today, appearance, banner_src, season
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")
    print(f"HTML 邮件预览已生成：{out_path}（{len(result.papers)} 篇）")
    print("用浏览器打开该文件即可查看效果，与实际收到的邮件一致。")


def _print_summary(papers, today) -> None:
    print(f"\n=== 文献抓取结果（{today.isoformat()}）===")
    for i, p in enumerate(papers, 1):
        print(f"{i:3d}. [{p.source}] {p.published}  {p.title}")
        print(f"      {p.url}  命中：{p.matched_str}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="AyaNews",
        description="按标题关键词爬取特定领域刊物（arXiv 分类 + Crossref 期刊）的最新文献。",
    )
    parser.add_argument("--config", default="config.yaml", help="配置文件路径（默认 config.yaml）")
    parser.add_argument("--init", action="store_true", help="在 --config 路径生成默认配置文件")
    parser.add_argument("--force", action="store_true", help="与 --init 配合：覆盖已存在的配置文件")
    parser.add_argument("--days", type=int, default=None, help="覆盖配置中的时间窗口（天）")
    parser.add_argument("--new-only", action="store_true", help="只输出未推送过的新文献，并更新去重状态文件")
    parser.add_argument("--no-email", action="store_true", help="本次运行不发送邮件")
    parser.add_argument(
        "--preview-email", nargs="?", const="output/email_preview.html", default=None,
        metavar="PATH",
        help="只生成 HTML 邮件预览文件（默认 output/email_preview.html），不发送、不影响去重状态",
    )
    parser.add_argument(
        "--season", choices=["spring", "summer", "autumn", "winter"], default=None,
        help="强制使用指定季节主题（默认按日期自动判断：春=浅绿/夏=深绿/秋=橙/冬=淡蓝）",
    )
    args = parser.parse_args(argv)

    cfg_path = Path(args.config)
    if args.init:
        try:
            save_default_config(cfg_path, force=args.force)
        except FileExistsError as exc:
            parser.error(str(exc))
        print(f"已生成默认配置：{cfg_path}")
        print("请编辑其中的 keywords / arxiv.categories / crossref.journals 后运行：")
        print(f"  python -m AyaNews.main --config {cfg_path}")
        return 0
    if not cfg_path.exists():
        parser.error(f"配置文件不存在：{cfg_path}（可先用 --init 生成）")

    cfg = load_config(cfg_path)
    if not cfg.keywords:
        parser.error("配置文件中未找到 keywords，请至少提供一个标题关键词")
    if args.days is not None:
        cfg.arxiv.days = args.days
        cfg.crossref.days = args.days

    if args.preview_email:
        appearance = load_appearance(Path(cfg.appearance_file))
        preview_email(cfg, appearance, Path(args.preview_email), season=args.season)
        return 0

    appearance = load_appearance(Path(cfg.appearance_file))
    run(cfg, appearance, new_only=args.new_only, send=not args.no_email, season=args.season)
    return 0


if __name__ == "__main__":
    sys.exit(main())
