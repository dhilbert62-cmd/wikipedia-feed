// Wikipedia Feed - Client Application

const API_BASE = window.location.origin;

// State
let currentSource = null; // 'local' or 'live'
let currentUser = null;
let currentAlgorithm = 'random';
let currentCategory = '';
let articles = [];
let isLoading = false;
let hasMore = true;

// DOM Elements
const sourcePicker = document.getElementById('source-picker');
const userPicker = document.getElementById('user-picker');
const mainFeed = document.getElementById('main-feed');
const sourceLocal = document.getElementById('source-local');
const sourceLive = document.getElementById('source-live');
const sourceGrokipedia = document.getElementById('source-grokipedia');
const sourceBadge = document.getElementById('source-badge');
const userList = document.getElementById('user-list');
const newUserName = document.getElementById('new-user-name');
const addUserBtn = document.getElementById('add-user-btn');
const guestBtn = document.getElementById('guest-btn');
const feedContainer = document.getElementById('feed-container');
const algorithmSelect = document.getElementById('algorithm-select');
const categorySelect = document.getElementById('category-select');
const userStats = document.getElementById('user-stats');
const clickCount = document.getElementById('click-count');
const loading = document.getElementById('loading');
const noMore = document.getElementById('no-more');
const articleModal = document.getElementById('article-modal');
const articleContent = document.getElementById('article-content');
const modalClose = document.getElementById('modal-close');
const switchUserBtn = document.getElementById('switch-user-btn');
const switchSourceBtn = document.getElementById('switch-source-btn');
const currentUserName = document.getElementById('current-user-name');

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    await checkLocalSource();
    setupEventListeners();
    checkSavedSource();
}

// ==================== SOURCE SELECTION ====================

async function checkLocalSource() {
    // Check if local ZIM is available
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        if (response.ok) {
            sourceLocal.classList.remove('disabled');
            sourceLocal.disabled = false;
            document.getElementById('local-status').textContent = 'Available';
            document.getElementById('local-status').className = 'source-status available';
        }
    } catch (e) {
        document.getElementById('local-status').textContent = 'Not found';
        document.getElementById('local-status').className = 'source-status unavailable';
    }
}

function selectSource(source) {
    currentSource = source;
    localStorage.setItem('wiki_source', source);
    
    // Update badge
    if (source === 'local') {
        sourceBadge.textContent = '💾 Local';
    } else if (source === 'grokipedia') {
        sourceBadge.textContent = '🤖 Grokipedia';
    } else {
        sourceBadge.textContent = '🌐 Live';
    }
    
    // Show user picker
    sourcePicker.classList.add('hidden');
    userPicker.classList.remove('hidden');
    
    loadUsers();
}

function checkSavedSource() {
    const saved = localStorage.getItem('wiki_source');
    if (saved) {
        currentSource = saved;
        if (saved === 'local') {
            sourceBadge.textContent = '💾 Local';
        } else if (saved === 'grokipedia') {
            sourceBadge.textContent = '🤖 Grokipedia';
        } else {
            sourceBadge.textContent = '🌐 Live';
        }
        userPicker.classList.remove('hidden');
        loadUsers();
    }
}

function switchSource() {
    currentSource = null;
    currentUser = null;
    localStorage.removeItem('wiki_source');
    localStorage.removeItem('wiki_user');
    userPicker.classList.add('hidden');
    mainFeed.classList.add('hidden');
    sourcePicker.classList.remove('hidden');
}

// ==================== USER MANAGEMENT ====================

async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE}/api/users`);
        const data = await response.json();
        renderUserList(data.users || []);
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function renderUserList(users) {
    userList.innerHTML = '';
    
    if (users.length === 0) {
        userList.innerHTML = '<p class="no-users">No users yet. Add one below!</p>';
        return;
    }
    
    users.forEach(user => {
        const userEl = document.createElement('div');
        userEl.className = 'user-item';
        userEl.textContent = user.name;
        userEl.onclick = () => loginUser(user.id, user.name);
        userList.appendChild(userEl);
    });
}

async function createUser() {
    const name = newUserName.value.trim();
    if (!name) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/users`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        
        if (response.ok) {
            const user = await response.json();
            newUserName.value = '';
            await loadUsers();
            loginUser(user.id, user.name);
        } else {
            const error = await response.json();
            alert(error.error || 'Error creating user');
        }
    } catch (error) {
        console.error('Error creating user:', error);
    }
}

