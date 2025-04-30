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
from discourse_scraper import DiscourseScraper
import keyword_config as config

class KeywordScraper(DiscourseScraper):
    """
    Extension of DiscourseScraper that adds keyword search functionality
    """
    
    def search_topics_by_keyword(self, keyword: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        Search for topics containing the specified keyword
        
        Args:
            keyword: Keyword to search for
            max_pages: Maximum number of search result pages to process
            
        Returns:
            List of topics containing the keyword
        """
        logging.info(f"Searching for topics containing keyword: {keyword}")
        matching_topics = []
        current_page = 0
        
        while current_page < max_pages:
            # Construct search API URL
            search_url = f"{self.base_url}/search.json"
            params = {
                'q': keyword,
                'page': current_page + 1  # Discourse search uses 1-based page numbers
            }
            
            response_data = self.get_json(search_url, params=params)
            
            if not response_data or 'topics' not in response_data:
                logging.warning(f"No results found on page {current_page + 1}")
                break
            
            topics = response_data.get('topics', [])
            
            if not topics:
                logging.info(f"No more topics found on page {current_page + 1}")
                break
            
            for topic_data in topics:
                try:
                    topic_title = topic_data.get('title', '')
                    topic_id = topic_data.get('id')
                    topic_slug = topic_data.get('slug', '')
                    
                    # Construct topic URL
                    topic_url = f"{self.base_url}/t/{topic_slug}/{topic_id}"
                    
                    # Get metadata
                    replies_count = topic_data.get('posts_count', 1) - 1
                    views_count = topic_data.get('views', 0)
                    created_at = topic_data.get('created_at')
                    last_posted_at = topic_data.get('last_posted_at')
                    
                    matching_topics.append({
                        'title': topic_title,
                        'url': topic_url,
                        'replies_count': replies_count,
                        'views_count': views_count,
                        'created_at': created_at,
                        'last_posted_at': last_posted_at
                    })
                    
                except Exception as e:
                    logging.error(f"Error processing topic data: {e}")
                    continue
            
            current_page += 1
            
        logging.info(f"Found {len(matching_topics)} topics containing keyword '{keyword}'")
        return matching_topics


def main():
    print("\nDiscourse Forum Keyword Scraper")
    print("=" * 50)
    
    while True:
        forum_url = input("\nEnter the Discourse forum URL (e.g., https://forum.example.com): ").strip()
        
        # Basic URL validation
        if not forum_url.startswith(('http://', 'https://')):
            print("Error: Please enter a valid URL starting with http:// or https://")
            continue
        
        # Initialize scraper
        scraper = KeywordScraper(forum_url)
        
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
        # Get keyword from user
        keyword = input("\nEnter the keyword to search for: ").strip()
        
        # Get max pages to search
        while True:
            try:
                max_pages = int(input("\nEnter maximum number of search pages to process (1-100): "))
                if 1 <= max_pages <= 100:
                    break
                print("Please enter a number between 1 and 100")
            except ValueError:
                print("Please enter a valid number")
        
        # Search for topics with keyword
        print(f"\nSearching for topics containing '{keyword}'...")
        matching_topics = scraper.search_topics_by_keyword(keyword, max_pages=max_pages)
        
        if not matching_topics:
            print(f"\nNo topics found containing the keyword '{keyword}'")
            sys.exit(0)
        
        # Display results
        print(f"\nFound {len(matching_topics)} topics containing '{keyword}'")
        
        # Create subdirectories
        topics_dir = f"{base_output_dir}/topics"
        contents_dir = f"{base_output_dir}/contents"
        os.makedirs(topics_dir, exist_ok=True)
        os.makedirs(contents_dir, exist_ok=True)
        
        # Save matching topics list
        safe_keyword = ''.join(c if c.isalnum() else '_' for c in keyword)
        topics_file = f"{topics_dir}/keyword_{safe_keyword}_topics.csv"
        scraper.save_data(matching_topics, topics_file)
        print(f"\nSaved topics list to {topics_file}")
        
        # Ask how many topics to scrape
        while True:
            try:
                max_topics = int(input(f"\nHow many topics would you like to scrape? (1-{len(matching_topics)}): "))
                if 1 <= max_topics <= len(matching_topics):
                    break
                print(f"Please enter a number between 1 and {len(matching_topics)}")
            except ValueError:
                print("Please enter a valid number")
        
        # Scrape selected number of topics
        print(f"\nScraping content from {max_topics} topics...")
        for i, topic in enumerate(matching_topics[:max_topics], 1):
            print(f"\nScraping topic {i}/{max_topics}: {topic['title']}")
            topic_data = scraper.scrape_topic_content(topic['url'])
            if topic_data:
                safe_title = ''.join(c if c.isalnum() else '_' for c in topic_data['title'])[:50]
                output_file = f"{contents_dir}/{safe_keyword}_{safe_title}_posts.csv"
                scraper.save_data(topic_data['posts'], output_file)
                print(f"Saved {len(topic_data['posts'])} posts to {output_file}")
        
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