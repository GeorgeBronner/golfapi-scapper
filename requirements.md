# Golf Course API Scraper - Requirements Document

## Project Overview
A containerized Python application that systematically scrapes golf course data from the GolfCourseAPI, stores it in a SQLite database, and respects API rate limits.

## API Information

### Base URL
```
https://api.golfcourseapi.com
```

### Authentication
- Method: API Key in header
- Header format: `Authorization: Key <api_key>`
- API Key stored in `.env` file as `GOLFCOURSEAPI_API_KEY`

### Endpoints

#### 1. Get Course by ID
```
GET /v1/courses/{id}
```

**Response Structure:**
```json
{
  "course": {
    "id": 18718,
    "club_name": "Pinehurst Golf Course",
    "course_name": "Pinehurst Golf Course",
    "location": {
      "address": "11 Country Club Ln, Pinehurst, ID 83850, USA",
      "city": "Pinehurst",
      "state": "ID",
      "country": "United States",
      "latitude": 47.53706,
      "longitude": -116.23311
    },
    "tees": {
      "female": [
        {
          "tee_name": "Blue 21",
          "course_rating": 74.5,
          "slope_rating": 128,
          "bogey_rating": 104.6,
          "total_yards": 5945,
          "total_meters": 5436,
          "number_of_holes": 18,
          "par_total": 74,
          "front_course_rating": 37.0,
          "front_slope_rating": 130,
          "front_bogey_rating": 52.3,
          "back_course_rating": 37.5,
          "back_slope_rating": 126,
          "back_bogey_rating": 52.3,
          "holes": [
            {
              "par": 4,
              "yardage": 297,
              "handicap": 9
            }
            // ... more holes
          ]
        }
        // ... more tee boxes
      ],
      "male": [
        // ... same structure as female
      ]
    }
  }
}
```

**Error Responses:**
- `404` - Course not found
- `401` - Authentication error

#### 2. Search Courses (Not used in scraper)
```
GET /v1/search?search_query=<term>
```
Returns array of courses matching search term.

## Database Schema

### SQLite Database: `golf_courses.db`

#### Table: `scrape_metadata`
Tracks scraping progress and state.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Always 1 (single row table) |
| last_scraped_id | INTEGER | NOT NULL DEFAULT 0 | Last successfully scraped course ID |
| consecutive_404s | INTEGER | NOT NULL DEFAULT 0 | Count of consecutive 404 responses |
| total_courses_scraped | INTEGER | NOT NULL DEFAULT 0 | Total number of courses in database |
| scraping_complete | BOOLEAN | NOT NULL DEFAULT 0 | Whether scraping has finished |
| last_updated | TIMESTAMP | NOT NULL | Last update timestamp |
| daily_api_calls | INTEGER | NOT NULL DEFAULT 0 | API calls made today |
| last_api_call_date | DATE | | Date of last API call |

#### Table: `courses`
Core course information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Course ID from API |
| club_name | TEXT | NOT NULL | Name of the golf club |
| course_name | TEXT | NOT NULL | Name of the course |
| created_at | TIMESTAMP | NOT NULL DEFAULT CURRENT_TIMESTAMP | Record creation time |

#### Table: `locations`
Location data for each course (1:1 relationship).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Location record ID |
| course_id | INTEGER | NOT NULL UNIQUE, FOREIGN KEY → courses(id) | Course reference |
| address | TEXT | | Full address |
| city | TEXT | | City name |
| state | TEXT | | State/province code |
| country | TEXT | | Country name |
| latitude | REAL | | Latitude coordinate |
| longitude | REAL | | Longitude coordinate |

#### Table: `tees`
Tee box data for each course (1:many relationship).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Tee record ID |
| course_id | INTEGER | NOT NULL, FOREIGN KEY → courses(id) | Course reference |
| gender | TEXT | NOT NULL CHECK(gender IN ('male', 'female')) | Gender category |
| tee_name | TEXT | NOT NULL | Name of tee box |
| course_rating | REAL | | Course rating |
| slope_rating | INTEGER | | Slope rating |
| bogey_rating | REAL | | Bogey rating |
| total_yards | INTEGER | | Total yardage |
| total_meters | INTEGER | | Total meters |
| number_of_holes | INTEGER | | Number of holes |
| par_total | INTEGER | | Total par |
| front_course_rating | REAL | | Front 9 course rating |
| front_slope_rating | INTEGER | | Front 9 slope rating |
| front_bogey_rating | REAL | | Front 9 bogey rating |
| back_course_rating | REAL | | Back 9 course rating |
| back_slope_rating | INTEGER | | Back 9 slope rating |
| back_bogey_rating | REAL | | Back 9 bogey rating |

