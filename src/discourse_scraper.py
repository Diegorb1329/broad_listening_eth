import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
import os
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
import sys
import config

class DiscourseScraper:
    """
    Generic scraper for any Discourse Forum
    """
    
    def __init__(self, base_url: str, custom_headers: Dict[str, str] = None):
        # Remove trailing slash if present
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Use custom headers if provided, otherwise use default headers from config
        headers = custom_headers if custom_headers is not None else config.DEFAULT_HEADERS
        self.session.headers.update(headers)
        
        # Create logs directory if it doesn't exist
        os.makedirs(config.OUTPUT_DIRS['logs'], exist_ok=True)
        
        # Set up logging with forum name in the log file
        forum_name = self.base_url.split('//')[1].split('.')[0]
        log_filename = f"{config.OUTPUT_DIRS['logs']}/discourse_scraping_{forum_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        
        logging.info(f"Initialized scraper for {self.base_url}")
        
    def validate_discourse_forum(self) -> bool:
        """
        Validate if the provided URL is a Discourse forum using both JSON API and HTML checks
        """
        try:
            # Try to access the site's JSON API
            categories_url = f"{self.base_url}{config.API_ENDPOINTS['categories']}"
            response = self.session.get(categories_url)
            
            # If we get a successful JSON response, it's definitely a Discourse forum
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'category_list' in data:
                        logging.info("Successfully validated Discourse forum via JSON API")
                        return True
                except json.JSONDecodeError:
                    pass
            
            # Fallback to HTML check
            response = self.session.get(self.base_url)
            response.raise_for_status()
            
            # Check if it's a Discourse site by looking for typical Discourse elements
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for common Discourse elements from config
            discourse_indicators = config.DISCOURSE_INDICATORS
            
            # Check meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                content = meta.get('content', '').lower()
                if 'discourse' in content:
                    logging.info("Successfully validated Discourse forum via meta tags")
                    return True
            
            # Check body classes and IDs
            body_tag = soup.find('body')
            if body_tag:
                body_classes = body_tag.get('class', [])
                body_id = body_tag.get('id', '')
                if 'discourse' in ' '.join(body_classes).lower() or 'discourse' in body_id.lower():
                    logging.info("Successfully validated Discourse forum via body attributes")
                    return True
            
            # Check for any of the indicators in the page source
            page_source = response.text.lower()
            if any(indicator in page_source for indicator in discourse_indicators):
                logging.info("Successfully validated Discourse forum via HTML indicators")
                return True
            
            logging.error("URL does not appear to be a Discourse forum")
            return False
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to validate forum URL: {e}")
            return False
    
    def get_page(self, url: str) -> Optional[str]:
        """Fetch a page with error handling and rate limiting"""
        try:
            logging.info(f"Fetching page: {url}")
            response = self.session.get(url)
            response.raise_for_status()
            
            # Be polite, wait between requests using config
            time.sleep(config.RATE_LIMIT_DELAY)
            
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None
    
    def scrape_categories(self) -> List[Dict[str, Any]]:
        """Scrape all categories from the forum homepage using the JSON API"""
        logging.info("Starting to scrape categories")
        
        # Use the categories.json endpoint
        categories_url = f"{self.base_url}/categories.json"
        categories_data = self.get_json(categories_url)
        
        if not categories_data or 'category_list' not in categories_data:
            logging.error("Failed to fetch categories data")
            return []
        
        categories = []
        category_list = categories_data['category_list'].get('categories', [])
        
        for category_data in category_list:
            try:
                # Skip uncategorized category if it's empty
                if category_data.get('name') == 'uncategorized' and category_data.get('topic_count', 0) == 0:
                    continue
                    
                category_name = category_data.get('name', '')
                category_id = category_data.get('id')
                
                # Construct the category URL
                slug = category_data.get('slug', category_name.lower().replace(' ', '-'))
                category_url = f"{self.base_url}/c/{slug}/{category_id}"
                
                # Get topic count
                topic_count = category_data.get('topic_count', 0)
                
                categories.append({
                    'name': category_name,
                    'url': category_url,
                    'topic_count': topic_count,
                    'id': category_id
                })
                
            except Exception as e:
                logging.error(f"Error processing category data: {e}")
                continue
        
        logging.info(f"Found {len(categories)} categories")
        return categories
    
    def scrape_topics_from_category(self, category_url: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """Scrape topics from a category using the JSON API"""
        logging.info(f"Scraping topics from category: {category_url}")
        topics = []
        seen_topic_ids = set()
        
        # Extract category ID from URL
        category_id_match = re.search(r'/c/[^/]+/(\d+)', category_url)
        if not category_id_match:
            logging.error(f"Could not extract category ID from URL: {category_url}")
            return topics
            
        category_id = category_id_match.group(1)
        current_page = 0
        
        while current_page < max_pages:
            # Construct API URL
            topics_url = f"{self.base_url}/c/{category_id}.json"
            if current_page > 0:
                topics_url += f"?page={current_page}"
            
            logging.info(f"Fetching JSON: {topics_url}")
            response_data = self.get_json(topics_url)
            
            if not response_data or 'topic_list' not in response_data:
                logging.warning(f"No topic data found on page {current_page}")
                break
            
            topic_list = response_data['topic_list'].get('topics', [])
            
            if not topic_list:
                logging.info(f"No more topics found on page {current_page}")
                break
            
            new_topics_count = 0
            
            for topic_data in topic_list:
                try:
                    # Skip if we've already seen this topic
                    topic_id = topic_data.get('id')
                    if topic_id in seen_topic_ids:
                        continue
                    
                    seen_topic_ids.add(topic_id)
                    
                    # Skip pinned topics after first page
                    if current_page > 0 and topic_data.get('pinned'):
                        continue
                    
                    topic_title = topic_data.get('title', '')
                    topic_slug = topic_data.get('slug', '')
                    
                    # Construct topic URL
                    topic_url = f"{self.base_url}/t/{topic_slug}/{topic_id}"
                    
                    # Get metadata
                    replies_count = topic_data.get('posts_count', 1) - 1  # Subtract original post
                    views_count = topic_data.get('views', 0)
                    created_at = topic_data.get('created_at')
                    last_posted_at = topic_data.get('last_posted_at')
                    
                    topics.append({
                        'title': topic_title,
                        'url': topic_url,
                        'replies_count': replies_count,
                        'views_count': views_count,
                        'created_at': created_at,
                        'last_posted_at': last_posted_at
                    })
                    
                    new_topics_count += 1
                    
                except Exception as e:
                    logging.error(f"Error processing topic data: {e}")
                    continue
            
            logging.info(f"Found {new_topics_count} new topics on page {current_page}")
            
            if new_topics_count == 0:
                break
                
            current_page += 1
        
        logging.info(f"Scraped {len(topics)} topics from category")
        return topics
    
    def get_json(self, url: str, params=None) -> Optional[Dict[str, Any]]:
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

    def extract_post_from_json(self, post_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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

    def extract_topic_id(self, topic_url: str) -> Optional[str]:
        """Extract the topic ID from a topic URL."""
        topic_id_match = re.search(r'/t/[^/]+/(\d+)', topic_url)
        if topic_id_match:
            return topic_id_match.group(1)
        return None

    def scrape_topic_content(self, topic_url: str) -> Optional[Dict[str, Any]]:
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
        
        logging.info(f"Topic '{title}' has approximately {post_count} posts")
        
        # Get all posts
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
    
    def save_data(self, data: List[Dict[str, Any]], filename: str):
        """Save data to CSV file"""
        if not data:
            logging.error(f"No data to save to {filename}")
            return
        
        try:
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            logging.info(f"Saved {len(data)} records to {filename}")
        except Exception as e:
            logging.error(f"Error saving data to {filename}: {e}")


def main():
    # Get forum URL from user
    print("\nDiscourse Forum Scraper")
    print("=" * 50)
    
    while True:
        forum_url = input("\nEnter the Discourse forum URL (e.g., https://forum.example.com): ").strip()
        
        # Basic URL validation
        if not forum_url.startswith(('http://', 'https://')):
            print("Error: Please enter a valid URL starting with http:// or https://")
            continue
        
        # Initialize scraper - allow for custom headers if needed
        custom_headers = None  # You could load this from a file or environment variables
        scraper = DiscourseScraper(forum_url, custom_headers)
        
        # Validate if it's a Discourse forum
        if not scraper.validate_discourse_forum():
            print("Error: The provided URL does not appear to be a valid Discourse forum.")
            continue
        
        break
    
    # Create output directory using forum name
    forum_name = forum_url.split('//')[1].split('.')[0]
    base_output_dir = f"{config.OUTPUT_DIRS['base']}/{forum_name}"
    os.makedirs(base_output_dir, exist_ok=True)
    
    try:
        # Step 1: Get categories
        print("\nFetching categories...")
        categories = scraper.scrape_categories()
        
        if not categories:
            print("No categories found. Exiting.")
            sys.exit(1)
        
        # Display categories
        print("\nAvailable Categories:")
        print("=" * 50)
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category['name']} ({category.get('topic_count', 'unknown')} topics)")
        
        # Ask user what to scrape
        while True:
            choice = input("\nDo you want to scrape:\n1. All categories\n2. Specific category\nEnter choice (1 or 2): ").strip()
            
            if choice in ('1', '2'):
                break
            print("Invalid choice. Please enter 1 or 2.")
        
        categories_to_scrape = []
        if choice == '1':
            categories_to_scrape = categories
        else:
            while True:
                try:
                    cat_num = int(input(f"\nEnter category number (1-{len(categories)}): "))
                    if 1 <= cat_num <= len(categories):
                        categories_to_scrape = [categories[cat_num - 1]]
                        break
                    print(f"Please enter a number between 1 and {len(categories)}")
                except ValueError:
                    print("Please enter a valid number")
        
        # Get max pages to scrape
        while True:
            try:
                max_pages = int(input("\nEnter maximum number of pages to scrape per category (1-100): "))
                if 1 <= max_pages <= 100:
                    break
                print("Please enter a number between 1 and 100")
            except ValueError:
                print("Please enter a valid number")
        
        # Create subdirectories
        topics_dir = f"{base_output_dir}/topics"
        contents_dir = f"{base_output_dir}/contents"
        os.makedirs(topics_dir, exist_ok=True)
        os.makedirs(contents_dir, exist_ok=True)
        
        # Save categories
        scraper.save_data(categories, f"{base_output_dir}/categories.csv")
        
        # Scrape topics for selected categories
        for category in categories_to_scrape:
            print(f"\nScraping topics from category: {category['name']}")
            topics = scraper.scrape_topics_from_category(category['url'], max_pages=max_pages)
            
            if topics:
                # Save topics
                safe_category_name = ''.join(c if c.isalnum() else '_' for c in category['name'])
                scraper.save_data(topics, f"{topics_dir}/{safe_category_name}_topics.csv")
                
                # Ask if user wants to scrape topic contents
                while True:
                    scrape_contents = input(f"\nDo you want to scrape the content of topics in '{category['name']}'? (y/n): ").strip().lower()
                    if scrape_contents in ('y', 'n'):
                        break
                    print("Please enter 'y' or 'n'")
                
                if scrape_contents == 'y':
                    while True:
                        try:
                            max_topics = int(input(f"\nHow many topics to scrape? (1-{len(topics)}): "))
                            if 1 <= max_topics <= len(topics):
                                break
                            print(f"Please enter a number between 1 and {len(topics)}")
                        except ValueError:
                            print("Please enter a valid number")
                    
                    print(f"\nScraping content from {max_topics} topics...")
                    for topic in topics[:max_topics]:
                        topic_data = scraper.scrape_topic_content(topic['url'])
                        if topic_data:
                            safe_title = ''.join(c if c.isalnum() else '_' for c in topic_data['title'])[:50]
                            scraper.save_data(topic_data['posts'], f"{contents_dir}/{safe_title}_posts.csv")
        
        print("\nScraping completed successfully!")
        print(f"Data has been saved in the '{base_output_dir}' directory")
        
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 