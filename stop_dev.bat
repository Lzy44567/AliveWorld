@echo off
echo [AliveWorld] Stopping development windows...
taskkill /FI "WINDOWTITLE eq AW_Backend*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq AW_Frontend*" /T /F >nul 2>nul
echo Done.
