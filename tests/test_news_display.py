"""Acceptance tests for News Tab display order (diversity cap + 36kr flashes).

X Tab is out of scope: these helpers are news-list only.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
APP_JS = ROOT / "site" / "app.js"

WINDOW = 50
CAP = 6


def _extract_news_display_helpers() -> str:
    app_js = APP_JS.read_text(encoding="utf-8")
    start = app_js.index("function articleListTime")
    end = app_js.index("// Render news list")
    return app_js[start:end]


def _run_node(script: str) -> dict:
    if not shutil.which("node"):
        raise AssertionError("node is required to execute the news-display helpers")
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _eval_fixture(articles: list[dict], expanded: bool = False) -> dict:
    helpers = _extract_news_display_helpers()
    payload = json.dumps({"articles": articles, "expanded": expanded}, ensure_ascii=False)
    script = (
        helpers
        + """
const input = """
        + payload
        + """;
const model = buildNewsDisplayModel(input.articles);
const rows = buildNewsDisplayRows(input.articles, { expanded: input.expanded }).rows;
const summarize = (article) => ({
  url: article.url,
  source: article.source,
  published_at: article.published_at,
  fetched_at: article.fetched_at,
  flash: isNewsflash(article),
  badge: newsflashBadgeLabel(article),
});
console.log(JSON.stringify({
  window: NEWS_DISPLAY_WINDOW,
  cap: NEWS_SOURCE_CAP,
  total: model.displayOrder.length,
  inputTotal: input.articles.length,
  top: model.top.map(summarize),
  overflow: model.overflow.map(summarize),
  displayOrder: model.displayOrder.map(summarize),
  foldCount: model.foldCount,
  topFlashes: model.topFlashes.map(summarize),
  rows: rows.map((row) => {
    if (row.type === 'fold') {
      return { type: 'fold', count: row.count, expanded: row.expanded };
    }
    return {
      type: 'article',
      url: row.article.url,
      source: row.article.source,
      badge: row.badge,
      inFold: row.inFold,
      flash: isNewsflash(row.article),
    };
  }),
}));
"""
    )
    return _run_node(script)


def _load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _source_counts(items: list[dict]) -> Counter:
    return Counter(item["source"] for item in items)


def test_helpers_are_news_tab_only():
    app_js = APP_JS.read_text(encoding="utf-8")
    assert "function buildNewsDisplayModel(articles)" in app_js
    assert "function buildNewsDisplayRows(articles, options)" in app_js
    assert "function isNewsflash(article)" in app_js
    assert "newsflash-badge" in app_js
    assert "快讯" in app_js
    assert "buildNewsDisplayRows(articlesData, { expanded: newsflashesExpanded })" in app_js
    # X Tab stays on posted_at and does not share the news display pipeline
    x_start = app_js.index("function renderXList")
    x_fn = app_js[x_start:]
    assert "buildNewsDisplayModel" not in x_fn
    assert "isNewsflash" not in x_fn
    assert "formatDate(post.posted_at || post.fetched_at)" in x_fn


def test_source_diversity_cap_fixture():
    """One source owns the 20 newest → ≤6 of that source in first 50; 7th+ after 50."""
    articles = _load_fixture("news_source_diversity.json")
    assert sum(1 for a in articles if a["source"] == "36kr") == 20
    result = _eval_fixture(articles)

    assert result["window"] == WINDOW
    assert result["cap"] == CAP
    assert result["total"] == result["inputTotal"] == len(articles)

    top = result["top"]
    overflow = result["overflow"]
    display = result["displayOrder"]
    assert len(top) == WINDOW
    assert len(display) == len(articles)
    assert [item["url"] for item in display[:WINDOW]] == [item["url"] for item in top]
    assert [item["url"] for item in display[WINDOW:]] == [item["url"] for item in overflow]

    top_counts = _source_counts(top)
    assert top_counts["36kr"] <= CAP
    assert top_counts["36kr"] == CAP
    assert max(top_counts.values()) <= CAP

    kr_sorted = [a for a in articles if a["source"] == "36kr"]
    kr_sorted.sort(key=lambda a: a["published_at"], reverse=True)
    seventh_plus = {a["url"] for a in kr_sorted[CAP:]}
    overflow_kr = {item["url"] for item in overflow if item["source"] == "36kr"}
    assert overflow_kr == seventh_plus
    assert all(item["url"] in {a["url"] for a in overflow} for item in display[WINDOW:] if item["source"] == "36kr")

    first_overflow_kr = next(item for item in overflow if item["source"] == "36kr")
    assert first_overflow_kr["url"] == kr_sorted[CAP]["url"]
    overflow_kr_urls = [item["url"] for item in overflow if item["source"] == "36kr"]
    assert overflow_kr_urls == [a["url"] for a in kr_sorted[CAP:]]


def test_live_any_source_at_most_six_in_first_50():
    """Property: after display-order, every source in the first 50 is ≤ 6."""
    articles = _load_fixture("news_source_diversity.json") + _load_fixture("news_newsflashes.json")
    result = _eval_fixture(articles)
    counts = _source_counts(result["displayOrder"][:WINDOW])
    assert counts
    assert max(counts.values()) <= CAP
    assert result["total"] == result["inputTotal"]


def test_newsflashes_fold_and_badge_fixture():
    """Default top-50 expanded flashes = 0; N = fold count; expanded items badged."""
    articles = _load_fixture("news_newsflashes.json")
    collapsed = _eval_fixture(articles, expanded=False)
    expanded = _eval_fixture(articles, expanded=True)

    flash_urls = {a["url"] for a in articles if "newsflashes" in a["url"]}
    non_flash_urls = {a["url"] for a in articles if "newsflashes" not in a["url"]}
    assert flash_urls
    assert non_flash_urls

    assert collapsed["foldCount"] == 6
    assert len(collapsed["topFlashes"]) == 6
    assert all(item["flash"] for item in collapsed["topFlashes"])

    collapsed_top_article_rows = [
        row for row in collapsed["rows"]
        if row["type"] == "article" and row["url"] in {item["url"] for item in collapsed["top"]}
    ]
    assert all(not row["flash"] for row in collapsed_top_article_rows)
    assert all(not row["inFold"] for row in collapsed["rows"] if row["type"] == "article")

    fold_rows = [row for row in collapsed["rows"] if row["type"] == "fold"]
    assert len(fold_rows) == 1
    assert fold_rows[0]["count"] == collapsed["foldCount"]
    assert fold_rows[0]["expanded"] is False
    assert fold_rows[0]["count"] == len(collapsed["topFlashes"])

    expanded_fold_items = [row for row in expanded["rows"] if row.get("inFold")]
    assert len(expanded_fold_items) == collapsed["foldCount"]
    assert all(row["badge"] == "快讯" for row in expanded_fold_items)
    assert all(row["flash"] for row in expanded_fold_items)

    for row in collapsed["rows"] + expanded["rows"]:
        if row["type"] != "article":
            continue
        if row["url"] in flash_urls:
            assert row["badge"] == "快讯"
        else:
            assert row["badge"] == ""
            assert row["flash"] is False


def test_non_flash_priority_for_source_cap():
    """Regular 36kr articles take the 6 cap slots even when flashes are newer."""
    articles = _load_fixture("news_newsflashes_priority.json")
    result = _eval_fixture(articles)

    top_kr = [item for item in result["top"] if item["source"] == "36kr"]
    assert len(top_kr) <= CAP
    assert len(top_kr) == CAP
    assert all(not item["flash"] for item in top_kr)
    assert all("newsflashes" not in item["url"] for item in top_kr)
    assert result["foldCount"] == 0
    assert not any(row["type"] == "fold" for row in result["rows"])

    overflow_kr_flashes = [
        item for item in result["overflow"]
        if item["source"] == "36kr" and item["flash"]
    ]
    assert len(overflow_kr_flashes) == 10
    assert all(item["badge"] == "快讯" for item in overflow_kr_flashes)

    regular_kr = [a for a in articles if a["source"] == "36kr" and "newsflashes" not in a["url"]]
    regular_kr.sort(key=lambda a: a["published_at"], reverse=True)
    assert [item["url"] for item in top_kr] == [a["url"] for a in regular_kr[:CAP]]
    squeezed_regular = [a["url"] for a in regular_kr[CAP:]]
    overflow_regular = [
        item["url"] for item in result["overflow"]
        if item["source"] == "36kr" and not item["flash"]
    ]
    assert overflow_regular == squeezed_regular


def test_newsflash_detector_and_badge_rules():
    helpers = _extract_news_display_helpers()
    script = helpers + """
