"""Golf Course API scraper with rate limiting and retry logic."""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import requests
from requests.exceptions import RequestException

from .config import Config
from .database import Database

logger = logging.getLogger(__name__)


class GolfCourseScraper:
    """Scraper for the Golf Course API."""

    def __init__(self, database: Database):
        """Initialize the scraper."""
        self.db = database
        self.session = requests.Session()
        self.session.headers.update(Config.get_auth_header())

    def fetch_course(self, course_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch course data from API.

        Returns:
            Course data dict if successful, None if 404, raises exception for other errors
        """
        url = f"{Config.API_BASE_URL}{Config.API_COURSE_ENDPOINT}/{course_id}"

        for attempt in range(1, Config.RETRY_MAX_ATTEMPTS + 1):
            try:
                logger.debug(f"Fetching course {course_id} (attempt {attempt}/{Config.RETRY_MAX_ATTEMPTS})")

                response = self.session.get(url, timeout=30)

                # Record API call for rate limiting
                self.db.record_api_call()

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 404:
                    logger.debug(f"Course {course_id} not found (404)")
                    return None

                elif response.status_code == 401:
                    logger.error("Authentication failed (401). Check API key.")
                    raise ValueError("Invalid API key")

                elif response.status_code == 429:
                    logger.warning(f"Rate limit hit (429) for course {course_id}")
                    logger.info(f"Sleeping {Config.RATE_LIMIT_SLEEP_SECONDS} seconds...")
                    time.sleep(Config.RATE_LIMIT_SLEEP_SECONDS)
                    continue  # Retry same ID

                else:
                    logger.warning(f"Unexpected status {response.status_code} for course {course_id}")
                    if attempt < Config.RETRY_MAX_ATTEMPTS:
                        wait_time = Config.RETRY_DELAY_SECONDS * attempt
                        logger.info(f"Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for course {course_id}")
                        return None

            except RequestException as e:
                logger.error(f"Network error fetching course {course_id}: {e}")
                if attempt < Config.RETRY_MAX_ATTEMPTS:
                    wait_time = Config.RETRY_DELAY_SECONDS * attempt
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries exceeded for course {course_id}")
                    return None

        return None

    def check_rate_limit(self) -> bool:
        """
        Check if we're within rate limit.

        Returns:
            True if we can make more calls, False if limit reached
        """
        calls_in_window = self.db.get_api_calls_in_window()
        return calls_in_window < Config.MAX_CALLS_PER_DAY

    def wait_for_rate_limit_window(self):
        """Wait until we can make more API calls."""
        oldest_call = self.db.get_oldest_api_call_in_window()

        if oldest_call:
            # Calculate when the oldest call will drop out of the 24-hour window
            window_reset_time = oldest_call + timedelta(hours=Config.RATE_LIMIT_WINDOW_HOURS)
            now = datetime.now()

            if window_reset_time > now:
                wait_seconds = (window_reset_time - now).total_seconds()
                logger.info(
                    f"Rate limit reached ({Config.MAX_CALLS_PER_DAY} calls in 24 hours). "
                    f"Sleeping until {window_reset_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"({int(wait_seconds)} seconds)..."
                )
                time.sleep(wait_seconds + 1)  # Add 1 second buffer
            else:
                # Clean up old records
                self.db.cleanup_old_api_calls()
        else:
            # No calls in window, wait a bit and continue
            logger.warning("Rate limit triggered but no calls in window. Waiting 60 seconds...")
            time.sleep(60)

    def scrape(self):
        """Main scraping loop."""
        logger.info("Starting scraper...")

        # Get current metadata
        metadata = self.db.get_scrape_metadata()

        if metadata.get('scraping_complete'):
            logger.info("Scraping already complete. Exiting.")
            logger.info(f"Total courses scraped: {metadata.get('total_courses_scraped', 0)}")
            return

        # Resume from last position
        current_id = metadata.get('last_scraped_id', 0) + 1
        consecutive_404s = metadata.get('consecutive_404s', 0)

        logger.info(f"Resuming from course ID: {current_id}")
        logger.info(f"Consecutive 404s: {consecutive_404s}/{Config.CONSECUTIVE_404_LIMIT}")

        while consecutive_404s < Config.CONSECUTIVE_404_LIMIT:
            # Skip if already attempted
            if self.db.is_course_already_attempted(current_id):
                logger.debug(f"Course ID {current_id} already attempted, skipping...")
                current_id += 1
                continue

            # Check rate limit
            if not self.check_rate_limit():
                calls_in_window = self.db.get_api_calls_in_window()
                logger.warning(f"Rate limit reached: {calls_in_window}/{Config.MAX_CALLS_PER_DAY} calls")
                self.wait_for_rate_limit_window()
                # Clean up old records after waiting
                self.db.cleanup_old_api_calls()

            # Fetch course
            logger.debug(f"Attempting to fetch course ID: {current_id}")
            course_data = self.fetch_course(current_id)

            if course_data:
                # Successfully fetched course
                course = course_data.get('course', {})
                club_name = course.get('club_name', 'Unknown')
                course_name = course.get('course_name', 'Unknown')

                logger.info(f"Successfully scraped course {current_id}: {club_name} - {course_name}")

                # Save to database
                try:
                    self.db.save_course(course_data)
                    # Record successful attempt
                    self.db.record_scrape_attempt(current_id, 200, True)
                    logger.info(f"Saved course {current_id} to database")
                except Exception as e:
                    logger.error(f"Failed to save course {current_id}: {e}")
                    # Record failed save attempt
                    self.db.record_scrape_attempt(current_id, 200, False)
                    # Continue to next course even if save fails

                # Reset consecutive 404s
                consecutive_404s = 0
                self.db.update_scrape_metadata(
                    last_scraped_id=current_id,
                    consecutive_404s=0
                )

            else:
                # Got 404 or error
                # Record 404 attempt
                self.db.record_scrape_attempt(current_id, 404, False)

                consecutive_404s += 1
                logger.warning(
                    f"Received 404 for course ID {current_id} "
                    f"(consecutive 404s: {consecutive_404s}/{Config.CONSECUTIVE_404_LIMIT})"
                )

                self.db.update_scrape_metadata(
                    last_scraped_id=current_id,
                    consecutive_404s=consecutive_404s
                )

            # Move to next ID
            current_id += 1

            # Respectful delay between requests
            time.sleep(Config.REQUEST_DELAY_SECONDS)

            # Periodic cleanup of old API call records (every 100 requests)
            if current_id % 100 == 0:
                self.db.cleanup_old_api_calls()

        # Scraping complete
        logger.info(f"Reached {Config.CONSECUTIVE_404_LIMIT} consecutive 404s. Scraping complete!")

        metadata = self.db.get_scrape_metadata()
        total_courses = metadata.get('total_courses_scraped', 0)

        self.db.update_scrape_metadata(scraping_complete=True)

        logger.info(f"Total courses scraped: {total_courses}")
        logger.info("Scraper finished successfully.")
