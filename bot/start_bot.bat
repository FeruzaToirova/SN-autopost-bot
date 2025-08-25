@echo off
echo Starting Telegram Auto-posting Bot...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.6+ and try again
    pause
    exit /b 1
)

REM Check if config.py exists
if not exist config.py (
    echo Error: config.py not found!
    echo Please create config.py with your bot token and chat ID
    echo See README.md for setup instructions
    pause
    exit /b 1
)

REM Run the bot
echo Starting bot...
python bot.py

REM Keep window open if bot exits
echo.
echo Bot stopped.
pause

