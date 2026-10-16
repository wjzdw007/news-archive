# news-archive

每天从稳定 RSS 抓取中文新闻，按 URL 去重后永久存档，schema 对 AI 友好。

## P0 源（26 主力含国际 / 亚太 / 中国 / EV / 硬科技 / 财经 / 科学 + 1 官方对照）

| id | 源 | Feed | 角色 |
|---|---|---|---|
| `36kr` | 36氪 | https://www.36kr.com/feed | primary |
| `tmtpost` | 钛媒体 | https://www.tmtpost.com/rss.xml | primary |
| `geekpark` | 极客公园 | https://www.geekpark.net/rss | primary |
| `ftchinese` | FT中文网 | https://www.ftchinese.com/rss/news | primary |
| `bbc_zh_simp` | BBC中文(简) | https://feeds.bbci.co.uk/zhongwen/simp/rss.xml | primary |
| `guardian_world` | Guardian World | https://www.theguardian.com/world/rss | primary |
| `nyt_world` | NYT World | https://rss.nytimes.com/services/xml/rss/nyt/World.xml | primary |
| `aljazeera` | Al Jazeera | https://www.aljazeera.com/xml/rss/all.xml | primary |
| `electrek` | Electrek | https://electrek.co/feed/ | primary |
| `insideevs` | InsideEVs | https://insideevs.com/rss/news/all/ | primary |
| `verge_transport` | The Verge Transportation | https://www.theverge.com/rss/transportation/index.xml | primary |
| `scmp` | SCMP | https://www.scmp.com/rss/2/feed | primary |
| `mit_tr` | MIT Technology Review | https://www.technologyreview.com/feed/ | primary |
| `bbc_world` | BBC World | https://feeds.bbci.co.uk/news/world/rss.xml | primary |
| `scmp_asia` | SCMP Asia | https://www.scmp.com/rss/3/feed | primary |
| `solidot` | Solidot | https://www.solidot.org/index.rss | primary |
| `bbc_technology` | BBC Technology | https://feeds.bbci.co.uk/news/technology/rss.xml | primary |
| `scmp_china` | SCMP China | https://www.scmp.com/rss/4/feed | primary |
| `nyt_technology` | NYT Technology | https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml | primary |
| `ifanr` | 爱范儿 | https://www.ifanr.com/feed | primary |
| `bbc_business` | BBC Business | https://feeds.bbci.co.uk/news/business/rss.xml | primary |
| `guardian_technology` | Guardian Technology | https://www.theguardian.com/uk/technology/rss | primary |
| `ars_technica` | Ars Technica | https://feeds.arstechnica.com/arstechnica/index | primary |
| `nyt_business` | NYT Business | https://rss.nytimes.com/services/xml/rss/nyt/Business.xml | primary |
| `bbc_science` | BBC Science | https://feeds.bbci.co.uk/news/science_and_environment/rss.xml | primary |
| `techcrunch` | TechCrunch | https://feeds.feedburner.com/TechCrunch | primary |
| `people_finance` | 人民网·财经 | https://www.people.com.cn/rss/finance.xml | control |

## Schema

`title` / `published_at` / `url` / `summary` / `source` / `fetched_at` / `content_snapshot` / `status`

- 主键 / 去重键：`url`
- `content_snapshot`：私有全文快照（优先 RSS `content:encoded`；http(s) 且 `status != gone`、快照空或过短/壳导航文本时抓取原文页写入纯文本）。公开站点从不导出此字段。已有可用快照不重抓。不扩展到 X 帖（仍仅 `text_snapshot`）
- 原文补抓：每轮最多 40 次 HTTP。403/429/timeout/空 body 时按源再试 1–2 个备用入口（`nyt_world`：AMP / mobile.nytimes.com；`ftchinese`：m.ftchinese.com / AMP），成功则写入私有 snapshot；全部失败才按**篇**计入连续失败（不是按每次 GET）。同一源连续 3 篇 403/429/timeout 则本轮停止该源，并在 sqlite `enrich_backoff` 写入 6 小时冷却（随 `data` 分支持久化）。daily-fetch 成功时把覆盖率写到 Actions Job Summary，不公开 `/stats` 页
- 公开 `summary`：纯文本，最多 280 字；已合格（≥80）则保留；空或 <80 时从快照派生 ≤280
- `status`：`active` | `gone`（后续探测不可达时标记，不删记录）
- 存储：SQLite（可导出 JSONL）
- X 帖子：P1（按 post id 去重 + 快照），不挡本轮 RSS 底座

## 持久化存储（Data Branch）

`archive.sqlite3` 通过 **专用 `data` 分支** 实现跨 Actions 运行持久化：

- **`data` 分支**（orphan branch）：仅存放 `data/archive.sqlite3` 和 `data/LAST_RUN.json`（最后一次运行元数据）
- **`main` 分支**：仅存代码，`.gitignore` 已排除 `*.sqlite3`
- **Artifacts**：每次运行同时上传 sqlite + jsonl + run-stats 作为 90 天备份（`news-archive-{run_id}`）

### 工作流程（Workflow）

1. **恢复数据库**：每次运行开始前，从 `data` 分支 checkout `data/archive.sqlite3`（若分支/文件不存在，则从空数据库开始 — 首次运行 OK）
2. **抓取去重**：运行抓取 → URL 去重 → 入库（`store.upsert()` 自动跳过已存在 URL）
3. **验收检查**：P0 验收 + 高频去重测试通过
4. **持久化回写**：成功后将更新的 `archive.sqlite3` 和 `LAST_RUN.json` commit 并 push 回 `data` 分支
   - 冲突处理：`git pull --rebase` + 最多重试 3 次
   - **禁止 force-push**：保留并发运行的提交历史
   - 持续冲突 → 失败（红），需人工介入
