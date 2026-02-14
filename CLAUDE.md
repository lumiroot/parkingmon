# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gimhae Airport (김해공항) parking lot availability monitor. Collects parking occupancy data on a schedule and displays it via a Flask web dashboard with Chart.js time-series graphs.

## Commands

```bash
uv sync                                  # Install dependencies
uv run python main.py                    # Run collector + web dashboard (default port 5000)
uv run python main.py --web-only         # Web dashboard only (no data collection)
uv run python main.py --collect-once     # Single data collection run, then exit
uv run python main.py --port 8080        # Custom port
```

## Environment Variables

- `PARKING_API_KEY` - Public Data Portal (공공데이터포털) service key. Without it, falls back to web scraping.
- `WEB_PORT` - Web server port (default: 5000)

## Architecture

**Data flow:** `collector.py` → `db.py` (SQLite) → `app.py` (Flask API) → inline HTML/JS dashboard

- **`main.py`** - Entry point. Initializes DB, starts APScheduler (5-min interval), runs Flask server.
- **`collector.py`** - Two collection strategies: public API (`collect_via_api`) or HTML scraping (`collect_via_scraping`). Selection is automatic based on whether `PARKING_API_KEY` is set.
- **`db.py`** - SQLite wrapper. Single table `parking_records` with columns: `collected_at`, `parking_name`, `total_spaces`, `occupied_spaces`, `available_spaces`.
- **`app.py`** - Flask app with inline HTML dashboard template. API endpoints: `/api/records`, `/api/latest`, `/api/parking_names`.
- **`config.py`** - All configuration constants and env var reads.

## Key Details

- Database file: `parking_data.db` (gitignored, created automatically)
- The dashboard auto-refreshes every 60 seconds via JS `setInterval`
- All code comments and UI text are in Korean
- No test suite exists
