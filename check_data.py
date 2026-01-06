"""Check database statistics."""
import sqlite3
import sys
import os

db_path = "data/golf_courses.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 60)
print("DATABASE STATISTICS")
print("=" * 60)

# Scrape metadata
cursor.execute("SELECT * FROM scrape_metadata WHERE id = 1")
meta = cursor.fetchone()
print(f"\nScrape Progress:")
print(f"  Last scraped ID: {meta['last_scraped_id']}")
print(f"  Total courses scraped: {meta['total_courses_scraped']}")
print(f"  Consecutive 404s: {meta['consecutive_404s']}")
print(f"  Scraping complete: {bool(meta['scraping_complete'])}")

# Courses count
cursor.execute("SELECT COUNT(*) as count FROM courses")
courses_count = cursor.fetchone()['count']
print(f"\nCourses in database: {courses_count}")

# Locations count
cursor.execute("SELECT COUNT(*) as count FROM locations")
locations_count = cursor.fetchone()['count']
print(f"Locations: {locations_count}")

# Tees count
cursor.execute("SELECT COUNT(*) as count FROM tees")
tees_count = cursor.fetchone()['count']
print(f"Tees: {tees_count}")

# Holes count
cursor.execute("SELECT COUNT(*) as count FROM holes")
holes_count = cursor.fetchone()['count']
print(f"Holes: {holes_count}")

# Scrape attempts
cursor.execute("""
    SELECT
        COUNT(*) as total_attempts,
        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
    FROM scrape_attempts
""")
attempts = cursor.fetchone()
print(f"\nScrape Attempts:")
print(f"  Total attempts: {attempts['total_attempts']}")
print(f"  Successful: {attempts['successful']}")
print(f"  Failed (404s): {attempts['failed']}")

# Check for any holes with NULL values
cursor.execute("""
    SELECT COUNT(*) as count
    FROM holes
    WHERE par IS NULL OR yardage IS NULL OR handicap IS NULL
""")
null_holes = cursor.fetchone()['count']
if null_holes > 0:
    print(f"\nWARNING: Found {null_holes} holes with NULL values (par/yardage/handicap)")
    cursor.execute("""
        SELECT DISTINCT c.id, c.club_name
        FROM courses c
        JOIN tees t ON t.course_id = c.id
        JOIN holes h ON h.tee_id = t.id
        WHERE h.par IS NULL OR h.yardage IS NULL OR h.handicap IS NULL
        LIMIT 5
    """)
    print("  Sample courses with incomplete hole data:")
    for row in cursor.fetchall():
        print(f"    - Course {row['id']}: {row['club_name']}")
else:
    print(f"\nSUCCESS: All holes have complete data")

# Sample courses
print("\nSample courses (first 5):")
cursor.execute("SELECT id, club_name, course_name FROM courses ORDER BY id LIMIT 5")
for row in cursor.fetchall():
    print(f"  {row['id']}: {row['club_name']} - {row['course_name']}")

conn.close()
print("\n" + "=" * 60)