function loginUser(userId, userName) {
    currentUser = {id: userId, name: userName};
    localStorage.setItem('wiki_user', JSON.stringify(currentUser));
    
    // Load user preferences
    loadUserPreferences(userId);
    
    // Show main feed
    userPicker.classList.add('hidden');
    mainFeed.classList.remove('hidden');
    currentUserName.textContent = userName;
    
    // Load articles
    loadArticles();
}

function loginAsGuest() {
    currentUser = null;
    localStorage.removeItem('wiki_user');
    
    userPicker.classList.add('hidden');
    mainFeed.classList.remove('hidden');
    currentUserName.textContent = 'Guest';
    
    loadArticles();
}

function switchUser() {
    currentUser = null;
    localStorage.removeItem('wiki_user');
    userPicker.classList.remove('hidden');
    mainFeed.classList.add('hidden');
    loadUsers();
}

async function loadUserPreferences(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/users/${userId}`);
        const data = await response.json();
        
        if (data.preferences) {
            currentAlgorithm = data.preferences.algorithm || 'random';
            currentCategory = data.preferences.selected_category || '';
            
            algorithmSelect.value = currentAlgorithm;
            if (currentCategory) {
                categorySelect.value = currentCategory;
                categorySelect.classList.remove('hidden');
            }
            
            updateUserStats(userId);
        }
    } catch (error) {
        console.error('Error loading preferences:', error);
    }
}

async function updateUserStats(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/clicks/${userId}/stats`);
        const data = await response.json();
        
        clickCount.textContent = `${data.total} clicks`;
        userStats.classList.remove('hidden');
        
        // Show learning indicator if enough clicks
        if (data.total >= 50) {
            clickCount.textContent += ' (learning active!)';
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ==================== ARTICLES ====================

async function loadArticles() {
    if (isLoading || !hasMore) return;
    
    isLoading = true;
    loading.classList.remove('hidden');
    noMore.classList.add('hidden');
    
    let url = `${API_BASE}/api/articles?limit=20&algorithm=${currentAlgorithm}&source=${currentSource}`;
    
    if (currentUser) {
        url += `&user_id=${currentUser.id}`;
    }
    
    if (currentAlgorithm === 'category' && currentCategory) {
        url += `&category=${currentCategory}`;
    }
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.articles && data.articles.length > 0) {
            articles = data.articles;
            renderArticles(articles);
            hasMore = data.articles.length >= 20;
        } else {
            hasMore = false;
            noMore.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error loading articles:', error);
    } finally {
        isLoading = false;
        loading.classList.add('hidden');
        if (!hasMore) {
            noMore.classList.remove('hidden');
        }
    }
}

function renderArticles(articleList) {
    feedContainer.innerHTML = '';
    
    articleList.forEach(article => {
        const card = createArticleCard(article);
        feedContainer.appendChild(card);
    });
    
    // Setup infinite scroll
    setupInfiniteScroll();
}

function createArticleCard(article) {
    const card = document.createElement('div');
    card.className = 'article-card';
    card.dataset.title = article.title;
    card.dataset.path = article.path || article.title;
    card.dataset.categories = JSON.stringify(article.categories || []);
    
    const categories = article.categories || [];
    const categoryBadges = categories.slice(0, 3).map(cat => 
        `<span class="category-badge">${cat}</span>`
    ).join('');
    
    // Add thumbnail if available
    const thumbnailHtml = article.thumbnail ? 
        `<img src="${article.thumbnail}" alt="" class="article-card-image">` : '';
    
    card.innerHTML = `
        ${thumbnailHtml}
        <div class="article-card-content">
            <h2 class="article-title">${article.title}</h2>
            <div class="article-categories">${categoryBadges}</div>
            <p class="article-preview">${article.preview || ''}</p>
        </div>
        <div class="article-meta">
            <span>${article.word_count || 0} words</span>
        </div>
    `;
    
    card.onclick = () => openArticle(article);
    
    return card;
}

