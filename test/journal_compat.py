"""刊物兼容性测试：逐本检测 Crossref 抓取是否可用，按领域输出报告。

用法（在项目根目录下运行）：
    python test/journal_compat.py --catalog journals_catalog.yaml --days 30

判定标准：
    ✅ 完全兼容 —— 接口正常、近 N 天有期刊论文、至少一半条目带摘要
    🟡 部分兼容 —— 接口正常但近期无论文 / 摘要缺失较多（标题抓取仍可用）
    ❌ 不兼容   —— ISSN 未收录、请求失败等（会尝试按刊名反查 ISSN）

目录格式见项目根目录的 journals_catalog.yaml：每项含 name、issn、field 三个字段，
field 仅用于报告分组。测试通过后把 ISSN 填入 config.yaml 的 crossref.journals 即可订阅。
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
import yaml

# 允许通过 `python test/journal_compat.py` 直接运行（把项目根目录加入 sys.path）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from AyaNews.providers.http import get_with_retry  # noqa: E402

API = "https://api.crossref.org"
SLEEP_BETWEEN_JOURNALS = 0.5


def _works(issn: str, start: date, mailto: str, rows: int = 20) -> requests.Response:
    params = {
        "filter": f"from-pub-date:{start.isoformat()},type:journal-article",
        "rows": rows,
        "sort": "published",
        "order": "desc",
        "select": "DOI,title,published,abstract",
    }
    if mailto:
        params["mailto"] = mailto
    return get_with_retry(f"{API}/journals/{issn}/works", params, label="journal-test")


def _resolve_issn(name: str) -> tuple[str | None, str | None]:
    """ISSN 失效时按期刊名在 Crossref 中反查，返回 (issn, 规范刊名)。"""
    try:
        resp = requests.get(
            f"{API}/journals", params={"query": name, "rows": 3}, timeout=30
        )
        items = (resp.json().get("message") or {}).get("items") or []
        for it in items:
            issns = it.get("ISSN") or []
            if issns:
                return issns[0], it.get("title") or name
    except (requests.RequestException, ValueError):
        pass
    return None, None


def test_journal(name: str, issn: str, field: str, start: date, mailto: str, days: int) -> dict:
    record = {
        "name": name, "field": field, "issn": issn, "used_issn": issn,
        "status": "", "items": 0, "abstract_ratio": None,
        "verdict": "", "note": "",
    }
    try:
        resp = _works(issn, start, mailto)
    except requests.RequestException as exc:
        record["status"] = "请求失败"
        record["verdict"] = "❌"
        record["note"] = f"{exc.__class__.__name__}: {str(exc)[:80]}"
        return record

    if resp.status_code == 404:
        new_issn, canonical = _resolve_issn(name)
        if new_issn:
            record["note"] = f"ISSN {issn} 未收录，已按刊名反查为 {new_issn}"
            record["used_issn"] = new_issn
            try:
                resp = _works(new_issn, start, mailto)
            except requests.RequestException as exc:
                record["status"] = "请求失败"
                record["verdict"] = "❌"
                record["note"] += f"；重试失败：{exc.__class__.__name__}"
                return record
            if resp.status_code != 200:
                record["status"] = f"HTTP {resp.status_code}"
                record["verdict"] = "❌"
                return record
        else:
            record["status"] = "HTTP 404（ISSN 未收录且按刊名反查失败）"
            record["verdict"] = "❌"
            return record
    elif resp.status_code != 200:
        record["status"] = f"HTTP {resp.status_code}"
        record["verdict"] = "❌"
        return record

    try:
        items = (resp.json().get("message") or {}).get("items") or []
    except ValueError:
        record["status"] = "响应解析失败"
        record["verdict"] = "❌"
        return record

    record["status"] = "HTTP 200"
    record["items"] = len(items)
    with_abstract = sum(1 for it in items if (it.get("abstract") or "").strip())
    record["abstract_ratio"] = round(with_abstract / len(items), 2) if items else 0.0

    if not items:
        record["verdict"] = "🟡"
        record["note"] = f"近 {days} 天无期刊论文（接口正常，刊期稀疏或已停刊）"
    elif record["abstract_ratio"] >= 0.5:
        record["verdict"] = "✅"
    else:
        record["verdict"] = "🟡"
        record["note"] = f"摘要缺失较多（{with_abstract}/{len(items)} 条有摘要）"
    return record


def _ratio_text(ratio) -> str:
    return f"{int(ratio * 100)}%" if ratio is not None else "-"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="journal-test", description="逐本检测刊物与脚本的兼容性（按领域分组）。"
    )
    parser.add_argument("--catalog", default="journals_catalog.yaml", help="刊物目录 YAML")
    parser.add_argument("--days", type=int, default=30, help="检测时间窗口（天）")
    parser.add_argument("--outdir", default="output", help="报告输出目录")
    parser.add_argument("--mailto", default="", help="Crossref 礼貌池邮箱")
    args = parser.parse_args(argv)

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        parser.error(f"刊物目录不存在：{catalog_path}")
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    journals = [j for j in (data.get("journals") or []) if isinstance(j, dict)]
    if not journals:
        parser.error("目录中没有 journals 条目")

    start = date.today() - timedelta(days=args.days)
    records = []
    print(f"开始检测 {len(journals)} 本刊物（窗口 {args.days} 天）…\n")
    for j in journals:
        rec = test_journal(
            str(j.get("name", "")), str(j.get("issn", "")),
            str(j.get("field", "未分类")), start, args.mailto, args.days,
        )
        records.append(rec)
        print(f"{rec['verdict']} [{rec['field']}] {rec['name']:<40} "
              f"ISSN {rec['used_issn']:<12} {rec['status']}  论文 {rec['items']:>3} 篇  摘要 {_ratio_text(rec['abstract_ratio']):>4}")
        time.sleep(SLEEP_BETWEEN_JOURNALS)

    _print_summary(records)
    stamp = date.today().isoformat()
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"journal_compat_{stamp}.md"
    csv_path = out_dir / f"journal_compat_{stamp}.csv"
    _write_report(md_path, csv_path, records, args.days, stamp)
    print(f"\n报告已生成：\n  Markdown: {md_path}\n  CSV:      {csv_path}")
    return 0


def _print_summary(records: list[dict]) -> None:
    by_field: dict[str, dict] = {}
    for r in records:
        field = r["field"]
        agg = by_field.setdefault(field, {"✅": 0, "🟡": 0, "❌": 0})
        agg[r["verdict"]] += 1
    print("\n分领域汇总：")
    for field, agg in by_field.items():
        print(f"  {field:<8} ✅ {agg['✅']:>2} · 🟡 {agg['🟡']:>2} · ❌ {agg['❌']}")
    total = {k: sum(a[k] for a in by_field.values()) for k in ("✅", "🟡", "❌")}
    print(f"  合计      ✅ {total['✅']:>2} · 🟡 {total['🟡']:>2} · ❌ {total['❌']}")


def _write_report(md_path: Path, csv_path: Path, records: list[dict], days: int, stamp: str) -> None:
    header = ["兼容性", "领域", "刊物", "ISSN", "实际使用 ISSN", "状态", "近N天论文数", "摘要覆盖率", "备注"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in records:
            writer.writerow([
                r["verdict"], r["field"], r["name"], r["issn"], r["used_issn"],
                r["status"], r["items"], _ratio_text(r["abstract_ratio"]), r["note"],
            ])

    lines = [
        f"# 刊物兼容性测试报告（{stamp}）",
        "",
        f"- 检测窗口：近 **{days}** 天（Crossref `from-pub-date` + `type:journal-article` 过滤）",
        "- 判定标准：✅ 接口正常且近 N 天有论文、摘要覆盖率 ≥ 50%；🟡 接口正常但近期无论文或摘要缺失较多；❌ ISSN 未收录/请求失败（自动按刊名反查 ISSN）",
        "",
        "| 兼容性 | 领域 | 刊物 | ISSN | 状态 | 论文数 | 摘要覆盖率 | 备注 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    current_field = None
    for r in records:
        if r["field"] != current_field:
            current_field = r["field"]
            lines.append(f"| **—— {current_field} ——** | | | | | | | |")
        note = r["note"].replace("|", "\\|")
        lines.append(
            f"| {r['verdict']} | {r['field']} | {r['name']} | {r['used_issn']} | "
            f"{r['status']} | {r['items']} | {_ratio_text(r['abstract_ratio'])} | {note} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
