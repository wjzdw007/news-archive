# P0 验收标准与 CI 检查

本文档描述新闻归档系统的 P0 验收标准，以及 CI 如何自动化执行这些检查。

## 验收标准（Acceptance Criteria）

### 1. 增量抓取（Source Incremental）

**要求**：每个已配置的源应当定期产出新内容或在库中有存量文章。

**检查逻辑**：
- ❌ 任一源在抓取过程中报错 → 失败（红）
- ❌ 数据库完全为空 → 失败（红）
- ❌ 本轮 0 条插入 **且** 任一源返回 0 条 → 失败（红）
- ❌ 任一已配置源在数据库中历史总数为 0 → 失败（红）
- ✅ 所有源在库中都有内容 → 通过

**实施**：`validate.py::check_source_incremental()`

---

### 2. URL 去重（Duplicate Rate）

**要求**：数据库中不应存在重复的 URL（`url` 列有 `PRIMARY KEY` 约束）。

**检查逻辑**：
- ❌ 任何 URL 在表中出现 >1 次 → 失败（红）
- ✅ 所有 URL 唯一 → 通过

**实施**：`validate.py::check_duplicate_urls()`

---

### 3. 必填字段完整性（Required Fields）

**要求**：活跃（`status='active'`）文章的必填字段不得为空或 null。

**必填字段**：
- `title`
- `url`
- `source`
- `fetched_at`
- `status`
- `content_snapshot` **或** `summary`（两者都为空才算失败）

**检查逻辑**：
- ❌ 任一必填字段（`title`/`url`/`source`/`fetched_at`/`status`）有空值或 null → 失败（红）
- ❌ `content_snapshot` 和 `summary` 同时为空 → 失败（红）
- ✅ 所有活跃文章的必填字段均已填充 → 通过

**实施**：`validate.py::check_required_fields()`

---

### 4. 抓取时效 SLA（Fetch Latency）

**要求**：文章从发布到抓取的延迟应 ≤ 4 小时（`published_at → fetched_at`）。

**检查逻辑**：
- **只检查本次运行新插入的文章**（通过最新的 `fetched_at` 时间戳识别）
- 排除：`published_at` 缺失或解析失败的文章（不计入失败）
- 排除：发布时间 >24 小时的旧文章（再版内容）
- ❌ 超过 **10%** 的文章延迟 >4h → 失败（红）
- ✅ ≤10% 文章超时 → 通过

**说明**：
- **首次运行回填旧文章不在检查范围内**：首次全量抓取 RSS 源时，历史存量文章（如一周前发布的）会显示较大延迟，但这是预期行为。延迟 SLA 只衡量增量新内容的时效性。
- 10% 阈值允许偶发的调度延迟（GitHub Actions cron 漂移、源更新时间不均等）
- 若需要更严格的 SLA，可降低阈值或实施「连续两轮超时 → 红」策略（需持久化前轮统计，P1 优先级）

**实施**：`validate.py::check_fetch_latency()`

---

### 5. 高频去重（High-Frequency Dedup）

**要求**：短时间内连续运行抓取任务不应产生重复 URL。

**检查逻辑**：
1. 使用固定测试数据创建一组文章（包含唯一的 URL）
2. 第一次插入应成功插入所有文章
3. ✅ 第二次插入相同文章应插入 0 条（PRIMARY KEY 约束生效）→ 通过
4. ❌ 第二次插入 >0 条 → 失败（重复去重逻辑失效）

**场景**：
- 手动触发 + 定时触发重叠
- 失败重试
- 多并发运行（虽然 workflow 配置了 `cancel-in-progress: false`）

**实施**：`tests/test_dedup.py`（单元测试，使用种子数据，不依赖实时 RSS 源）

**注意**：此测试已从实时 RSS 抓取改为使用固定测试数据，以避免源在两次抓取之间发布新内容导致的误报失败。

---

## CI 集成（GitHub Actions）

### Workflow: `.github/workflows/daily-fetch.yml`

**运行时机**：
- 定时：`0 */4 * * *`（UTC 每 4 小时）
- 手动：`workflow_dispatch`

**数据持久化（Data Branch）**：

每次运行自动从 `data` 分支恢复并回写 `archive.sqlite3`：

1. **恢复阶段**（fetch 前）：
   - `git fetch origin data:data`
   - `git show data:data/archive.sqlite3 > data/archive.sqlite3`
   - 若 `data` 分支或文件不存在 → 从空数据库开始（首次运行正常）

2. **验证阶段**（fetch + P0 验收）

3. **持久化阶段**（验证成功后立即执行，在其他测试之前）：
   - Checkout `data` 分支（不存在则创建 orphan branch）
   - 将更新的 `data/archive.sqlite3` 和 `data/LAST_RUN.json` commit 并 push
   - 冲突处理：`git pull --rebase origin data` + 最多重试 3 次
   - 持续冲突 → 失败（红），需人工介入

4. **备份上传**：上传 Artifacts（独立于 data 分支，保留 90 天）

