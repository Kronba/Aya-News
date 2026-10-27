# AyaNews

AyaNews 是一个面向科研工作者的文献自动推送工具。它按你给定的标题关键词，从 arXiv 预印本库与 Crossref 收录的高质量期刊中抓取最新论文，清洗摘要、按来源分组、以季节主题排版成一份 HTML 报纸邮件，每天定时投递到你的邮箱。

![邮件报头](docs/email_banner.png)

<div align="center">秋季主题的邮件封面示意图</div>

## Introduce

数据来自两个免费接口。arXiv 一侧按学科分类与标题关键词查询，按提交时间倒序取回结果；Crossref 一侧按期刊 ISSN 拉取近期条目，只保留期刊论文（`type:journal-article`），新闻与勘误不会混入。关键词支持分组：组内必须同时出现，组间命中任意一组即可，匹配时忽略大小写与连字符。Crossref 摘要中的 JATS 标签会被自动剥除，缺失的摘要会尝试从 Semantic Scholar 按 DOI 补全。

仓库自带的 `test/` 目录可以直接对任意期刊做抓取兼容性测试：它读取 `journals_catalog.yaml`（9 个领域共 79 本刊物），逐本向 Crossref 发请求，按接口可用性与摘要覆盖率给出 ✅/🟡/❌ 结论。✅ 表示接口正常、近期有论文且摘要覆盖率不低于一半，可以直接订阅；🟡 表示接口正常但摘要缺失较多或近期无新论文，标题与元数据仍可正常抓取。下面是几本刊物的实测结果：

| 刊物 | 领域 | 结论 | 摘要覆盖率 |
| --- | --- | --- | --- |
| SIAM Journal on Numerical Analysis | 计算数学 | ✅ 完全兼容 | 100% |
| Mathematics of Computation | 计算数学 | ✅ 完全兼容 | 62% |
| Journal of Computational Physics | 计算数学 | 🟡 部分兼容 | 0% |
| Physical Review X | 物理 | ✅ 完全兼容 | 50% |
| Nature Physics | 物理 | 🟡 部分兼容 | 25% |
| Journal of the American Chemical Society | 化学 | ✅ 完全兼容 | 90% |
| Nature | 生物医学 | 🟡 部分兼容 | 10% |
| American Economic Review | 经济学 | ✅ 完全兼容 | 90% |

复测只需运行 `python test/journal_compat.py --catalog journals_catalog.yaml --days 30`，报告与明细会写入 `output/` 目录。



# Quick Start



### 安装与配置

要求 Python 3.10 或更高版本。克隆仓库并运行初始化脚本：

```
git clone <repository-url>
cd CMath-paper
bash setup.sh
```

脚本将自动创建 `.venv` 虚拟环境、安装 `requests` 和 `pyyaml` 依赖，并生成 `config.yaml` 与 `.env` 配置模板。

- `config.yaml`：配置关键词分组（`keywords`）、arXiv 学科与时间范围（`arxiv`）、期刊 ISSN（`crossref`）及邮件参数（`email`）。
- `.env`：填写邮箱授权码，格式如下：

```
CMATH_EMAIL_PASSWORD='邮箱授权码'
```



### 运行

执行以下命令，抓取论文并发送邮件：

```
set -a && . ./.env && set +a
.venv/bin/python -m AyaNews.main --config config.yaml --new-only
```

`--new-only` 仅推送尚未发送的论文，记录保存在 `state.json` 中。使用 `--preview-email` 可生成 HTML 邮件预览，文件位于 `output/`，不会实际发送邮件。

### 定时推送（可选）

Linux 环境下，可通过 `cron` 设置每日 09:00 自动推送。将项目路径替换为实际路径后执行一次：

```
(crontab -l 2>/dev/null; echo '0 9 * * * cd /path/to/CMath-paper && . ./.env && .venv/bin/python -m AyaNews.main --config config.yaml --new-only >> cron.log 2>&1') | crontab -
```

使用 `crontab -l` 查看任务，`crontab -e` 编辑任务，`cat cron.log` 查看运行日志。



# 邮件外观

邮件顶部是横幅：先以原比例完整显示当季插画（不做裁剪和拉伸），下方紧接一条主题色标题栏，标题文字、颜色、字号与阴影都来自 `background.yaml` 的 `title` 段，目前显示为「🍁 AyaNews----Computation Mathematics」与当日日期。横幅图片按季节自动选择，四季素材放在 `background/` 文件夹中，春、夏、秋、冬分别对应 `spring.png`、`summer.png`、`autumn.png`、`winter.png`，文件名可以在 `background.yaml` 的 `seasonal.themes` 里修改。

横幅之下是一条统计栏，用一句话概括本期内容，例如「共 26 篇 · 期刊 18 篇 · arXiv 8 篇」。正文按来源分成两组：期刊论文在前，arXiv 预印本在后，每组都有浅色分组的标题栏，组内按发表日期倒序排列。每篇论文是一张白色卡片，卡片里依次是序号、可点击跳转原文的标题、来源徽章（arXiv 为红色、期刊使用主题亮色）、分类标签与日期、作者列表（超过五人显示为「等 N 人」）、命中的关键词标签，以及默认折叠的摘要。摘要使用 `<details>` 元素折叠，支持的客户端点击展开，不支持的客户端会直接展开全文，属于可接受的降级。

文字配色随季节自动切换：春季浅绿、夏季蓝色、秋季橙色、冬季紫色。每个季节的强调色、徽章色、分组栏底色、标题下划线色与无图时的横幅渐变都定义在 `background.yaml` 的 `seasonal.themes` 中，日期与季节的对应关系由 `seasonal.rules` 决定，规则是「在某时间段内使用哪套主题」，可以自由增删时段或增加如「考试周」之类的自定义主题，程序按 `MM-DD` 顺序匹配，跨年时段写成起始晚于结束即可。



