#!/usr/bin/env python3
"""Wikipedia Feed - Flask API Server with User System"""

import sqlite3
import json
import re
import random
from pathlib import Path
from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Paths
DB_PATH = Path(__file__).parent / 'data' / 'users.db'
ZIM_PATH = Path('/home/dave/data/wikipedia/wikipedia_en_all_2016-02.zim')

# Jeopardy category weights (percentages)
JEOPARDY_WEIGHTS = {
    'History': 20,
    'Science': 18,
    'Geography': 15,
    'Literature': 12,
    'Arts': 10,
    'Sports': 8,
    'Politics': 7,
    'Religion': 5,
    'Nature': 3,
    'Technology': 2,
    'People': 0  # People is cross-cutting
}

# Category keywords for extraction
CATEGORY_KEYWORDS = {
    'Science': ['physics', 'chemistry', 'biology', 'scientist', 'research', 'experiment', 'scientific', 'theory', 'discover'],
    'History': ['war', 'battle', 'century', 'ancient', 'historic', 'dynasty', 'empire', 'revolt', 'treaty'],
    'Geography': ['country', 'city', 'river', 'mountain', 'continent', 'island', 'region', 'capital', 'population'],
    'Literature': ['book', 'author', 'novel', 'poem', 'playwright', 'wrote', 'published', 'literary', 'fiction'],
    'Arts': ['painting', 'sculpture', 'music', 'film', 'artist', 'museum', 'gallery', 'exhibition'],
    'Sports': ['game', 'player', 'team', 'championship', 'tournament', 'league', 'score', 'match'],
    'Politics': ['government', 'election', 'president', 'law', 'parliament', 'minister', 'senate', 'congress'],
    'Religion': ['god', 'church', 'bible', 'religious', 'faith', 'christian', 'islam', 'jewish', 'temple'],
    'Nature': ['animal', 'plant', 'species', 'ecosystem', 'environment', 'bird', 'fish', 'mammal'],
    'Technology': ['computer', 'software', 'internet', 'engineering', 'patent', 'invented', 'digital'],
    'People': ['born', 'died', 'biography', 'king', 'queen', 'president', 'scientist', 'author', 'actor']
}