**关键约束**：
- **禁止 force-push**：并发运行时保留所有提交历史
- **main 分支无大文件**：`.gitignore` 已排除 `*.sqlite3`
- **Gone 状态持久化**：`status='gone'` 的 URL 在 `data` 分支数据库中保留
- **持久化优先**：数据库持久化在 P0 验收通过后立即执行，不等待后续单元测试（如 `test_dedup.py`），确保即使非关键测试失败也能创建/更新 `data` 分支

**检查步骤**：

#### 1. 运行 P0 验收验证
```yaml
- name: Run P0 acceptance validation
  id: validate
  run: |
    PYTHONPATH=src python -m news_archive.validate \
      --db data/archive.sqlite3 \
      --stats data/run-stats.json
```

- 执行所有上述 4 项检查（增量、去重、字段、时效）
- 任一失败 → **workflow 失败（红）**，不执行后续步骤

#### 2. 持久化数据库
```yaml
- name: Persist SQLite to data branch
  if: steps.validate.outcome == 'success'
  run: |
    # ... 详见完整 workflow
```

- **仅在 P0 验收通过后执行**
- 先于单元测试运行，确保验收通过的数据立即持久化
- 单元测试失败不会阻止数据库更新

#### 3. 测试高频去重
```yaml
- name: Test high-frequency dedup
  run: |
    PYTHONPATH=src python tests/test_dedup.py
```

- 使用种子测试数据（不依赖实时 RSS）运行两次插入
- 验证第二次插入为 0（PRIMARY KEY 约束）
- 失败 → **workflow 失败（红）**，但不影响已完成的数据持久化

---

## 本地运行

### 验收检查
```bash
# 安装依赖
pip install -r requirements.txt

# 抓取并生成统计
PYTHONPATH=src python -m news_archive \
  --db data/archive.sqlite3 \
  --export-jsonl data/archive.jsonl \
  --json | tee data/run-stats.json

# 运行 P0 验收
PYTHONPATH=src python -m news_archive.validate \
  --db data/archive.sqlite3 \
  --stats data/run-stats.json
```

### 高频去重测试
```bash
PYTHONPATH=src python tests/test_dedup.py
```

**注意**：此测试使用固定的种子数据，不需要网络连接或实时 RSS 源。测试验证 `INSERT OR IGNORE` 和 URL PRIMARY KEY 约束的正确性。

### 标记失效 URL

对持久化在 `data` 分支的数据库标记失效链接：

```bash
# Checkout data 分支
git fetch origin data:data
git checkout data

# 标记 URL 为 gone
PYTHONPATH=src python -m news_archive.mark_gone \
  --db data/archive.sqlite3 \
  --url "https://example.com/dead-link"

# 查看预览（dry-run）
PYTHONPATH=src python -m news_archive.mark_gone \
  --db data/archive.sqlite3 \
  --url "https://example.com/link1" \
  --url "https://example.com/link2" \
  --dry-run

# Commit 并 push 回 data 分支
git add data/archive.sqlite3
git commit -m "Mark gone URLs from manual probe"
git push origin data

# 返回 main
git checkout main
```

**说明**：
- `mark_gone` 工具直接调用 `Store.mark_gone(url)`，将 `status` 改为 `gone` 而不删除记录
- Gone 状态会持久化到 `data` 分支，后续运行的 `upsert()` 不会重新激活它
- 支持 `--dry-run` 预览将要标记的 URL

---

## 故障排查

### 验收失败场景

| 失败检查 | 可能原因 | 处理建议 |
|---------|---------|---------|
| Source Incremental | 源 RSS feed 不可达、返回 404/500 | 检查源健康状况；临时移除问题源或等待恢复 |
| Duplicate URLs | `upsert()` 逻辑错误、并发写入 | 检查 `store.py` 的 `INSERT OR IGNORE` 逻辑 |
| Required Fields | 上游 RSS 缺失 `<title>` / `<link>` | 检查 `fetch.py` 解析逻辑；过滤不完整条目 |
| Fetch Latency | 调度延迟 >4h、源发布延迟、时区解析错误 | 检查 Actions 运行历史；验证 `published_at` 解析 |
| High-Freq Dedup | `url` 主键约束失效、多进程写入冲突 | 检查数据库 schema；避免并发写入 |

### Actions 调试

```bash
# 查看最近运行
gh run list --workflow=daily-fetch.yml

# 查看失败日志
gh run view <run-id> --log-failed
```

---

## 未来改进（P1/P2）

- [ ] **连续两轮超时 → 红**：持久化前轮时效统计到 artifact，实现更严格 SLA
- [ ] **逐源时效监控**：按源拆分时效检查，精准定位慢源
- [ ] **自动降级**：连续失败的源自动标记为 `degraded`，不阻塞整体流水线
- [ ] **Slack/邮件告警**：失败时发送通知
- [ ] **增量检查增强**：检测「连续 N 轮某源 0 新增」的沉默故障
