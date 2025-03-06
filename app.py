import os
import logging
import time
from datetime import datetime

import utils
import rss_fetcher
import google_alerts_fetcher

def main():
    """
    Main function to run both RSS feed and Google Alerts fetching.
    This combines the functionality of both independent modules.
    """
    # Load configuration and set up logging
    env = utils.load_environment()
    utils.setup_logging()
    
    logging.info("=" * 80)
    logging.info("STARTING BIOTECH RSS & GOOGLE ALERTS FETCHER")
    logging.info("=" * 80)
    
    # Get the last run time
    last_run_time = utils.get_last_run_time()
    if last_run_time:
        logging.info(f"Using last run time: {last_run_time.isoformat()}")
    else:
        logging.info("First run or no last run time found. Will fetch all available articles.")
    
    # Initialize counters
    rss_articles_fetched = 0
    google_articles_fetched = 0
    rss_articles_added = 0
    google_articles_added = 0
    all_added_articles = []
    
    # Step 1: Process RSS feeds
    logging.info("STEP 1: Processing RSS feeds...")
    rss_articles = rss_fetcher.fetch_all_rss_feeds(last_run_time)
    rss_articles_fetched = len(rss_articles)
    logging.info(f"Fetched {rss_articles_fetched} articles from RSS feeds")
    
    # Step 2: Process Google Alerts
    logging.info("STEP 2: Processing Google Alerts...")
    if env["EMAIL"] and env["APP_PASSWORD"]:
        google_articles = google_alerts_fetcher.fetch_google_alerts(last_run_time)
        google_articles_fetched = len(google_articles)
        logging.info(f"Fetched {google_articles_fetched} articles from Google Alerts")
    else:
        google_articles = []
        logging.warning("Gmail credentials not found, skipping Google Alerts")
    
    # Step 3: Combine all articles
    all_articles = rss_articles + google_articles
    logging.info(f"STEP 3: Combined {len(all_articles)} total articles")
    
    # Sort articles by date (newest first)
    all_articles.sort(key=lambda x: x.get('published_date', datetime.now()), reverse=True)
    
    # Step 4: Calculate relevancy for all articles
    logging.info("STEP 4: Calculating relevancy scores...")
    for article in all_articles:
        if "relevancy" not in article:
            article["relevancy"] = utils.calculate_relevancy(
                article.get('title', ''), 
                article.get('summary', ''),
                article.get('source_type', ''),
                article.get('source', '')
            )
        # Log the relevancy score for debugging
        logging.info(f"Article relevancy: {article['relevancy']:.2f} - {article.get('title', '')[:50]}... (Source: {article.get('source', '')})")
    
    # Step 5: Sort by relevancy (highest first)
    all_articles.sort(key=lambda x: x.get("relevancy", 0), reverse=True)
    
    # Step 6: Add articles to Notion
    logging.info("STEP 6: Adding articles to Notion...")
    for article in all_articles[:30]:  # Limit to top 30 most relevant articles
        try:
            # Skip articles without a link
            if 'link' not in article or not article['link']:
                logging.warning(f"Skipping article without link: {article.get('title', 'Unknown')}")
                continue
                
            success, article_info = utils.add_to_notion(article, last_run_time)
            if success:
                # Count by source type
                if article.get('source_type') == 'RSS Feed':
                    rss_articles_added += 1
                elif article.get('source_type') == 'Google Alerts':
                    google_articles_added += 1
                
                if article_info:
                    all_added_articles.append(article_info)
            
            # Respect Notion's rate limits
            time.sleep(0.5)
            
        except Exception as e:
            logging.error(f"Error adding article to Notion: {e} - Article: {article.get('title', 'Unknown')}")
    
    # Step 7: Create PDF index
    logging.info("STEP 7: Creating PDF index...")
    index_path = utils.create_pdf_index(all_added_articles)
    if index_path:
        logging.info(f"PDF index created at {index_path}")
    
    # Step 8: Save last run time (unless in debug mode)
    debug_mode = env["DEBUG_FETCH"]
    if not debug_mode:
        utils.save_last_run_time()
        logging.info("Updated last run time")
    else:
        logging.info("DEBUG MODE: Not updating last run time")
    
    # Show summary
    logging.info("=" * 80)
    logging.info("SUMMARY")
    logging.info("=" * 80)
    logging.info(f"Total articles added: {rss_articles_added + google_articles_added}")
    logging.info(f"  - From RSS Feeds: {rss_articles_added} (of {rss_articles_fetched} fetched)")
    logging.info(f"  - From Google Alerts: {google_articles_added} (of {google_articles_fetched} fetched)")
    logging.info(f"  - Articles fetched but not added: {len(all_articles) - (rss_articles_added + google_articles_added)}")
    logging.info("=" * 80)
    
    logging.info("Run complete.")
    
if __name__ == "__main__":
    main() 