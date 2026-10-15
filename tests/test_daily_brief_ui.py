"""日报 Tab: last 7 Shanghai days, ok/failed/empty rendering, no news banner."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
APP_JS = ROOT / "site" / "app.js"
INDEX = ROOT / "site" / "index.html"


def _run_node(script: str) -> dict:
    if not shutil.which("node"):
        raise AssertionError("node is required to execute daily-brief UI helpers")
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _escape_html_stub() -> str:
    return r"""
function escapeHtml(text) {
  if (typeof text !== 'string') return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
"""


def _extract_daily_helpers() -> str:
    app_js = APP_JS.read_text(encoding="utf-8")
    start = app_js.index("// Daily brief helpers")
    end = app_js.index("// Render daily tab")
    return app_js[start:end] + _escape_html_stub()


def _eval(script_body: str) -> dict:
    return _run_node(_extract_daily_helpers() + script_body)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_fourth_tab_and_no_news_banner():
    html = INDEX.read_text(encoding="utf-8")
    assert 'data-tab="news"' in html
    assert 'data-tab="topics"' in html
    assert 'data-tab="x"' in html
    assert 'data-tab="daily"' in html
    assert ">日报<" in html
    news_start = html.index('id="news-tab"')
    news_end = html.index('id="topics-tab"')
    news = html[news_start:news_end]
    assert "日报" not in news
    assert "当日暂无摘要" not in news
    assert "当日摘要生成失败" not in news
    assert "banner" not in news.lower()
    assert "daily-lede" not in news

    app_js = APP_JS.read_text(encoding="utf-8")
    news_fn_start = app_js.index("function renderNewsList")
    news_fn_end = app_js.index("function toggleNewsflashes")
    news_fn = app_js[news_fn_start:news_fn_end]
    assert "daily" not in news_fn.lower()
    assert "日报" not in news_fn
    assert "当日暂无摘要" not in news_fn


def test_shanghai_today_and_last_seven_days():
    result = _eval(
        """
const now = new Date('2026-10-15T04:00:00.000Z');
const today = shanghaiCalendarDate(now);
const dates = lastNShanghaiDates(DAILY_BRIEF_DAYS, now);
const beforeMidnight = shanghaiCalendarDate(new Date('2026-10-14T15:59:00.000Z'));
const atMidnight = shanghaiCalendarDate(new Date('2026-10-14T16:00:00.000Z'));
console.log(JSON.stringify({
  today, dates, n: dates.length, beforeMidnight, atMidnight,
  firstIsToday: dates[0] === today,
  defaultLabel: dailyDateButtonLabel(dates[0], today),
}));
"""
    )
    assert result["today"] == "2026-10-15"
    assert result["n"] == 7
    assert result["dates"] == [
        "2026-10-15",
        "2026-10-14",
        "2026-10-13",
        "2026-10-12",
        "2026-10-11",
        "2026-10-10",
        "2026-10-09",
    ]
    assert result["firstIsToday"] is True
    assert result["defaultLabel"] == "今天"
    assert result["beforeMidnight"] == "2026-10-14"
    assert result["atMidnight"] == "2026-10-15"


def test_ok_failed_empty_rendering():
    ok = _load_fixture("daily_brief_ok.json")
    failed = _load_fixture("daily_brief_failed.json")
    empty = _load_fixture("daily_brief_empty.json")
    payload = json.dumps(
        {"ok": ok, "failed": failed, "empty": empty},
        ensure_ascii=False,
    )
    result = _eval(
        "const input = "
        + payload
        + """;
const switcher = renderDateSwitcherHtml(
  lastNShanghaiDates(7, new Date('2026-10-15T04:00:00.000Z')),
  '2026-10-15',
  '2026-10-15'
);
console.log(JSON.stringify({
  ok: renderDailyBriefHtml(input.ok, '2026-10-15'),
  failed: renderDailyBriefHtml(input.failed, '2026-10-15'),
  empty: renderDailyBriefHtml(input.empty, '2026-10-15'),
  missing: renderDailyBriefHtml(null, '2026-10-15'),
  switcher,
  emptyMsg: DAILY_EMPTY_MESSAGE,
  failedMsg: DAILY_FAILED_MESSAGE,
}));
"""
    )
    assert result["emptyMsg"] == "当日暂无摘要"
    assert result["failedMsg"] == "当日摘要生成失败"
    assert "多源关注航天发射与市场动态" in result["ok"]
    assert "航天发射" in result["ok"]
    assert "SpaceX 今日完成发射" in result["ok"]
    assert "https://example.com/spacex" in result["ok"]
    assert "其它" in result["ok"]
    assert "X 动态" in result["ok"]
    assert "https://x.com/FT/status/1" in result["ok"]
    assert "content_snapshot" not in result["ok"]
    assert result["failedMsg"] in result["failed"]
    assert "多源关注" not in result["failed"]
    assert result["emptyMsg"] in result["empty"]
    assert result["emptyMsg"] in result["missing"]
    assert 'data-date="2026-10-15"' in result["switcher"]
    assert result["switcher"].count("data-date=") == 7
    assert "今天" in result["switcher"]


def test_fixtures_and_helpers_omit_content_snapshot():
    for name in (
        "daily_brief_ok.json",
        "daily_brief_failed.json",
        "daily_brief_empty.json",
    ):
        raw = (FIXTURES / name).read_text(encoding="utf-8")
        assert "content_snapshot" not in raw
    helpers = _extract_daily_helpers()
    assert "content_snapshot" not in helpers


if __name__ == "__main__":
    test_fourth_tab_and_no_news_banner()
    test_shanghai_today_and_last_seven_days()
    test_ok_failed_empty_rendering()
    test_fixtures_and_helpers_omit_content_snapshot()
    print("✓ All daily brief UI tests passed")
