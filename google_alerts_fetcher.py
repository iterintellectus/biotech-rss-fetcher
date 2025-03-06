import os
import logging
import time
import imaplib
import email
from email import utils
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional

import utils as util_module

# Constants
TOP_ARTICLES_MIN = 10
TOP_ARTICLES_LIMIT = 30

def fetch_google_alerts(last_run_time):
    """Fetch Google Alerts from Gmail inbox."""
    articles = []
    
    # Get environment variables
    env = util_module.load_environment()
    email_address = env["EMAIL"]
    app_password = env["APP_PASSWORD"]
    
    # Check for credentials
    if not email_address or not app_password:
        logging.error("Gmail credentials missing. EMAIL or APP_PASSWORD not set in environment.")
        return articles
    
    logging.info(f"Attempting to connect to Gmail using account: {email_address}")
    
    try:
        # Connect to Gmail
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        login_result = imap.login(email_address, app_password)
        logging.info(f"Gmail login result: {login_result}")
        
        # Select the inbox
        select_result = imap.select("inbox")
        logging.info(f"Gmail select inbox result: {select_result}")
        
        # Search for Google Alert emails since last run
        since_date = last_run_time.strftime("%d-%b-%Y")
        search_criteria = f'(SINCE "{since_date}" FROM "googlealerts-noreply@google.com")'
        logging.info(f"Gmail search criteria: {search_criteria}")
        
        search_result = imap.search(None, search_criteria)
        logging.info(f"Gmail search result status: {search_result[0]}")
        
        # Parse emails
        if search_result[0] != 'OK' or not search_result[1][0]:
            logging.info(f"No Google Alert emails found matching the criteria: {search_criteria}")
            imap.logout()
            return articles
            
        email_ids = search_result[1][0].split()
        logging.info(f"Found {len(email_ids)} Google Alert emails since {since_date}")
        
        # Process each email
        for num in email_ids:
            _, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Get email date
            date_tuple = utils.parsedate_tz(msg["Date"])
            if not date_tuple:
                logging.warning(f"Could not parse date from email: {msg['Subject']}")
                continue
                
            email_date = datetime.fromtimestamp(utils.mktime_tz(date_tuple))
            logging.info(f"Processing Google Alert email from {email_date}, Subject: {msg['Subject']}")
            
            if email_date <= last_run_time:
                logging.info(f"Skipping Google Alert email from {email_date} - older than last run time {last_run_time}")
                continue
            
            # Try to extract the alert topic from the subject line
            subject = msg["Subject"] or ""
            alert_topic = "Google Alerts"
            # Google Alert emails usually have subjects like "Google Alert - biotech" or "Google Alert - CRISPR"
            if "Google Alert - " in subject:
                topic = subject.split("Google Alert - ", 1)[1].strip()
                alert_topic = f"Google Alerts: {topic}"
                logging.info(f"Extracted alert topic: {topic}")
            
            # Parse email body
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        body = part.get_payload(decode=True).decode()
                        soup = BeautifulSoup(body, "html.parser")
                        
                        # Find all article links in the Google Alert email
                        links_found = 0
                        for a in soup.find_all("a", href=True):
                            url = a["href"]
                            # Filter out Google's own links and tracking URLs
                            if "google.com/alerts" in url or "support.google.com" in url:
                                continue
                            
                            links_found += 1
                            title = a.text.strip()
                            if not title:
                                continue
                                
                            # Extract summary from parent element
                            parent = a.find_parent()
                            summary = parent.text.strip() if parent else ""
                            # Remove the title from the summary and trim it
                            summary = summary.replace(title, "", 1).strip()[:2000]
                            
                            # Skip if we don't have a valid URL
                            if not url or not url.startswith(('http://', 'https://')):
                                logging.warning(f"Skipping Google Alert article with invalid URL: {url}")
                                continue
                                
                            # Skip if we don't have a title
                            if not title:
                                logging.warning(f"Skipping Google Alert article with missing title for URL: {url}")
                                continue
                            
                            logging.info(f"Found article in Google Alert: {title[:50]}...")
                            
                            # Create an article entry similar to RSS format
                            articles.append({
                                "title": title.strip(),
                                "link": url.strip(),  # Ensure URL is properly stripped
                                "summary": summary,
                                "source": alert_topic,
                                "source_type": "Google Alerts",
                                "published_date": email_date,
                                "published_parsed": email_date.timetuple()[:6]
                            })
                        
                        logging.info(f"Found {links_found} links in the email")
            else:
                logging.info(f"Email is not multipart, skipping: {subject}")
            
            # Mark email as deleted to avoid processing it again
            imap.store(num, '+FLAGS', '\\Deleted')
        
        # Permanently remove emails marked for deletion
        imap.expunge()
        imap.logout()
        logging.info(f"Successfully processed {len(articles)} articles from Google Alerts")
        for i, article in enumerate(articles[:3]):  # Log first 3 articles for debugging
            logging.info(f"Google Alert article {i+1}: {article['title'][:50]}... | Date: {article['published_date']}")
        
        return articles
    except Exception as e:
        logging.error(f"Error fetching Google Alerts: {str(e)}")
        if 'imap' in locals() and imap:
            try:
                imap.logout()
            except:
                pass
        return articles

