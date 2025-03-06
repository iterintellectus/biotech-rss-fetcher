# Biotech RSS & Google Alerts to Notion

This application fetches biotech articles from various RSS feeds and Google Alerts, processes them, and adds them to a Notion database. The code has been modularized into separate components that can be run independently.

## Features

- Fetches articles from 20+ biotech RSS feeds
- Fetches articles from Google Alerts in your Gmail inbox
- Calculates relevancy scores based on content
- Adds the most relevant articles to your Notion database
- Downloads PDFs for scientific articles when available
- Creates an index.html file for all downloaded PDFs

## Setup

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your credentials (based on the example below)
4. Run the application

## Environment Configuration

Create a `.env` file with the following content:

```
# Notion API token and database ID
NOTION_TOKEN=your_notion_token
DATABASE_ID=your_notion_database_id

# Gmail credentials (for Google Alerts)
EMAIL=your_gmail_address
APP_PASSWORD=your_gmail_app_password

# Debug mode - set to "true" to fetch articles from the past 7 days regardless of last run time
DEBUG_FETCH=false

# RSS feed configuration - you can modify this to add or remove feeds
RSS_FEEDS={"BioPharma Dive": "https://www.biopharmadive.com/feeds/news/", "Fierce Biotech": "https://www.fiercebiotech.com/feed", "GEN": "https://www.genengnews.com/feed/", "Nature Biotechnology": "https://www.nature.com/subjects/biotechnology.rss", "BioSpace": "https://www.biospace.com/rss/news/", "MIT Tech Review Biotech": "https://www.technologyreview.com/c/biomedicine/feed", "STAT News": "https://www.statnews.com/feed/", "The Scientist": "https://www.the-scientist.com/rss", "Cell": "https://www.cell.com/cell/current.rss", "Science Magazine": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science", "PLOS Biology": "https://journals.plos.org/plosbiology/feed/atom", "Longevity Technology": "https://www.longevity.technology/feed/", "Singularity Hub": "https://singularityhub.com/feed/", "FDA MedWatch": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch/rss.xml", "EMA News": "https://www.ema.europa.eu/en/rss-feeds", "Labiotech.eu": "https://www.labiotech.eu/feed/", "BioEngineer.org": "https://bioengineer.org/feed/", "ScienceDaily Biotech": "https://www.sciencedaily.com/rss/plants_animals/biotechnology.xml", "Phys.org Biotech": "https://phys.org/rss-feed/biology-news/biotechnology/", "Endpoints News": "https://endpts.com/feed/", "BioTecNika": "https://www.biotecnika.org/category/biotech-news/feed/", "LifeSciVC": "https://lifescivc.com/feed/", "SENS Research": "https://www.sens.org/feed/", "European Biotechnology": "https://european-biotechnology.com/feed.xml"}
```

### Gmail Setup for Google Alerts

To use Gmail to fetch Google Alerts, you need to:

1. Set up Google Alerts for topics you're interested in
2. Create an App Password for your Gmail account:
   - Go to your Google Account settings
   - Navigate to Security > App Passwords
   - Create a new app password for "Mail"
   - Use this app password in your .env file

## Usage

You can run the application in three different ways:

### Run everything (RSS feeds + Google Alerts)

```bash
python app.py
```

### Run only RSS feed fetching

```bash
python rss_fetcher.py
```

### Run only Google Alerts fetching

```bash
python google_alerts_fetcher.py
```

## Troubleshooting Google Alerts

If you're not getting any articles from Google Alerts:

1. Check your Gmail credentials - make sure your app password is correct
2. Verify you have Google Alerts set up and that they're being delivered to your inbox
3. Check that the emails are coming from "googlealerts-noreply@google.com"
4. Try running in debug mode (`DEBUG_FETCH=true`) to fetch alerts from the past 7 days
5. Check the logs for any error messages related to Gmail connection

## Notion Database Setup

Your Notion database should have the following properties:

- Title (title) - Article title
- URL (url) - Article URL
- Summary (rich text) - Article summary
- Source (select) - Source name
- Type (select) - RSS Feed or Google Alerts
- Date (date) - Publication date
- Relevancy (number) - Calculated relevancy score
- PDF (url) - PDF link if available
- Theme (multi-select) - Detected themes
- Tags (multi-select) - Extracted tags

## Customization

- Edit the RSS feeds in your .env file to add or remove sources
- Modify the relevancy calculation in utils.py
- Adjust the theme detection in utils.py
- Change the tag extraction in utils.py 