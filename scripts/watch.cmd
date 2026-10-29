@echo off
rem While collection is paused (tracker/pause.py): refresh the Yandex data, resume
rem collection if Yandex Cloud has recovered, then republish the site. Windows Task
rem Scheduler runs this once a day (see docs/HOSTING.md, phase 1). Output goes to
rem data\watch.log.
cd /d "%~dp0.."
if not exist data mkdir data
".venv\Scripts\python.exe" -m tracker watch >> data\watch.log 2>&1
".venv\Scripts\python.exe" -m tracker publish >> data\watch.log 2>&1
