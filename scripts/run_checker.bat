@echo off
rem Run the checker once from anywhere, e.g. double-click or: scripts\run_checker.bat --dry-run
cd /d "%~dp0\.."
"venv\Scripts\python.exe" -m ycfc_tickets %*
