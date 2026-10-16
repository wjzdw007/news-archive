# Bot-side X fetch (免 key)

GitHub Actions **cannot** call Grok Bot `x` MCP. This path runs on a Bot (程序老王), not in CI.

## Steps
1. `get_users_by_usernames` with `BBCChinese,Reuters,FT,TechCrunch,Tesla,elonmusk,AP,WSJ,BBCWorld,NPR,nytimes,TheEconomist,SCMPNews,Bloomberg,WIRED,AFP,CNBC,AJEnglish,Nature,SkyNews,ABC,CBSNews` → numeric ids
2. Per id: `get_users_posts` with `max_results=20`, `exclude=retweets,replies`
3. Map: `id`→`post_id`, username→`author`, `url`, `text`→`text_snapshot`, `created_at`→`posted_at`
4. Write JSONL, then:
   `PYTHONPATH=src python -m news_archive.x_cli --import-jsonl path.jsonl [--mark-missing-gone]`
5. Persist `data/archive.sqlite3` on the `data` branch (same as RSS). Soft-fail: never block `daily-fetch`.

## Not in scope
- Actions live X API / Bearer
- Keyword search / `topic_briefs` merge
