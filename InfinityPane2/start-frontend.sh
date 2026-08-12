#!/bin/bash
# Start InfinityPane Frontend

cd "$(dirname "$0")/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    npm install
fi

echo "🚀 Starting React Frontend on http://localhost:3000"
npm start