def add_articles_to_notion(articles, last_run_time):
    """Add articles to Notion and return statistics."""
    articles_added = 0
    added_articles_info = []
    
    # Calculate relevancy for all articles
    for article in articles:
        if "relevancy" not in article:
            article["relevancy"] = util_module.calculate_relevancy(
                article.get('title', ''), 
                article.get('summary', ''),
                article.get('source_type', 'Google Alerts'),
                article.get('source', '')
            )
        # Log the relevancy score for debugging
        logging.info(f"Article relevancy: {article['relevancy']:.2f} - {article.get('title', '')[:50]}... (Source: {article.get('source', '')})")
    
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
                
            success, article_info = util_module.add_to_notion(article, last_run_time)
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
    """Main function to run the Google Alerts fetcher independently."""
    # Load configuration and set up logging
    util_module.load_environment()
    util_module.setup_logging()
    
    logging.info("Starting Google Alerts fetch process...")
    
    # Get the last run time
    last_run_time = util_module.get_last_run_time()
    if last_run_time:
        logging.info(f"Using last run time: {last_run_time.isoformat()}")
    else:
        logging.info("First run or no last run time found. Will fetch all available articles.")
    
    # In debug mode, use a date 7 days ago instead of last run time
    debug_mode = os.getenv("DEBUG_FETCH", "false").lower() == "true"
    if debug_mode:
        effective_last_run = datetime.now() - timedelta(days=30)  # Use 30 days for greater testing scope
        logging.info(f"DEBUG MODE: Using effective date of {effective_last_run.isoformat()}")
    else:
        effective_last_run = last_run_time
    
    # Fetch articles from Google Alerts
    articles = fetch_google_alerts(effective_last_run)
    logging.info(f"Fetched {len(articles)} articles from Google Alerts")
    
    # Add articles to Notion
    articles_added, added_articles_info = add_articles_to_notion(articles, effective_last_run)
    
    # Create an index of all downloaded PDFs
    index_path = util_module.create_pdf_index(added_articles_info)
    if index_path:
        logging.info(f"PDF index created at {index_path}")
    
    # Do not save the last run time if in debug mode
    if not debug_mode:
        util_module.save_last_run_time()
        logging.info("Updated last run time")
    else:
        logging.info("DEBUG MODE: Not updating last run time")
    
    # Show summary
    logging.info("=" * 50)
    logging.info(f"SUMMARY: Added {articles_added} new articles from Google Alerts")
    logging.info(f"  - Articles fetched: {len(articles)}")
    logging.info(f"  - Articles fetched but not added: {len(articles) - articles_added}")
    logging.info("=" * 50)

if __name__ == "__main__":
    main() 