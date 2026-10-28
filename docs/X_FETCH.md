# X Posts Fetching

X/Twitter 帖子抓取功能支持两种模式，**严格遵循 [x-crawler](https://github.com/wjzdw007/x-crawler) 认证和抓取模式**。

## 实现路径

### 双路径（同一套 Cookie / Bearer，不新增 Secret）

1. **新闻账号 — HomeLatestTimeline / HomeTimeline** GraphQL（x-crawler）
   - Query ID: `1_nms9JVtHQxTw8VwZJciQ` (HomeTimeline, **default following**)
   - Query ID: `xNGIIoXaz9DyeBXBfn3AjA` (HomeLatestTimeline, recommended)
   - 来源：x-crawler `crawler.py` lines 40-42
   - 抓 home timeline，再过滤 `X_NEWS_ACCOUNTS`

2. **科技/AI 账号 — UserByScreenName + UserTweets**（按 handle，不必 Follow）
   - `UserByScreenName` query ID: `AMIBMjtxEEATh4z8V9GtRg`（twitter-openapi）
   - `UserTweets` query ID: `7_KBXBpG0zBPRN6UCIV0-w`
   - 每个主账号 1 次 lookup + 1 次 timeline（约 20 条）
   - 备用账号仅当主账号在近 24h 窗口无可用帖时才请求
   - `since_id`：CLI 从 DB 读各 AI handle 最新 `post_id`，写入前丢掉更旧 snowflake（upsert 仍按 `post_id` 去重）

3. **认证方式**（x-crawler `config_loader.py` + `crawler.py`）：
   - **必需**: Cookies (`auth_token`, `ct0`)
   - **推荐**: Headers (`Authorization` Bearer, `X-Csrf-Token`)
   - 从浏览器 DevTools 提取（见下文）

## Author 字段解析

X 已将 `screen_name` 从 `user_results.result.legacy.screen_name` 迁移到 **`user_results.result.core.screen_name`**。

解析逻辑（`x_http_client.py:_parse_single_tweet`）：
1. 优先从 `user_results.result.core.screen_name` 获取（新位置）
2. Fallback 到 `user_results.result.legacy.screen_name`（旧位置）
3. 若都缺失，返回 `"unknown"`

## TweetWithVisibilityResults Unwrap

部分 timeline entry 的 tweet 被包装在 `TweetWithVisibilityResults` 中：

```json
{
  "result": {
    "__typename": "TweetWithVisibilityResults",
    "tweet": { "__typename": "Tweet", ... }
  }
}
```

`_parse_tweets_from_timeline` 自动展开该包装，提取内层 `Tweet` 对象。

## 诊断日志

抓取时输出两条日志（stderr）：

1. **HomeTimeline 过滤前**: 总条数 + author 分布（top 20）  
   → 用于诊断新闻路径：「目标账号未出现在 following feed」vs「author 解析挂了全变 unknown」

2. **HomeTimeline 过滤后**: 匹配新闻白名单的帖子数

3. **UserTweets**: 每 handle 条数；单账号失败 skip，429 中止剩余 AI handle（新闻帖仍保留）

示例：

```
[x-fetch] HomeTimeline: 38 tweets, author distribution (top 20): {"BBCChinese": 3, "Reuters": 2, "elonmusk": 5, "unknown": 1, ...}
[x-fetch] Filtered to 5 posts from target accounts: ['BBCChinese', 'Reuters', ...]
[x-fetch] UserTweets: 9 posts from 12 handles {"OpenAI": 2, "karpathy": 1, ...}
```

新闻过滤后为 0 且 `"unknown"` 占比高 → author 解析问题；  
新闻过滤后为 0 且无 `"unknown"` → following feed 暂无新闻白名单帖子。  
AI 路径不依赖 Follow；某 handle 0 条是该账号窗口空或 skip，不是改回 HomeTimeline 的理由。

## 模式

### 1. Mock 模式（默认）
- 使用固定测试数据
- 不需要任何凭证
- 用于离线测试和 CI

### 2. Live 模式（可选）
- 通过 X HTTP API 实时抓取（HomeLatestTimeline GraphQL）
- 需要配置 X API 凭证（见下文）
- 自动降级：缺少凭证时 soft-fail（exit 0），不阻断 RSS workflow

## 配置 X API 凭证（Live 模式）

需要从 X/Twitter 网页版获取以下凭证（x-crawler 模式）：

### 所需 Secrets（GitHub Actions）

在 **Repository Settings → Secrets and variables → Actions** 中添加：

| Secret Name | 必需性 | 说明 | 获取方式 |
|-------------|--------|------|----------|
| `X_AUTH_TOKEN` | **必需** | X 认证 cookie | 浏览器登录 X → DevTools → Application → Cookies → `.x.com` → `auth_token` |
| `X_CT0_TOKEN` | **必需** | X CSRF token cookie | 同上 → `ct0` |
| `X_BEARER_TOKEN` | 推荐 | Authorization Bearer header | DevTools → Network → 任意 GraphQL 请求 → Headers → `authorization` |
| `X_CSRF_TOKEN` | 可选 | X CSRF header | 通常与 `ct0` 相同，或从 Headers → `x-csrf-token` |

**最小配置**：`X_AUTH_TOKEN` + `X_CT0_TOKEN`  
**推荐配置**：上述 + `X_BEARER_TOKEN`（提高稳定性）

### 本地开发环境变量

```bash
export X_AUTH_TOKEN="your_auth_token_from_cookie"
export X_CT0_TOKEN="your_ct0_token_from_cookie"
export X_BEARER_TOKEN="Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D..."  # 推荐
export X_CSRF_TOKEN="your_ct0_token_from_cookie"  # 可选
```

## 使用

### CLI

```bash
# Mock 模式（默认）
PYTHONPATH=src python -m news_archive.x_cli --db data/archive.sqlite3 --mode mock

# Live 模式（需要环境变量）
PYTHONPATH=src python -m news_archive.x_cli --db data/archive.sqlite3 --mode live

# 输出 JSON 格式统计
PYTHONPATH=src python -m news_archive.x_cli --db data/archive.sqlite3 --mode live --json
```

### GitHub Actions Workflow

`.github/workflows/x-fetch.yml` 会自动检测凭证：
- **有凭证**（`X_AUTH_TOKEN` + `X_CT0_TOKEN`）：使用 live 模式抓取真实帖子
- **无凭证**：降级到 mock 模式，不会 fail（soft-fail）

数据持久化到 `data` 分支的 `archive.sqlite3.gz`（与 RSS 文章共享同一 DB；Restore 解压到 `data/archive.sqlite3`）。

## 数据库持久化

### 单一 DB 设计

- **RSS 文章** + **X 帖子** 共享 `data/archive.sqlite3`
- `articles` 表：RSS 文章（URL 去重）
- `x_posts` 表：X 帖子（post_id 去重）

### 迁移说明

**现有 79 条 X 帖子**（已在 `data` 分支 `archive.sqlite3` 中）：
- Schema 兼容：现有 `x_posts` 表结构与本实现完全一致
- 无需迁移：新抓取的帖子会追加到同一表，post_id 去重自动生效
- 状态保留：现有帖子的 `status` 字段（active/gone）不受影响

**验证方法**：
```bash
# 检查 data 分支现有数据
git checkout data
sqlite3 data/archive.sqlite3 "SELECT COUNT(*) FROM x_posts"  # 应显示 79+
git checkout main
```

## 测试

- `tests/test_x_posts.py`: mock/dedupe/soft-fail 测试
- `tests/test_x_http_client.py`: author 解析 + TweetWithVisibilityResults unwrap + UserTweets 按账号抓取（无网络，模拟 GraphQL 形状）
- `tests/test_x_import.py`: JSONL import 测试

## 参考实现

新闻路径遵循 [x-crawler](https://github.com/wjzdw007/x-crawler) 的认证与 HomeTimeline 模式：
- `crawler.py` lines 40-42: GraphQL query IDs（HomeLatestTimeline / HomeTimeline）
- `config_loader.py` lines 59-65: 认证配置加载（cookies + headers）
- `crawler.py` lines 660-720: Home timeline 抓取 + 用户过滤模式

AI 路径用同一认证，改为按账号 `UserTweets`（twitter-openapi queryId）。

**关键差异**：
- x-crawler 从 `user_prompt_templates.json` 读取关注用户列表
- news-archive 硬编码抓取账号：新闻白名单走 HomeTimeline；科技/AI 主/备走 UserTweets（见 `x_config`；专题规则见 [TECH_AI.md](TECH_AI.md)）

## Soft-Fail 设计

X 抓取失败**不会**阻断 RSS daily-fetch：
- 两个 workflow 完全独立（`x-fetch.yml` vs `daily-fetch.yml`）
- X CLI 默认 soft-fail（`--hard-fail` 可开启严格模式）
- Workflow 缺少凭证时自动降级 mock，exit 0

## Bot MCP 作为可选后备

文档仍保留 Grok Bot MCP 路径作为**可选方案**，但不是主要路径：
- **主路径**：HTTP API + env secrets（本实现，x-crawler 模式）
- **后备路径**：Grok Bot MCP（需额外配置，docs only）

推荐使用 HTTP API 路径，更轻量且无 MCP 依赖。

## 限制

- **不支持搜索**: 本配置仅按账号抓取，不做关键词搜索
- **新闻仍走 HomeTimeline**: Cookie 账号须 Follow 新闻白名单，following 窗口 (~40) 才能看到它们。未 follow → 该新闻账号本轮 0 条是 WARN
- **科技/AI 不依赖 Follow**: 主账号（及窗口内主账号全空时的备用）走 UserTweets
- **配额**: 每 4h 一轮：HomeTimeline ×1 + 主账号最多 12×(UserByScreenName+UserTweets)=24 次 GraphQL；handle 之间 pause 0.45s。备用最多再 +10 次，且仅主账号 24h 窗口为空时触发。429 时停 AI 剩余请求，保留已抓到的新闻帖
- **QueryId 稳定性**: HomeTimeline 用 x-crawler queryId；UserTweets / UserByScreenName 用 twitter-openapi。X 更新 API 时需改常量
