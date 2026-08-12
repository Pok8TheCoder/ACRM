#!/bin/bash

# InfinityPane - Development Startup Script

echo "🚀 Starting InfinityPane Development Environment..."
echo ""

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    echo "❌ Error: Please run this script from the InfinityPane2 root directory"
    exit 1
fi

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python
if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Check Node.js
if ! command_exists node; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js found: $(node --version)${NC}"

# Check npm
if ! command_exists npm; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ npm found: $(npm --version)${NC}"

echo ""

# Setup Backend
echo -e "${BLUE}📦 Setting up Backend...${NC}"
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo -e "${GREEN}✓ Backend ready${NC}"

cd ..

# Setup Frontend
echo -e "${BLUE}📦 Setting up Frontend...${NC}"
cd frontend

# Install npm dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo -e "${GREEN}✓ Frontend ready${NC}"

cd ..

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "To start the application:"
echo ""
echo "  1. Start Backend (Terminal 1):"
echo -e "     ${YELLOW}cd backend && source venv/bin/activate && python app.py${NC}"
echo ""
echo "  2. Start Frontend (Terminal 2):"
echo -e "     ${YELLOW}cd frontend && npm start${NC}"
echo ""
echo "  Or use the quick start scripts:"
echo -e "     ${YELLOW}./start-backend.sh${NC}"
echo -e "     ${YELLOW}./start-frontend.sh${NC}"
echo ""
echo -e "${BLUE}🌐 The app will be available at: http://localhost:3000${NC}"
echo ""
