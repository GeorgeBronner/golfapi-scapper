# Getting Started - Production Server Setup

This guide will walk you through setting up and running the Golf Course API scraper on your production server.

## Prerequisites

- Docker and Docker Compose installed
- `uv` installed (Python package manager)
- Git installed
- Access to the production server

## Step-by-Step Setup

### 1. Clone the Repository

```bash
cd /path/to/your/projects
git clone https://github.com/GeorgeBronner/golfapi-scapper.git
cd golfapi-scapper
```

### 2. Create .env File

Copy the example environment file and edit it with your API credentials:

```bash
# Copy the example
cp .env.example .env

# Edit with your API key
nano .env  # or use vim, vi, etc.
```

Your `.env` file should look like this:

```env
GOLFCOURSEAPI_API_KEY=your_actual_api_key_here

# API Configuration
API_BASE_URL=https://api.golfcourseapi.com

# Rate limiting - maximum API calls per 24-hour rolling window
MAX_CALLS_PER_DAY=295

# Scraping behavior - stop after this many consecutive 404s
CONSECUTIVE_404_LIMIT=5000
```

**Important:** Replace `your_actual_api_key_here` with your real API key.

### 3. Set Starting Course ID

The scraper uses sequential ID scraping. Set where you want it to start:

```bash
# This creates the database and sets it to start from ID 4600
uv run python update_start_id.py 4600
```

You should see output like:

```
Updated scrape_metadata:
  last_scraped_id: 4599
  consecutive_404s: 0
  total_courses_scraped: 0

Scraper will resume from ID: 4600
```

**Note:** The scraper will begin with ID 4600 (last_scraped_id + 1).

### 4. Start the Scraper with Docker

Build and start the scraper in detached mode:

```bash
docker-compose up -d --build
```

The scraper is now running in the background!

### 5. Monitor the Logs

Watch the scraper in real-time:

```bash
# Follow the logs continuously
docker-compose logs -f scraper

# Or check the last 50 log lines
docker-compose logs --tail=50 scraper
```

Press `Ctrl+C` to stop following logs (scraper keeps running).

### 6. Check Progress

View database statistics at any time:

```bash
uv run python check_data.py
```

This shows:
- Last scraped course ID
- Total courses in database
- Number of locations, tees, and holes
- Success/failure statistics

## Common Operations

### Stop the Scraper

```bash
docker-compose down
```

### Restart the Scraper

```bash
docker-compose restart
```

### View Container Status

```bash
docker-compose ps
```

### Update Starting ID (After Stopping)

If you need to change where the scraper resumes from:

```bash
# Stop scraper first
docker-compose down

# Update to new starting ID
uv run python update_start_id.py 10000

# Start again
docker-compose up -d
```

### Rebuild After Code Changes

If you pull updates from the repository:

```bash
docker-compose down
docker-compose up -d --build
```

### View Database Contents

Connect to the SQLite database directly:

```bash
sqlite3 data/golf_courses.db
```

Example queries:

```sql
-- View recent courses
SELECT id, club_name, course_name FROM courses ORDER BY id DESC LIMIT 10;

-- Count total courses
SELECT COUNT(*) FROM courses;

-- Check scraping progress
SELECT * FROM scrape_metadata;

-- Exit sqlite
.quit
```

## Monitoring and Maintenance

### Daily Monitoring

The scraper will:
- Automatically resume from the last position if restarted
- Respect the rate limit (295 calls per 24 hours by default)
- Stop after 5000 consecutive 404 responses
- Log all operations to stdout (visible via `docker-compose logs`)

### Disk Space

The SQLite database will grow as courses are added. Monitor disk space:

```bash
# Check database size
du -h data/golf_courses.db

# Check available disk space
df -h
```

### Backup the Database

It's recommended to periodically backup the database:

```bash
# Create a backup
cp data/golf_courses.db data/golf_courses_backup_$(date +%Y%m%d).db

# Or compress it
tar -czf golf_courses_backup_$(date +%Y%m%d).tar.gz data/golf_courses.db
```

## Troubleshooting

### "Authentication failed" Error

Check your API key in `.env`:

```bash
cat .env | grep GOLFCOURSEAPI_API_KEY
```

### Scraper Not Starting

Check container status and logs:

```bash
docker-compose ps
docker-compose logs scraper
```

### Database Locked

Only one instance should run at a time. Check for multiple containers:

```bash
docker ps | grep golf
```

### Rate Limit Issues

Check the current rate limit status:

```bash
uv run python check_data.py
```

Look at the "Scrape Attempts" section. If you're hitting the limit, the scraper will automatically wait.

### Starting Over

To completely reset and start fresh:

```bash
# Stop the scraper
docker-compose down

# Remove the database
rm data/golf_courses.db

# Set new starting ID
uv run python update_start_id.py 1

# Start scraper
docker-compose up -d
```

## Expected Behavior

- **Scraping Speed:** ~2 courses per minute (1.5 second delay between requests)
- **Daily Limit:** 295 courses per day (with current rate limit)
- **Automatic Resume:** If stopped, scraper picks up where it left off
- **Completion:** Stops automatically after 5000 consecutive 404 responses

## Getting Help

For issues or questions:
1. Check the logs: `docker-compose logs -f scraper`
2. Review the README.md for detailed documentation
3. Check the requirements.md for technical specifications
4. Open an issue on the GitHub repository
