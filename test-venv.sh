#!/bin/bash

# Test Virtual Environment Setup Script
# Usage: ./test-venv.sh

echo "Testing virtual environment setup..."

# Check if venv directory exists
if [ -d "venv" ]; then
    echo "✅ Virtual environment directory exists"
    
    # Try to activate
    source venv/bin/activate
    
    if [ "$VIRTUAL_ENV" != "" ]; then
        echo "✅ Virtual environment activated successfully"
        echo "   Virtual environment path: $VIRTUAL_ENV"
        echo "   Python version: $(python --version)"
        echo "   Pip version: $(pip --version)"
        
        # Check if flask is installed
        if pip show flask > /dev/null 2>&1; then
            echo "✅ Flask is installed in virtual environment"
        else
            echo "❌ Flask is not installed in virtual environment"
        fi
        
        deactivate
        echo "✅ Virtual environment deactivated"
    else
        echo "❌ Failed to activate virtual environment"
        exit 1
    fi
else
    echo "❌ Virtual environment directory does not exist"
    echo "Run ./deploy-simple.sh or ./deploy.sh setup first"
    exit 1
fi

echo "Virtual environment test completed successfully!"
