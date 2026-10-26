# 静态新闻浏览器

只读新闻浏览器，从 `data` 分支的 SQLite 归档导出 JSON，生成静态 HTML+JS 并部署到 GitHub Pages。

## 产品功能（CEO 锁定）

### 四个 Tab

1. **新闻** (`/` 或 `#news`)
   - 列表：先按 `published_at` 倒序（缺失 / null / 空则回退 `fetched_at`），再计算展示序
   - **来源多样性**：展示位 1–50 内同一 `source` ≤ 6 条；被挤出的文章按时间序排在第 50 位之后（仍可滚动，总数不变）
   - **36氪快讯**：URL 含 `newsflashes` 显示「快讯」角标；进入前 50 展示位的快讯默认折成一行「快讯 N 条」，展开后列出
   - 非快讯优先占用来源上限名额（快讯不挤掉同源正式稿）
   - 展示：标题 / 来源 / 时间（同样优先 `published_at`，否则 `fetched_at`）/ 单行摘要
   - 详情：点击后展示 ≤280 字纯文本 `summary` + 原文链接（**不含** `content_snapshot` 全文）；时间字段与列表一致
   - 关联专题：若 `topic_id` 存在，显示「查看相关专题」链接
   - **X Tab 不套用上述展示序**

2. **专题** (`#topics`)
   - 常设 **科技/AI** 专题（`#topics/tech-ai`）始终排在第一：RSS 白名单 + AI 关键词 ∪ X 主/备账号。详情分栏「资讯 | X」；资讯上限 100，X 独立上限 30。规则见 [TECH_AI.md](TECH_AI.md)
   - 另展示 `topic_briefs` 中 `status=ok` 的专题
   - 卡片：专题标题 + 前 3 条来源标题（项目符号）
   - 详情：完整来源列表（标题 + 原文链接）；科技/AI 详情为「资讯 | X」分栏（窄屏上下堆叠）
   - **无 brief 的聚类专题不出现**（规则强制）；科技/AI 即使 0 条也保留卡片，避免「暂无专题」死胡同

3. **X** (`#x`)
   - 列表：X 帖子按 `posted_at` 倒序
   - 展示字段仅：`author` / `posted_at` / `fetched_at` / `text_snapshot` / `url` / `status`
   - gone 状态：变灰但快照仍可见
   - 点击：跳转原始 URL（新窗口）
   - **禁止**导出 Cookie / Authorization / headers / `post_id`

4. **日报** (`#daily`)
   - 默认上海日历「今天」；可切换近 7 日
   - `status=ok`：导语 + RSS 最多 8 个分组（优先已有 `topic_id`；未归类最多一个「其它」）
   - 当日 `x_posts`（`status=active`，白名单 `BBCChinese` / `Reuters` / `FT` / `TechCrunch` / `Tesla` / `elonmusk` / `AP` / `WSJ` / `BBCWorld` / `NPR` / `nytimes` / `TheEconomist` / `SCMPNews` / `Bloomberg` / `WIRED` / `AFP` / `CNBC` / `AJEnglish` / `Nature` / `SkyNews` / `ABC` / `CBSNews` / `axios` / `NikkeiAsia` / `politico`）按上海日历 `posted_at` 进入独立分组 **「X 动态」**（`topic_id` 固定 `"x-daily"`，不并入 RSS 聚类）；无当日 X 帖则整节省略（不是 failed）
   - 「X 动态」子弹 1–3 条（跨账号综述，不是一帖一条）；`links` ≤8，`source` 为作者；LLM/展示只用 `author` / `text_snapshot` / `url` / `posted_at`（截断后的 `text_snapshot` 来自 SQLite，不调 GraphQL / X API）
   - `status=empty` 或无记录：空态「当日暂无摘要」
   - `status=failed`：降级文案「当日摘要生成失败」（不打断 Pages）。**当天** failed/missing 必须让 daily-fetch 红灯，禁止绿洗
   - **新闻 Tab 不插日报 banner**
   - RSS 子弹从 title + summary 生成；**禁止**读/写 `content_snapshot`；公开 JSON 无 Cookie / Authorization / `post_id`
   - `input_fingerprint` 含当日 RSS 所选集合 **和** X selected set；**今天**同日 X/RSS 增删改会尝试重生成，失败则保留已有 ok（禁止 failed 覆盖 ok）。历史 ok 不再重生成，只回填 failed/missing
   - 公开导出：`site/data/daily_briefs.json`（无 `content_snapshot`、无内部 error、无 `input_fingerprint`）

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
# ✓ Exported D daily briefs
# ✓ Exported 科技/AI (rss=… x=…)

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
3. 检查四个 Tab（新闻 | 专题 | X | 日报）是否正常展示

