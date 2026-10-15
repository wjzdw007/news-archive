# X Posts Fetching

X/Twitter 帖子抓取功能支持两种模式：

## 模式

### 1. Mock 模式（默认）
- 使用固定测试数据
- 不需要任何凭证
- 用于离线测试和 CI
- 始终返回确定性的模拟帖子

### 2. Live 模式（可选）
- 通过 X HTTP API 实时抓取
- 需要配置 X API 凭证（见下文）
- 自动降级：缺少凭证时 soft-fail（exit 0），不阻断 RSS workflow

## 配置 X API 凭证（Live 模式）

需要从 X/Twitter 网页版获取以下凭证：

### 所需 Secrets（GitHub Actions）

在 **Repository Settings → Secrets and variables → Actions** 中添加：

| Secret Name | 说明 | 获取方式 |
|-------------|------|----------|
| `X_BEARER_TOKEN` | X API Bearer token | 浏览器 DevTools → Network → 任意 GraphQL 请求 → Headers → `authorization` |
| `X_AUTH_TOKEN` | X 认证 cookie | 浏览器 DevTools → Application → Cookies → `auth_token` |
| `X_CT0_TOKEN` | X CSRF token cookie | 浏览器 DevTools → Application → Cookies → `ct0` |
| `X_CSRF_TOKEN` | X CSRF header（可选） | 通常与 `ct0` 相同 |

### 本地开发环境变量

```bash
export X_BEARER_TOKEN="Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D..."
export X_AUTH_TOKEN="your_auth_token_from_cookie"
export X_CT0_TOKEN="your_ct0_token_from_cookie"
export X_CSRF_TOKEN="your_ct0_token_from_cookie"  # 可选，默认使用 ct0
```

## 使用

### CLI

```bash
# Mock 模式（默认）
PYTHONPATH=src python -m news_archive.x_cli --db data/x_posts.sqlite3 --mode mock

# Live 模式（需要环境变量）
PYTHONPATH=src python -m news_archive.x_cli --db data/x_posts.sqlite3 --mode live

# 输出 JSON 格式统计
PYTHONPATH=src python -m news_archive.x_cli --db data/x_posts.sqlite3 --mode live --json
```

### GitHub Actions Workflow

`.github/workflows/x-fetch.yml` 会自动检测凭证：
- **有凭证**：使用 live 模式抓取真实帖子
- **无凭证**：降级到 mock 模式，不会 fail（soft-fail）

数据持久化到 `data` 分支（与 RSS 独立，使用 `data/x_posts.sqlite3`）。

## 数据库隔离

- **RSS 文章**：`data/archive.sqlite3`（主 workflow）
- **X 帖子**：`data/x_posts.sqlite3`（X workflow）
- 两个 DB 文件可共存，互不干扰

## 参考实现

参考了 [x-crawler](https://github.com/wjzdw007/x-crawler) 的认证与抓取模式：
- HTTP 直接调用 X GraphQL API（无需 Grok Bot MCP）
- Bearer token + cookies 认证
- UserTweets endpoint 获取用户时间线

## Soft-Fail 设计

X 抓取失败**不会**阻断 RSS daily-fetch：
- 两个 workflow 完全独立（`x-fetch.yml` vs `daily-fetch.yml`）
- X CLI 默认 soft-fail（`--hard-fail` 可开启严格模式）
- Workflow 缺少凭证时自动降级 mock，exit 0

## Bot MCP 作为可选后备

文档仍保留 Grok Bot MCP 路径作为**可选方案**，但不是主要路径：
- 主路径：HTTP API + env secrets（本实现）
- 后备路径：Grok Bot MCP（需额外配置，docs only）

推荐使用 HTTP API 路径，更轻量且无 MCP 依赖。
