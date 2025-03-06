import os
import logging
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import PyPDF2
from notion_client import Client
from typing import Dict, List, Tuple, Any, Optional, Union

# Setup logging function
def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('biotech_rss.log')
        ]
    )
    
# Load environment variables
def load_environment():
    """Load environment variables from .env file."""
    load_dotenv()
    return {
        "NOTION_TOKEN": os.getenv("NOTION_TOKEN"),
        "DATABASE_ID": os.getenv("DATABASE_ID"),
        "EMAIL": os.getenv("EMAIL"),
        "APP_PASSWORD": os.getenv("APP_PASSWORD"),
        "DEBUG_FETCH": os.getenv("DEBUG_FETCH", "false").lower() == "true",
        "RSS_FEEDS": json.loads(os.getenv("RSS_FEEDS", "{}"))
    }

# Functions related to time tracking
def get_last_run_time():
    """Get the timestamp of the last run from the last_run.txt file."""
    try:
        with open("last_run.txt", "r") as f:
            timestamp_str = f.read().strip()
            return datetime.fromisoformat(timestamp_str)
    except (FileNotFoundError, ValueError):
        # If file doesn't exist or contains invalid data, return a date 24 hours ago
        return datetime.now() - timedelta(days=1)

def save_last_run_time():
    """Save the current timestamp to the last_run.txt file."""
    with open("last_run.txt", "w") as f:
        f.write(datetime.now().isoformat())

# Common functions for article processing
def calculate_relevancy(title, summary, source_type=None, source=None):
    """Calculate a relevancy score based on keywords."""
    keywords = {
        "biotech": 0.3, "biotechnology": 0.3, "genetic": 0.2, "genomics": 0.2,
        "ai": 0.3, "artificial intelligence": 0.3, "machine learning": 0.2,
        "longevity": 0.4, "aging": 0.3, "senescence": 0.2,
        "neurotech": 0.4, "neuroscience": 0.3, "brain": 0.2,
        "crispr": 0.4, "gene editing": 0.3, "genome": 0.2,
        "cancer": 0.3, "oncology": 0.2, "tumor": 0.2,
        "health": 0.1, "innovation": 0.1, "breakthrough": 0.2
    }
    text = (title + " " + summary).lower()
    score = sum(weight for keyword, weight in keywords.items() if keyword in text)
    
    # Give a boost to Google Alerts since they are pre-filtered by the alert criteria
    if source_type == "Google Alerts":
        # Base boost for being a Google Alert
        score += 0.3
        
        # Additional boost if the alert source contains specific high-value topics
        if source:
            source_lower = source.lower()
            high_value_topics = ["crispr", "gene editing", "longevity", "neurotech", 
                                 "brain", "biotech", "ai", "genetic"]
            
            for topic in high_value_topics:
                if topic in source_lower:
                    score += 0.2
                    break
    
    return min(score, 1.0)  # Cap at 1.0

def get_theme(summary):
    """Classify articles based on themes in the summary or title."""
    themes = {
        "longevity": ["longevity", "aging", "senescence", "lifespan"],
        "neurotech": ["neurotech", "neuroscience", "brain", "neural", "cognitive"],
        "crispr": ["crispr", "gene editing", "genome editing"],
        "cancer": ["cancer", "oncology", "tumor", "malignancy"],
        "biotech": ["biotech", "biotechnology", "genetics", "genomics"],
        "ai": ["ai", "artificial intelligence", "machine learning", "deep learning"],
        "ethics": ["ethics", "bioethics", "morality", "ethical"]
    }
    detected_themes = [theme for theme, keywords in themes.items() if any(keyword in summary.lower() for keyword in keywords)]
    return detected_themes if detected_themes else ["general"]

def get_tags(summary):
    """Extract tags from article summary."""
    tags = []
    # Add tags based on content
    keywords = {
        "longevity": ["longevity", "aging", "lifespan", "senescence"],
        "AI": ["artificial intelligence", "machine learning", "ai ", "deep learning"],
        "CRISPR": ["crispr", "gene editing", "cas9"],
        "Cancer": ["cancer", "oncology", "tumor"],
        "Neuroscience": ["brain", "neural", "neuroscience", "cognitive"],
        "Genetics": ["genetic", "gene", "dna", "genomics"],
        "Clinical Trial": ["clinical trial", "phase 1", "phase 2", "phase 3", "phase i", "phase ii", "phase iii"],
        "Funding": ["funding", "investment", "million", "billion", "series", "venture"],
        "FDA": ["fda", "approval", "approved", "food and drug administration"],
        "Research": ["research", "study", "studies", "discovery", "discovered"],
        "Policy": ["policy", "regulation", "regulatory", "law", "legislation"]
    }
    
    summary_lower = summary.lower()
    for tag, trigger_words in keywords.items():
        if any(word in summary_lower for word in trigger_words):
            tags.append(tag)
    
    return tags[:5]  # Limit to 5 tags

