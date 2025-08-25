#!/bin/bash

echo "Starting Telegram Auto-posting Bot..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    echo "Please install Python 3.6+ and try again"
    exit 1
fi

# Use python3 if available, otherwise python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 -a "$PYTHON_MINOR" -lt 6 ]; then
    echo "Error: Python 3.6+ is required. Found version $PYTHON_VERSION"
    exit 1
fi

# Check if config.py exists
if [ ! -f "config.py" ]; then
    echo "Error: config.py not found!"
    echo "Please create config.py with your bot token and chat ID"
    echo "See README.md for setup instructions"
    exit 1
fi

# Run the bot
echo "Starting bot with $PYTHON_CMD..."
$PYTHON_CMD bot.py

echo
echo "Bot stopped."

