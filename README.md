# news-archive

每天从稳定 RSS 抓取中文新闻，按 URL 去重后永久存档，schema 对 AI 友好。

## P0 源（116 主力含国际 / 亚太 / 中国 / EV / 硬科技 / 财经 / 科学 + 1 官方对照）

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
| `economist_china` | The Economist China | https://www.economist.com/china/rss.xml | primary |
| `bbc_asia` | BBC Asia | https://feeds.bbci.co.uk/news/world/asia/rss.xml | primary |
| `verge` | The Verge | https://www.theverge.com/rss/index.xml | primary |
| `axios` | Axios | https://api.axios.com/feed/ | primary |
| `npr_news` | NPR News | https://feeds.npr.org/1001/rss.xml | primary |
| `japan_times` | Japan Times | https://www.japantimes.co.jp/feed/ | primary |
| `sky_world` | Sky News World | https://feeds.skynews.com/feeds/rss/world.xml | primary |
| `lemonde` | Le Monde | https://www.lemonde.fr/rss/une.xml | primary |
| `cbs_news` | CBS News | https://www.cbsnews.com/latest/rss/main | primary |
| `dw_en` | Deutsche Welle (EN) | https://rss.dw.com/rdf/rss-en-all | primary |
| `rfi_en` | RFI English | https://www.rfi.fr/en/rss | primary |
| `bbc_europe` | BBC Europe | https://feeds.bbci.co.uk/news/world/europe/rss.xml | primary |
| `abc_news` | ABC News | https://abcnews.go.com/abcnews/topstories | primary |
| `bbc_us_canada` | BBC US & Canada | https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml | primary |
| `wired` | WIRED | https://www.wired.com/feed/rss | primary |
| `npr_world` | NPR World | https://feeds.npr.org/1004/rss.xml | primary |
| `guardian_us` | Guardian US | https://www.theguardian.com/us-news/rss | primary |
| `bbc_middle_east` | BBC Middle East | https://feeds.bbci.co.uk/news/world/middle_east/rss.xml | primary |
| `bbc_africa` | BBC Africa | https://feeds.bbci.co.uk/news/world/africa/rss.xml | primary |
| `nyt_science` | NYT Science | https://rss.nytimes.com/services/xml/rss/nyt/Science.xml | primary |
| `guardian_environment` | Guardian Environment | https://www.theguardian.com/environment/rss | primary |
| `bbc_latin_america` | BBC Latin America | https://feeds.bbci.co.uk/news/world/latin_america/rss.xml | primary |
| `nyt_climate` | NYT Climate | https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml | primary |
| `guardian_business` | Guardian Business | https://www.theguardian.com/uk/business/rss | primary |
| `bbc_health` | BBC Health | https://feeds.bbci.co.uk/news/health/rss.xml | primary |
| `nyt_health` | NYT Health | https://rss.nytimes.com/services/xml/rss/nyt/Health.xml | primary |
| `straitstimes_world` | Straits Times World | https://www.straitstimes.com/news/world/rss.xml | primary |
| `guardian_science` | Guardian Science | https://www.theguardian.com/science/rss | primary |
| `bbc_china` | BBC China | https://feeds.bbci.co.uk/news/world/asia/china/rss.xml | primary |
| `guardian_australia` | Guardian Australia | https://www.theguardian.com/australia-news/rss | primary |
| `bbc_education` | BBC Education | https://feeds.bbci.co.uk/news/education/rss.xml | primary |
| `guardian_americas` | Guardian Americas | https://www.theguardian.com/world/americas/rss | primary |
| `nyt_education` | NYT Education | https://rss.nytimes.com/services/xml/rss/nyt/Education.xml | primary |
| `guardian_uk` | Guardian UK | https://www.theguardian.com/uk-news/rss | primary |
| `guardian_europe` | Guardian Europe | https://www.theguardian.com/world/europe-news/rss | primary |
| `nyt_politics` | NYT Politics | https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml | primary |
| `bbc_uk` | BBC UK | https://feeds.bbci.co.uk/news/uk/rss.xml | primary |
| `nyt_us` | NYT US | https://rss.nytimes.com/services/xml/rss/nyt/US.xml | primary |
| `guardian_global_dev` | Guardian Global Development | https://www.theguardian.com/global-development/rss | primary |
| `bbc_politics` | BBC Politics | https://feeds.bbci.co.uk/news/politics/rss.xml | primary |
| `nyt_europe` | NYT Europe | https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml | primary |
| `guardian_law` | Guardian Law | https://www.theguardian.com/law/rss | primary |
| `guardian_society` | Guardian Society | https://www.theguardian.com/society/rss | primary |
| `bbc_scotland` | BBC Scotland | https://feeds.bbci.co.uk/news/scotland/rss.xml | primary |
| `guardian_cities` | Guardian Cities | https://www.theguardian.com/cities/rss | primary |
| `guardian_world_africa` | Guardian World Africa | https://www.theguardian.com/world/africa/rss | primary |
| `guardian_politics` | Guardian Politics | https://www.theguardian.com/politics/rss | primary |
| `bbc_wales` | BBC Wales | https://feeds.bbci.co.uk/news/wales/rss.xml | primary |
| `bbc_england` | BBC England | https://feeds.bbci.co.uk/news/england/rss.xml | primary |
| `nyt_upshot` | NYT The Upshot | https://rss.nytimes.com/services/xml/rss/nyt/Upshot.xml | primary |
| `france24_en` | France 24 English | https://www.france24.com/en/europe/rss | primary |
| `bbc_northern_ireland` | BBC Northern Ireland | https://feeds.bbci.co.uk/news/northern_ireland/rss.xml | primary |
| `guardian_middle_east` | Guardian Middle East | https://www.theguardian.com/world/middleeast/rss | primary |
| `euronews` | Euronews English | https://www.euronews.com/rss?level=theme&name=news | primary |
| `nyt_africa` | NYT Africa | https://rss.nytimes.com/services/xml/rss/nyt/Africa.xml | primary |
| `smh_world` | Sydney Morning Herald World | https://www.smh.com.au/rss/world.xml | primary |
| `nbc_world` | NBC News World | https://feeds.nbcnews.com/nbcnews/public/world | primary |
| `csmonitor_world` | Christian Science Monitor World | https://rss.csmonitor.com/feeds/world | primary |
| `latimes_world` | LA Times World | https://www.latimes.com/world-nation/rss2.0.xml | primary |
| `hindu_international` | The Hindu International | https://www.thehindu.com/news/international/feeder/default.rss | primary |
| `cbc_world` | CBC World | https://www.cbc.ca/webfeed/rss/rss-world | primary |
| `cna_asia` | Channel NewsAsia Asia | https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511 | primary |
| `elpais_en` | El País English | https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada | primary |
| `yonhap` | Yonhap English | https://en.yna.co.kr/RSS/news.xml | primary |
| `anadolu_world` | Anadolu Agency World | https://www.aa.com.tr/en/rss/default?cat=world | primary |
| `trt_world` | TRT World | https://www.trtworld.com/feed/rss.xml | primary |
| `semafor` | Semafor | https://www.semafor.com/rss.xml | primary |
| `france24_americas` | France 24 Americas | https://www.france24.com/en/americas/rss | primary |
| `middleeasteye` | Middle East Eye | https://www.middleeasteye.net/rss | primary |
| `scmp_business` | SCMP Business | https://www.scmp.com/rss/92/feed | primary |
| `rfi_asia` | RFI Asia-Pacific | https://www.rfi.fr/en/tag/asia/rss | primary |
| `theconversation` | The Conversation | https://theconversation.com/articles.atom | primary |
| `nyt_arts` | NYT Arts | https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml | primary |
| `guardian_sport` | Guardian Sport | https://www.theguardian.com/sport/rss | primary |
| `intercept` | The Intercept | https://theintercept.com/feed/ | primary |
| `nyt_opinion` | NYT Opinion | https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml | primary |
| `guardian_film` | Guardian Film | https://www.theguardian.com/film/rss | primary |
| `propublica` | ProPublica | https://www.propublica.org/feeds/propublica/main | primary |
| `forbes_innovation` | Forbes Innovation | https://www.forbes.com/innovation/feed/ | primary |
| `dw_world` | Deutsche Welle World | https://rss.dw.com/rdf/rss-en-world | primary |
| `rfi_americas` | RFI Americas | https://www.rfi.fr/en/tag/latin-america/rss | primary |
| `nyt_movies` | NYT Movies | https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml | primary |
| `guardian_music` | Guardian Music | https://www.theguardian.com/music/rss | primary |
| `guardian_stage` | Guardian Stage | https://www.theguardian.com/stage/rss | primary |
| `nyt_books` | NYT Books | https://rss.nytimes.com/services/xml/rss/nyt/Books.xml | primary |
| `guardian_books` | Guardian Books | https://www.theguardian.com/books/rss | primary |
| `npr_arts` | NPR Arts | https://feeds.npr.org/1008/rss.xml | primary |
| `nyt_food` | NYT Food | https://rss.nytimes.com/services/xml/rss/nyt/DiningandWine.xml | primary |
| `guardian_tv` | Guardian TV | https://www.theguardian.com/tv-and-radio/rss | primary |
| `npr_science` | NPR Science | https://feeds.npr.org/1007/rss.xml | primary |
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
- P0 时效：`published_at → fetched_at` ≤ 4h（单轮超时→警告且 `latency_sla_passed` 仍为 true；**连续两轮 large-N 超时→红灯**）
  - 详见 [docs/SLA.md](docs/SLA.md)
