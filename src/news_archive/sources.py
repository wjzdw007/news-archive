"""P0 sources: non-official primary + international + EV/hard-tech + 1 official control."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    feed_url: str
    category: str
    role: str  # primary | control


SOURCES: tuple[Source, ...] = (
    Source(
        id="36kr",
        name="36氪",
        feed_url="https://www.36kr.com/feed",
        category="科技商业",
        role="primary",
    ),
    Source(
        id="tmtpost",
        name="钛媒体",
        feed_url="https://www.tmtpost.com/rss.xml",
        category="科技商业",
        role="primary",
    ),
    Source(
        id="geekpark",
        name="极客公园",
        feed_url="https://www.geekpark.net/rss",
        category="科技",
        role="primary",
    ),
    Source(
        id="ftchinese",
        name="FT中文网",
        feed_url="https://www.ftchinese.com/rss/news",
        category="财经·独立",
        role="primary",
    ),
    Source(
        id="bbc_zh_simp",
        name="BBC中文(简)",
        feed_url="https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",
        category="综合·独立",
        role="primary",
    ),
    Source(
        id="guardian_world",
        name="Guardian World",
        feed_url="https://www.theguardian.com/world/rss",
        category="国际",
        role="primary",
    ),
    Source(
        id="nyt_world",
        name="NYT World",
        feed_url="https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        category="国际",
        role="primary",
    ),
    Source(
        id="aljazeera",
        name="Al Jazeera",
        feed_url="https://www.aljazeera.com/xml/rss/all.xml",
        category="国际",
        role="primary",
    ),
    Source(
        id="electrek",
        name="Electrek",
        feed_url="https://electrek.co/feed/",
        category="汽车·EV",
        role="primary",
    ),
    Source(
        id="insideevs",
        name="InsideEVs",
        feed_url="https://insideevs.com/rss/news/all/",
        category="汽车·EV",
        role="primary",
    ),
    Source(
        id="verge_transport",
        name="The Verge Transportation",
        feed_url="https://www.theverge.com/rss/transportation/index.xml",
        category="硬科技·出行",
        role="primary",
    ),
    Source(
        id="scmp",
        name="SCMP",
        feed_url="https://www.scmp.com/rss/2/feed",
        category="国际·亚太",
        role="primary",
    ),
    Source(
        id="mit_tr",
        name="MIT Technology Review",
        feed_url="https://www.technologyreview.com/feed/",
        category="硬科技",
        role="primary",
    ),
    Source(
        id="bbc_world",
        name="BBC World",
        feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
        category="国际",
        role="primary",
    ),
    Source(
        id="scmp_asia",
        name="SCMP Asia",
        feed_url="https://www.scmp.com/rss/3/feed",
        category="国际·亚太",
        role="primary",
    ),
    Source(
        id="solidot",
        name="Solidot",
        feed_url="https://www.solidot.org/index.rss",
        category="科技",
        role="primary",
    ),
    Source(
        id="bbc_technology",
        name="BBC Technology",
        feed_url="https://feeds.bbci.co.uk/news/technology/rss.xml",
        category="硬科技",
        role="primary",
    ),
    Source(
        id="scmp_china",
        name="SCMP China",
        feed_url="https://www.scmp.com/rss/4/feed",
        category="国际·中国",
        role="primary",
    ),
    Source(
        id="nyt_technology",
        name="NYT Technology",
        feed_url="https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        category="硬科技",
        role="primary",
    ),
    Source(
        id="ifanr",
        name="爱范儿",
        feed_url="https://www.ifanr.com/feed",
        category="科技",
        role="primary",
    ),
    Source(
        id="bbc_business",
        name="BBC Business",
        feed_url="https://feeds.bbci.co.uk/news/business/rss.xml",
        category="财经",
        role="primary",
    ),
    Source(
        id="guardian_technology",
        name="Guardian Technology",
        feed_url="https://www.theguardian.com/uk/technology/rss",
        category="科技",
        role="primary",
    ),
    Source(
        id="ars_technica",
        name="Ars Technica",
        feed_url="https://feeds.arstechnica.com/arstechnica/index",
        category="硬科技",
        role="primary",
    ),
    Source(
        id="nyt_business",
        name="NYT Business",
        feed_url="https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        category="财经",
        role="primary",
    ),
    Source(
        id="bbc_science",
        name="BBC Science",
        feed_url="https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        category="科学",
        role="primary",
    ),
    Source(
        id="techcrunch",
        name="TechCrunch",
        feed_url="https://feeds.feedburner.com/TechCrunch",
        category="科技",
        role="primary",
    ),
    Source(
        id="economist_china",
        name="The Economist China",
        feed_url="https://www.economist.com/china/rss.xml",
        category="国际·中国",
        role="primary",
    ),
    Source(
        id="bbc_asia",
        name="BBC Asia",
        feed_url="https://feeds.bbci.co.uk/news/world/asia/rss.xml",
        category="国际·亚太",
        role="primary",
    ),
    Source(
        id="verge",
        name="The Verge",
        feed_url="https://www.theverge.com/rss/index.xml",
        category="科技",
        role="primary",
    ),
    Source(
        id="people_finance",
        name="人民网·财经",
        feed_url="https://www.people.com.cn/rss/finance.xml",
        category="官方",
        role="control",
    ),
)
