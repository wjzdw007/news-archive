// Global data store
let articlesData = [];
let topicsData = [];
let xPostsData = [];
let articlesMap = new Map(); // url -> article

// Tab switching
document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        const tabName = button.dataset.tab;
        switchTab(tabName);
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

// Load data on page load
async function loadData() {
    try {
        const [articles, topics, xPosts] = await Promise.all([
            fetch('data/articles.json').then(r => r.json()),
            fetch('data/topics.json').then(r => r.json()),
            fetch('data/x_posts.json').then(r => r.json())
        ]);
        
        articlesData = articles;
        topicsData = topics;
        xPostsData = xPosts;
        
        // Build articles map for quick lookup
        articles.forEach(article => {
            articlesMap.set(article.url, article);
        });
        
        renderNewsList();
        renderTopicsList();
        renderXList();
        
    } catch (error) {
        console.error('Failed to load data:', error);
        document.querySelectorAll('.loading').forEach(el => {
            el.textContent = '加载失败';
        });
    }
}

// Render news list
function renderNewsList() {
    const container = document.getElementById('news-list');
    
    if (articlesData.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无新闻</div>';
        return;
    }
    
    const html = articlesData.map(article => {
        const date = formatDate(article.fetched_at);
        const summary = article.summary || '无摘要';
        const oneLineSummary = summary.length > 100 ? summary.substring(0, 100) + '...' : summary;
        
        return `
            <div class="article-item" onclick="showArticleDetail('${escapeHtml(article.url)}')">
                <h3 class="article-title">${escapeHtml(article.title)}</h3>
                <div class="article-meta">
                    <span class="source">${escapeHtml(article.source)}</span>
                    <span class="date">${date}</span>
                </div>
                <p class="article-summary">${escapeHtml(oneLineSummary)}</p>
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

// Show article detail
function showArticleDetail(url) {
    const article = articlesMap.get(url);
    if (!article) return;
    
    // Public site: summary + original link + topic jump only (no content_snapshot).
    const summary = article.summary || '无摘要';
    const date = formatDate(article.published_at || article.fetched_at);
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

// Render topics list
function renderTopicsList() {
    const container = document.getElementById('topics-list');
    
    if (topicsData.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无专题</div>';
        return;
    }
    
    const html = topicsData.map(topic => {
        const date = formatDate(topic.generated_at);
        const sources = topic.sources || [];
        const bulletPoints = sources.slice(0, 3).map(s => `• ${s.title || '无标题'}`).join('<br>');
        const moreText = sources.length > 3 ? `<br>...及 ${sources.length - 3} 条更多` : '';
        
        return `
            <div class="topic-item" onclick="showTopicDetail('${escapeHtml(topic.topic_id)}')">
                <h3 class="topic-title">${escapeHtml(topic.title)}</h3>
                <div class="topic-meta">
                    <span class="date">${date}</span>
                    <span class="source-count">${sources.length} 个来源</span>
                </div>
                <div class="topic-preview">${bulletPoints}${moreText}</div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

// Show topic detail
function showTopicDetail(topicId) {
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
