# 静态新闻浏览器

只读新闻浏览器，从 `data` 分支的 SQLite 归档导出 JSON，生成静态 HTML+JS 并部署到 GitHub Pages。

## 产品功能（CEO 锁定）

### 三个 Tab

1. **新闻** (`/` 或 `#news`)
   - 列表：按 `published_at` 倒序展示所有文章（缺失 / null / 空则回退 `fetched_at`）
   - 展示：标题 / 来源 / 时间（同样优先 `published_at`，否则 `fetched_at`）/ 单行摘要
   - 详情：点击后展示 `summary` + 原文链接（**不含** `content_snapshot` 全文）；时间字段与列表一致
   - 关联专题：若 `topic_id` 存在，显示「查看相关专题」链接

2. **专题** (`#topics`)
   - 仅展示 `topic_briefs` 中 `status=ok` 的专题
   - 卡片：专题标题 + 前 3 条来源标题（项目符号）
   - 详情：完整来源列表（标题 + 原文链接）
   - **无 brief 的专题不出现**（规则强制）

3. **X** (`#x`)
   - 列表：X 帖子按 `posted_at` 倒序
   - 展示字段仅：`author` / `posted_at` / `fetched_at` / `text_snapshot` / `url` / `status`
   - gone 状态：变灰但快照仍可见
   - 点击：跳转原始 URL（新窗口）
   - **禁止**导出 Cookie / Authorization / headers / `post_id`

### 约束

- **只读**：无搜索、无登录、无写 API
- **移动友好**：响应式布局，中文 UI 标签
- **软失败**：若 `data` 分支无 sqlite，导出空 JSON，Pages 构建不红

## 本地构建

### 前置条件

需要本地存在 `data/archive.sqlite3`（可从 `data` 分支下载）。

### 步骤

```bash
# 1. 导出 JSON 数据
python scripts/export_site_data.py

# 输出：
# ✓ Exported N articles
# ✓ Exported M topics (status=ok only)
# ✓ Exported K X posts

# 2. 查看生成的 JSON
ls -lh site/data/*.json

# 3. 本地预览（需要 HTTP 服务器）
cd site
python -m http.server 8000

# 访问 http://localhost:8000
```

**注意**：直接用 `file://` 打开 `index.html` 会因 CORS 策略导致 JSON 加载失败，必须用 HTTP 服务器。

## GitHub Pages 部署

### 私有仓库注意事项

- **私有仓库 Pages**：需要 GitHub Pro / Team / Enterprise 订阅
- **数据分支**：`data` 分支是 orphan 分支，仅存放 `archive.sqlite3`，不影响 main 分支

### 一次性设置

1. **启用 GitHub Pages**
   - 进入仓库 Settings → Pages
   - Source: **GitHub Actions**（不是 "Deploy from a branch"）
   - 保存

2. **检查 Workflow 权限**
   - Settings → Actions → General → Workflow permissions
   - 确认已启用 "Read and write permissions"（或至少 "Read repository contents and packages permissions"）
   - 勾选 "Allow GitHub Actions to create and approve pull requests"（可选，用于其他自动化）

### 触发部署

部署 workflow (`.github/workflows/deploy-pages.yml`) 会在以下情况触发：

1. **自动**：`daily-fetch` workflow 完成后（数据更新后自动刷新 Pages）
2. **手动**：在 Actions 页面点击 "Run workflow"
3. **Push main**：推送到 `main` 分支时

### 部署流程

```
[main 分支代码] + [data 分支 sqlite]
  ↓
export_site_data.py 导出 JSON
  ↓
site/* 静态文件 → _site/
  ↓
GitHub Pages (https://<username>.github.io/<repo>/)
```

### 验证部署

1. 部署成功后，在 Actions 页面查看 `deploy-pages` workflow 运行日志
2. 访问 Pages URL（在 Settings → Pages 中显示）
3. 检查三个 Tab 是否正常展示

### 故障排查

- **404 错误**：检查 Pages 是否已启用（Source: GitHub Actions）
- **空列表**：检查 `data` 分支是否存在 `archive.sqlite3`
- **加载失败**：查看浏览器控制台，确认 JSON 文件是否存在于 `data/` 目录

## 架构说明

```
news-archive/
├── site/                      # 静态网站源文件
│   ├── index.html             # 主页面（三个 Tab）
│   ├── app.js                 # 前端逻辑（加载 JSON + 渲染）
│   ├── style.css              # 样式（响应式 + 移动友好）
│   └── data/                  # 导出的 JSON（构建时生成）
│       ├── articles.json      # 所有文章（按 published_at desc，缺则 fetched_at；无 content_snapshot）
│       ├── topics.json        # 专题（仅 status=ok）
│       └── x_posts.json       # X 帖子（仅 author/posted_at/fetched_at/text_snapshot/url/status）
├── scripts/
│   └── export_site_data.py    # 从 SQLite 导出 JSON
└── .github/workflows/
    └── deploy-pages.yml       # Pages 部署 workflow
```

### 数据流

```
[daily-fetch] → data branch (archive.sqlite3)
                     ↓
[deploy-pages] → export JSON → static site → GitHub Pages
```

### 分离原则

- **数据层**（`data` 分支）：daily-fetch / x-fetch 持续更新
- **展示层**（Pages）：deploy-pages 读取 sqlite 快照，生成不可变静态站点
- **解耦**：Pages 挂掉不影响 daily-fetch；data 分支为空时 Pages 显示空列表（不红）

## 不涉及的功能

按照产品锁定，以下功能 **不在范围内**：

- ❌ 搜索功能
- ❌ 用户登录 / 权限管理
- ❌ 实时更新 / WebSocket
- ❌ 评论 / 点赞 / 收藏
- ❌ 后端 API / 数据库写入
- ❌ 修改 fetch/clustering/briefs 逻辑（仅读取结果）

## 测试清单（QA 用）

提交 PR 时，确认以下各项：

- [ ] 本地构建：`python scripts/export_site_data.py` 成功导出 JSON
- [ ] 本地预览：`cd site && python -m http.server 8000` 打开页面正常
- [ ] 新闻 Tab：列表显示、详情页（仅 summary + 原链，无全文快照）、返回列表、原文链接
- [ ] 专题 Tab：仅显示 status=ok 的专题、来源列表、gone 标记变灰
- [ ] X Tab：帖子列表、作者/时间/文本、gone 变灰、原文链接
- [ ] 移动端：手机浏览器打开，布局适配、可滚动、无横向溢出
- [ ] 无登录入口：确认没有任何登录或注册按钮
- [ ] Pages 部署：workflow 成功运行、访问 URL 展示正确内容
- [ ] 软失败：删除 `data/archive.sqlite3` 后导出，生成空 JSON 但不报错
