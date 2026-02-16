"""Recommendation engine for Wikipedia feed"""

import sqlite3
import random
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class RecommendationEngine:
    """
    Self-learning recommendation engine for Wikipedia articles.
    
    Uses content-based filtering with engagement-weighted categories.
    """
    
    def __init__(self, db_path: str = "data/wikipedia.db"):
        self.db_path = db_path
    
    def get_recommendations(self,
                            user_id: str = "captain",
                            count: int = 20,
                            feed_mix: float = 0.3,
                            excluded_articles: List[int] = None) -> List[Dict]:
        """
        Get article recommendations for a user.
        
        Args:
            user_id: User identifier
            count: Number of recommendations
            feed_mix: 0.0 = all recommended, 1.0 = all random
            excluded_articles: Article IDs to exclude
            
        Returns:
            List of article dicts with relevance scores
        """
        excluded_articles = excluded_articles or []
        
        # Get user category preferences
        category_weights = self._get_category_weights(user_id)
        
        # Get user's read articles (for exclusion)
        read_articles = self._get_read_articles(user_id)
        exclude_set = set(excluded_articles + read_articles)
        
        # Calculate article scores
        scored_articles = self._score_articles(
            category_weights, 
            exclude_set,
            user_id
        )
        
        # Separate recommended vs random pools
        recommend_count = int(count * (1 - feed_mix))
        random_count = count - recommend_count
        
        recommendations = []
        
        # Get recommended articles (top scored)
        if scored_articles and recommend_count > 0:
            recommended = scored_articles[:recommend_count]
            for article, score in recommended:
                article['relevance_score'] = score
                article['recommendation_type'] = 'recommended'
                recommendations.append(article)
        
        # Fill remaining with random articles
        if random_count > 0:
            random_articles = self._get_random_articles(
                exclude_set, 
                random_count,
                user_id
            )
            for article in random_articles:
                article['relevance_score'] = 0.3  # Base score for random
                article['recommendation_type'] = 'discovery'
                recommendations.append(article)
        
        # Shuffle to mix types
        random.shuffle(recommendations)
        
        return recommendations[:count]
    
    def _get_category_weights(self, user_id: str) -> Dict[str, float]:
        """Get user's learned category preferences."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # First, calculate from engagement data
        cursor.execute("""
            SELECT 
                c.name,
                SUM(CASE 
                    WHEN e.event_type = 'view' THEN 1.0
                    WHEN e.event_type = 'read' THEN 2.0
                    WHEN e.event_type = 'bookmark' THEN 5.0
                    WHEN e.event_type = 'skip' THEN -2.0
                    ELSE 0.5
                END * 
                CASE WHEN e.duration_seconds > 0 
                    THEN MIN(e.duration_seconds / 600.0, 1.0) 
                    ELSE 0.5 
                END)
            FROM engagement e
            JOIN article_categories ac ON e.article_id = ac.article_id
            JOIN categories c ON ac.category_id = c.id
            WHERE e.user_id = ?
            GROUP BY c.name
            ORDER BY SUM(CASE 
                    WHEN e.event_type = 'view' THEN 1.0
                    WHEN e.event_type = 'read' THEN 2.0
                    WHEN e.event_type = 'bookmark' THEN 5.0
                    WHEN e.event_type = 'skip' THEN -2.0
                    ELSE 0.5
                END) DESC
            LIMIT 50
        """, (user_id,))
        
        weights = {}
        for row in cursor.fetchall():
            weights[row[0]] = max(0.1, row[1])  # Minimum weight
        
        conn.close()
        
        # Normalize weights
        if weights:
            max_w = max(weights.values())
            weights = {k: v / max_w for k, v in weights.items()}
        
        return weights
    
    def _score_articles(self,
                         category_weights: Dict[str, float],
                         exclude_set: set,
                         user_id: str) -> List[Tuple[Dict, float]]:
        """Score articles based on category match."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build category filter
        if category_weights:
            category_conditions = []
            params = []
            for cat, weight in category_weights.items():
                category_conditions.append("(a.categories LIKE ?)")
                params.append(f'%{cat}%')
            
            category_filter = " AND (" + " OR ".join(category_conditions) + ")"
        else:
            category_filter = ""
            params = []
        
        # Exclude blacklisted and already read
        if exclude_set:
            placeholders = ','.join('?' * len(exclude_set))
            exclude_filter = f" AND a.id NOT IN ({placeholders})"
            params.extend(exclude_set)
        else:
            exclude_filter = ""
        
        # Get articles matching categories
        query = f"""
            SELECT a.id, a.page_id, a.title, a.content, a.categories,
                   a.reading_time, a.word_count, a.access_count
            FROM articles a
            WHERE a.id > 0 {category_filter} {exclude_filter}
            ORDER BY a.access_count DESC
            LIMIT 500
        """
        
        cursor.execute(query, params)
        
        scored = []
        for row in cursor.fetchall():
            article = {
                'id': row[0],
                'page_id': row[1],
                'title': row[2],
                'content': row[3],
                'categories': json.loads(row[4]) if row[4] else [],
                'reading_time': row[5],
                'word_count': row[6],
                'access_count': row[7]
            }
            
            # Calculate category match score
            article_cats = article.get('categories', [])
            if article_cats and category_weights:
                match_scores = []
                for cat in article_cats:
                    if cat in category_weights:
                        match_scores.append(category_weights[cat])
                
                if match_scores:
                    category_score = max(match_scores)  # Best category match
                else:
                    category_score = 0.5  # Default score
            else:
                category_score = 0.5
            
            # Boost by popularity
            popularity_boost = min(article['access_count'] / 100, 1.0) * 0.2
            
            # Combined score
            total_score = (category_score * 0.7) + (popularity_boost * 0.3)
            
            scored.append((article, total_score))
        
        conn.close()
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored
    
    def _get_random_articles(self,
                             exclude_set: set,
                             count: int,
                             user_id: str) -> List[Dict]:
        """Get random articles for discovery."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if exclude_set:
            placeholders = ','.join('?' * len(exclude_set))
            exclude_filter = f"WHERE a.id NOT IN ({placeholders})"
            params = list(exclude_set)
        else:
            exclude_filter = ""
            params = []
        
        query = f"""
            SELECT a.id, a.page_id, a.title, a.content, a.categories,
                   a.reading_time, a.word_count
            FROM articles a
            {exclude_filter}
            ORDER BY RANDOM()
            LIMIT ?
        """
        params.append(count)
        
        cursor.execute(query, params)
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row[0],
                'page_id': row[1],
                'title': row[2],
                'content': row[3],
                'categories': json.loads(row[4]) if row[4] else [],
                'reading_time': row[5],
                'word_count': row[6]
            })
        
        conn.close()
        return articles
    
    def _get_read_articles(self, user_id: str) -> List[int]:
        """Get article IDs the user has read."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT article_id FROM engagement
            WHERE user_id = ? AND event_type IN ('view', 'read')
        """, (user_id,))
        
        articles = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return articles
    
    def get_category_browse(self, 
                            category: str,
                            user_id: str = "captain",
                            count: int = 20) -> List[Dict]:
        """Browse articles in a specific category."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.id, a.page_id, a.title, a.content, a.categories,
                   a.reading_time, a.word_count, a.access_count
            FROM articles a
            JOIN article_categories ac ON a.id = ac.article_id
            JOIN categories c ON ac.category_id = c.id
            WHERE c.name = ?
            ORDER BY a.access_count DESC
            LIMIT ?
        """, (category, count))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row[0],
                'page_id': row[1],
                'title': row[2],
                'content': row[3],
                'categories': json.loads(row[4]) if row[4] else [],
                'reading_time': row[5],
                'word_count': row[6],
                'access_count': row[7]
            })
        
        conn.close()
        return articles
    
    def search_articles(self, 
                        query: str,
                        user_id: str = "captain",
                        count: int = 20) -> List[Dict]:
        """Search articles by title or content."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.id, a.page_id, a.title, a.content, a.categories,
                   a.reading_time, a.word_count
            FROM articles a
            WHERE a.title LIKE ? OR a.content LIKE ?
            ORDER BY a.access_count DESC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', count))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': row[0],
                'page_id': row[1],
                'title': row[2],
                'content': row[3],
                'categories': json.loads(row[4]) if row[4] else [],
                'reading_time': row[5],
                'word_count': row[6]
            })
        
        conn.close()
        return articles


# Singleton instance
recommendation_engine = RecommendationEngine()
