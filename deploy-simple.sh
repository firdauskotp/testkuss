#!/bin/bash

# Simple Production Deployment Script
# For use on production servers

# Exit on any error
set -e

# Configuration
APP_NAME="testkuss"
WSGI_MODULE="backend:app"
BIND_ADDRESS="0.0.0.0:5000"
WORKERS=4
TIMEOUT=120
VENV_DIR="venv"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo -e "${GREEN}Starting $APP_NAME deployment...${NC}"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed or not in PATH"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Verify virtual environment is activated
if [ "$VIRTUAL_ENV" != "" ]; then
    print_success "Virtual environment activated: $VIRTUAL_ENV"
else
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Python dependencies installed"

# Install Node dependencies and build CSS
if [ -f "package.json" ]; then
    if command -v npm &> /dev/null; then
        print_status "Installing Node.js dependencies..."
        npm install
        
        print_status "Building CSS..."
        npm run build:css
        print_success "Node.js dependencies installed and CSS built"
    else
        print_error "npm is not installed. Skipping Node.js dependencies."
    fi
else
    print_status "No package.json found. Skipping Node.js dependencies."
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p static/uploads
print_success "Directories created"

# Start Gunicorn server
print_success "Starting Gunicorn server on $BIND_ADDRESS..."
exec gunicorn $WSGI_MODULE \
    --bind $BIND_ADDRESS \
    --workers $WORKERS \
    --timeout $TIMEOUT \
    --log-level info \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --preload \
    --max-requests 1000 \
    --max-requests-jitter 100
