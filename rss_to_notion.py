import os
import time
import logging
import feedparser
import requests
import re
import json
from datetime import datetime, timedelta
from notion_client import Client
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from pathlib import Path
import PyPDF2
import imaplib
import email
from email import utils

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rss_log.txt"),
        logging.StreamHandler()
    ]
)

def setup_logging():
    """Set up enhanced logging with more detail for debugging."""
    # Clear existing handlers
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
    
    # Configure with both file and console output
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("rss_log.txt"),
            logging.StreamHandler()
        ]
    )
    
    # Set more verbose logging if in debug mode
    if os.getenv("DEBUG_FETCH", "false").lower() == "true":
        logging.getLogger().setLevel(logging.DEBUG)
        logging.info("[DIAG] Debug mode enabled - verbose logging activated")

# Configurable settings for article selection
TOP_ARTICLES_MIN = int(os.getenv("TOP_ARTICLES_MIN", 10))  # Minimum articles to select
TOP_ARTICLES_MAX = int(os.getenv("TOP_ARTICLES_MAX", 20))  # Maximum articles to consider
TOP_ARTICLES_LIMIT = int(os.getenv("TOP_ARTICLES_LIMIT", 15))  # Default number to select

# Load environment variables
load_dotenv()

# Notion configuration
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")  # Updated key name

# Gmail configuration for Google Alerts
EMAIL = os.getenv("EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")

if not NOTION_TOKEN or not DATABASE_ID:
    logging.error("Missing environment variables. Please set NOTION_TOKEN and DATABASE_ID")
    exit(1)

notion = Client(auth=NOTION_TOKEN)

# Directory for storing downloaded PDFs
PDF_DIR = Path("pdfs")
if not PDF_DIR.exists():
    PDF_DIR.mkdir(exist_ok=True)

# Load RSS feeds from environment variable
try:
    RSS_FEEDS_ENV = os.getenv("RSS_FEEDS")
    if RSS_FEEDS_ENV:
        RSS_FEEDS = json.loads(RSS_FEEDS_ENV)
        logging.info(f"[DIAG] Loaded {len(RSS_FEEDS)} RSS feeds from environment")
    else:
        # Fallback to default RSS feeds
        RSS_FEEDS = {
            "BioPharma Dive": "https://www.biopharmadive.com/feeds/news/",
            "Fierce Biotech": "https://www.fiercebiotech.com/feed",
            "GEN": "https://www.genengnews.com/feed/",
            "Nature Biotechnology": "https://www.nature.com/subjects/biotechnology.rss",
            "BioSpace": "https://www.biospace.com/rss/news/",
            "MIT Tech Review Biotech": "https://www.technologyreview.com/c/biomedicine/feed",
            "STAT News": "https://www.statnews.com/feed/",
            "The Scientist": "https://www.the-scientist.com/rss",
            "Cell": "https://www.cell.com/cell/current.rss",
            "Science Magazine": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
            "PLOS Biology": "https://journals.plos.org/plosbiology/feed/atom",
            "Longevity Technology": "https://www.longevity.technology/feed/",
            "Singularity Hub": "https://singularityhub.com/feed/",
            "FDA MedWatch": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch/rss.xml",
            "EMA News": "https://www.ema.europa.eu/en/rss-feeds",
            "Labiotech.eu": "https://www.labiotech.eu/feed/",
            "BioEngineer.org": "https://bioengineer.org/feed/",
            "ScienceDaily Biotech": "https://www.sciencedaily.com/rss/plants_animals/biotechnology.xml",
            "Phys.org Biotech": "https://phys.org/rss-feed/biology-news/biotechnology/",
            "Endpoints News": "https://endpts.com/feed/",
            "BioTecNika": "https://www.biotecnika.org/category/biotech-news/feed/",
            "LifeSciVC": "https://lifescivc.com/feed/",
            "SENS Research": "https://www.sens.org/feed/",
            "European Biotechnology": "https://european-biotechnology.com/feed.xml"
        }
        logging.info(f"[DIAG] Using complete set of {len(RSS_FEEDS)} RSS feeds")
