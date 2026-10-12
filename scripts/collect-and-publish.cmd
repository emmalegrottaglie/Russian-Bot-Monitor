@echo off
rem Collect once, then publish the static site to GitHub Pages.
rem Windows Task Scheduler runs this every 30 minutes (see docs/HOSTING.md, phase 1).
cd /d "%~dp0.."
if not exist data mkdir data
".venv\Scripts\python.exe" -m tracker publish --collect >> data\publish.log 2>&1