def get_user_db():
    """Get user database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def extract_categories(text):
    """Extract categories from article text."""
    text_lower = text.lower()
    categories = []
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            categories.append(category)
    
    # Always add People if person-related keywords
    person_keywords = ['born', 'died', 'king', 'queen', 'president', 'emperor', 'scientist', 'author', 'actor']
    if any(kw in text_lower for kw in person_keywords):
        if 'People' not in categories:
            categories.append('People')
    
    return categories if categories else ['General']


# Wikipedia API headers (required)
WIKI_HEADERS = {
    'User-Agent': 'WikipediaFeed/1.0 (Firstmateclaw; research)'
}


def get_live_random_articles(limit=20):
    """Get random articles from live Wikipedia API."""
    import requests
    articles = []
    
    # Use Wikipedia's random endpoint
    for _ in range(limit * 2):
        try:
            # Get random article summary
            resp = requests.get(
                'https://en.wikipedia.org/api/rest_v1/page/random/summary',
                headers=WIKI_HEADERS,
                timeout=10
            )
            if resp.status_code != 200:
                continue
            
            data = resp.json()
            title = data.get('title', '')
            
            # Skip redirects and special pages
            if title.startswith('Wikipedia:') or title.startswith('Template:'):
                continue
            
            # Get full content with categories
            content_resp = requests.get(
                f'https://en.wikipedia.org/w/api.php',
                headers=WIKI_HEADERS,
                params={
                    'action': 'query',
                    'titles': title,
                    'prop': 'extracts|categories',
                    'exintro': False,
                    'explaintext': True,
                    'cllimit': 20,
                    'format': 'json'
                },
                timeout=10
            )
            
            categories = []
            content = ''
            if content_resp.status_code == 200:
                pages = content_resp.json().get('query', {}).get('pages', {})
                for page_id, page in pages.items():
                    if page_id == '-1':
                        continue
                    content = page.get('extract', '')
                    for cat in page.get('categories', []):
                        cat_name = cat.get('title', '').replace('Category:', '')
                        categories.append(cat_name)
            
            # Map Wikipedia categories to our categories
            mapped_cats = map_categories(categories)
            
            # Get thumbnail
            thumbnail = data.get('thumbnail', {}).get('source') if 'thumbnail' in data else None
            
            articles.append({
                'title': title,
                'path': title.replace(' ', '_'),
                'preview': data.get('extract', '')[:300],
                'content': content or data.get('extract', ''),
                'categories': mapped_cats,
                'word_count': len((content or '').split()),
                'thumbnail': thumbnail
            })
            
            if len(articles) >= limit:
                break
                
        except Exception as e:
            print(f"Error fetching live article: {e}")
            continue
    
    return articles


def get_live_article(title):
    """Get article from live Wikipedia API."""
    import requests
    
    # Get summary
    resp = requests.get(
        f'https://en.wikipedia.org/api/rest_v1/page/summary/{title}',
        headers=WIKI_HEADERS,
        timeout=10
    )
    
    if resp.status_code != 200:
        return None
    
    data = resp.json()
    
    # Get full content with categories
    content_resp = requests.get(
        'https://en.wikipedia.org/w/api.php',
        headers=WIKI_HEADERS,
        params={
            'action': 'query',
            'titles': title,
            'prop': 'extracts|categories',
            'exintro': False,
            'explaintext': True,
            'cllimit': 50,
            'format': 'json'
        },
        timeout=10
    )
    
    categories = []
    content = ''
    if content_resp.status_code == 200:
        pages = content_resp.json().get('query', {}).get('pages', {})
        for page_id, page in pages.items():
            if page_id == '-1':
                continue
            content = page.get('extract', '')
            for cat in page.get('categories', []):
                cat_name = cat.get('title', '').replace('Category:', '')
                categories.append(cat_name)
    
    mapped_cats = map_categories(categories)
    
    # Get full HTML
    html_resp = requests.get(
        f'https://en.wikipedia.org/api/rest_v1/page/mobile-html/{title}',
        headers=WIKI_HEADERS,
        timeout=15
    )
    
    full_content = content
    if html_resp.status_code == 200:
        full_content = html_resp.text
    
    # Get thumbnail from summary
    thumbnail = data.get('thumbnail', {}).get('source') if 'thumbnail' in data else None
    
    return {
        'title': data.get('title', title),
        'content': full_content,
        'categories': mapped_cats,
        'path': title.replace(' ', '_'),
        'thumbnail': thumbnail
    }


def map_categories(wiki_categories):
    """Map Wikipedia categories to our categories."""
    # Wikipedia category keywords to our categories
    category_map = {
        'Science': ['science', 'scientist', 'physics', 'chemistry', 'biology', 'research'],
        'History': ['history', 'war', 'battle', 'century', 'ancient', 'empire'],
        'Geography': ['geography', 'country', 'city', 'river', 'mountain', 'island'],
        'Literature': ['literature', 'book', 'author', 'novel', 'poem', 'writer'],
        'Arts': ['art', 'painting', 'sculpture', 'music', 'film', 'artist'],
        'Sports': ['sport', 'game', 'player', 'team', 'championship'],
        'Politics': ['politics', 'government', 'president', 'minister', 'election'],
        'Religion': ['religion', 'god', 'church', 'faith', 'religious'],
        'Nature': ['nature', 'animal', 'plant', 'species', 'environment'],
        'Technology': ['technology', 'computer', 'software', 'internet', 'engineering'],
        'People': ['people', 'born', 'died', 'king', 'queen', 'president']
    }
    
    matched = set()
    
    for wiki_cat in wiki_categories:
        wiki_cat_lower = wiki_cat.lower()
        for our_cat, keywords in category_map.items():
            if any(kw in wiki_cat_lower for kw in keywords):
                matched.add(our_cat)
    
    return list(matched) if matched else ['General']


def get_random_articles(limit=20, source='local'):
    """Get random articles from local ZIM or live Wikipedia."""
    
    if source == 'live':
        return get_live_random_articles(limit)
    
    # Local ZIM mode
    import libzim
    articles = []
    
    try:
        archive = libzim.Archive(str(ZIM_PATH))
        
        for _ in range(limit * 3):  # Try more times to get valid articles
            try:
                entry = archive.get_random_entry()
                if not entry or not entry.path.startswith('A/'):
                    continue
                    
                item = entry.get_item()
                if item.size > 50000:  # Skip very short articles
                    continue
                    
                content_bytes = item.content.tobytes()
                try:
                    content = content_bytes.decode('utf-8')
                except:
                    continue
                
                # Extract title and preview
                title = entry.title
                preview = re.sub(r'<[^>]+>', '', content[:500])
                preview = preview.replace('&nbsp;', ' ').replace('&amp;', '&')
                
                # Extract categories
                categories = extract_categories(content)
                
                articles.append({
                    'title': title,
                    'path': entry.path,
                    'preview': preview[:300] + '...' if len(preview) > 300 else preview,
                    'content': content,
                    'categories': categories,
                    'word_count': len(content.split())
                })
                
                if len(articles) >= limit:
                    break
            except:
                continue
                
    except Exception as e:
        print(f"Error reading ZIM: {e}")
    
    return articles


# ==================== USER ENDPOINTS ====================

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users."""
    conn = get_user_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, created_at FROM users ORDER BY name")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'users': users})


