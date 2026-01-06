# Golf Course API Scraper - Implementation Log

## Project Overview
This document tracks the implementation of a containerized Python application that scrapes golf course data from the GolfCourseAPI.

## Implementation Date
2026-01-05

## Key Design Decisions

### 1. Rate Limiting Strategy
- **Decision**: 24-hour rolling window instead of UTC day reset
- **Implementation**: Store timestamp of each API call in a rolling list
- **Limit**: 295 calls per 24-hour window (buffer of 5 from 300 limit)
- **Behavior**: When limit reached, sleep until oldest call drops out of window

### 2. Database Schema
Five normalized tables:
- `scrape_metadata` - Single row tracking scraping state
- `courses` - Core course information
- `locations` - Location data (1:1 with courses)
- `tees` - Tee box configurations (1:many with courses)
- `holes` - Individual hole data (1:many with tees)

### 3. Resume Capability
- On startup, query `scrape_metadata.last_scraped_id`
- Continue from `last_scraped_id + 1`
- If `scraping_complete = 1`, exit gracefully

### 4. Completion Detection
- Stop after 20 consecutive 404 responses
- Set `scraping_complete = 1` in database
- Log total courses scraped

## Module Structure

### `src/config.py`
- Load environment variables from `.env`
- Define constants (API URL, rate limits, retry delays)
- Validate API key presence

### `src/database.py`
- SQLite database connection management
- Table creation with proper schema
- CRUD operations for all tables
- Transaction management
- Helper methods:
  - `get_scrape_metadata()` - Get current state
  - `update_scrape_metadata()` - Update progress
  - `save_course()` - Save complete course data
  - `record_api_call()` - Track API calls for rate limiting
  - `get_api_calls_in_window()` - Check rate limit status

### `src/scraper.py`
- Main scraping logic
- API client with retry logic
- Rate limiting enforcement
- Error handling:
  - 200: Parse and save
  - 404: Increment consecutive counter
  - 401: Fatal error, exit
  - 429: Rate limit hit, sleep 1 hour
  - Other: Retry with backoff
- Methods:
  - `fetch_course(course_id)` - Make API request
  - `parse_course_data(response)` - Parse JSON response
  - `check_rate_limit()` - Verify calls within limit
  - `wait_for_rate_limit()` - Sleep until window opens

### `src/main.py`
- Entry point for the application
- Initialize database
- Load configuration
- Start scraping loop
- Handle graceful shutdown (SIGTERM, SIGINT)

## Logging Strategy

**Format**: `[TIMESTAMP] [LEVEL] message`

**Levels Used**:
- INFO: Normal operations
- WARNING: Recoverable issues (404s, rate limits)
- ERROR: Errors requiring intervention

**Key Log Messages**:
- Startup and configuration loaded
- Resume from ID
- Successfully scraped course with name
- Database save confirmation
- Rate limit status
- 404 warnings with consecutive count
- Completion message
- Error details

## Docker Setup

### Dockerfile
- Base: `python:3.11-slim`
- Working directory: `/app`
- Copy source code to `/app/src`
- Install dependencies from `requirements.txt`
- Create `/app/data` directory for database
- Entry point: `python -u src/main.py` (unbuffered for live logging)

### docker-compose.yml
- Single service: `scraper`
- Volume mount: `./data:/app/data`
- Environment: Load from `.env`
- Restart policy: `unless-stopped`

## Error Handling

### Network Errors
- Catch `requests.exceptions.RequestException`
- Log error
- Wait 5 minutes
- Retry same ID
- Max 3 retries before moving to next ID

### Database Errors
- Use transactions for atomicity
- Rollback on any failure
- Log error with course ID
- Continue to next course

### API Errors
- 401: Log and exit (bad API key)
- 429: Sleep 1 hour, retry same ID
- 5xx: Retry with exponential backoff
- Other: Log and skip to next ID

## Data Validation

Before inserting to database:
- Verify required fields exist (`id`, `club_name`, `course_name`)
- Validate data types
- Handle null/missing optional fields
- Ensure hole numbers are sequential (1-18)

## Testing Checklist

- [ ] Database tables created correctly
- [ ] API authentication works
- [ ] Can fetch course by ID
- [ ] Data parsed and saved correctly
- [ ] Resume from last ID works
- [ ] Rate limiting enforced
- [ ] 404 detection stops after 20 consecutive
- [ ] Logging outputs correctly
- [ ] Docker container builds
- [ ] Docker container runs continuously
- [ ] Database persists after container restart
- [ ] Graceful shutdown on SIGTERM

## Implementation Status

### Completed
- Requirements analysis
- API exploration and testing
- Database schema design
- Architecture planning

### In Progress
- Creating project files

### Pending
- Implementation
- Testing
- Deployment

## Notes

- API returns nested JSON structure with `course` wrapper
- Each course can have multiple tee boxes for male/female
- Each tee box has 18 holes
- Tee box data varies (not all courses have all tee boxes)
- API uses `Authorization: Key <api_key>` header format