- 聚合/专题：P1 `topic_id` 弱聚合 → P2 综述；本轮不做
- 注：讨论里的 `*/6 * * * *` 是每 6 分钟，按「4 小时一轮」落地为 `0 */4 * * *`
- 失败条件：任一源报错、入库后库为空、或连续两轮 latency 超时 → job 失败
- **数据持久化与 SLA 解耦**：
  - Persist 步骤只依赖 fetch 成功，**不受 latency 验证失败影响**
  - 即使 latency 连续失败（红灯），增量数据仍会写回 `data` 分支（丢数据不可接受）
  - **`data` 分支**：存放跨运行持久化的 `archive.sqlite3` 和 `LAST_RUN.json`（含 `latency_sla_passed` + `latency_soft_miss` 用于连续检测）
  - **Artifacts**：每次运行额外上传 `data/archive.sqlite3` + `archive.jsonl` + `run-stats.json`（保留 90 天备份）
- 权限：workflow 需要 `contents: write` 以便 push 到 `data` 分支
- 仓库默认 **private**（`content_snapshot` 有版权风险）；要开源再单独评估可公开字段
- X 帖子仍为 P1，不在本 workflow

推到 GitHub 后在仓库 Settings → Actions 确认已启用；私有仓的 schedule 需要至少一次成功的 workflow 或手动触发来激活。

