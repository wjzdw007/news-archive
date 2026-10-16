"""Registry checks for RSS primary sources."""

from __future__ import annotations

from news_archive.sources import SOURCES

# CEO-approved EV / hard-tech RSS primaries (X Tesla/elonmusk is separate backlog).
_EV_HARDTECH_PRIMARY = {
    "electrek": {
        "name": "Electrek",
        "feed_url": "https://electrek.co/feed/",
        "category": "汽车·EV",
    },
    "insideevs": {
        "name": "InsideEVs",
        "feed_url": "https://insideevs.com/rss/news/all/",
        "category": "汽车·EV",
    },
    "verge_transport": {
        "name": "The Verge Transportation",
        "feed_url": "https://www.theverge.com/rss/transportation/index.xml",
        "category": "硬科技·出行",
    },
}


def test_source_ids_unique():
    ids = [s.id for s in SOURCES]
    assert len(ids) == len(set(ids)), f"duplicate source ids: {ids}"


def test_ev_hardtech_primaries_registered():
    by_id = {s.id: s for s in SOURCES}
    for source_id, expected in _EV_HARDTECH_PRIMARY.items():
        assert source_id in by_id, f"missing source id {source_id}"
        source = by_id[source_id]
        assert source.role == "primary"
        assert source.name == expected["name"]
        assert source.feed_url == expected["feed_url"]
        assert source.category == expected["category"]


if __name__ == "__main__":
    test_source_ids_unique()
    test_ev_hardtech_primaries_registered()
    print("✓ source registry tests PASSED")
