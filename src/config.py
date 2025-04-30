"""
Configuration file for the Discourse Scraper
"""

# Default headers for requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; DiscourseScraper/1.0; +http://your-contact-email.com)',
    'Accept': 'application/json, text/html,application/xhtml+xml,application/xml;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'X-Requested-With': 'XMLHttpRequest'
}

# Rate limiting configuration
RATE_LIMIT_DELAY = 2  # seconds between requests

# API endpoints
API_ENDPOINTS = {
    'categories': '/categories.json',
    'topics': '/t/{topic_id}.json',
    'posts': '/t/{topic_id}/posts.json'
}

# Discourse indicators for forum validation
DISCOURSE_INDICATORS = [
    'discourse',
    'd-header',
    'category-list',
    'topic-list',
    'discourse-forum'
]

# Output directory structure
OUTPUT_DIRS = {
    'base': 'Data',
    'logs': 'Data/logs',
    'topics': 'topics',
    'contents': 'contents'
}

# Pagination settings
POSTS_PER_PAGE = 50
MAX_PAGES_DEFAULT = 5 