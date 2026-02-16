"""Wikipedia Feed Configuration"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database path
DB_PATH = os.environ.get('WIKIPEDIA_DB', str(BASE_DIR / 'data' / 'wikipedia.db'))

# Wikipedia dump path
DUMP_PATH = os.environ.get('WIKIPEDIA_DUMP', str(BASE_DIR / 'data' / 'enwiki-2016-pages-articles.xml.bz2'))

# Server configuration
SERVER_HOST = os.environ.get('HOST', '0.0.0.0')
SERVER_PORT = int(os.environ.get('PORT', 5000))
DEBUG_MODE = os.environ.get('DEBUG', 'false').lower() == 'true'

# Ingestion settings
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', 100))
MAX_CATEGORIES_PER_ARTICLE = 20
MIN_ARTICLE_LENGTH = 100  # Skip very short articles

# Engagement weights
WEIGHTS = {
    'view': 1.0,
    'read': 2.0,
    'bookmark': 5.0,
    'skip': -2.0,
    'scroll': 0.5
}

# Reading speed (words per minute)
READING_SPEED_WPM = 200

# Feed settings
DEFAULT_FEED_MIX = 0.3  # 30% recommended, 70% random
ARTICLES_PER_PAGE = 20
MAX_ARTICLES_PER_REQUEST = 50