## 静态新闻浏览器（GitHub Pages）

只读网页版，展示归档数据（新闻 / 专题 / X / 日报），自动部署到 GitHub Pages。公开站点不含 RSS `content_snapshot` 全文，仅 summary + 原链 + 专题跳转 + 日报摘要。

日报在 `daily-fetch` 成功后软生成：需要 GitHub Actions Secrets `DAILY_BRIEF_API_KEY` 与 `DAILY_BRIEF_API_BASE`（腾讯云 LKEAP OpenAI 兼容）。默认模型 id 为 `deepseek/deepseek-flash`（可用环境变量 `DAILY_BRIEF_MODEL` 覆盖，**不是** Secret）。缺 key/base、模型错误或当日无稿时写入 `failed`/`empty`，**不打断** fetch/persist/Pages。当日已有 `status=ok` 且所选 RSS+X 指纹未变则跳过 LLM（含今天）。绝不把 Secret 值打进日志。同一上海日历日的 `x_posts`（白名单 `BBCChinese` / `Reuters` / `FT` / `TechCrunch` / `Tesla` / `elonmusk` / `AP` / `WSJ` / `BBCWorld` / `NPR` / `nytimes` / `TheEconomist` / `SCMPNews` / `Bloomberg` / `WIRED` / `AFP` / `CNBC` / `AJEnglish` / `Nature` / `SkyNews` / `ABC` / `CBSNews` / `axios` / `NikkeiAsia` / `politico`、`status=active`）进入独立「X 动态」分组；无当日 X 帖则省略该节。LLM 只用库内 `author` / `text_snapshot` / `url` / `posted_at`，不调 X API。Cookie 登录账号须 Follow 这些 handle，HomeLatestTimeline / following 才能看到它们（运维说明，不是代码 Secret）。

- **访问**：`https://<username>.github.io/<repo>/`（需启用 Pages）
- **更新**：`daily-fetch` 完成后自动刷新（或手动触发 `deploy-pages` workflow）
- **本地预览**：
  ```bash
  python3 scripts/export_site_data.py  # 导出 JSON
  cd site && python3 -m http.server 8000
  # 访问 http://localhost:8000
  ```
- **详细文档**：见 [docs/SITE.md](docs/SITE.md)
