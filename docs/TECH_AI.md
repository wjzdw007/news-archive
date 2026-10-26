# 科技/AI 专题（MVP）

常设专题，挂在现有 **专题** Tab（`#topics/tech-ai`）。RSS ∪ X 按时间倒序合并。无 LLM。新闻 Tab 的 `NEWS_SOURCE_CAP=6` 不变。

## RSS 白名单

只收录已注册源。专题页不会出现白名单外的 `source`。

### 直接收录（科技 / 硬科技 / 科技商业）

| id | 源 |
|---|---|
| `36kr` | 36氪 |
| `tmtpost` | 钛媒体 |
| `geekpark` | 极客公园 |
| `solidot` | Solidot |
| `ifanr` | 爱范儿 |
| `verge` | The Verge |
| `wired` | WIRED |
| `techcrunch` | TechCrunch |
| `mit_tr` | MIT Technology Review |
| `bbc_technology` | BBC Technology |
| `nyt_technology` | NYT Technology |
| `guardian_technology` | Guardian Technology |
| `ars_technica` | Ars Technica |
| `forbes_innovation` | Forbes Innovation |

### 关键词过滤（科学 / 财经等宽源）

标题或摘要命中下方关键词才入专题：

`bbc_science` · `nyt_science` · `guardian_science` · `npr_science` · `bbc_business` · `nyt_business` · `nyt_economy` · `cnbc_top` · `scmp_business` · `ftchinese` · `theconversation` · `axios` · `bloomberg_markets`

## AI 关键词

英文（词边界 / 短语，不用裸 `ML`）：

`AI` / `A.I.` · `AGI` · `LLM(s)` · `GPT` · `OpenAI` · `Anthropic` · `Claude` · `Gemini` · `DeepMind` · `xAI` · `Grok` · `ChatGPT` · `Copilot` · `Nvidia` · `Hugging Face` · `machine learning` · `deep learning` · `neural network` · `foundation model` · `generative AI/model` · `Mistral` · `Cohere` · `Karpathy` · `LeCun` · `Hassabis` · `Sam Altman` · `Sora` · `DALL-E` · `DeepSeek`

中文（子串）：

人工智能 · 生成式 · 大模型 · 大语言模型 · 机器学习 · 深度学习 · 智能体 · 算力 · 英伟达 · 深度求索 · 通义 · 文心 · 豆包 · 智谱 · 月之暗面

## X 账号

走现有 `x-fetch`（与新闻账号同一套 Cookie / Bearer Secrets，不新增 Secret）。

**主账号**：`OpenAI` · `AnthropicAI` · `xai` · `elonmusk` · `GoogleDeepMind` · `AIatMeta` · `nvidia` · `huggingface` · `karpathy` · `sama` · `demishassabis` · `ylecun`

**备用**（仅当主账号在窗口内无可用帖才抓取 / 上页）：`AndrewYNg` · `miramurati` · `gdb` · `MistralAI` · `cohere`

AI 主/备账号走 **UserByScreenName + UserTweets**（按账号 timeline），**不必 Follow**。新闻 X 账号仍走 HomeTimeline + filter。

专题页 `MAX=100` 混排时预留 **25** 个 X 槽（约 25%）：有 X 帖时 RSS 最多占 75，避免 RSS 把 X 挤成 0。无 X 帖时 RSS 可用满 100，页上显示 X 空态提示（不是静默 0）。

## 时效

- 优先近 24 小时（`published_at` / `posted_at`，缺则 `fetched_at`）
- 窗口为空则回退最近 7 天，并在页上说明「近 24 小时暂无新条目」
- 仍为空：专题卡 + 页内提示仍在，不是「暂无专题」死胡同
- RSS 靠 `daily-fetch`；X 靠现有 `x-fetch`（当前 cron 每 4 小时）

## 本地验证

```bash
PYTHONPATH=src python tests/test_tech_ai.py
PYTHONPATH=src python tests/test_tech_ai_ui.py
PYTHONPATH=src python tests/test_site_export.py
PYTHONPATH=src python tests/test_news_display.py   # CAP=6 仍为 6
python3 scripts/export_site_data.py
cd site && python3 -m http.server 8000
# 打开 http://localhost:8000/#topics/tech-ai
```

公开 JSON（`articles.json` / `topics.json` / `x_posts.json` / `tech_ai.json`）不得含 `content_snapshot` 或 X `post_id`。