### 故障排查

- **404 错误**：检查 Pages 是否已启用（Source: GitHub Actions）
- **空列表**：检查 `data` 分支是否存在 `archive.sqlite3`
- **加载失败**：查看浏览器控制台，确认 JSON 文件是否存在于 `data/` 目录

## 架构说明

```
news-archive/
├── site/                      # 静态网站源文件
│   ├── index.html             # 主页面（四个 Tab）
│   ├── app.js                 # 前端逻辑（加载 JSON + 渲染）
│   ├── style.css              # 样式（响应式 + 移动友好）
│   └── data/                  # 导出的 JSON（构建时生成）
│       ├── articles.json      # 所有文章（按 published_at desc，缺则 fetched_at；无 content_snapshot）
│       ├── topics.json        # 专题（仅 status=ok；科技/AI 常设卡在前）
│       ├── x_posts.json       # X 帖子（仅 author/posted_at/fetched_at/text_snapshot/url/status）
│       ├── daily_briefs.json  # 日报（ok/failed/empty；无 content_snapshot）
│       └── tech_ai.json       # 科技/AI 分栏（rss_items / x_items；无 content_snapshot / post_id）
├── scripts/
│   └── export_site_data.py    # 从 SQLite 导出 JSON
└── .github/workflows/
    └── deploy-pages.yml       # Pages 部署 workflow
```

### 数据流

```
[daily-fetch] → (daily_brief via DAILY_BRIEF_API_KEY + DAILY_BRIEF_API_BASE;
                     model default deepseek/deepseek-flash, override DAILY_BRIEF_MODEL;
                     today-first + retries; today failed/missing reds the run after Persist;
                     skip LLM when ok + selected RSS+X fingerprint unchanged, including today)
                     ↓
              data branch (archive.sqlite3)
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
- ❌ 修改 fetch/clustering/topic_briefs 规则、fetch SLA、来源筛选、people.cn 日期

## 测试清单（QA 用）

提交 PR 时，确认以下各项：

- [ ] 本地构建：`python scripts/export_site_data.py` 成功导出 JSON
- [ ] 本地预览：`cd site && python -m http.server 8000` 打开页面正常
- [ ] 新闻 Tab：列表显示、详情页（仅 summary + 原链，无全文快照）、返回列表、原文链接
- [ ] 新闻 Tab 展示位 1–50：任一 `source` ≤ 6；被挤出的仍在 50 位之后
- [ ] 36氪快讯：`newsflashes` URL 有「快讯」角标；前 50 快讯默认折行；非快讯 URL 无角标
- [ ] 展示序 fixture：`PYTHONPATH=src python3 tests/test_news_display.py`
- [ ] 专题 Tab：科技/AI 常设卡可打开；`#topics/tech-ai` 为「资讯 | X」分栏（X 上限 30）；无「暂无专题」死胡同；仅显示 status=ok 的聚类专题、来源列表、gone 标记变灰
- [ ] X Tab：帖子列表、作者/时间/文本、gone 变灰、原文链接
- [ ] 日报 Tab：默认今天（上海日历）、近 7 日切换、空态「当日暂无摘要」、failed 降级文案
- [ ] 当日有 X 帖：日报含且仅含一节「X 动态」；当日无 X：该节不出现；RSS 分组仍在
- [ ] 新闻 Tab **无**日报 banner
- [ ] `daily_briefs.json` / `articles.json` 均无 `content_snapshot`；日报/X 导出无 Cookie / Authorization / `post_id`
- [ ] 移动端：手机浏览器打开，布局适配、可滚动、无横向溢出
- [ ] 无登录入口：确认没有任何登录或注册按钮
- [ ] Pages 部署：workflow 成功运行、访问 URL 展示正确内容
- [ ] 软失败：删除 `data/archive.sqlite3` 后导出，生成空 JSON 但不报错
