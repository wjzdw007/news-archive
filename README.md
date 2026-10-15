# news-archive

每天从稳定 RSS 抓取中文新闻，按 URL 去重后永久存档，schema 对 AI 友好。

## P0 源（8 主力含国际 + 1 官方对照）

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
| `people_finance` | 人民网·财经 | https://www.people.com.cn/rss/finance.xml | control |

## Schema

`title` / `published_at` / `url` / `summary` / `source` / `fetched_at` / `content_snapshot` / `status`

- 主键 / 去重键：`url`
- `content_snapshot`：入库时快照（优先 RSS `content:encoded`，否则 summary），链接失效后本地仍可读
- `status`：`active` | `gone`（后续探测不可达时标记，不删记录）
- 存储：SQLite（可导出 JSONL）
- X 帖子：P1（按 post id 去重 + 快照），不挡本轮 RSS 底座

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
- P0 时效：`published_at → fetched_at` ≤ 4h（允许调度漂移；连续两轮超时再红）
- 聚合/专题：P1 `topic_id` 弱聚合 → P2 综述；本轮不做
- 注：讨论里的 `*/6 * * * *` 是每 6 分钟，按「4 小时一轮」落地为 `0 */4 * * *`
- 失败即红：任一源报错或入库后库为空 → job 失败
- 数据：`data/archive.sqlite3` + `archive.jsonl` 走 **artifact**（保留 90 天），不往主分支狂推大文件
- 仓库默认 **private**（`content_snapshot` 有版权风险）；要开源再单独评估可公开字段
- X 帖子仍为 P1，不在本 workflow

推到 GitHub 后在仓库 Settings → Actions 确认已启用；私有仓的 schedule 需要至少一次成功的 workflow 或手动触发来激活。
