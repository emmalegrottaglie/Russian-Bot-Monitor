@echo off
rem Load Reddit history from the Arctic Shift archive, skipping series already loaded.
rem Takes many hours; safe to stop and run again. Output goes to data\backfill.log.
cd /d "%~dp0.."
if not exist data mkdir data
echo Reddit backfill running. Progress: data\backfill.log
".venv\Scripts\python.exe" -m tracker backfill --days 50 --platform reddit --missing-only >> data\backfill.log 2>&1
echo Backfill finished with exit code %ERRORLEVEL%.
