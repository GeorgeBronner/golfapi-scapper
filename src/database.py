"""Database management for the Golf Course API scraper."""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

from .config import Config

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for golf course data."""

    def __init__(self, db_path: str = None):
        """Initialize database connection."""
        self.db_path = db_path or Config.DB_PATH
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Connect to SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Transaction failed, rolling back: {e}")
            raise

    def _create_tables(self):
        """Create database tables if they don't exist."""
        with self.transaction():
            cursor = self.conn.cursor()

            # Scrape metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scrape_metadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_scraped_id INTEGER NOT NULL DEFAULT 0,
                    consecutive_404s INTEGER NOT NULL DEFAULT 0,
                    total_courses_scraped INTEGER NOT NULL DEFAULT 0,
                    scraping_complete BOOLEAN NOT NULL DEFAULT 0,
                    last_updated TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # API call tracking table (for 24-hour rolling window)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create index on timestamp for efficient rate limit queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp
                ON api_calls(timestamp)
            ''')

            # Scrape attempts table (tracks all IDs tried, including 404s)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scrape_attempts (
                    course_id INTEGER PRIMARY KEY,
                    status_code INTEGER NOT NULL,
                    success BOOLEAN NOT NULL,
                    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create index on attempted_at for efficient queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_scrape_attempts_attempted_at
                ON scrape_attempts(attempted_at)
            ''')

            # Courses table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY,
                    club_name TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Locations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL UNIQUE,
                    address TEXT,
                    city TEXT,
                    state TEXT,
                    country TEXT,
                    latitude REAL,
                    longitude REAL,
                    FOREIGN KEY (course_id) REFERENCES courses(id)
                )
            ''')

            # Tees table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    gender TEXT NOT NULL CHECK(gender IN ('male', 'female')),
                    tee_name TEXT NOT NULL,
                    course_rating REAL,
                    slope_rating INTEGER,
                    bogey_rating REAL,
                    total_yards INTEGER,
                    total_meters INTEGER,
                    number_of_holes INTEGER,
                    par_total INTEGER,
                    front_course_rating REAL,
                    front_slope_rating INTEGER,
                    front_bogey_rating REAL,
                    back_course_rating REAL,
                    back_slope_rating INTEGER,
                    back_bogey_rating REAL,
                    FOREIGN KEY (course_id) REFERENCES courses(id)
                )
            ''')

            # Holes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS holes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tee_id INTEGER NOT NULL,
                    hole_number INTEGER NOT NULL CHECK(hole_number BETWEEN 1 AND 18),
                    par INTEGER,
                    yardage INTEGER,
                    handicap INTEGER,
                    FOREIGN KEY (tee_id) REFERENCES tees(id)
                )
            ''')

            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_locations_course_id
                ON locations(course_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tees_course_id
                ON tees(course_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_holes_tee_id
                ON holes(tee_id)
            ''')

            # Initialize metadata if not exists
            cursor.execute('SELECT COUNT(*) FROM scrape_metadata')
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO scrape_metadata (id, last_scraped_id, last_updated)
                    VALUES (1, 0, ?)
                ''', (datetime.now(),))
                logger.info("Initialized scrape_metadata table")

        logger.info("Database tables created/verified")

    def get_scrape_metadata(self) -> Dict[str, Any]:
        """Get current scraping metadata."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM scrape_metadata WHERE id = 1')
        row = cursor.fetchone()
        return dict(row) if row else {}

    def update_scrape_metadata(self, **kwargs):
        """Update scraping metadata."""
        with self.transaction():
            cursor = self.conn.cursor()

            # Build SET clause dynamically
            set_clauses = []
            values = []
            for key, value in kwargs.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)

            # Always update last_updated
            set_clauses.append("last_updated = ?")
            values.append(datetime.now())
            values.append(1)  # WHERE id = 1

            query = f"UPDATE scrape_metadata SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, values)

    def record_api_call(self):
        """Record an API call for rate limiting purposes."""
        with self.transaction():
            cursor = self.conn.cursor()
            cursor.execute('INSERT INTO api_calls (timestamp) VALUES (?)', (datetime.now(),))

    def get_api_calls_in_window(self) -> int:
        """Get count of API calls in the last 24 hours."""
        cursor = self.conn.cursor()
        window_start = datetime.now() - timedelta(hours=Config.RATE_LIMIT_WINDOW_HOURS)
        cursor.execute('''
            SELECT COUNT(*) FROM api_calls
            WHERE timestamp > ?
        ''', (window_start,))
        return cursor.fetchone()[0]

    def cleanup_old_api_calls(self):
        """Remove API call records older than 24 hours."""
        with self.transaction():
            cursor = self.conn.cursor()
            window_start = datetime.now() - timedelta(hours=Config.RATE_LIMIT_WINDOW_HOURS)
            cursor.execute('DELETE FROM api_calls WHERE timestamp <= ?', (window_start,))
            deleted = cursor.rowcount
            if deleted > 0:
                logger.debug(f"Cleaned up {deleted} old API call records")

    def get_oldest_api_call_in_window(self) -> Optional[datetime]:
        """Get timestamp of oldest API call in current window."""
        cursor = self.conn.cursor()
        window_start = datetime.now() - timedelta(hours=Config.RATE_LIMIT_WINDOW_HOURS)
        cursor.execute('''
            SELECT MIN(timestamp) FROM api_calls
            WHERE timestamp > ?
        ''', (window_start,))
        result = cursor.fetchone()[0]
        return datetime.fromisoformat(result) if result else None

    def is_course_already_attempted(self, course_id: int) -> bool:
        """Check if a course ID has already been attempted."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM scrape_attempts WHERE course_id = ?', (course_id,))
        return cursor.fetchone() is not None

    def record_scrape_attempt(self, course_id: int, status_code: int, success: bool):
        """Record a scrape attempt (both successful and failed)."""
        with self.transaction():
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO scrape_attempts (course_id, status_code, success)
                VALUES (?, ?, ?)
            ''', (course_id, status_code, success))

    def save_course(self, course_data: Dict[str, Any]):
        """Save complete course data to database."""
        with self.transaction():
            cursor = self.conn.cursor()

            course = course_data.get('course', {})
            course_id = course.get('id')

            if not course_id:
                raise ValueError("Course data missing 'id'")

            # Insert course
            cursor.execute('''
                INSERT OR REPLACE INTO courses (id, club_name, course_name)
                VALUES (?, ?, ?)
            ''', (
                course_id,
                course.get('club_name', ''),
                course.get('course_name', '')
            ))

            # Insert location
            location = course.get('location', {})
            if location:
                cursor.execute('''
                    INSERT OR REPLACE INTO locations
                    (course_id, address, city, state, country, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    course_id,
                    location.get('address'),
                    location.get('city'),
                    location.get('state'),
                    location.get('country'),
                    location.get('latitude'),
                    location.get('longitude')
                ))

            # Insert tees and holes
            tees_data = course.get('tees', {})
            for gender in ['male', 'female']:
                tees_list = tees_data.get(gender, [])
                for tee in tees_list:
                    cursor.execute('''
                        INSERT INTO tees (
                            course_id, gender, tee_name, course_rating, slope_rating,
                            bogey_rating, total_yards, total_meters, number_of_holes,
                            par_total, front_course_rating, front_slope_rating,
                            front_bogey_rating, back_course_rating, back_slope_rating,
                            back_bogey_rating
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        course_id,
                        gender,
                        tee.get('tee_name'),
                        tee.get('course_rating'),
                        tee.get('slope_rating'),
                        tee.get('bogey_rating'),
                        tee.get('total_yards'),
                        tee.get('total_meters'),
                        tee.get('number_of_holes'),
                        tee.get('par_total'),
                        tee.get('front_course_rating'),
                        tee.get('front_slope_rating'),
                        tee.get('front_bogey_rating'),
                        tee.get('back_course_rating'),
                        tee.get('back_slope_rating'),
                        tee.get('back_bogey_rating')
                    ))

                    tee_id = cursor.lastrowid

                    # Insert holes for this tee
                    holes = tee.get('holes', [])
                    for hole_num, hole in enumerate(holes, start=1):
                        cursor.execute('''
                            INSERT INTO holes (tee_id, hole_number, par, yardage, handicap)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            tee_id,
                            hole_num,
                            hole.get('par'),
                            hole.get('yardage'),
                            hole.get('handicap')
                        ))

            # Update total courses scraped
            cursor.execute('''
                UPDATE scrape_metadata
                SET total_courses_scraped = total_courses_scraped + 1,
                    last_updated = ?
                WHERE id = 1
            ''', (datetime.now(),))

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
