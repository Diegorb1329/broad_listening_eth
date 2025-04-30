#!/usr/bin/env python
"""
Script para extraer el contenido completo de un tema, incluyendo todas las respuestas
con manejo de scroll infinito.

Uso:
    python scrape_full_topic.py <topic_url>

Ejemplo:
    python scrape_full_topic.py https://ethereum-magicians.org/t/eip-1559-fee-market-change-for-eth-1-0-chain/2783
"""

import sys
import os
import re
import json
import time
import logging
import pandas as pd
from bs4 import BeautifulSoup
import requests
from datetime import datetime

# Create logs directory if it doesn't exist
os.makedirs("Data/logs", exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"Data/logs/topic_scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

class TopicScraper:
    """Scraper para extraer todo el contenido de un tema, incluyendo todas las respuestas."""
    
    def __init__(self, base_url="https://ethereum-magicians.org"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest'
        })
        logging.info(f"Initialized scraper for {self.base_url}")
    
    def validate_topic_url(self, topic_url):
        """
        Validate a topic URL and attempt to correct it if necessary.
        
        Args:
            topic_url: The URL to validate
            
        Returns:
            Corrected URL or the original if validation was successful or couldn't be corrected
        """
        logging.info(f"Validating URL: {topic_url}")
        
        # Check if URL is well-formed and extract topic ID
        topic_id_match = re.search(r'/t/([^/]+)/(\d+)', topic_url)
        
        if not topic_id_match:
            logging.error(f"Invalid topic URL format: {topic_url}")
            return topic_url
        
        slug = topic_id_match.group(1)
        topic_id = topic_id_match.group(2)
        logging.info(f"Extracted topic ID: {topic_id} with slug: {slug}")
        
        # Try to get the topic via the Discourse API
        api_url = f"{self.base_url}/t/{topic_id}.json"
        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            
            # If we get a successful response, extract the correct slug
            topic_data = response.json()
            correct_slug = topic_data.get('slug', slug)
            
            # Build the correct URL
            corrected_url = f"{self.base_url}/t/{correct_slug}/{topic_id}"
            
            if corrected_url != topic_url:
                logging.info(f"URL corrected from {topic_url} to {corrected_url}")
                return corrected_url
            else:
                logging.info(f"URL is valid: {topic_url}")
                return topic_url
            
        except requests.exceptions.RequestException as e:
            logging.warning(f"Could not verify topic URL via API: {e}")
            
            # Try a HEAD request to check if the URL exists
            try:
                head_response = self.session.head(topic_url)
                if head_response.status_code == 200:
                    logging.info(f"URL exists: {topic_url}")
                    return topic_url
                else:
                    logging.warning(f"URL returns {head_response.status_code}: {topic_url}")
                    # Try alternative URLs if available in topics CSVs
                    alternative_url = self.find_alternative_url(topic_id, slug)
                    if alternative_url:
                        logging.info(f"Found alternative URL: {alternative_url}")
                        return alternative_url
            except requests.exceptions.RequestException:
                logging.error(f"Could not verify topic URL with HEAD request: {topic_url}")
        
        # If all validation attempts fail, return the original URL
        return topic_url
    
    def find_alternative_url(self, topic_id, slug):
        """
        Try to find alternative URL for a topic by searching in the CSV files.
        
        Args:
            topic_id: The topic ID to look for
            slug: The slug to look for in the search
            
        Returns:
            Alternative URL if found, None otherwise
        """
        topics_dir = "Data/topics"
        if not os.path.exists(topics_dir):
            return None
        
        for csv_file in os.listdir(topics_dir):
            if not csv_file.endswith("_topics.csv"):
                continue
                
            csv_path = os.path.join(topics_dir, csv_file)
            try:
                df = pd.read_csv(csv_path)
                
                # Search for the topic ID in the URLs
                for _, row in df.iterrows():
                    url = row.get('url', '')
                    if f"/{topic_id}" in url:
                        return url
                
                # If not found by ID, try searching by title/slug
                search_terms = slug.replace('-', ' ').lower().split()
                for _, row in df.iterrows():
                    title = row.get('title', '').lower()
                    if all(term in title for term in search_terms):
                        return row.get('url', '')
                        
            except Exception as e:
                logging.error(f"Error searching in CSV {csv_file}: {e}")
                
        return None
    
    def get_json(self, url, params=None):
        """Fetch JSON data with error handling and rate limiting"""
        try:
            logging.info(f"Fetching JSON: {url}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            # Be polite, wait between requests
            time.sleep(2)
            
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {url}: {e}")
            return None
    
    def extract_topic_id(self, topic_url):
        """Extract the topic ID from a topic URL."""
        topic_id_match = re.search(r'/t/[^/]+/(\d+)', topic_url)
        if topic_id_match:
            return topic_id_match.group(1)
        return None
    
    def scrape_topic_content(self, topic_url):
        """
        Scrape the content of a specific topic, including all replies
        
        Args:
            topic_url: URL of the topic to scrape
        
        Returns:
            Topic data including all posts
        """
        logging.info(f"Scraping content from topic: {topic_url}")
        
        # Extract topic ID
        topic_id = self.extract_topic_id(topic_url)
        if not topic_id:
            logging.error(f"Could not extract topic ID from URL: {topic_url}")
            return None
        
        # Get topic info from the JSON API
        topic_json_url = f"{self.base_url}/t/{topic_id}.json"
        topic_data = self.get_json(topic_json_url)
        
        if not topic_data:
            logging.error(f"Failed to fetch topic data from {topic_json_url}")
            return None
        
        # Extract basic topic information
        title = topic_data.get('title', 'Unknown Title')
        post_count = topic_data.get('posts_count', 0)
        category_id = topic_data.get('category_id')
        
        # Get category info if available
        subcategory = None
        if category_id:
            category_url = f"{self.base_url}/c/{category_id}.json"
            category_data = self.get_json(category_url)
            if category_data and 'category' in category_data:
                subcategory = category_data['category'].get('name')
        
        logging.info(f"Topic '{title}' has approximately {post_count} posts, will need to load multiple pages")
        
        # Get the first batch of posts
        posts = []
        
        # Discourse API limits the number of posts per request, so we need to paginate
        post_ids = topic_data.get('post_stream', {}).get('stream', [])
        chunks = [post_ids[i:i+50] for i in range(0, len(post_ids), 50)]
        
        for chunk in chunks:
            post_json_url = f"{self.base_url}/t/{topic_id}/posts.json"
            posts_data = self.get_json(post_json_url, params={'post_ids[]': chunk})
            
            if not posts_data or 'post_stream' not in posts_data:
                logging.warning(f"Failed to fetch post data chunk from {post_json_url}")
                continue
                
            post_list = posts_data.get('post_stream', {}).get('posts', [])
            
            for post_data in post_list:
                post = self.extract_post_from_json(post_data)
                if post:
                    posts.append(post)
            
            logging.info(f"Extracted {len(post_list)} posts from chunk")
        
        # Sort posts by post number to ensure they're in the correct order
        posts.sort(key=lambda x: x.get('post_number', 0))
        
        topic_data = {
            'url': topic_url,
            'title': title,
            'subcategory': subcategory,
            'posts': posts,
            'post_count': len(posts)
        }
        
        
        logging.info(f"Successfully scraped topic '{title}' with {len(posts)} posts")
        
        return topic_data
    
    def extract_post_from_json(self, post_data):
        """Extract post data from JSON response."""
        if not post_data:
            return None
        
        # Skip deleted or hidden posts
        if post_data.get('deleted') or post_data.get('hidden'):
            return None
            
        return {
            'post_number': post_data.get('post_number'),
            'username': post_data.get('username', 'Unknown User'),
            'date': post_data.get('created_at'),
            'content': BeautifulSoup(post_data.get('cooked', ''), 'html.parser').text.strip(),
            'content_html': post_data.get('cooked', ''),
            'likes': post_data.get('like_count', 0)
        }
    
    def save_topic_to_csv(self, topic_data, output_dir="Data/full_topics"):
        """Save the topic data to CSV files."""
        if not topic_data:
            logging.error("No topic data to save")
            return None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Sanitize topic title for filename
        title = topic_data['title']
        safe_title = ''.join(c if c.isalnum() else '_' for c in title)
        safe_title = safe_title[:50]  # Limit filename length
        
        # Save basic topic metadata
        topic_meta = {
            'url': [topic_data['url']],
            'title': [topic_data['title']],
            'subcategory': [topic_data.get('subcategory')],
            'post_count': [topic_data['post_count']]
        }
        meta_df = pd.DataFrame(topic_meta)
        meta_filename = f"{output_dir}/{safe_title}_meta.csv"
        meta_df.to_csv(meta_filename, index=False)
        
        # Save posts as CSV
        posts_df = pd.DataFrame(topic_data['posts'])
        posts_filename = f"{output_dir}/{safe_title}_posts.csv"
        posts_df.to_csv(posts_filename, index=False)
        
        logging.info(f"Saved topic '{title}' with {topic_data['post_count']} posts to {posts_filename}")
        return posts_filename

def main():
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Error: Topic URL required")
        print(__doc__)
        sys.exit(1)
    
    topic_url = sys.argv[1]
    
    # Validate URL
    if not topic_url.startswith("https://ethereum-magicians.org/t/"):
        print("Error: URL must be an Ethereum Magicians topic URL")
        print("Example: https://ethereum-magicians.org/t/eip-1559-fee-market-change-for-eth-1-0-chain/2783")
        sys.exit(1)
    
    # Create output directory
    os.makedirs("Data/full_topics", exist_ok=True)
    
    # Initialize scraper
    scraper = TopicScraper()
    
    # Validate and potentially correct the URL
    validated_url = scraper.validate_topic_url(topic_url)
    if validated_url != topic_url:
        print(f"URL corrected to: {validated_url}")
        topic_url = validated_url
    
    # Extract topic content
    topic_data = scraper.scrape_topic_content(topic_url)
    
    if topic_data:
        # Save to CSV
        output_file = scraper.save_topic_to_csv(topic_data)
        print(f"Successfully scraped topic '{topic_data['title']}' with {topic_data['post_count']} posts")
        print(f"Data saved to: {output_file}")
    else:
        print("Failed to scrape topic. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main() 