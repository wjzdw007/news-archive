# SLA 策略

## Latency SLA（P0）

- 指标仍是本轮增量的 published_at → fetched_at ≤ 4h（缺 published_at / >24h 旧稿 / 品牌新源首次入库回填跳过）
- 单轮或个位数超窗 → 告警，不红灯、不挡 run
- 连续两轮整体超时（large-N，checked ≥ 10 且 >10%）→ 红灯
- 单轮 WARN **保持** `latency_sla_passed=true`，只把 `latency_soft_miss=true` 写入 `LAST_RUN.json`。下一轮 large-N 再超窗才硬失败。一次 soft miss 不能把 persist / 流水线打成红灯。
- 新源首次回填不进分母，也不会单独把 `latency_soft_miss` 打成 true
- 兼容旧 `LAST_RUN`（无 `latency_soft_miss` 字段、仅有 `latency_sla_passed=false`，例如 run 39299196711）：仍视为上一轮 miss，避免部署窗口丢掉已武装的连续检测

## Persist 与 SLA 解耦

- 校验再红也必须落库；禁止因 latency 跳过 Persist（丢增量不可接受）

## 实现机制

### 连续检测

1. **状态记录**：每次运行在 `data/LAST_RUN.json` 中记录：
   - `latency_sla_passed`：本轮 job 级结果（true，除非连续两轮 large-N 硬失败）
   - `latency_soft_miss`：本轮是否 large-N >10% 超窗（供下一轮连续判定）
2. **读取历史**：下一轮运行从 `data` 分支读取上一轮 `LAST_RUN.json`
3. **判定逻辑**：
   - 当前轮 large-N 超窗 + 上一轮无 miss → **WARN**（打印警告，exit 0，`passed=true`，`soft_miss=true`）
   - 当前轮 large-N 超窗 + 上一轮 miss（`latency_soft_miss=true` 或旧格式 `passed=false`）→ **FAIL**（红灯，exit 1）
   - 当前轮通过 → **PASS**（`passed=true`，`soft_miss=false`，清除连续失败）
   - small-N（checked < 10）永远 WARN，且不写 `soft_miss`

### Persist 解耦

- **触发条件**：`if: always() && steps.fetch.outcome == 'success' && hashFiles('data/archive.sqlite3') != ''`
- **不依赖 validate**：只要 fetch 成功且数据库存在，就执行 Persist
- **保障数据安全**：即使 latency 连续两轮失败（红灯），增量数据仍会写回 `data` 分支

### Workflow 步骤顺序与超时预算

Job `timeout-minutes: 45`（87 源串行 + 日报 LLM 曾打满旧的 30m cap：runs 39243037763 / 39340262352）。

1. **Restore SQLite** → 从 `data` 分支恢复数据库（含上一轮 `LAST_RUN.json`）
2. **Fetch feeds** → 并行 RSS（8 workers）、单源 15s×3 次重试（#53 soft-fail）、RSS 波次 600s 墙钟；剩余源 soft-fail，已完成源仍入库。密集源（Electrek/36kr 风格）每源最多入 30 条。
3. **Run validation** → P0 验收检查（含 latency 连续检测），输出 `validation-meta.json`（`latency_sla_passed` + `latency_soft_miss`）
4. **Generate daily brief** → `continue-on-error`，步骤 8 分钟 + CLI `--deadline-seconds 300`；超时跳过剩余日期，不覆盖已有 ok 日报，不挡 Persist
5. **Persist SQLite** → 写回 `data` 分支（含新的 `LAST_RUN.json`）
6. **Test dedup / enrich / required fields / RSS soft-fail / latency consecutive**
7. **Upload artifact** → 备份数据库/JSONL/stats（90 天）

## 测试验证

参见 [TESTING.md](../TESTING.md) 中的「Latency SLA 连续检测测试」章节。
