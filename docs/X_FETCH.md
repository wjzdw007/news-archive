# X Posts Fetching

X/Twitter 帖子抓取功能支持两种模式，**严格遵循 [x-crawler](https://github.com/wjzdw007/x-crawler) 认证和抓取模式**。

## 实现路径

### x-crawler 模式（唯一支持路径）

1. **HomeLatestTimeline / HomeTimeline** GraphQL endpoint
   - Query ID: `1_nms9JVtHQxTw8VwZJciQ` (HomeTimeline, **default following**)
   - Query ID: `xNGIIoXaz9DyeBXBfn3AjA` (HomeLatestTimeline, recommended)
   - Query ID: `1_nms9JVtHQxTw8VwZJciQ` (HomeTimeline, following)
   - 来源：x-crawler `crawler.py` lines 40-42

2. **认证方式**（x-crawler `config_loader.py` + `crawler.py`）：
   - **必需**: Cookies (`auth_token`, `ct0`)
   - **推荐**: Headers (`Authorization` Bearer, `X-Csrf-Token`)
   - 从浏览器 DevTools 提取（见下文）

3. **抓取逻辑**（x-crawler `crawler.py` crawl_daily_posts + save_by_user_daily）：
   - 抓取 home timeline（推荐/关注流）
   - 过滤出目标账号帖子：`BBCChinese`, `Reuters`, `FT`, `TechCrunch`
   - 去重并持久化到 SQLite

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

数据持久化到 `data` 分支的 `archive.sqlite3`（与 RSS 文章共享同一 DB）。

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

## 参考实现

严格遵循 [x-crawler](https://github.com/wjzdw007/x-crawler) 的认证与抓取模式：
- `crawler.py` lines 40-42: GraphQL query IDs（HomeLatestTimeline / HomeTimeline）
- `config_loader.py` lines 59-65: 认证配置加载（cookies + headers）
- `crawler.py` lines 660-720: Home timeline 抓取 + 用户过滤模式

**关键差异**：
- x-crawler 从 `user_prompt_templates.json` 读取关注用户列表
- news-archive 硬编码 4 个新闻账号：`BBCChinese`, `Reuters`, `FT`, `TechCrunch`

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
