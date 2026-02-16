"""Engagement tracking for Wikipedia feed"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class EventType(Enum):
    VIEW = "view"
    READ = "read"
    BOOKMARK = "bookmark"
    SKIP = "skip"
    SCROLL = "scroll"

@dataclass
class EngagementEvent:
    article_id: int
    event_type: str
    user_id: str = "captain"
    duration_seconds: int = 0
    scroll_depth: float = 0.0
    timestamp: datetime = None

class EngagementTracker:
    """
    Track user engagement with articles.
    Provides data for the recommendation algorithm.
    """
    
    def __init__(self, db_path: str = "data/wikipedia.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize engagement tables if needed."""
        # Tables are created via schema.sql
        pass
    
    def record_event(self, 
                     article_id: int,
                     event_type: str,
                     user_id: str = "captain",
                     duration_seconds: int = 0,
                     scroll_depth: float = 0.0) -> int:
        """
        Record an engagement event.
        
        Args:
            article_id: Wikipedia article ID
            event_type: Type of engagement
            user_id: User identifier
            duration_seconds: Time spent (for view/read events)
            scroll_depth: How much was scrolled (0.0 to 1.0)
            
        Returns:
            Event ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO engagement 
            (article_id, user_id, event_type, duration_seconds, scroll_depth)
            VALUES (?, ?, ?, ?, ?)
        """, (article_id, user_id, event_type, duration_seconds, scroll_depth))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return event_id
    
    def get_article_engagement(self, 
                                article_id: int, 
                                user_id: str = "captain") -> Dict:
        """
        Get engagement summary for an article.
        
        Returns:
            Dict with: total_views, avg_duration, avg_scroll, bookmarks, skips
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_views,
                AVG(duration_seconds) as avg_duration,
                AVG(scroll_depth) as avg_scroll
            FROM engagement
            WHERE article_id = ? AND user_id = ?
        """, (article_id, user_id))
        
        row = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) FROM engagement
            WHERE article_id = ? AND user_id = ? AND event_type = 'bookmark'
        """, (article_id, user_id))
        
        bookmarks = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM engagement
            WHERE article_id = ? AND user_id = ? AND event_type = 'skip'
        """, (article_id, user_id))
        
        skips = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_views': row[0] or 0,
            'avg_duration': row[1] or 0,
            'avg_scroll': row[2] or 0,
            'bookmarks': bookmarks,
            'skips': skips
        }
    
    def get_user_category_preferences(self, 
                                       user_id: str = "captain",
                                       days: int = 30) -> Dict[str, float]:
        """
        Calculate user's category preferences based on engagement.
        
        Returns:
            Dict mapping category name to preference weight
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get engagement by category
        cursor.execute("""
            SELECT 
                ac.article_id,
                e.event_type,
                e.duration_seconds,
                e.scroll_depth,
                e.timestamp
            FROM engagement e
            JOIN articles a ON e.article_id = a.id
            JOIN article_categories ac ON a.id = ac.article_id
            JOIN categories c ON ac.category_id = c.id
            WHERE e.user_id = ?
            AND e.timestamp > datetime('now', '-' || ? || ' days')
        """, (user_id, days))
        
        category_scores = {}
        category_counts = {}
        
        for row in cursor.fetchall():
            article_id, event_type, duration, scroll_depth, timestamp = row
            
            # Get categories for this article
            cursor.execute("""
                SELECT c.name FROM categories c
                JOIN article_categories ac ON c.id = ac.category_id
                WHERE ac.article_id = ?
            """, (article_id,))
            
            for (cat_name,) in cursor.fetchall():
                # Calculate event weight
                weights = {
                    'view': 1.0,
                    'read': 2.0,
                    'bookmark': 5.0,
                    'skip': -2.0,
                    'scroll': 0.5
                }
                
                weight = weights.get(event_type, 1.0)
                
                # Time factor (cap at 10 minutes)
                time_factor = min((duration or 0) / 600, 1.0)
                
                # Recency factor (exponential decay)
                days_ago = (datetime.now() - datetime.fromisoformat(timestamp)).days
                recency_factor = 0.9 ** days_ago
                
                score = weight * time_factor * recency_factor
                
                category_scores[cat_name] = category_scores.get(cat_name, 0) + score
                category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
        
        conn.close()
        
        # Normalize scores
        max_score = max(category_scores.values()) if category_scores else 1
        normalized = {k: v / max_score for k, v in category_scores.items()}
        
        return normalized
    
    def get_recent_sessions(self, 
                            user_id: str = "captain",
                            limit: int = 10) -> List[Dict]:
        """Get recent reading sessions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reading_sessions
            WHERE user_id = ?
            ORDER BY start_time DESC
            LIMIT ?
        """, (user_id, limit))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row[0],
                'start_time': row[2],
                'end_time': row[3],
                'articles_read': row[4],
                'total_duration': row[5]
            })
        
        conn.close()
        return sessions
    
    def start_session(self, user_id: str = "captain") -> int:
        """Start a new reading session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO reading_sessions (user_id)
            VALUES (?)
        """, (user_id,))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def end_session(self, 
                    session_id: int,
                    articles_read: int = 0,
                    total_duration: int = 0):
        """End a reading session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE reading_sessions
            SET end_time = CURRENT_TIMESTAMP,
                articles_read = ?,
                total_duration_seconds = ?
            WHERE id = ?
        """, (articles_read, total_duration, session_id))
        
        conn.commit()
        conn.close()


# Singleton instance
engagement_tracker = EngagementTracker()
