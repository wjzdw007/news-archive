"""科技/AI 专题 UI: always listed, hash route, RSS∪X, no snapshot leak."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP_JS = ROOT / "site" / "app.js"
INDEX = ROOT / "site" / "index.html"
CSS = ROOT / "site" / "style.css"


def _run_node(script: str) -> dict:
    if not shutil.which("node"):
        raise AssertionError("node is required to execute tech-ai UI helpers")
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_page_opens_and_not_dead_end():
    html = INDEX.read_text(encoding="utf-8")
    assert 'data-tab="topics"' in html
    assert "onclick=\"goBackTopics()\"" in html
    assert "科技/AI" in html

    app = APP_JS.read_text(encoding="utf-8")
    assert "const TECH_AI_TOPIC_ID = 'tech-ai'" in app
    assert "function topicsForList()" in app
    assert "function renderTechAiDetail()" in app
    assert "function applyRoute()" in app
    assert "topics/tech-ai" in app or "TECH_AI_TOPIC_ID" in app
    assert 'empty-state">暂无专题' not in app
    assert "article.content_snapshot" not in app
    assert "const NEWS_SOURCE_CAP = 6;" in app
    assert "科技/AI" in app

    css = CSS.read_text(encoding="utf-8")
    assert ".tech-ai-feed" in css
    assert ".item-kind-badge" in css
    print("✓ page wiring")


def test_topics_for_list_always_has_tech_ai():
    app = APP_JS.read_text(encoding="utf-8")
    start = app.index("function curatedTechAiCard")
    end = app.index("// Render topics list")
    helpers = app[start:end]
    result = _run_node(
        helpers
        + """
let techAiData = null;
let topicsData = [];
const TECH_AI_TOPIC_ID = 'tech-ai';
const empty = topicsForList();
techAiData = {
  topic_id: 'tech-ai',
  title: '科技/AI',
  generated_at: '2026-10-25T17:00:00+00:00',
  items: [
    {kind:'rss', title:'WIRED AI', url:'https://wired/1', source:'wired'},
    {kind:'x', title:'hello', url:'https://x.com/OpenAI/status/1', source:'@OpenAI', author:'OpenAI'}
  ]
};
topicsData = [{topic_id:'other', title:'其它', sources:[]}];
const filled = topicsForList();
console.log(JSON.stringify({
  emptyId: empty[0].topic_id,
  emptyTitle: empty[0].title,
  emptyCount: empty[0].item_count,
  filledKinds: filled.map(t => t.topic_id),
  filledCount: filled[0].item_count,
}));
"""
    )
    assert result["emptyId"] == "tech-ai"
    assert result["emptyTitle"] == "科技/AI"
    assert result["emptyCount"] == 0
    assert result["filledKinds"] == ["tech-ai", "other"]
    assert result["filledCount"] == 2
    print("✓ topics list always has 科技/AI")


def test_render_mixes_rss_and_x_without_snapshot():
    app = APP_JS.read_text(encoding="utf-8")
    start = app.index("function renderTechAiItemHtml")
    end = app.index("function renderTechAiDetail")
    helpers = (
        r"""
function formatDate(isoString) { return isoString || ''; }
function escapeHtml(text) {
  if (typeof text !== 'string') return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
"""
        + app[start:end]
    )
    result = _run_node(
        helpers
        + """
const rss = renderTechAiItemHtml({
  kind: 'rss',
  title: 'WIRED AI chip',
  url: 'https://wired.example/1',
  source: 'wired',
  summary: 'A visible summary',
  sort_at: '2026-10-25T16:00:00Z',
  status: 'active',
});
const x = renderTechAiItemHtml({
  kind: 'x',
  title: 'Shipping GPT',
  url: 'https://x.com/OpenAI/status/1',
  source: '@OpenAI',
  author: 'OpenAI',
  summary: 'Shipping GPT',
  sort_at: '2026-10-25T17:00:00Z',
  status: 'active',
});
console.log(JSON.stringify({rss, x}));
"""
    )
    assert "WIRED AI chip" in result["rss"]
    assert "https://wired.example/1" in result["rss"]
    assert "kind-rss" in result["rss"]
    assert "@OpenAI" in result["x"]
    assert "https://x.com/OpenAI/status/1" in result["x"]
    assert "kind-x" in result["x"]
    assert "content_snapshot" not in result["rss"]
    assert "content_snapshot" not in result["x"]
    assert "post_id" not in result["x"]
    print("✓ RSS∪X render")


if __name__ == "__main__":
    test_page_opens_and_not_dead_end()
    test_topics_for_list_always_has_tech_ai()
    test_render_mixes_rss_and_x_without_snapshot()
    print("✓ All tech_ai UI tests passed")
