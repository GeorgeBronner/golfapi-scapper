"""Update the starting ID for the scraper."""
import sqlite3
import sys
import os

# Add src to path and import database module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.environ['DB_PATH'] = os.path.join(os.path.dirname(__file__), 'data', 'golf_courses.db')

from src.database import Database

if len(sys.argv) < 2:
    print("Usage: python update_start_id.py <start_id>")
    print("This will set last_scraped_id to start_id - 1")
    sys.exit(1)

start_id = int(sys.argv[1])
last_scraped_id = start_id - 1

# Initialize database (creates tables if needed)
db = Database()

# Update metadata
db.update_scrape_metadata(
    last_scraped_id=last_scraped_id,
    consecutive_404s=0
)

# Show updated metadata
metadata = db.get_scrape_metadata()
print(f"Updated scrape_metadata:")
print(f"  last_scraped_id: {metadata['last_scraped_id']}")
print(f"  consecutive_404s: {metadata['consecutive_404s']}")
print(f"  total_courses_scraped: {metadata['total_courses_scraped']}")
print(f"\nScraper will resume from ID: {metadata['last_scraped_id'] + 1}")

db.close()