5. **备份上传**：上传 artifact（独立于 data 分支，保留 90 天）

### 标记失效 URL（Gone Status）

链接失效后，使用 `mark_gone` 工具标记 URL 而非删除记录：

```bash
# 标记单个 URL
PYTHONPATH=src python -m news_archive.mark_gone \
  --db data/archive.sqlite3 \
  --url "https://example.com/article"

# 标记多个 URL
PYTHONPATH=src python -m news_archive.mark_gone \
  --db data/archive.sqlite3 \
  --url "https://example.com/1" \
  --url "https://example.com/2"

# 预览（不实际修改）
PYTHONPATH=src python -m news_archive.mark_gone \
  --db data/archive.sqlite3 \
  --url "https://example.com/article" \
  --dry-run
```

**注意**：
- `mark_gone` 可以直接操作 `data` 分支上的数据库（checkout `data` 分支后运行）
- 失效状态（`status='gone'`）会持久化到 `data` 分支
- `store.upsert()` 保留已存在记录的 `status`（gone 不会被重新激活）

## 用法

```bash
pip install -r requirements.txt
python -m news_archive --db data/archive.sqlite3 --export-jsonl data/archive.jsonl --json
```

需在 `PYTHONPATH=src` 下运行，或 `pip install -e .`。

## 验收（测试侧）

**P0 验收标准**已集成到 CI 流水线，详见 [TESTING.md](TESTING.md)：

1. **增量抓取**：各源产出内容，无源失败
2. **URL 去重**：数据库中无重复 URL
3. **字段完整性**：`title`/`url`/`source`/`fetched_at`/`status` 非空；`content_snapshot` 或 `summary` 至少一个有值
4. **抓取时效 SLA**：`published_at → fetched_at` ≤ 4h（允许 ≤10% 超时）
5. **高频去重**：连续两次抓取不产生重复

任一检查失败 → **workflow 失败（红）**

## GitHub Actions（P0）

- Workflow: `.github/workflows/daily-fetch.yml`
- 定时：`0 */4 * * *`（UTC，每 4 小时），也可手动 `workflow_dispatch`
- P0 时效：`published_at → fetched_at` ≤ 4h（单轮超时→警告；**连续两轮超时→红灯**）
  - 详见 [docs/SLA.md](docs/SLA.md)
- 聚合/专题：P1 `topic_id` 弱聚合 → P2 综述；本轮不做
- 注：讨论里的 `*/6 * * * *` 是每 6 分钟，按「4 小时一轮」落地为 `0 */4 * * *`
- 失败条件：任一源报错、入库后库为空、或连续两轮 latency 超时 → job 失败
- **数据持久化与 SLA 解耦**：
  - Persist 步骤只依赖 fetch 成功，**不受 latency 验证失败影响**
  - 即使 latency 连续失败（红灯），增量数据仍会写回 `data` 分支（丢数据不可接受）
  - **`data` 分支**：存放跨运行持久化的 `archive.sqlite3` 和 `LAST_RUN.json`（含 `latency_sla_passed` 状态用于连续检测）
  - **Artifacts**：每次运行额外上传 `data/archive.sqlite3` + `archive.jsonl` + `run-stats.json`（保留 90 天备份）
- 权限：workflow 需要 `contents: write` 以便 push 到 `data` 分支
- 仓库默认 **private**（`content_snapshot` 有版权风险）；要开源再单独评估可公开字段
- X 帖子仍为 P1，不在本 workflow

推到 GitHub 后在仓库 Settings → Actions 确认已启用；私有仓的 schedule 需要至少一次成功的 workflow 或手动触发来激活。

## 静态新闻浏览器（GitHub Pages）

只读网页版，展示归档数据（新闻 / 专题 / X / 日报），自动部署到 GitHub Pages。公开站点不含 RSS `content_snapshot` 全文，仅 summary + 原链 + 专题跳转 + 日报摘要。

日报在 `daily-fetch` 成功后软生成：需要 GitHub Actions Secrets `DAILY_BRIEF_API_KEY` 与 `DAILY_BRIEF_API_BASE`（腾讯云 LKEAP OpenAI 兼容）。默认模型 id 为 `deepseek/deepseek-flash`（可用环境变量 `DAILY_BRIEF_MODEL` 覆盖，**不是** Secret）。缺 key/base、模型错误或当日无稿时写入 `failed`/`empty`，**不打断** fetch/persist/Pages。当日已有 `status=ok` 且所选 RSS+X 指纹未变则跳过 LLM（含今天）。绝不把 Secret 值打进日志。同一上海日历日的 `x_posts`（白名单 `BBCChinese` / `Reuters` / `FT` / `TechCrunch` / `Tesla` / `elonmusk` / `AP` / `WSJ` / `BBCWorld` / `NPR` / `nytimes` / `TheEconomist` / `SCMPNews` / `Bloomberg` / `WIRED` / `AFP`、`status=active`）进入独立「X 动态」分组；无当日 X 帖则省略该节。LLM 只用库内 `author` / `text_snapshot` / `url` / `posted_at`，不调 X API。Cookie 登录账号须 Follow 这些 handle，HomeLatestTimeline / following 才能看到它们（运维说明，不是代码 Secret）。

- **访问**：`https://<username>.github.io/<repo>/`（需启用 Pages）
- **更新**：`daily-fetch` 完成后自动刷新（或手动触发 `deploy-pages` workflow）
- **本地预览**：
  ```bash
  python3 scripts/export_site_data.py  # 导出 JSON
  cd site && python3 -m http.server 8000
  # 访问 http://localhost:8000
  ```
- **详细文档**：见 [docs/SITE.md](docs/SITE.md)