except json.JSONDecodeError as e:
    logging.error(f"[DIAG] Error parsing RSS_FEEDS from environment: {e}")
    # Fallback to default feeds
    RSS_FEEDS = {
        "BioPharma Dive": "https://www.biopharmadive.com/feeds/news/",
        "Fierce Biotech": "https://www.fiercebiotech.com/feed",
        "GEN": "https://www.genengnews.com/feed/",
        "Nature Biotechnology": "https://www.nature.com/subjects/biotechnology.rss",
        "BioSpace": "https://www.biospace.com/rss/news/",
        "MIT Tech Review Biotech": "https://www.technologyreview.com/c/biomedicine/feed",
        "STAT News": "https://www.statnews.com/feed/",
        "The Scientist": "https://www.the-scientist.com/rss",
        "Cell": "https://www.cell.com/cell/current.rss",
        "Science Magazine": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
        "PLOS Biology": "https://journals.plos.org/plosbiology/feed/atom",
        "Longevity Technology": "https://www.longevity.technology/feed/",
        "Singularity Hub": "https://singularityhub.com/feed/",
        "FDA MedWatch": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch/rss.xml",
        "EMA News": "https://www.ema.europa.eu/en/rss-feeds",
        "Labiotech.eu": "https://www.labiotech.eu/feed/",
        "BioEngineer.org": "https://bioengineer.org/feed/",
        "ScienceDaily Biotech": "https://www.sciencedaily.com/rss/plants_animals/biotechnology.xml",
        "Phys.org Biotech": "https://phys.org/rss-feed/biology-news/biotechnology/",
        "Endpoints News": "https://endpts.com/feed/",
        "BioTecNika": "https://www.biotecnika.org/category/biotech-news/feed/",
        "LifeSciVC": "https://lifescivc.com/feed/",
        "SENS Research": "https://www.sens.org/feed/",
        "European Biotechnology": "https://european-biotechnology.com/feed.xml"
    }
    logging.info(f"[DIAG] Using complete set of {len(RSS_FEEDS)} RSS feeds")

def fetch_rss_feed(url):
    """Fetch and parse an RSS feed."""
    try:
        logging.info(f"Fetching feed: {url}")
        return feedparser.parse(url)
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def fetch_google_alerts(last_run_time):
    """Fetch Google Alerts from Gmail inbox."""
    articles = []
    
    # Print diagnostic info about Gmail connection
    if not EMAIL or not APP_PASSWORD:
        logging.error("[DIAG] Gmail credentials missing. EMAIL or APP_PASSWORD not set in environment.")
        return articles
    
    logging.info(f"[DIAG] Attempting to connect to Gmail using account: {EMAIL}")
    
    try:
        # Connect to Gmail
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        login_result = imap.login(EMAIL, APP_PASSWORD)
        logging.info(f"[DIAG] Gmail login result: {login_result}")
        
        # Select the inbox
        select_result = imap.select("inbox")
        logging.info(f"[DIAG] Gmail select inbox result: {select_result}")
        
        # Search for Google Alert emails since last run
        since_date = last_run_time.strftime("%d-%b-%Y")
        search_criteria = f'(SINCE "{since_date}" FROM "googlealerts-noreply@google.com")'
        logging.info(f"[DIAG] Gmail search criteria: {search_criteria}")
        
        search_result = imap.search(None, search_criteria)
        logging.info(f"[DIAG] Gmail search result status: {search_result[0]}")
        
        # Parse emails
        if search_result[0] != 'OK' or not search_result[1][0]:
            logging.info("[DIAG] No Google Alert emails found matching the criteria")
            imap.logout()
            return articles
            
        email_ids = search_result[1][0].split()
        logging.info(f"[DIAG] Found {len(email_ids)} Google Alert emails since {since_date}")
        
        # Process each email
        for num in email_ids:
            _, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Get email date
            date_tuple = utils.parsedate_tz(msg["Date"])
            if not date_tuple:
                logging.warning(f"[DIAG] Could not parse date from email: {msg['Subject']}")
                continue
                
            email_date = datetime.fromtimestamp(utils.mktime_tz(date_tuple))
            logging.info(f"[DIAG] Processing Google Alert email from {email_date}, Subject: {msg['Subject']}")
            
            if email_date <= last_run_time:
                logging.info(f"[DIAG] Skipping Google Alert email from {email_date} - older than last run time {last_run_time}")
                continue
            
            # Try to extract the alert topic from the subject line
            subject = msg["Subject"] or ""
            alert_topic = "Google Alerts"
            # Google Alert emails usually have subjects like "Google Alert - biotech" or "Google Alert - CRISPR"
            if "Google Alert - " in subject:
                topic = subject.split("Google Alert - ", 1)[1].strip()
                alert_topic = f"Google Alerts: {topic}"
                logging.info(f"[DIAG] Extracted alert topic: {topic}")
            
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
                            
                            logging.info(f"[DIAG] Found article in Google Alert: {title[:50]}...")
                            
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
                        
                        logging.info(f"[DIAG] Found {links_found} links in the email")
            else:
                logging.info("[DIAG] Email is not multipart, skipping")
            
            # Mark email as deleted to avoid processing it again
            imap.store(num, '+FLAGS', '\\Deleted')
        
        # Permanently remove emails marked for deletion
        imap.expunge()
        imap.logout()
        logging.info(f"[DIAG] Successfully processed {len(articles)} articles from Google Alerts")
        for i, article in enumerate(articles[:3]):  # Log first 3 articles for debugging
            logging.info(f"[DIAG] Google Alert article {i+1}: {article['title'][:50]}... | Date: {article['published_date']}")
        
        return articles
    except Exception as e:
        logging.error(f"[DIAG] Error fetching Google Alerts: {str(e)}")
        if 'imap' in locals() and imap:
            try:
                imap.logout()
            except:
                pass
        return articles

