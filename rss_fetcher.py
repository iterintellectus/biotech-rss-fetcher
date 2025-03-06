import os
import logging
import time
import json
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import utils

# Constants
TOP_ARTICLES_MIN = 10
TOP_ARTICLES_LIMIT = 30

def fetch_rss_feed(url):
    """Fetch and parse an RSS feed."""
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            logging.warning(f"No entries found in feed: {url}")
        return feed
    except Exception as e:
        logging.error(f"Error fetching RSS feed {url}: {e}")
        return None

def process_rss_feed(feed_url, feed_name, last_run_time):
    """Process a single RSS feed and return new articles."""
    logging.info(f"Fetching RSS feed: {feed_name} ({feed_url})")
    feed = fetch_rss_feed(feed_url)
    
    if not feed or not hasattr(feed, 'entries'):
        logging.error(f"Failed to fetch feed {feed_name} or no entries found")
        return []
    
    articles = []
    debug_mode = os.getenv("DEBUG_FETCH", "false").lower() == "true"
    
    # In debug mode, use a date 7 days ago instead of last run time
    if debug_mode:
        effective_last_run = datetime.now() - timedelta(days=30)  # Use 30 days for greater testing scope
        logging.info(f"DEBUG MODE: Using effective date of {effective_last_run.isoformat()}")
    else:
        effective_last_run = last_run_time
    
    for entry in feed.entries:
        try:
            # Extract publication date
            published_parsed = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_parsed = entry.published_parsed
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_parsed = entry.updated_parsed
                
            published_date = None
            if published_parsed:
                published_date = datetime(*published_parsed[:6])
            else:
                # If no date is available, use current time
                logging.warning(f"No date found for entry in {feed_name}, using current time")
                published_date = datetime.now()
                
            # Skip entries older than the effective last run time
            if effective_last_run and published_date <= effective_last_run:
                continue
                
            # Extract link
            link = ""
            if hasattr(entry, 'link'):
                link = entry.link
                
            # Skip entries without a link
            if not link:
                logging.warning(f"No link found for entry in {feed_name}, skipping")
                continue
                
            # Extract summary
            summary = ""
            if hasattr(entry, 'summary'):
                summary = entry.summary
            elif hasattr(entry, 'description'):
                summary = entry.description
            elif hasattr(entry, 'content') and entry.content:
                summary = entry.content[0].value
                
            # Create article object
            article = {
                "title": entry.title if hasattr(entry, 'title') else "No Title",
                "link": link,
                "summary": summary,
                "source": feed_name,
                "source_type": "RSS Feed",
                "published_date": published_date,
                "published_parsed": published_parsed,
                "relevancy": utils.calculate_relevancy(
                    entry.title if hasattr(entry, 'title') else "", 
                    summary,
                    "RSS Feed",
                    feed_name
                )
            }
            
            articles.append(article)
        except Exception as e:
            logging.error(f"Error processing entry in feed {feed_name}: {e}")
    
    logging.info(f"Found {len(articles)} new articles in feed {feed_name}")
    return articles

def fetch_all_rss_feeds(last_run_time):
    """Fetch all RSS feeds and return all new articles."""
    env = utils.load_environment()
    rss_feeds = env["RSS_FEEDS"]
    
    if not rss_feeds:
        logging.error("No RSS feeds defined. Check your .env file.")
        return []
        
    logging.info(f"Fetching {len(rss_feeds)} RSS feeds...")
    
    all_articles = []
    for feed_name, feed_url in rss_feeds.items():
        feed_articles = process_rss_feed(feed_url, feed_name, last_run_time)
        all_articles.extend(feed_articles)
        
    logging.info(f"Total of {len(all_articles)} articles fetched from all RSS feeds")
    
    # Sort articles by date (newest first)
    all_articles.sort(key=lambda x: x.get('published_date', datetime.now()), reverse=True)
    
    return all_articles

def add_articles_to_notion(articles, last_run_time):
    """Add articles to Notion and return statistics."""
    articles_added = 0
    added_articles_info = []
    
    # Calculate relevancy for all articles
    for article in articles:
        if "relevancy" not in article:
            article["relevancy"] = utils.calculate_relevancy(
                article.get('title', ''), 
                article.get('summary', ''),
                article.get('source_type', 'RSS'),
                article.get('source', '')
            )
    
    # Sort by relevancy (highest first)
    articles.sort(key=lambda x: x.get("relevancy", 0), reverse=True)
    
    # Take top N articles
    articles_to_add = articles[:TOP_ARTICLES_LIMIT]
    logging.info(f"Adding top {len(articles_to_add)} articles (from {len(articles)} total)")
    
    # Add articles to Notion
    for article in articles_to_add:
        try:
            if 'link' not in article or not article['link']:
                logging.warning(f"Skipping article without link: {article.get('title', 'Unknown')}")
                continue
                
            success, article_info = utils.add_to_notion(article, last_run_time)
            if success:
                articles_added += 1
                if article_info:
                    added_articles_info.append(article_info)
            
            # Respect Notion's rate limits
            time.sleep(0.5)
            
        except Exception as e:
            logging.error(f"Error adding article to Notion: {e} - Article: {article.get('title', 'Unknown')}")
    
    return articles_added, added_articles_info

def main():
    """Main function to run the RSS fetcher independently."""
    # Load configuration and set up logging
    utils.load_environment()
    utils.setup_logging()
    
    logging.info("Starting RSS feed fetch process...")
    
    # Get the last run time
    last_run_time = utils.get_last_run_time()
    if last_run_time:
        logging.info(f"Using last run time: {last_run_time.isoformat()}")
    else:
        logging.info("First run or no last run time found. Will fetch all available articles.")
    
    # Fetch articles from RSS feeds
    articles = fetch_all_rss_feeds(last_run_time)
    logging.info(f"Fetched {len(articles)} articles from RSS feeds")
    
    # Add articles to Notion
    articles_added, added_articles_info = add_articles_to_notion(articles, last_run_time)
    
    # Create an index of all downloaded PDFs
    index_path = utils.create_pdf_index(added_articles_info)
    if index_path:
        logging.info(f"PDF index created at {index_path}")
    
    # Do not save the last run time if in debug mode
    debug_mode = os.getenv("DEBUG_FETCH", "false").lower() == "true"
    if not debug_mode:
        utils.save_last_run_time()
        logging.info("Updated last run time")
    else:
        logging.info("DEBUG MODE: Not updating last run time")
    
    # Show summary
    logging.info("=" * 50)
    logging.info(f"SUMMARY: Added {articles_added} new articles from RSS feeds")
    logging.info(f"  - Articles fetched: {len(articles)}")
    logging.info(f"  - Articles fetched but not added: {len(articles) - articles_added}")
    logging.info("=" * 50)

if __name__ == "__main__":
    main() 