# PDF related functions
def fetch_pdf_link(url):
    """Enhanced PDF link detection with site-specific rules."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Site-specific rules for better PDF detection
        if "nature.com" in url:
            pdf_link = soup.find("a", {"data-track-label": "Download PDF"})
            if pdf_link and "href" in pdf_link.attrs:
                return pdf_link["href"] if pdf_link["href"].startswith('http') else "https://www.nature.com" + pdf_link["href"]
        
        elif "cell.com" in url:
            pdf_link = soup.find("a", {"class": "pdf-download"})
            if pdf_link and "href" in pdf_link.attrs:
                return pdf_link["href"] if pdf_link["href"].startswith('http') else "https://www.cell.com" + pdf_link["href"]
        
        elif "science.org" in url:
            pdf_link = soup.find("a", text=re.compile("PDF", re.I))
            if pdf_link and "href" in pdf_link.attrs:
                return pdf_link["href"] if pdf_link["href"].startswith('http') else "https://www.science.org" + pdf_link["href"]
        
        elif "plos.org" in url:
            pdf_link = soup.find("a", {"class": "btn-multi-primary"}, text=re.compile("Download PDF", re.I))
            if pdf_link and "href" in pdf_link.attrs:
                return pdf_link["href"] if pdf_link["href"].startswith('http') else "https://journals.plos.org" + pdf_link["href"]
                
        # General case - look for any PDF links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.pdf'):
                return href if href.startswith('http') else url.rstrip('/') + href
            # Sometimes PDFs are in query parameters
            if '.pdf?' in href or 'pdf=' in href:
                return href if href.startswith('http') else url.rstrip('/') + href
                
        # Look for links with PDF in text
        for link in soup.find_all('a', href=True):
            if 'pdf' in link.text.lower() and not link.has_attr('class'):
                return link['href'] if link['href'].startswith('http') else url.rstrip('/') + link['href']
                
        return None
    except Exception as e:
        logging.warning(f"Couldn't fetch PDF for {url}: {e}")
        return None

def extract_pdf_text(pdf_path):
    """Extract text from PDF for additional insights."""
    if not pdf_path:
        return ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            # Extract text from first few pages (limit processing time)
            pages_to_extract = min(3, len(reader.pages))
            text = " ".join(
                reader.pages[i].extract_text() 
                for i in range(pages_to_extract) 
                if reader.pages[i].extract_text()
            )
            
            # Clean and limit text
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:1000]  # Limit for Notion
    except Exception as e:
        logging.error(f"PDF text extraction failed for {pdf_path}: {e}")
        return ""

def download_pdf(pdf_url, article_title):
    """Download a PDF file and save it to the PDF directory."""
    try:
        if not pdf_url:
            return None
            
        # Create a safe filename from the article title
        safe_title = re.sub(r'[^\w\-]', '_', article_title)
        safe_title = re.sub(r'_+', '_', safe_title)  # Replace multiple underscores with one
        safe_title = safe_title[:100]  # Limit filename length
        
        # Add timestamp to make filename unique
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Create PDFs directory if it doesn't exist
        os.makedirs("PDFs", exist_ok=True)
        
        pdf_path = f"PDFs/{safe_title}_{timestamp}.pdf"
        
        # Download the PDF
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(pdf_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        with open(pdf_path, "wb") as f:
            f.write(response.content)
            
        logging.info(f"Downloaded PDF to {pdf_path}")
        return pdf_path
    except Exception as e:
        logging.error(f"Failed to download PDF: {e}")
        return None

# Notion integration
def get_notion_client():
    """Get a Notion client with the token from environment variables."""
    token = os.getenv("NOTION_TOKEN")
    if not token:
        logging.error("NOTION_TOKEN is not set")
        return None
    return Client(auth=token)

def add_to_notion(article, last_run_time):
    """Add an article to Notion database."""
    try:
        # Get Notion client and database ID
        notion = get_notion_client()
        database_id = os.getenv("DATABASE_ID")
        
        if not notion or not database_id:
            logging.error("Notion client or database ID not available")
            return False, None
            
        # Extract article data
        title = article.get("title", "No Title")
        link = article.get("link", "")
        summary = article.get("summary", "")
        source = article.get("source", "Unknown")
        source_type = article.get("source_type", "Unknown")
        published_date = article.get("published_date")
        relevancy = article.get("relevancy", calculate_relevancy(title, summary, source_type, source))
        
        # Skip if no link
        if not link:
            logging.warning(f"Skipping article with no link: {title}")
            return False, None
            
        # Convert published_date to ISO format for Notion
        if published_date:
            published_iso = published_date.isoformat()
        else:
            published_iso = datetime.now().isoformat()
            
        # Set a default date for comparison if none exists
        if not published_date:
            published_date = datetime.now()
            
        # Skip articles older than 7 days in debug mode, or older than last run time in normal mode
        debug_mode = os.getenv("DEBUG_FETCH", "false").lower() == "true"
        if debug_mode:
            cutoff_date = datetime.now() - timedelta(days=7)
            if published_date < cutoff_date:
                logging.info(f"Skipping older article in debug mode: {title} (published {published_date.isoformat()})")
                return False, None
        elif last_run_time and published_date <= last_run_time:
            logging.info(f"Skipping older article: {title} (published {published_date.isoformat()})")
            return False, None
            
        # Get themes from the summary
        themes = get_theme(summary)
        
        # Get tags
        tags = get_tags(summary)
        
        # Check if article already exists in Notion
        existing_page = notion.databases.query(
            database_id=database_id,
            filter={
                "property": "URL",
                "url": {
                    "equals": link
                }
            }
        )
        
        if existing_page.get("results"):
            logging.info(f"Article already exists in Notion: {title}")
            return False, None
            
        # Try to get PDF link for scientific articles
        pdf_link = None
        pdf_path = None
        pdf_text = ""
        
        if source in ["Nature Biotechnology", "Science Magazine", "Cell", "PLOS Biology"]:
            logging.info(f"Attempting to fetch PDF for scientific article: {title}")
            pdf_link = fetch_pdf_link(link)
            if pdf_link:
                logging.info(f"Found PDF link: {pdf_link}")
                pdf_path = download_pdf(pdf_link, title)
                if pdf_path:
                    pdf_text = extract_pdf_text(pdf_path)
                    logging.info(f"Extracted {len(pdf_text)} characters of text from PDF")
                    
        # Prepare properties for Notion - UPDATED to match user's database columns
        properties = {
            "Title": {"title": [{"text": {"content": title[:2000]}}]},
            "URL": {"url": link},
            "Summary": {"rich_text": [{"text": {"content": summary[:2000]}}]},
            "Source": {"select": {"name": source[:100]}},
            "Publication Date": {"date": {"start": published_iso}},
            "Relevancy Score": {"number": round(relevancy * 100) / 100},
            "Fetch Date": {"date": {"start": datetime.now().isoformat()}},
            "Status": {"select": {"name": "New"}},
        }
        
        # Add PDF link if available
        if pdf_link:
            properties["PDF Link"] = {"url": pdf_link}
            
        # Add themes as select if the column exists
        if themes and themes[0]:
            properties["Themes"] = {
                "select": {"name": themes[0]}  # Use the first theme as select
            }
            
        # Add tags as multi-select if the column exists
        if tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in tags]
            }

        # Add article age
        if published_date:
            age_days = (datetime.now() - published_date).days
            properties["Article Age"] = {"number": age_days}
            
        # Add PDF path if available
        if pdf_path:
            properties["PDF Local Path"] = {"rich_text": [{"text": {"content": pdf_path}}]}
            
        # Create the page in Notion
        response = notion.pages.create(
            parent={"database_id": database_id},
            properties=properties,
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "Summary"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": summary[:2000]}}]
                    }
                }
            ]
        )
        
        # If we have PDF text, add it to the page
        if pdf_text:
            notion.blocks.children.append(
                block_id=response["id"],
                children=[
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": "PDF Text"}}]
                        }
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": pdf_text}}]
                        }
                    }
                ]
            )
            
            # Update PDF Insights property
            notion.pages.update(
                page_id=response["id"],
                properties={
                    "PDF Insights": {"rich_text": [{"text": {"content": pdf_text[:2000]}}]}
                }
            )
            
        logging.info(f"Added to Notion: {title}")
        
        # Return success and article info
        article_info = {
            "title": title,
            "link": link,
            "source": source,
            "published_date": published_date,
            "pdf_path": pdf_path,
            "notion_page_id": response["id"]
        }
        
        return True, article_info
    except Exception as e:
        logging.error(f"Error adding to Notion: {e}")
        return False, None

def create_pdf_index(added_articles):
    """Create an index.html file for all downloaded PDFs."""
    pdfs = [a for a in added_articles if a and 'pdf_path' in a and a['pdf_path']]
    
    if not pdfs:
        return None
        
    index_path = "PDFs/index.html"
    
    with open(index_path, "w") as f:
        f.write("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Biotech RSS PDFs</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                h1 { color: #333; }
                .pdf-list { margin-top: 20px; }
                .pdf-item { margin-bottom: 15px; padding: 10px; border: 1px solid #eee; border-radius: 5px; }
                .pdf-title { font-weight: bold; }
                .pdf-link { color: #0066cc; }
                .pdf-source { color: #666; font-style: italic; }
                .pdf-date { color: #666; }
            </style>
        </head>
        <body>
            <h1>Biotech RSS PDFs</h1>
            <p>Last updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            <div class="pdf-list">
        """)
        
        for article in pdfs:
            pdf_filename = os.path.basename(article['pdf_path'])
            f.write(f"""
                <div class="pdf-item">
                    <div class="pdf-title">{article['title']}</div>
                    <div class="pdf-link"><a href="{pdf_filename}" target="_blank">View PDF</a> | <a href="{article['link']}" target="_blank">Original Source</a></div>
                    <div class="pdf-source">Source: {article['source']}</div>
                    <div class="pdf-date">Date: {article['published_date'].strftime('%Y-%m-%d')}</div>
                </div>
            """)
            
        f.write("""
            </div>
        </body>
        </html>
        """)
        
    return index_path 