#### Table: `holes`
Individual hole data for each tee (1:many relationship).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Hole record ID |
| tee_id | INTEGER | NOT NULL, FOREIGN KEY → tees(id) | Tee reference |
| hole_number | INTEGER | NOT NULL CHECK(hole_number BETWEEN 1 AND 18) | Hole number (1-18) |
| par | INTEGER | NOT NULL | Par for the hole |
| yardage | INTEGER | NOT NULL | Yardage for the hole |
| handicap | INTEGER | NOT NULL | Handicap rating |

**Indexes:**
- `idx_locations_course_id` on `locations(course_id)`
- `idx_tees_course_id` on `tees(course_id)`
- `idx_holes_tee_id` on `holes(tee_id)`

## Program Behavior

### Scraping Logic

1. **Initialization**
   - Load API key from `.env` file
   - Connect to SQLite database
   - Create tables if they don't exist
   - Initialize `scrape_metadata` table if empty

2. **Resume from Last Position**
   - Query `scrape_metadata` to get `last_scraped_id`
   - Check if `scraping_complete = 1`, if so, log and exit gracefully
   - Start scraping from `last_scraped_id + 1`

3. **Rate Limiting**
   - Maximum 295 API calls per day (buffer of 5 from 300 limit)
   - Track daily call count in `scrape_metadata.daily_api_calls`
   - Reset counter at midnight UTC (check `last_api_call_date`)
   - If daily limit reached, sleep until next day and continue

4. **Scraping Loop**
   - For each ID starting from resume position:
     - Check if daily API limit reached, if so sleep until reset
     - Make GET request to `/v1/courses/{id}`
     - Update `daily_api_calls` and `last_api_call_date`
     - Handle response:
       - **200 OK**: Parse and save to database, reset `consecutive_404s` to 0
       - **404 Not Found**: Increment `consecutive_404s` counter
       - **401 Unauthorized**: Log error and exit (API key issue)
       - **429 Too Many Requests**: Log warning, sleep 1 hour, retry
       - **Other errors**: Log error, wait 5 minutes, retry same ID
     - Update `last_scraped_id` after each attempt
     - If `consecutive_404s >= 20`: Set `scraping_complete = 1`, log completion, exit
     - Add small delay between requests (1-2 seconds) to be respectful

5. **Data Storage**
   - Use database transactions for each course
   - Insert course data into `courses` table
   - Insert location data into `locations` table
   - Insert all tees into `tees` table
   - Insert all holes into `holes` table
   - Update `scrape_metadata` with latest stats
   - Commit transaction

### Logging Requirements

Log the following events with timestamps:

- **INFO**: Program startup
- **INFO**: Resuming from ID {id}
- **INFO**: Successfully scraped course {id}: {club_name} - {course_name}
- **INFO**: Saved course {id} to database
- **INFO**: Daily API limit reached ({count}/295), sleeping until {next_reset_time}
- **WARNING**: Received 404 for course ID {id} (consecutive 404s: {count}/20)
- **INFO**: Reached 20 consecutive 404s, scraping complete
- **INFO**: Total courses scraped: {count}
- **ERROR**: Authentication failed, check API key
- **ERROR**: API error {status_code} for course ID {id}: {error_message}
- **INFO**: Waiting {seconds} seconds before retry

### Error Handling

- Catch network errors and retry after delay
- Handle malformed JSON responses
- Validate data before inserting to database
- Use try/except blocks around database operations
- Graceful shutdown on SIGTERM/SIGINT

## Docker Configuration

### Requirements
- Python 3.11+ base image
- Install dependencies from `requirements.txt`
- Mount volume for SQLite database persistence
- Environment variables from `.env` file

### Docker Compose Structure
```yaml
services:
  scraper:
    build: .
    volumes:
      - ./data:/app/data  # SQLite database location
    env_file:
      - .env
    restart: unless-stopped
```

### File Structure
```
golfcourseapi-scraper/
├── .env                    # API key
├── .gitignore
├── requirements.md         # This file
├── requirements.txt        # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── src/
│   ├── __init__.py
│   ├── main.py            # Entry point
│   ├── scraper.py         # Scraping logic
│   ├── database.py        # Database operations
│   └── config.py          # Configuration management
└── data/
    └── golf_courses.db    # SQLite database (created at runtime)
```

## Python Dependencies (requirements.txt)

```
requests>=2.31.0
python-dotenv>=1.0.0
```

## Success Criteria

- Program successfully scrapes all available courses
- No data loss between restarts
- Respects API rate limits (never exceeds 295 calls/day)
- All course data properly normalized across tables
- Comprehensive logging for monitoring
- Can run indefinitely in Docker container
- Handles network failures and API errors gracefully

## Future Enhancements (Out of Scope for v1)

- Web UI to browse scraped courses
- Periodic re-scraping to detect updated course data
- Export functionality (CSV, JSON)
- Search and filter capabilities
- API endpoint to query local database