def calculate_relevancy(title, summary):
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
        filename = f"{safe_title}_{timestamp}.pdf"
        filepath = PDF_DIR / filename
        
        # Download the file
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        # Check if it's actually a PDF
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' not in content_type and not pdf_url.endswith('.pdf'):
            logging.warning(f"URL does not return a PDF: {pdf_url}, Content-Type: {content_type}")
            return None
        
        # Save the file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logging.info(f"Downloaded PDF: {filename}")
        return filepath
    except Exception as e:
        logging.error(f"Error downloading PDF from {pdf_url}: {e}")
        return None

def get_last_run_time():
    """Get the last run time from the last_run.txt file."""
    try:
        with open("last_run.txt", "r") as f:
            last_run_time_str = f.read().strip()
            last_run_time = datetime.fromisoformat(last_run_time_str)
            logging.info(f"[DIAG] Last run time loaded: {last_run_time}")
            
            # In debug mode, override last run time to 60 days ago for testing
            DEBUG_MODE = os.getenv("DEBUG_FETCH", "false").lower() == "true"
            if DEBUG_MODE:
                last_run_time = datetime.now() - timedelta(days=60)  # Changed from 7 to 60 days
                logging.info(f"[DIAG] DEBUG MODE: Overriding last run time to 60 days ago: {last_run_time}")
                
            return last_run_time
    except (FileNotFoundError, ValueError) as e:
        logging.warning(f"[DIAG] Could not read last run time: {str(e)}. Using a default value from 7 days ago.")
        # Default to 7 days ago if file doesn't exist or has invalid format
        return datetime.now() - timedelta(days=7)

def save_last_run_time():
    """Save the current time to file."""
    with open("last_run.txt", "w") as f:
        f.write(datetime.now().isoformat())

def get_tags(summary):
    """Extract relevant tags from the content."""
    # Common biotech tags that might appear in content
    all_tags = [
        "protein folding", "AI", "gene editing", "CRISPR", "longevity", "drugs",
        "neurotech", "implants", "cancer", "therapy", "FDA", "ethics", "augmentation",
        "genomics", "clinical trial", "vaccine", "immunity", "cell therapy", "stem cells",
        "diagnostics", "microbiome", "bioinformatics", "sequencing", "synthetic biology"
    ]
    
    # Extract tags that appear in the summary
    content_lower = summary.lower()
    extracted_tags = [tag for tag in all_tags if tag.lower() in content_lower]
    
    # Limit to 5 tags maximum
    return extracted_tags[:5]

