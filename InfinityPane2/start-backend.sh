#!/bin/bash
# Start InfinityPane Backend

cd "$(dirname "$0")/backend"

# Create venv if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt --quiet

echo "🚀 Starting Flask Backend on http://localhost:5000"
python app.py
