@echo off
rem Reload the last 7 days of Reddit (from the Arctic Shift archive, which runs about
rem 2 days behind) and Bluesky (hour by hour). Exact hourly counts replace the live
rem estimates taken in the same hours. Windows Task Scheduler runs this once a day
rem (see docs/HOSTING.md, phase 1). Output goes to data\catch-up.log.
cd /d "%~dp0.."
if not exist data mkdir data
".venv\Scripts\python.exe" -m tracker backfill --days 7 --platform reddit --platform bluesky >> data\catch-up.log 2>&1
