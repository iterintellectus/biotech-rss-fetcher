import os
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Notion configuration
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

print(f"Attempting to connect to Notion with token: {NOTION_TOKEN[:4]}...")
print(f"Database ID: {DATABASE_ID}")

if not NOTION_TOKEN or not DATABASE_ID:
    print("Missing environment variables. Please set NOTION_TOKEN and NOTION_DATABASE_ID")
    exit(1)

# Initialize the Notion client
notion = Client(auth=NOTION_TOKEN)

# Test retrieving the database metadata
try:
    response = notion.databases.retrieve(database_id=DATABASE_ID)
    print("Successfully connected to Notion database!")
    print("Database title:", response.get("title", [{}])[0].get("plain_text", "Untitled"))
    
    # List database properties
    print("\nDatabase properties:")
    for name, prop in response.get("properties", {}).items():
        prop_type = prop.get("type", "unknown")
        print(f" - {name} ({prop_type})")
    
    # Check if required properties exist
    required_properties = [
        ("Title", "title"),
        ("URL", "url"),
        ("Summary", "rich_text"),
        ("PDF Insights", "rich_text"),
        ("PDF Link", "url"),
        ("PDF Local Path", "rich_text")
    ]
    
    missing = []
    for prop_name, prop_type in required_properties:
        found = False
        for name, prop in response.get("properties", {}).items():
            if name == prop_name and prop.get("type") == prop_type:
                found = True
                break
        if not found:
            missing.append(f"{prop_name} ({prop_type})")
    
    if missing:
        print("\nWARNING: Missing required properties:")
        for prop in missing:
            print(f" - {prop}")
    else:
        print("\nAll required properties found!")
    
    # Try to query the database
    print("\nAttempting to query the database...")
    query = notion.databases.query(database_id=DATABASE_ID, page_size=1)
    print(f"Found {len(query.get('results', []))} entries in the database")
    
except Exception as e:
    print(f"ERROR connecting to Notion: {e}") 