async function openArticle(article) {
    try {
        const response = await fetch(`${API_BASE}/api/article/${encodeURIComponent(article.title)}?source=${currentSource}`);
        const data = await response.json();
        
        if (data.content) {
            // Build thumbnail HTML if available
            const thumbnailHtml = data.thumbnail ? 
                `<img src="${data.thumbnail}" alt="${data.title}" class="article-hero-image">` : '';
            
            // Process content to prevent new tabs - make links open internally
            let content = data.content;
            if (currentSource === 'live') {
                // Convert Wikipedia links to internal navigation
                content = content.replace(/href="\/wiki\//g, 'href="#" data-wiki="');
            }
            
            articleContent.innerHTML = `
                ${thumbnailHtml}
                <h1>${data.title}</h1>
                <div class="article-categories">
                    ${(data.categories || []).map(cat => `<span class="category-badge">${cat}</span>`).join('')}
                </div>
                <div class="article-body">${content}</div>
            `;
            
            // Add click handler for wiki links
            articleContent.querySelectorAll('[data-wiki]').forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const wikiTitle = link.getAttribute('data-wiki');
                    if (wikiTitle) {
                        openArticle({title: wikiTitle});
                    }
                });
            });
            
            articleModal.classList.remove('hidden');
            
            // Record click if user is logged in
            if (currentUser) {
                recordClick(article);
            }
        }
    } catch (error) {
        console.error('Error loading article:', error);
    }
}

async function recordClick(article) {
    if (!currentUser) return;
    
    try {
        await fetch(`${API_BASE}/api/clicks`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: currentUser.id,
                title: article.title,
                path: article.path || article.title,
                categories: article.categories || []
            })
        });
        
        // Update stats
        updateUserStats(currentUser.id);
    } catch (error) {
        console.error('Error recording click:', error);
    }
}

function closeModal() {
    articleModal.classList.add('hidden');
}

// ==================== INFINITE SCROLL ====================

function setupInfiniteScroll() {
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    feedContainer.appendChild(sentinel);
    
    const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && !isLoading && hasMore) {
            loadMoreArticles();
        }
    }, {rootMargin: '100px'});
    
    observer.observe(sentinel);
}

async function loadMoreArticles() {
    if (isLoading || !hasMore) return;
    
    isLoading = true;
    loading.classList.remove('hidden');
    
    let url = `${API_BASE}/api/articles?limit=20&algorithm=${currentAlgorithm}&source=${currentSource}`;
    
    if (currentUser) {
        url += `&user_id=${currentUser.id}`;
    }
    
    if (currentAlgorithm === 'category' && currentCategory) {
        url += `&category=${currentCategory}`;
    }
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.articles && data.articles.length > 0) {
            data.articles.forEach(article => {
                const card = createArticleCard(article);
                feedContainer.appendChild(card);
            });
            hasMore = data.articles.length >= 20;
        } else {
            hasMore = false;
            noMore.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error loading more articles:', error);
    } finally {
        isLoading = false;
        loading.classList.add('hidden');
    }
}

// ==================== EVENT LISTENERS ====================

function setupEventListeners() {
    // Source selection
    sourceLocal.onclick = () => {
        if (!sourceLocal.disabled) selectSource('local');
    };
    sourceLive.onclick = () => selectSource('live');
    sourceGrokipedia.onclick = () => selectSource('grokipedia');
    
    // User creation
    addUserBtn.onclick = createUser;
    newUserName.onkeypress = (e) => {
        if (e.key === 'Enter') createUser();
    };
    
    // Guest login
    guestBtn.onclick = loginAsGuest;
    
    // Switch user
    switchUserBtn.onclick = switchUser;
    
    // Switch source
    switchSourceBtn.onclick = switchSource;
    
    // Algorithm selection
    algorithmSelect.onchange = async () => {
        currentAlgorithm = algorithmSelect.value;
        
        // Show/hide category select
        if (currentAlgorithm === 'category') {
            categorySelect.classList.remove('hidden');
        } else {
            categorySelect.classList.add('hidden');
        }
        
        // Save preference if logged in
        if (currentUser) {
            await fetch(`${API_BASE}/api/users/${currentUser.id}/preferences`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({algorithm: currentAlgorithm})
            });
        }
        
        // Reload articles
        hasMore = true;
        loadArticles();
    };
    
    // Category selection
    categorySelect.onchange = async () => {
        currentCategory = categorySelect.value;
        
        // Save preference
        if (currentUser && currentCategory) {
            await fetch(`${API_BASE}/api/users/${currentUser.id}/preferences`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({selected_category: currentCategory})
            });
        }
        
        // Reload
        hasMore = true;
        loadArticles();
    };
    
    // Modal close
    modalClose.onclick = closeModal;
    articleModal.onclick = (e) => {
        if (e.target === articleModal) closeModal();
    };
    
    // Keyboard shortcuts
    document.onkeydown = (e) => {
        if (e.key === 'Escape') closeModal();
    };
}