@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Name required'}), 400
    
    conn = get_user_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO preferences (user_id, algorithm) VALUES (?, 'random')", (user_id,))
        conn.commit()
        
        return jsonify({'id': user_id, 'name': name})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'User already exists'}), 400
    finally:
        conn.close()


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user info with preferences."""
    conn = get_user_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    
    cursor.execute("SELECT * FROM preferences WHERE user_id = ?", (user_id,))
    prefs = cursor.fetchone()
    
    conn.close()
    
    return jsonify({
        'user': dict(user),
        'preferences': dict(prefs) if prefs else {}
    })


@app.route('/api/users/<int:user_id>/preferences', methods=['PUT'])
def update_preferences(user_id):
    """Update user preferences."""
    data = request.get_json()
    
    conn = get_user_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM preferences WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO preferences (user_id) VALUES (?)", (user_id,))
    
    # Update fields
    if 'algorithm' in data:
        cursor.execute("UPDATE preferences SET algorithm = ? WHERE user_id = ?", 
                     (data['algorithm'], user_id))
    if 'selected_category' in data:
        cursor.execute("UPDATE preferences SET selected_category = ? WHERE user_id = ?",
                     (data['selected_category'], user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


# ==================== CLICK ENDPOINTS ====================

@app.route('/api/clicks', methods=['POST'])
def record_click():
    """Record a user click on an article."""
    data = request.get_json()
    user_id = data.get('user_id')
    title = data.get('title', '')
    path = data.get('path', '')
    categories = data.get('categories', [])
    
    if not user_id or not title:
        return jsonify({'error': 'user_id and title required'}), 400
    
    conn = get_user_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO clicks (user_id, article_title, article_path, categories)
        VALUES (?, ?, ?, ?)
    """, (user_id, title, path, json.dumps(categories)))
    
    # Update click count
    cursor.execute("UPDATE preferences SET click_count = click_count + 1 WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


@app.route('/api/clicks/<int:user_id>/stats')
def get_click_stats(user_id):
    """Get user's click statistics (category percentages)."""
    conn = get_user_db()
    cursor = conn.cursor()
    
    # Get total clicks
    cursor.execute("SELECT click_count FROM preferences WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    total_clicks = row[0] if row else 0
    
    if total_clicks == 0:
        conn.close()
        return jsonify({'total': 0, 'categories': {}})
    
    # Get category breakdown
    cursor.execute("SELECT categories FROM clicks WHERE user_id = ?", (user_id,))
    category_counts = {}
    
    for row in cursor.fetchall():
        cats = json.loads(row[0]) if row[0] else ['General']
        for cat in cats:
            category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Calculate percentages
    percentages = {cat: (count / total_clicks * 100) for cat, count in category_counts.items()}
    
    conn.close()
    
    return jsonify({
        'total': total_clicks,
        'categories': percentages
    })


# ==================== ARTICLE ENDPOINTS ====================

@app.route('/api/articles')
def get_articles():
    """Get articles with algorithm selection."""
    limit = int(request.args.get('limit', 20))
    user_id = request.args.get('user_id', type=int)
    algorithm = request.args.get('algorithm', 'random')
    selected_category = request.args.get('category', None)
    source = request.args.get('source', 'live')  # Default to live
    
    articles = get_random_articles(limit, source)
    
    # Filter by category if specified
    if selected_category and selected_category != 'all':
        articles = [a for a in articles if selected_category in a['categories']]
        # Need more if filtered
        while len(articles) < limit:
            more = get_random_articles(limit, source)
            for m in more:
                if selected_category in m['categories'] and m not in articles:
                    articles.append(m)
                    if len(articles) >= limit:
                        break
    
    # Apply user-based learning if enabled
    if user_id and algorithm == 'user_based':
        conn = get_user_db()
        cursor = conn.cursor()
        cursor.execute("SELECT click_count FROM preferences WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        click_count = row[0] if row else 0
        conn.close()
        
        # If we have enough clicks, weight by user preferences
        if click_count >= 50:
            # Get user stats
            stats = get_click_stats(user_id)
            user_cats = json.loads(stats.data)['categories']
            
            # Sort articles by user preference match
            def pref_score(article):
                score = 0
                for cat in article['categories']:
                    score += user_cats.get(cat, 0)
                return score
            
            articles.sort(key=pref_score, reverse=True)
    
    # Apply jeopardy weights if selected
    if algorithm == 'jeopardy':
        def jeopardy_score(article):
            score = 0
            for cat in article['categories']:
                score += JEOPARDY_WEIGHTS.get(cat, 0)
            return score
        
        articles.sort(key=jeopardy_score, reverse=True)
    
    # Return with standardized format
    return jsonify({
        'articles': articles[:limit],
        'algorithm': algorithm,
        'user_id': user_id
    })


@app.route('/api/article/<path:title>')
def get_article(title):
    """Get article by title."""
    import urllib.parse
    
    title = urllib.parse.unquote(title)
    source = request.args.get('source', 'live')
    
    # Try live first (default)
    if source == 'live':
        article = get_live_article(title)
        if article:
            return jsonify(article)
    
    # Fall back to local ZIM
    import libzim
    
    try:
        archive = libzim.Archive(str(ZIM_PATH))
        entry = archive.get_entry_by_title(title)
        
        if not entry:
            return jsonify({'error': 'Article not found'}), 404
        
        if entry.is_redirect:
            entry = entry.get_redirect_entry()
        
        item = entry.get_item()
        content = item.content.tobytes().decode('utf-8', errors='ignore')
        
        categories = extract_categories(content)
        
        return jsonify({
            'title': entry.title,
            'content': content,
            'categories': categories,
            'path': entry.path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/categories')
def get_categories():
    """Get available categories."""
    return jsonify({
        'categories': list(CATEGORY_KEYWORDS.keys()),
        'jeopardy_weights': JEOPARDY_WEIGHTS
    })


@app.route('/api/stats')
def get_stats():
    """Get database statistics."""
    conn = get_user_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(click_count) FROM preferences")
    click_count = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'users': user_count,
        'clicks': click_count
    })


# ==================== UI ====================

@app.route('/')
def index():
    """Serve the UI."""
    from flask import send_from_directory
    return send_from_directory('ui', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files."""
    from flask import send_from_directory
    return send_from_directory('ui', filename)


if __name__ == '__main__':
    print("🚀 Starting Wikipedia Feed Server...")
    print(f"   Users DB: {DB_PATH}")
    print(f"   ZIM: {ZIM_PATH}")
    print(f"   Open http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False, threaded=True)