def create_pdf_index(added_articles):
    """Create an HTML index of all downloaded PDFs with links to Notion pages."""
    try:
        index_path = PDF_DIR / "index.html"
        pdf_files = list(PDF_DIR.glob("*.pdf"))
        
        # Create a simple HTML index file
        with open(index_path, "w") as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Biotech RSS PDFs</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1 {{ color: #333; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    tr:nth-child(even) {{ background-color: #f2f2f2; }}
                    th {{ background-color: #4CAF50; color: white; }}
                    .search {{ margin-bottom: 20px; padding: 8px; width: 300px; }}
                    .notion-link {{ color: #0000EE; }}
                    .date {{ color: #666; }}
                </style>
                <script>
                    function searchTable() {{
                        const input = document.getElementById('searchInput');
                        const filter = input.value.toLowerCase();
                        const table = document.getElementById('pdfTable');
                        const rows = table.getElementsByTagName('tr');
                        
                        for (let i = 1; i < rows.length; i++) {{
                            const titleCell = rows[i].getElementsByTagName('td')[0];
                            if (titleCell) {{
                                const text = titleCell.textContent || titleCell.innerText;
                                rows[i].style.display = text.toLowerCase().indexOf(filter) > -1 ? '' : 'none';
                            }}
                        }}
                    }}
                </script>
            </head>
            <body>
                <h1>Biotech RSS PDFs</h1>
                <p>Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <input type="text" id="searchInput" class="search" onkeyup="searchTable()" placeholder="Search for titles...">
                <table id="pdfTable">
                    <tr>
                        <th>Title</th>
                        <th>Date</th>
                        <th>PDF</th>
                        <th>Notion Link</th>
                    </tr>
            """)
            
            # Collect mapping between articles and PDFs if available
            article_pdf_map = {}
            if added_articles:
                for article_info in added_articles:
                    if article_info.get('pdf_path'):
                        article_pdf_map[str(article_info['pdf_path'])] = {
                            'title': article_info['title'],
                            'notion_url': article_info.get('notion_url', ''),
                            'date': article_info.get('date', datetime.now().strftime("%Y-%m-%d"))
                        }
            
            # Add rows for each PDF file
            for pdf_file in sorted(pdf_files, key=lambda x: x.stat().st_mtime, reverse=True):
                if pdf_file.name == "index.html":
                    continue
                    
                # Extract title from filename (removing timestamp)
                title = pdf_file.stem
                title = re.sub(r'_\d{14}$', '', title)  # Remove timestamp
                title = title.replace('_', ' ')
                
                # Use mapping info if available
                pdf_info = article_pdf_map.get(str(pdf_file), {})
                title = pdf_info.get('title', title)
                notion_url = pdf_info.get('notion_url', '')
                date = pdf_info.get('date', datetime.fromtimestamp(pdf_file.stat().st_mtime).strftime("%Y-%m-%d"))
                
                f.write(f"""
                    <tr>
                        <td>{title}</td>
                        <td class="date">{date}</td>
                        <td><a href="{pdf_file.name}" target="_blank">Open PDF</a></td>
                        <td>{"<a href='" + notion_url + "' class='notion-link' target='_blank'>Open in Notion</a>" if notion_url else "No link"}</td>
                    </tr>
                """)
            
            f.write("""
                </table>
            </body>
            </html>
            """)
        
        logging.info(f"Created PDF index at {index_path}")
        return index_path
    except Exception as e:
        logging.error(f"Error creating PDF index: {e}")
        return None

def add_to_notion(article, last_run_time):
    """Add an article to the Notion database if it doesn't already exist."""
    try:
        # Make sure article has required fields
        if 'link' not in article or not article['link']:
            logging.error(f"Article missing 'link' field: {article.get('title', 'Unknown title')}")
            return False, None

        # Check for duplicates by URL
        query = notion.databases.query(
            database_id=DATABASE_ID,
            filter={"property": "URL", "url": {"equals": article['link']}}
        )
        
        if query['results']:
            logging.info(f"Skipping duplicate: {article['title']}")
            return False, None

        # Check if article is newer than last run
        published_date = None
        if 'published_parsed' in article and article['published_parsed']:
            try:
                published_date = datetime(*article['published_parsed'][:6])
                if published_date <= last_run_time:
                    logging.info(f"Skipping old article: {article['title']}")
                    return False, None
            except (TypeError, ValueError) as e:
                logging.warning(f"Could not parse published date for {article['title']}: {e}")
                # Continue processing the article without date filtering

        # Calculate article age and fetch date
        fetch_date = datetime.now()
        age_days = (fetch_date - published_date).days if published_date else 0

        # Format the published date if available
        published_iso = None
        if published_date:
            published_iso = published_date.isoformat()

        # Calculate relevancy score based on title and summary
        content = article.get('summary', '') + " " + article.get('title', '')
        relevancy = calculate_relevancy(article.get('title', ''), article.get('summary', ''))
        
        # Classify themes based on summary or title
        themes = get_theme(content)
        if not themes:
            themes = ["General"]
            
        # Extract tags from title and summary
        tags = extract_tags(article.get('title', '') + " " + article.get('summary', ''))
        
        # Look for a PDF link in the article or its links
        pdf_link = None
        pdf_path = None
        
        # Check if the article itself is a PDF
        article_url = article['link']
        if article_url.lower().endswith(".pdf"):
            pdf_link = article_url
        else:
            # Try to find a PDF link in the summary or content
            pdf_link = find_pdf_link(article.get('summary', ''))
        
        pdf_text = ""
        if pdf_link:
            pdf_path = download_pdf(pdf_link, article['title'])
            pdf_status = "PDF downloaded" if pdf_path else "PDF link found but download failed"
            
            # Extract text from PDF if download was successful
            if pdf_path:
                pdf_text = extract_pdf_text(pdf_path)
                if pdf_text:
                    logging.info(f"Extracted {len(pdf_text)} characters of text from PDF")
                    
                    # Further enhance relevancy based on PDF content
                    pdf_relevancy = calculate_relevancy(article['title'], pdf_text)
                    if pdf_relevancy > relevancy:
                        relevancy = (relevancy + pdf_relevancy) / 2
                        logging.info(f"Enhanced relevancy score to {relevancy:.2f} based on PDF content")
        else:
            pdf_status = "No PDF available"

        # Add new article to Notion
        properties = {
            "Title": {"title": [{"text": {"content": article['title']}}]},
            "URL": {"url": article['link']},
            "Notes": {"rich_text": []},  # Left blank as requested
            "Summary": {"rich_text": [{"text": {"content": article.get('summary', '')[:2000]}}]},
            "Source": {"select": {"name": article.get('source', 'Unknown')}},
            "Categories": {"multi_select": [{"name": theme.capitalize()} for theme in themes]},
            "Status": {"select": {"name": "New"}},
            "Tags": {"multi_select": [{"name": tag} for tag in tags]},
            "Relevancy Score": {"number": relevancy},  # Updated to use number instead of select
            "Themes": {"select": {"name": themes[0].capitalize()}},  # Primary theme as select
            "Article Age": {"number": age_days},  # New property for article age in days
            "Fetch Date": {"date": {"start": fetch_date.isoformat()}},  # When the article was added
        }
        
        # Add source_type info to the Notes field instead of as a property
        if 'source_type' in article:
            notes_content = f"Source Type: {article['source_type']}"
            properties["Notes"] = {"rich_text": [{"text": {"content": notes_content}}]}
        
        # Add PDF link if found
        if pdf_link:
            properties["PDF Link"] = {"url": pdf_link}
            
        # Add local PDF path if downloaded successfully
        if pdf_path:
            properties["PDF Local Path"] = {"rich_text": [{"text": {"content": str(pdf_path)}}]}
            
        # Add PDF insights if we have extracted text
        if pdf_text:
            properties["PDF Insights"] = {"rich_text": [{"text": {"content": pdf_text}}]}
            
        # Add published date if available
        if published_iso:
            properties["Publication Date"] = {"date": {"start": published_iso}}
        
        # Create the page in Notion
        response = notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties
        )
        
        # Get the Notion page URL and page ID
        notion_url = response["url"]
        page_id = response["id"]
        
        # Create a more detailed log entry showing source type
        source_type = article.get('source_type', 'Unknown')
        source_name = article.get('source', 'Unknown Source')
        logging.info(f"Added: {article['title']} | Source: {source_name} | Type: {source_type} | Theme: {themes[0].capitalize()} | Relevancy: {relevancy:.2f} | Age: {age_days} days")
        
        # Return success and article info for PDF index creation
        article_info = {
            "title": article['title'],
            "link": article['link'],
            "pdf_path": pdf_path,
            "notion_url": notion_url,
            "date": published_date.strftime("%Y-%m-%d") if published_date else fetch_date.strftime("%Y-%m-%d")
        }
        
        return True, article_info
        
    except KeyError as e:
        logging.error(f"Missing key in article: {e} - Article title: {article.get('title', 'Unknown title')}")
        return False, None
    except Exception as e:
        logging.error(f"Error adding article to Notion: {e} - Article: {str(article)[:200]}")
        return False, None

def process_rss_feed(feed_url, feed_name, last_run_time):
    """
    Process a single RSS feed and return new articles
    """
    articles = []
    
    try:
        feed = feedparser.parse(feed_url)
        logging.info(f"[DIAG] Processing {feed_name} feed with {len(feed.entries)} entries")
        
        # Check if feed parsed successfully
        if not hasattr(feed, 'entries') or not feed.entries:
            logging.warning(f"[DIAG] No entries found in feed: {feed_name}")
            if hasattr(feed, 'bozo_exception'):
                logging.error(f"[DIAG] Feed parsing error: {feed.bozo_exception}")
            return articles
        
        for entry in feed.entries:
            # Skip entries without links or titles
            if not hasattr(entry, 'link') or not hasattr(entry, 'title'):
                continue
                
            # Parse the published date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_date = datetime(*entry.updated_parsed[:6])
            
            # Log the article date for debugging
            if published_date:
                logging.debug(f"[DIAG] Article date: {published_date}, Last run: {last_run_time}, Skip: {published_date < last_run_time}")
                
            # Skip entries that are older than the last run time
            if published_date and last_run_time and published_date < last_run_time:
                logging.debug(f"[DIAG] Skipping old article: {entry.title[:50]}...")
                continue
            
            # Log accepted articles
            logging.info(f"[DIAG] Found new article from {feed_name}: {entry.title[:50]}... | Date: {published_date}")
                
            # Extract summary and handle different feed formats
            summary = ""
            if hasattr(entry, 'summary'):
                summary = entry.summary
            elif hasattr(entry, 'description'):
                summary = entry.description
            elif hasattr(entry, 'content'):
                summary = entry.content[0].value
            
            # Clean up the summary
            summary = BeautifulSoup(summary, "html.parser").get_text().strip()
            
            # Create article entry
            article = {
                'title': entry.title,
                'link': entry.link,
                'summary': summary,
                'published_date': published_date,
                'source': feed_name,
                'source_type': 'RSS Feed'  # Add source type for RSS feeds
            }
            
            articles.append(article)
            
        logging.info(f"[DIAG] Extracted {len(articles)} new articles from {feed_name}")
        return articles
        
    except Exception as e:
        logging.error(f"[DIAG] Error processing feed {feed_name}: {str(e)}")
        
    return articles

def main():
    """Fetch articles from RSS feeds and Google Alerts, and add them to Notion."""
    # Load configuration and set up logging
    load_dotenv()
    setup_logging()
    
    # Get the last run time
    last_run_time = get_last_run_time()
    if last_run_time:
        logging.info(f"[DIAG] Using last run time: {last_run_time.isoformat()}")
    else:
        logging.info("[DIAG] First run or no last run time found. Will fetch all available articles.")
    
    # Initialize counters
    articles_added = 0
    rss_added = 0
    alerts_added = 0
    added_article_info = []
    
    # Collect all articles first before adding to Notion
    all_articles = []
    
    # Process RSS feeds
    rss_articles_count = 0
    for feed_name, feed_url in RSS_FEEDS.items():
        feed_articles = process_rss_feed(feed_url, feed_name, last_run_time)
        all_articles.extend(feed_articles)
        rss_articles_count += len(feed_articles)
    
    logging.info(f"[DIAG] Fetched {rss_articles_count} articles from RSS feeds")
    
    # Process Google Alerts
    google_alerts_count = 0
    if EMAIL and APP_PASSWORD:
        google_alert_articles = fetch_google_alerts(last_run_time)
        all_articles.extend(google_alert_articles)
        google_alerts_count = len(google_alert_articles)
        logging.info(f"[DIAG] Fetched {google_alerts_count} articles from Google Alerts")
    else:
        logging.warning("[DIAG] Gmail credentials not found, skipping Google Alerts")
    
    # Log the total number of articles found
    logging.info(f"[DIAG] Found {len(all_articles)} total new articles ({rss_articles_count} from RSS feeds, {google_alerts_count} from Google Alerts)")
    
    # Sort articles by published date (newest first)
    all_articles.sort(key=lambda x: x.get('published_date', datetime.now()), reverse=True)
    
    # Print the first few articles for debugging
    for i, article in enumerate(all_articles[:5]):
        logging.info(f"[DIAG] Article {i+1}: {article.get('title', 'No title')[:50]}... | Date: {article.get('published_date')} | Source: {article.get('source')} | Type: {article.get('source_type')}")
    
    # Define a 24-hour cutoff for "recent" articles
    cutoff_time = datetime.now() - timedelta(days=1)
    
    # Group articles by day
    articles_by_day = {}
    recent_articles = []
    
    for article in all_articles:
        # Track recent articles (last 24 hours) separately
        pub_date = article.get("published_date")
        if pub_date and pub_date > cutoff_time:
            recent_articles.append(article)
            logging.info(f"[DIAG] Recent article (last 24h): {article.get('title', 'No title')[:50]}...")
        
        # Also keep the day-based grouping for historical articles
        day_key = "unknown"
        if pub_date:
            day_key = pub_date.strftime("%Y-%m-%d")
        
        if day_key not in articles_by_day:
            articles_by_day[day_key] = []
        
        articles_by_day[day_key].append(article)
    
    logging.info(f"[DIAG] Found {len(recent_articles)} articles from the last 24 hours")
    
    # Calculate relevancy for any articles that don't have it yet
    for article in recent_articles:
        if "relevancy" not in article:
            article["relevancy"] = calculate_relevancy(article.get('title', ''), article.get('summary', ''))
    
    # First process recent articles from the last 24 hours
    if recent_articles:
        # Sort by relevancy (highest first)
        recent_articles.sort(key=lambda x: x["relevancy"], reverse=True)
        
        # Take only the top N within configured limits
        top_recent_limit = min(max(TOP_ARTICLES_MIN, len(recent_articles) // 2), TOP_ARTICLES_LIMIT)
        top_recent_articles = recent_articles[:top_recent_limit]
        
        logging.info(f"Adding top {len(top_recent_articles)} articles from the last 24 hours (from {len(recent_articles)} total)")
        
        # Add the top articles to Notion
        for article in top_recent_articles:
            try:
                # Skip articles without a link
                if 'link' not in article or not article['link']:
                    logging.warning(f"Skipping recent article without link: {article.get('title', 'Unknown')}")
                    continue
                    
                success, article_info = add_to_notion(article, last_run_time)
                if success:
                    articles_added += 1
                    # Count by source type
                    if article.get('source_type') == 'RSS Feed':
                        rss_added += 1
                    elif article.get('source_type') == 'Google Alerts':
                        alerts_added += 1
                    
                    if article_info:
                        added_article_info.append(article_info)
                
                # Respect Notion's rate limits
                time.sleep(0.5)
            
            except KeyError as e:
                logging.error(f"Missing key in recent article: {e} - Article title: {article.get('title', 'Unknown title')}")    
            except Exception as e:
                logging.error(f"Error adding recent article to Notion: {e} - Article: {str(article)[:200]}")
    
    # Then process remaining articles by day if we haven't reached the limit
    remaining_slots = TOP_ARTICLES_LIMIT - articles_added
    
    if remaining_slots > 0:
        # Group remaining articles by day
        if remaining_slots > 0 and recent_articles:
            grouped_by_day = {}
            
            # First group articles by day
            for article in recent_articles:
                # Skip if missing link
                if 'link' not in article or not article['link']:
                    logging.warning(f"Skipping article without link: {article.get('title', 'Unknown')}")
                    continue
                    
                # Get the date from the article
                date_key = None
                if 'published_parsed' in article and article['published_parsed']:
                    try:
                        published_date = datetime(*article['published_parsed'][:6])
                        date_key = published_date.strftime("%Y-%m-%d")
                    except (TypeError, ValueError) as e:
                        logging.warning(f"Could not parse published date for {article['title']}: {e}")
                
                # Use fetch date if published date is not available
                if not date_key:
                    date_key = datetime.now().strftime("%Y-%m-%d")
                
                if date_key not in grouped_by_day:
                    grouped_by_day[date_key] = []
                    
                grouped_by_day[date_key].append(article)
            
            # Sort days (newest first)
            days = sorted(grouped_by_day.keys(), reverse=True)
            
            # Add top articles from each day
            for day in days:
                if remaining_slots <= 0:
                    break
                    
                day_articles = grouped_by_day[day]
                
                # Calculate relevancy for any articles that don't have it yet
                for article in day_articles:
                    if "relevancy" not in article:
                        article["relevancy"] = calculate_relevancy(article.get('title', ''), article.get('summary', ''))
                    
                # Sort by relevancy (highest first)
                day_articles.sort(key=lambda x: x.get("relevancy", 0), reverse=True)
                
                # Get top articles for this day (at most 50% of remaining slots)
                day_limit = max(1, min(10, remaining_slots // 2))
                top_day_articles = day_articles[:day_limit]
                
                logging.info(f"Adding top {len(top_day_articles)} articles for {day} (from {len(day_articles)} total)")
                
                # Add the top articles to Notion
                for article in top_day_articles:
                    try:
                        # Skip any that were already processed in the recent list or missing link
                        if 'link' not in article or not article['link']:
                            logging.warning(f"Skipping article without link: {article.get('title', 'Unknown')}")
                            continue
                            
                        # Skip if already processed
                        if any(a.get('link') == article['link'] for a in added_article_info if 'link' in a):
                            continue
                            
                        success, article_info = add_to_notion(article, last_run_time)
                        if success:
                            articles_added += 1
                            # Count by source type
                            if article.get('source_type') == 'RSS Feed':
                                rss_added += 1
                            elif article.get('source_type') == 'Google Alerts':
                                alerts_added += 1
                            
                            remaining_slots -= 1
                            if article_info:
                                added_article_info.append(article_info)
                        
                        # Respect Notion's rate limits
                        time.sleep(0.5)
                        
                        if remaining_slots <= 0:
                            break
                            
                    except KeyError as e:
                        logging.error(f"Missing key in article: {e} - Article title: {article.get('title', 'Unknown title')}")
                    except Exception as e:
                        logging.error(f"Error adding article to Notion: {e} - Article: {str(article)[:200]}")
    
    # Create an index of all downloaded PDFs
    index_path = create_pdf_index(added_article_info)
    if index_path:
        logging.info(f"PDF index created at {index_path}")
    
    # Do not save the last run time if in debug mode
    debug_mode = os.getenv("DEBUG_FETCH", "false").lower() == "true"
    if debug_mode:
        logging.info("[DIAG] DEBUG MODE: Not updating last run time")
    else:
        # Always save the last run time, even if there were errors
        save_last_run_time()
        logging.info("[DIAG] Updated last run time")
    
    # Generate a summary of articles by source type
    rss_count = sum(1 for article in all_articles if article.get('source_type') == 'RSS Feed')
    alerts_count = sum(1 for article in all_articles if article.get('source_type') == 'Google Alerts')
    
    logging.info("=" * 50)
    logging.info(f"SUMMARY: Added {articles_added} new articles")
    logging.info(f"  - From RSS Feeds: {rss_added} (of {rss_count} fetched)")
    logging.info(f"  - From Google Alerts: {alerts_added} (of {alerts_count} fetched)")
    logging.info(f"  - Articles fetched but not added: {len(all_articles) - articles_added}")
    logging.info("=" * 50)
    
    logging.info(f"Run complete. Updated last run time.")

if __name__ == "__main__":
    main() 