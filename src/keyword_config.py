"""
Configuration file for the Keyword-based Discourse Scraper
"""

# Default headers for HTTP requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# API endpoints
API_ENDPOINTS = {
    'categories': '/categories.json',
    'search': '/search.json',
    'topics': '/latest.json'
}

# Output directory structure
OUTPUT_DIRS = {
    'base': 'Data',  # Base directory for all output
    'logs': 'Data/logs',  # Directory for log files
    'topics': 'Data/topics',  # Directory for topic lists
    'contents': 'Data/topic_contents'  # Directory for topic contents
}

# Discourse HTML indicators for site validation
DISCOURSE_INDICATORS = [
    'discourse',
    'discourse-theme',
    'discourse-color-scheme',
    'd-header',
    'd-topic'
]

# Rate limiting delay (in seconds)
RATE_LIMIT_DELAY = 2

# Search settings
MAX_SEARCH_PAGES = 100  # Maximum number of search pages to process
RESULTS_PER_PAGE = 30   # Typical number of results per search page 