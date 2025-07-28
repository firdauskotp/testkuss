#!/bin/bash

# Flask Application Deployment Script
# Usage: ./deploy.sh [start|stop|restart|status|logs]

# Configuration
APP_NAME="testkuss"
APP_DIR="/Users/ahmet/Development/mididle/testkuss"
VENV_DIR="$APP_DIR/venv"
WSGI_MODULE="backend:app"
BIND_ADDRESS="0.0.0.0:5000"
WORKERS=4
TIMEOUT=120
PID_FILE="$APP_DIR/gunicorn.pid"
LOG_FILE="$APP_DIR/logs/gunicorn.log"
ERROR_LOG_FILE="$APP_DIR/logs/gunicorn_error.log"
ACCESS_LOG_FILE="$APP_DIR/logs/gunicorn_access.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if virtual environment exists
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        print_status "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    fi
}

# Function to activate virtual environment
activate_venv() {
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        print_status "Virtual environment activated"
    else
        print_error "Cannot activate virtual environment"
        exit 1
    fi
}

# Function to install dependencies
install_deps() {
    print_status "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    print_status "Installing Node.js dependencies..."
    npm install
    
    print_status "Building CSS..."
    npm run build:css
    
    print_success "Dependencies installed and CSS built"
}

# Function to create necessary directories
create_dirs() {
    mkdir -p logs
    mkdir -p static/uploads
    print_status "Created necessary directories"
}

# Function to start the application
start_app() {
    cd "$APP_DIR"
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_warning "Application is already running (PID: $PID)"
            return 1
        else
            print_warning "Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi
    
    check_venv
    activate_venv
    create_dirs
    
    print_status "Starting $APP_NAME with Gunicorn..."
    
    gunicorn $WSGI_MODULE \
        --bind $BIND_ADDRESS \
        --workers $WORKERS \
        --timeout $TIMEOUT \
        --pid $PID_FILE \
        --daemon \
        --log-file $LOG_FILE \
        --error-logfile $ERROR_LOG_FILE \
        --access-logfile $ACCESS_LOG_FILE \
        --log-level info \
        --preload \
        --max-requests 1000 \
        --max-requests-jitter 100
    
    if [ $? -eq 0 ]; then
        sleep 2
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            print_success "$APP_NAME started successfully (PID: $PID)"
            print_status "Application is running on http://$BIND_ADDRESS"
        else
            print_error "Failed to start $APP_NAME"
            return 1
        fi
    else
        print_error "Failed to start $APP_NAME"
        return 1
    fi
}

# Function to stop the application
stop_app() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_status "Stopping $APP_NAME (PID: $PID)..."
            kill $PID
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p $PID > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            
            # Force kill if still running
            if ps -p $PID > /dev/null 2>&1; then
                print_warning "Force killing $APP_NAME..."
                kill -9 $PID
            fi
            
            rm -f "$PID_FILE"
            print_success "$APP_NAME stopped successfully"
        else
            print_warning "$APP_NAME is not running"
            rm -f "$PID_FILE"
        fi
    else
        print_warning "PID file not found. $APP_NAME may not be running"
    fi
}

# Function to restart the application
restart_app() {
    print_status "Restarting $APP_NAME..."
    stop_app
    sleep 2
    start_app
}

# Function to check application status
status_app() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_success "$APP_NAME is running (PID: $PID)"
            
            # Show memory and CPU usage
            PS_OUTPUT=$(ps -p $PID -o pid,ppid,pcpu,pmem,etime,comm --no-headers)
            echo "Process details: $PS_OUTPUT"
            
            # Check if port is listening
            if netstat -tuln | grep -q ":5000 "; then
                print_success "Application is listening on port 5000"
            else
                print_warning "Port 5000 is not listening"
            fi
        else
            print_error "$APP_NAME is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        print_error "$APP_NAME is not running"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        print_status "Showing last 50 lines of logs..."
        tail -50 "$LOG_FILE"
    else
        print_error "Log file not found"
    fi
}

# Function to setup the application
setup_app() {
    cd "$APP_DIR"
    print_status "Setting up $APP_NAME..."
    
    check_venv
    activate_venv
    install_deps
    create_dirs
    
    print_success "Setup completed successfully"
    print_status "You can now start the application with: ./deploy.sh start"
}

# Main script logic
case "$1" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        status_app
        ;;
    logs)
        show_logs
        ;;
    setup)
        setup_app
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|setup}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the application"
        echo "  stop    - Stop the application"
        echo "  restart - Restart the application"
        echo "  status  - Check application status"
        echo "  logs    - Show application logs"
        echo "  setup   - Initial setup (install deps, create dirs)"
        echo ""
        exit 1
        ;;
esac

exit 0
