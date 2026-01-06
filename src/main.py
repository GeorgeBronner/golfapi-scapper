"""Main entry point for the Golf Course API scraper."""

import logging
import signal
import sys
import os

from .config import Config
from .database import Database
from .scraper import GolfCourseScraper

# Global flag for graceful shutdown
shutdown_requested = False


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format=Config.LOG_FORMAT,
        datefmt=Config.LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    signal_name = signal.Signals(signum).name
    logger = logging.getLogger(__name__)
    logger.info(f"Received {signal_name} signal. Initiating graceful shutdown...")
    shutdown_requested = True


def main():
    """Main application entry point."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Golf Course API Scraper")
    logger.info("=" * 60)

    # Validate configuration
    try:
        Config.validate()
        logger.info("Configuration validated")
        logger.info(f"API Base URL: {Config.API_BASE_URL}")
        logger.info(f"Rate limit: {Config.MAX_CALLS_PER_DAY} calls per {Config.RATE_LIMIT_WINDOW_HOURS} hours")
        logger.info(f"Database path: {Config.DB_PATH}")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Ensure data directory exists
    os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Initialize database
    db = None
    try:
        logger.info("Initializing database...")
        db = Database()

        metadata = db.get_scrape_metadata()
        logger.info(f"Last scraped ID: {metadata.get('last_scraped_id', 0)}")
        logger.info(f"Total courses in database: {metadata.get('total_courses_scraped', 0)}")
        logger.info(f"Scraping complete: {metadata.get('scraping_complete', False)}")

        # Check if already complete
        if metadata.get('scraping_complete'):
            logger.info("Scraping already marked as complete.")
            logger.info("To restart scraping, update the scrape_metadata table in the database.")
            return

        # Initialize scraper
        logger.info("Starting scraper...")
        scraper = GolfCourseScraper(db)

        # Run scraper
        scraper.scrape()

        logger.info("Scraping completed successfully")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if db:
            db.close()
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    main()
