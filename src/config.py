"""Configuration management for the Golf Course API scraper."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # API Configuration
    API_KEY = os.getenv('GOLFCOURSEAPI_API_KEY')
    API_BASE_URL = os.getenv('API_BASE_URL', 'https://api.golfcourseapi.com')
    API_COURSE_ENDPOINT = '/v1/courses'

    # Rate Limiting (24-hour rolling window)
    # Default to 295 calls per day, but allow override from .env
    MAX_CALLS_PER_DAY = int(os.getenv('MAX_CALLS_PER_DAY', '295'))
    RATE_LIMIT_WINDOW_HOURS = 24

    # Scraping Configuration
    CONSECUTIVE_404_LIMIT = int(os.getenv('CONSECUTIVE_404_LIMIT', '1000'))  # Stop after this many consecutive 404s
    REQUEST_DELAY_SECONDS = 1.5  # Delay between requests to be respectful

    # Retry Configuration
    RETRY_DELAY_SECONDS = 300  # 5 minutes
    RETRY_MAX_ATTEMPTS = 3
    RATE_LIMIT_SLEEP_SECONDS = 3600  # 1 hour if we hit 429

    # Database Configuration
    DB_PATH = os.getenv('DB_PATH', '/app/data/golf_courses.db')

    # Logging Configuration
    LOG_FORMAT = '[%(asctime)s] [%(levelname)s] %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.API_KEY:
            raise ValueError("GOLFCOURSEAPI_API_KEY not found in environment variables")

        if cls.MAX_CALLS_PER_DAY <= 0:
            raise ValueError("MAX_CALLS_PER_DAY must be greater than 0")

    @classmethod
    def get_auth_header(cls):
        """Get the authorization header for API requests."""
        return {'Authorization': f'Key {cls.API_KEY}'}
