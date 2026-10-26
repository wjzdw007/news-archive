// Global data store
let articlesData = [];
let topicsData = [];
let xPostsData = [];
let dailyBriefsData = [];
let techAiData = null;
let articlesMap = new Map(); // url -> article
let selectedDailyDate = null;

const TECH_AI_TOPIC_ID = 'tech-ai';

// Tab switching
document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        navigateTo(button.dataset.tab);
    });
});

function switchTab(tabName) {
    // Update active tab button
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // Update active tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-tab`);
    });
    
    // Close any open details
    closeDetail();
    closeTopicDetail();
}

function navigateTo(hash) {
    const clean = String(hash || 'news').replace(/^#/, '');
    if ((location.hash || '').replace(/^#/, '') === clean) {
        applyRoute();
        return;
    }
    location.hash = clean;
}

function applyRoute() {
    const raw = (location.hash || '#news').replace(/^#/, '') || 'news';
    const parts = raw.split('/');
    const known = ['news', 'topics', 'x', 'daily'];
    const tabName = known.includes(parts[0]) ? parts[0] : 'news';
    switchTab(tabName);
    if (tabName === 'topics' && parts[1] === TECH_AI_TOPIC_ID) {
        renderTechAiDetail();
    }
}

window.addEventListener('hashchange', applyRoute);

// Load data on page load
async function loadData() {
    try {
        const [articles, topics, xPosts, dailyBriefs, techAi] = await Promise.all([
            fetch('data/articles.json').then(r => r.json()),
            fetch('data/topics.json').then(r => r.json()),
            fetch('data/x_posts.json').then(r => r.json()),
            fetch('data/daily_briefs.json').then(r => r.ok ? r.json() : []).catch(() => []),
            fetch('data/tech_ai.json').then(r => r.ok ? r.json() : null).catch(() => null)
        ]);
        
        articlesData = articles;
        topicsData = topics;
        xPostsData = xPosts;
        dailyBriefsData = Array.isArray(dailyBriefs) ? dailyBriefs : [];
        techAiData = techAi && typeof techAi === 'object' ? techAi : null;
        
        // Build articles map for quick lookup
        articles.forEach(article => {
            articlesMap.set(article.url, article);
        });
        
        renderNewsList();
        renderTopicsList();
        renderXList();
        renderDailyTab();
        applyRoute();
        
    } catch (error) {
        console.error('Failed to load data:', error);
        document.querySelectorAll('.loading').forEach(el => {
            el.textContent = '加载失败';
        });
    }
}

// News list SORT + displayed time: published_at, else fetched_at.
// X tab keeps posted_at || fetched_at and does not share this helper.
function articleListTime(article) {
    const published = typeof article.published_at === 'string' ? article.published_at.trim() : '';
    if (published) return published;
    return (article.fetched_at || '').toString().trim();
}

function compareArticleListTimeDesc(a, b) {
    return articleListTime(b).localeCompare(articleListTime(a));
}

// News Tab DISPLAY order (X Tab does not use these helpers):
// 1) sort by published_at desc (fallback fetched_at)
// 2) positions 1–50: same source ≤ 6; overflow stays in time order after 50
// 3) non-flash articles take per-source cap slots before newsflashes
// 4) newsflashes that land in the top-50 window fold into one row by default
const NEWS_DISPLAY_WINDOW = 50;
const NEWS_SOURCE_CAP = 6;
let newsflashesExpanded = false;

function isNewsflash(article) {
    return typeof article.url === 'string' && article.url.includes('newsflashes');
}

function newsflashBadgeLabel(article) {
    return isNewsflash(article) ? '快讯' : '';
}

function buildNewsDisplayModel(articles) {
    const sorted = [...articles].sort(compareArticleListTimeDesc);
    const sourceCounts = {};
    const top = [];
    const overflow = [];

    function tryPlace(article) {
        const src = article.source || '';
        const count = sourceCounts[src] || 0;
        if (top.length < NEWS_DISPLAY_WINDOW && count < NEWS_SOURCE_CAP) {
            top.push(article);
            sourceCounts[src] = count + 1;
            return;
        }
        overflow.push(article);
    }

    // Non-flash first so they consume per-source cap slots before flashes.
    for (const article of sorted) {
        if (!isNewsflash(article)) tryPlace(article);
    }
    for (const article of sorted) {
        if (isNewsflash(article)) tryPlace(article);
    }

    top.sort(compareArticleListTimeDesc);
    overflow.sort(compareArticleListTimeDesc);

    const topFlashes = top.filter(isNewsflash);
    return {
        sorted: sorted,
        top: top,
        overflow: overflow,
        topFlashes: topFlashes,
        foldCount: topFlashes.length,
        displayOrder: top.concat(overflow),
    };
}

function buildNewsDisplayRows(articles, options) {
    const expanded = !!(options && options.expanded);
    const model = buildNewsDisplayModel(articles);
    const rows = [];
    let foldInserted = false;

    for (const article of model.top) {
        if (isNewsflash(article)) {
            if (!foldInserted) {
                rows.push({ type: 'fold', count: model.foldCount, expanded: expanded });
                if (expanded) {
                    for (const flash of model.topFlashes) {
                        rows.push({
                            type: 'article',
                            article: flash,
                            badge: '快讯',
                            inFold: true,
                        });
                    }
                }
                foldInserted = true;
            }
            continue;
        }
        rows.push({
            type: 'article',
            article: article,
            badge: newsflashBadgeLabel(article),
            inFold: false,
        });
    }

    for (const article of model.overflow) {
        rows.push({
            type: 'article',
            article: article,
            badge: newsflashBadgeLabel(article),
            inFold: false,
        });
    }

    return Object.assign({}, model, { rows: rows });
}

// Render news list
function renderNewsList() {
    const container = document.getElementById('news-list');
    
    if (articlesData.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无新闻</div>';
        return;
    }

    const { rows } = buildNewsDisplayRows(articlesData, { expanded: newsflashesExpanded });
    container.innerHTML = rows.map(renderNewsRowHtml).join('');
}

function toggleNewsflashes(event) {
    if (event) event.stopPropagation();
    newsflashesExpanded = !newsflashesExpanded;
    renderNewsList();
}

function renderArticleItemHtml(article) {
    const date = formatDate(articleListTime(article));
    const summary = article.summary || '无摘要';
    const oneLineSummary = summary.length > 100 ? summary.substring(0, 100) + '...' : summary;
    const badge = newsflashBadgeLabel(article);
    const badgeHtml = badge
        ? `<span class="newsflash-badge">${escapeHtml(badge)}</span>`
        : '';

    return `
            <div class="article-item" onclick="showArticleDetail('${escapeHtml(article.url)}')">
                <h3 class="article-title">${badgeHtml}${badgeHtml ? ' ' : ''}${escapeHtml(article.title)}</h3>
                <div class="article-meta">
                    <span class="source">${escapeHtml(article.source)}</span>
                    <span class="date">${date}</span>
                </div>
                <p class="article-summary">${escapeHtml(oneLineSummary)}</p>
            </div>
        `;
}

function renderNewsRowHtml(row) {
    if (row.type === 'fold') {
        const hint = row.expanded ? '点击收起' : '点击展开';
        return `
            <div class="newsflash-fold" role="button" tabindex="0" onclick="toggleNewsflashes(event)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleNewsflashes(event);}">
                <span class="newsflash-badge">快讯</span>
                <span class="newsflash-fold-label">快讯 ${row.count} 条</span>
                <span class="newsflash-fold-hint">${hint}</span>
            </div>
        `;
    }
    return renderArticleItemHtml(row.article);
}

// Show article detail
function showArticleDetail(url) {
    const article = articlesMap.get(url);
    if (!article) return;
    
    // Public site: summary + original link + topic jump only (no content_snapshot).
    const summary = article.summary || '无摘要';
    const date = formatDate(articleListTime(article));
    const topicLink = article.topic_id ? `<p class="topic-link"><a href="#" onclick="showTopicFromArticle('${article.topic_id}'); return false;">→ 查看相关专题</a></p>` : '';
    
    const html = `
        <h2>${escapeHtml(article.title)}</h2>
        <div class="article-meta">
            <span class="source">${escapeHtml(article.source)}</span>
            <span class="date">${date}</span>
        </div>
        <div class="article-body">${escapeHtml(summary)}</div>
        <p class="original-link">
            <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer">查看原文 ↗</a>
        </p>
        ${topicLink}
    `;
    
    document.getElementById('article-content').innerHTML = html;
    document.getElementById('news-list').style.display = 'none';
    document.getElementById('news-detail').style.display = 'block';
}

function closeDetail() {
    document.getElementById('news-list').style.display = 'block';
    document.getElementById('news-detail').style.display = 'none';
}

// 科技/AI is a curated 专题 (always listed; never a 暂无专题 dead end).
function curatedTechAiCard() {
    const items = (techAiData && Array.isArray(techAiData.items)) ? techAiData.items : [];
    return {
        topic_id: TECH_AI_TOPIC_ID,
        title: (techAiData && techAiData.title) || '科技/AI',
        generated_at: (techAiData && techAiData.generated_at) || '',
        status: 'ok',
        sources: items.slice(0, 3).map(i => ({ title: i.title || '无标题', url: i.url })),
        item_count: items.length,
        kind: 'curated',
        used_fallback: !!(techAiData && techAiData.used_fallback),
    };
}

function topicsForList() {
    const rest = (topicsData || []).filter(t => t.topic_id !== TECH_AI_TOPIC_ID);
    return [curatedTechAiCard()].concat(rest);
}

// Render topics list
function renderTopicsList() {
    const container = document.getElementById('topics-list');
    const topics = topicsForList();
    
    const html = topics.map(topic => {
        const curated = topic.topic_id === TECH_AI_TOPIC_ID;
        const date = formatDate(topic.generated_at);
        const sources = topic.sources || [];
        const bulletPoints = sources.slice(0, 3).map(s => `• ${s.title || '无标题'}`).join('<br>');
        const moreText = sources.length > 3 ? `<br>...及 ${sources.length - 3} 条更多` : '';
        const emptyHint = curated && (topic.item_count || 0) === 0
            ? '<div class="topic-preview">专题已就绪，等待抓取写入科技与 AI 条目</div>'
            : `<div class="topic-preview">${bulletPoints}${moreText}</div>`;
        const countLabel = curated
            ? `${topic.item_count || 0} 条 · RSS+X`
            : `${sources.length} 个来源`;
        const badge = curated ? '<span class="topic-badge">常设</span> ' : '';
        const extraClass = curated ? ' topic-item-featured' : '';
        
        return `
            <div class="topic-item${extraClass}" onclick="showTopicDetail('${escapeHtml(topic.topic_id)}')">
                <h3 class="topic-title">${badge}${escapeHtml(topic.title)}</h3>
                <div class="topic-meta">
                    <span class="date">${date}</span>
                    <span class="source-count">${countLabel}</span>
                </div>
                ${emptyHint}
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

// Show topic detail
function showTopicDetail(topicId) {
    if (topicId === TECH_AI_TOPIC_ID) {
        navigateTo('topics/' + TECH_AI_TOPIC_ID);
        return;
    }
    const topic = topicsData.find(t => t.topic_id === topicId);
    if (!topic) return;
    
    switchTab('topics');
    
    const date = formatDate(topic.generated_at);
    const sources = topic.sources || [];
    const sourcesHtml = sources.map(source => {
        const article = articlesMap.get(source.url);
        const statusClass = article && article.status === 'gone' ? 'gone' : '';
        return `
            <li class="${statusClass}">
                <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">
                    ${escapeHtml(source.title || '无标题')} ↗
                </a>
            </li>
        `;
    }).join('');
    
    const html = `
        <h2>${escapeHtml(topic.title)}</h2>
        <div class="topic-meta">
            <span class="date">${date}</span>
            <span class="source-count">${sources.length} 个来源</span>
        </div>
        <div class="topic-sources">
            <h3>相关报道</h3>
            <ul>${sourcesHtml}</ul>
        </div>
    `;
    
    document.getElementById('topic-content').innerHTML = html;
    document.getElementById('topics-list').style.display = 'none';
    document.getElementById('topic-detail').style.display = 'block';
}

function showTopicFromArticle(topicId) {
    showTopicDetail(topicId);
}

function closeTopicDetail() {
    document.getElementById('topics-list').style.display = 'block';
    document.getElementById('topic-detail').style.display = 'none';
}

function goBackTopics() {
    const raw = (location.hash || '').replace(/^#/, '');
    if (raw === 'topics/' + TECH_AI_TOPIC_ID) {
        navigateTo('topics');
        return;
    }
    closeTopicDetail();
}

function renderTechAiItemHtml(item) {
    const kind = item.kind === 'x' ? 'x' : 'rss';
    const badge = kind === 'x' ? 'X' : 'RSS';
    const date = formatDate(item.sort_at || item.published_at || item.fetched_at);
    const statusClass = item.status === 'gone' ? ' gone' : '';
    const summary = item.summary || '';
    const oneLine = summary.length > 140 ? summary.substring(0, 140) + '...' : summary;
    const href = escapeHtml(item.url || '');
    if (kind === 'x') {
        return `
            <div class="x-post-item tech-ai-item${statusClass}">
                <div class="x-post-header">
                    <span class="item-kind-badge kind-x">${badge}</span>
                    <span class="x-author">${escapeHtml(item.source || '')}</span>
                    <span class="date">${date}</span>
                </div>
                <p class="x-post-text">${escapeHtml(summary || '无内容')}</p>
                ${href ? `<a href="${href}" target="_blank" rel="noopener noreferrer" class="x-post-link">查看原帖 ↗</a>` : ''}
            </div>
        `;
    }
    return `
        <div class="article-item tech-ai-item${statusClass}">
            <h3 class="article-title"><span class="item-kind-badge kind-rss">${badge}</span> ${escapeHtml(item.title || '无标题')}</h3>
            <div class="article-meta">
                <span class="source">${escapeHtml(item.source || '')}</span>
                <span class="date">${date}</span>
            </div>
            <p class="article-summary">${escapeHtml(oneLine)}</p>
            ${href ? `<p class="original-link"><a href="${href}" target="_blank" rel="noopener noreferrer">查看原文 ↗</a></p>` : ''}
        </div>
    `;
}

function techAiColumns(data) {
    const items = (data && Array.isArray(data.items)) ? data.items : [];
    const rssItems = (data && Array.isArray(data.rss_items))
        ? data.rss_items
        : items.filter(i => i.kind === 'rss');
    const xItems = (data && Array.isArray(data.x_items))
        ? data.x_items
        : items.filter(i => i.kind === 'x');
    return { rssItems, xItems };
}

function renderTechAiDetail() {
    const container = document.getElementById('topic-content');
    const { rssItems, xItems } = techAiColumns(techAiData);
    const usedFallback = !!(techAiData && techAiData.used_fallback);
    const usedBackups = !!(techAiData && techAiData.used_x_backups);
    const rssCount = techAiData && typeof techAiData.rss_count === 'number'
        ? techAiData.rss_count
        : rssItems.length;
    const xCount = techAiData && typeof techAiData.x_count === 'number'
        ? techAiData.x_count
        : xItems.length;

    const pageHints = [];
    if (rssItems.length === 0 && xItems.length === 0) {
        pageHints.push('专题已就绪。等待下一次 daily-fetch / x-fetch 写入科技与 AI 条目。');
    } else if (usedFallback) {
        pageHints.push('近 24 小时暂无新条目，以下为最近归档（最多 7 天）。');
    }
    const pageHint = pageHints.map(t => `<div class="topic-empty-hint">${t}</div>`).join('');

    const rssHtml = rssItems.map(renderTechAiItemHtml).join('');
    const xHtml = xItems.map(renderTechAiItemHtml).join('');
    const xEmpty = xCount === 0
        ? '<div class="topic-empty-hint">X 栏暂无可用帖。已按账号抓取 user timeline（不必 Follow），等待下一次 x-fetch 写入。</div>'
        : '';
    const rssEmpty = rssCount === 0
        ? '<div class="topic-empty-hint">资讯栏暂无条目。</div>'
        : '';
    const backupNote = usedBackups ? ' · 含备用账号' : '';
    const generated = techAiData && techAiData.generated_at ? techAiData.generated_at : '';

    container.innerHTML = `
        <h2>科技/AI</h2>
        <div class="topic-meta">
            <span class="date">${formatDate(generated)}</span>
            <span class="source-count">资讯 ${rssCount} · X ${xCount}${backupNote}</span>
        </div>
        ${pageHint}
        <div class="tech-ai-columns">
            <section class="tech-ai-col tech-ai-col-rss">
                <h3 class="tech-ai-col-title">资讯 <span class="tech-ai-col-count">${rssCount}</span></h3>
                ${rssEmpty}
                <div class="tech-ai-feed">${rssHtml}</div>
            </section>
            <section class="tech-ai-col tech-ai-col-x">
                <h3 class="tech-ai-col-title">X <span class="tech-ai-col-count">${xCount}</span></h3>
                ${xEmpty}
                <div class="tech-ai-feed">${xHtml}</div>
            </section>
        </div>
    `;
    document.getElementById('topics-list').style.display = 'none';
    document.getElementById('topic-detail').style.display = 'block';
}

// Render X posts list
function renderXList() {
    const container = document.getElementById('x-list');
    
    if (xPostsData.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无 X 帖子</div>';
        return;
    }
    
    const html = xPostsData.map(post => {
        const date = formatDate(post.posted_at || post.fetched_at);
        const statusClass = post.status === 'gone' ? 'gone' : '';
        const text = post.text_snapshot || '无内容';
        
        return `
            <div class="x-post-item ${statusClass}">
                <div class="x-post-header">
                    <span class="x-author">@${escapeHtml(post.author)}</span>
                    <span class="date">${date}</span>
                </div>
                <p class="x-post-text">${escapeHtml(text)}</p>
                ${post.url ? `<a href="${escapeHtml(post.url)}" target="_blank" rel="noopener noreferrer" class="x-post-link">查看原帖 ↗</a>` : ''}
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

// Daily brief helpers
const DAILY_BRIEF_DAYS = 7;
const SHANGHAI_TZ = 'Asia/Shanghai';
const DAILY_EMPTY_MESSAGE = '当日暂无摘要';
const DAILY_FAILED_MESSAGE = '当日摘要生成失败';

function shanghaiCalendarDate(date) {
    const d = date instanceof Date ? date : new Date();
    return new Intl.DateTimeFormat('en-CA', {
        timeZone: SHANGHAI_TZ,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).format(d);
}

function lastNShanghaiDates(n, now) {
    const origin = now instanceof Date ? now : new Date();
    const dates = [];
    for (let i = 0; i < n; i++) {
        dates.push(shanghaiCalendarDate(new Date(origin.getTime() - i * 24 * 60 * 60 * 1000)));
    }
    return dates;
}

function findDailyBrief(briefs, date) {
    if (!Array.isArray(briefs) || !date) return null;
    return briefs.find(b => b && b.date === date) || null;
}

function dailyDateButtonLabel(ymd, todayYmd) {
    if (ymd === todayYmd) return '今天';
    return ymd.slice(5);
}

function renderDateSwitcherHtml(dates, selected, todayYmd) {
    return dates.map(ymd => {
        const active = ymd === selected ? ' active' : '';
        const label = dailyDateButtonLabel(ymd, todayYmd);
        return `<button type="button" class="date-chip${active}" data-date="${ymd}" onclick="selectDailyDate('${ymd}')">${label}</button>`;
    }).join('');
}

function renderDailySectionHtml(section) {
    const title = escapeHtml(section.title || '无标题');
    const bullets = (section.bullets || []).map(b => `<li>${escapeHtml(b)}</li>`).join('');
    const links = (section.links || []).map(link => {
        const href = escapeHtml(link.url || '');
        const label = escapeHtml(link.title || link.url || '原文');
        const source = link.source ? `<span class="source">${escapeHtml(link.source)}</span>` : '';
        return `<li><a href="${href}" target="_blank" rel="noopener noreferrer">${label} ↗</a> ${source}</li>`;
    }).join('');
    return `
        <section class="daily-section">
            <h3 class="daily-section-title">${title}</h3>
            ${bullets ? `<ul class="daily-bullets">${bullets}</ul>` : ''}
            ${links ? `<ul class="daily-links">${links}</ul>` : ''}
        </section>
    `;
}

function renderDailyBriefHtml(brief, date) {
    if (!brief || brief.status === 'empty') {
        return `<div class="empty-state">${DAILY_EMPTY_MESSAGE}</div>`;
    }
    if (brief.status === 'failed') {
        return `<div class="empty-state daily-failed">${DAILY_FAILED_MESSAGE}</div>`;
    }
    const lede = brief.lede ? `<p class="daily-lede">${escapeHtml(brief.lede)}</p>` : '';
    const sections = (brief.sections || []).map(renderDailySectionHtml).join('');
    const generated = brief.generated_at
        ? `<p class="daily-meta">${escapeHtml(date)} · ${escapeHtml(brief.model || '')}</p>`
        : '';
    return `${generated}${lede}${sections || `<div class="empty-state">${DAILY_EMPTY_MESSAGE}</div>`}`;
}

// Render daily tab
function renderDailyTab() {
    const today = shanghaiCalendarDate();
    const dates = lastNShanghaiDates(DAILY_BRIEF_DAYS);
    if (!selectedDailyDate || !dates.includes(selectedDailyDate)) {
        selectedDailyDate = dates[0] || today;
    }
    const switcher = document.getElementById('daily-date-switcher');
    const container = document.getElementById('daily-brief');
    if (switcher) {
        switcher.innerHTML = renderDateSwitcherHtml(dates, selectedDailyDate, today);
    }
    if (container) {
        const brief = findDailyBrief(dailyBriefsData, selectedDailyDate);
        container.innerHTML = renderDailyBriefHtml(brief, selectedDailyDate);
    }
}

function selectDailyDate(ymd) {
    selectedDailyDate = ymd;
    renderDailyTab();
}

// Utility functions
function formatDate(isoString) {
    if (!isoString) return '未知时间';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize
loadData();