const cases = [
  {url:'https://www.36kr.com/newsflashes/123', source:'36kr'},
  {url:'https://www.36kr.com/p/123', source:'36kr'},
  {url:'https://www.tmtpost.com/newsflashes/9', source:'tmtpost'},
  {url:'https://www.tmtpost.com/123', source:'tmtpost'},
  {url:'', source:'36kr'},
  {source:'36kr'},
];
console.log(JSON.stringify(cases.map(a => ({
  url: a.url || null,
  flash: isNewsflash(a),
  badge: newsflashBadgeLabel(a),
}))));
"""
    rows = _run_node(script)
    assert rows[0] == {"url": "https://www.36kr.com/newsflashes/123", "flash": True, "badge": "快讯"}
    assert rows[1] == {"url": "https://www.36kr.com/p/123", "flash": False, "badge": ""}
    assert rows[2]["flash"] is True and rows[2]["badge"] == "快讯"
    assert rows[3]["flash"] is False and rows[3]["badge"] == ""
    assert rows[4]["flash"] is False and rows[4]["badge"] == ""
    assert rows[5]["flash"] is False and rows[5]["badge"] == ""


if __name__ == "__main__":
    test_helpers_are_news_tab_only()
    test_source_diversity_cap_fixture()
    test_live_any_source_at_most_six_in_first_50()
    test_newsflashes_fold_and_badge_fixture()
    test_non_flash_priority_for_source_cap()
    test_newsflash_detector_and_badge_rules()
    print("✓ All news display tests passed")
