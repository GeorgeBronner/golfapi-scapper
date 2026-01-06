# Golf Course API Scraper

A containerized Python application that systematically scrapes golf course data from the GolfCourseAPI and stores it in a SQLite database.

## Features

- **Sequential ID Scraping**: Scrapes courses by ID from 1 onwards
- **Smart Resume**: Automatically resumes from the last scraped ID on restart
- **Rate Limiting**: 24-hour rolling window rate limiting (configurable, defaults to 295 calls/day)
- **Robust Error Handling**: Retries failed requests, handles network errors gracefully
- **Comprehensive Logging**: Detailed logs for monitoring progress
- **Docker Support**: Runs in a container with persistent database storage
- **Auto-completion Detection**: Stops after 1000 consecutive 404 responses (configurable)

## Quick Start

**For production server setup, see [GETTING_STARTED.md](GETTING_STARTED.md) for detailed step-by-step instructions.**

### Running with Docker Compose (Recommended)

```bash
# Build and start the scraper
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the scraper
docker-compose down
```

### Running Locally with uv

```bash
# Run the scraper
uv run run.py

# Or run directly
uv run python -m src.main
```

## Configuration

Edit the `.env` file to configure the scraper:

```env
# Required: Your API key from golfcourseapi.com
GOLFCOURSEAPI_API_KEY=your_api_key_here

# Optional: Maximum API calls per 24-hour rolling window (default: 295)
MAX_CALLS_PER_DAY=295

# Optional: Stop after this many consecutive 404s (default: 1000)
CONSECUTIVE_404_LIMIT=1000
```

## Database Schema

The scraper creates a SQLite database at `./data/golf_courses.db` with the following tables:

### `scrape_metadata`
Tracks scraping progress and state.

### `courses`
Core course information (id, club_name, course_name).

### `locations`
Location data for each course (address, city, state, country, coordinates).

### `tees`
Tee box configurations for male and female golfers.

### `holes`
Individual hole data for each tee (par, yardage, handicap).

### `api_calls`
Tracks API calls for the 24-hour rolling window rate limit.

### `scrape_attempts`
Tracks all course IDs attempted (including 404s) to avoid retrying failed IDs.

## How It Works

1. **Initialization**: On startup, the scraper connects to the database and checks the last scraped ID
2. **Sequential Scraping**: Starts from `last_scraped_id + 1` and increments
3. **Skip Already Attempted**: Checks `scrape_attempts` table to avoid retrying 404s
4. **Rate Limiting**: Enforces a 24-hour rolling window (not daily reset)
5. **Data Storage**: Saves complete course data with location, tees, and holes
6. **Track All Attempts**: Records both successful fetches and 404s in `scrape_attempts` table
7. **Completion**: Stops after 1000 consecutive 404 responses, marking scraping as complete

## Project Structure

```
golfcourseapi-scraper/
├── src/
│   ├── config.py          # Configuration management
│   ├── database.py        # Database operations
│   ├── scraper.py         # Scraping logic
│   └── main.py            # Entry point
├── data/                  # Database storage (created at runtime)
│   └── golf_courses.db
├── .env                   # Environment variables
├── pyproject.toml         # Dependencies
├── Dockerfile
├── docker-compose.yml
├── run.py                 # Local testing script
├── requirements.md        # Detailed requirements
├── CLAUDE.md              # Implementation notes
└── README.md              # This file
```

## Monitoring Progress

### View Logs (Docker)
```bash
docker-compose logs -f scraper
```

### Check Database Status

```bash
# Connect to the database
sqlite3 data/golf_courses.db

# Check progress
SELECT * FROM scrape_metadata;

# Count courses scraped
SELECT COUNT(*) FROM courses;

# View recent courses
SELECT id, club_name, course_name FROM courses ORDER BY id DESC LIMIT 10;
```

## Stopping the Scraper

The scraper will automatically stop when:
- 1000 consecutive 404 responses are received (configurable via `CONSECUTIVE_404_LIMIT`)
- `scraping_complete` flag is set to 1 in the database

To manually stop:
```bash
# Docker
docker-compose down

# Local (Ctrl+C)
# The scraper will shut down gracefully and save progress
```

## Restarting After Completion

If scraping is marked complete but you want to continue (e.g., new courses added):

```bash
sqlite3 data/golf_courses.db
UPDATE scrape_metadata SET scraping_complete = 0, consecutive_404s = 0;
```

## Rate Limiting Details

- **Window**: 24-hour rolling window (not daily reset at midnight)
- **Default Limit**: 295 calls per 24 hours (buffer of 5 from the 300/day API limit)
- **Behavior**: When limit reached, scraper sleeps until oldest call drops out of window
- **Configurable**: Set `MAX_CALLS_PER_DAY` in `.env` for higher-tier API keys

## API Information

- **Base URL**: https://api.golfcourseapi.com
- **Endpoint**: `/v1/courses/{id}`
- **Authentication**: `Authorization: Key <api_key>` header
- **Rate Limit**: 300 calls/day (default API key tier)

## Troubleshooting

### "Authentication failed" error
Check that your API key in `.env` is correct:
```bash
cat .env | grep GOLFCOURSEAPI_API_KEY
```

### Database locked errors
Ensure only one instance of the scraper is running at a time.

### Rate limit not working correctly
The scraper uses a rolling 24-hour window. Check `api_calls` table:
```sql
SELECT COUNT(*) FROM api_calls WHERE timestamp > datetime('now', '-24 hours');
```

### Want to start over
```bash
rm data/golf_courses.db
docker-compose restart  # or uv run run.py
```

## Dependencies

Managed via `pyproject.toml` and `uv`:
- Python 3.11+
- requests >= 2.31.0
- python-dotenv >= 1.0.0

## License

This project is for personal use with the GolfCourseAPI. Ensure you comply with the API's terms of service.

## Documentation

- `requirements.md` - Detailed technical requirements
- `CLAUDE.md` - Implementation notes and design decisions
