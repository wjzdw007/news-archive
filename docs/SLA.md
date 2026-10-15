# SLA 策略

## Latency SLA（P0）

- 指标仍是本轮增量的 published_at → fetched_at ≤ 4h（缺 published_at / >24h 旧稿跳过）
- 单轮或个位数超窗 → 告警，不红灯、不挡 run
- 连续两轮整体超时 → 红灯

## Persist 与 SLA 解耦

- 校验再红也必须落库；禁止因 latency 跳过 Persist（丢增量不可接受）

## 实现机制

### 连续检测

1. **状态记录**：每次运行在 `data/LAST_RUN.json` 中记录 `latency_sla_passed` 字段（true/false）
2. **读取历史**：下一轮运行从 `data` 分支读取上一轮的 `latency_sla_passed` 状态
3. **判定逻辑**：
   - 当前轮失败 + 上一轮通过 → **WARN**（打印警告，exit 0，继续运行）
   - 当前轮失败 + 上一轮失败 → **FAIL**（红灯，exit 1，阻塞流水线）
   - 当前轮通过 → **PASS**（正常，清除连续失败计数）

### Persist 解耦

- **触发条件**：`if: always() && steps.fetch.outcome == 'success' && hashFiles('data/archive.sqlite3') != ''`
- **不依赖 validate**：只要 fetch 成功且数据库存在，就执行 Persist
- **保障数据安全**：即使 latency 连续两轮失败（红灯），增量数据仍会写回 `data` 分支

### Workflow 步骤顺序

1. **Restore SQLite** → 从 `data` 分支恢复数据库（含上一轮 `LAST_RUN.json`）
2. **Fetch feeds** → 抓取 RSS、去重、入库
3. **Run validation** → P0 验收检查（含 latency 连续检测），输出 `validation-meta.json`
4. **Persist SQLite** → 写回 `data` 分支（含新的 `LAST_RUN.json`，包含本轮 `latency_sla_passed` 状态）
5. **Test dedup** → 高频去重单元测试
6. **Upload artifact** → 备份数据库/JSONL/stats（90 天）

## 测试验证

参见 [TESTING.md](../TESTING.md) 中的「Latency SLA 连续检测测试」章节。
