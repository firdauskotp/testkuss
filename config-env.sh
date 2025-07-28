#!/bin/bash

# Environment Configuration Script
# This file can be customized for different server environments
# Usage: Source this file before running deployment scripts
#        source ./config-env.sh && ./deploy-simple.sh

# Detect current environment
if [ -f "/etc/os-release" ]; then
    . /etc/os-release
    OS_NAME=$NAME
else
    OS_NAME=$(uname -s)
fi

echo "Detected OS: $OS_NAME"

# Default configuration (can be overridden)
export APP_NAME="${APP_NAME:-testkuss}"
export BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0:5000}"
export WORKERS="${WORKERS:-4}"
export TIMEOUT="${TIMEOUT:-120}"

# Environment-specific configurations
case "$OS_NAME" in
    *"Ubuntu"*|*"Debian"*)
        echo "Configuring for Ubuntu/Debian environment"
        export WORKERS="${WORKERS:-2}"  # Conservative for smaller VPS
        ;;
    *"CentOS"*|*"Red Hat"*|*"Rocky"*)
        echo "Configuring for CentOS/RHEL environment"
        export WORKERS="${WORKERS:-4}"
        ;;
    *"Amazon Linux"*)
        echo "Configuring for Amazon Linux environment"
        export WORKERS="${WORKERS:-3}"
        ;;
    "Darwin")
        echo "Configuring for macOS development environment"
        export WORKERS="${WORKERS:-2}"
        export BIND_ADDRESS="${BIND_ADDRESS:-127.0.0.1:5000}"
        ;;
    *)
        echo "Using default configuration for unknown environment"
        ;;
esac

# Check available memory and adjust workers if needed
if command -v free >/dev/null 2>&1; then
    MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$MEMORY_GB" -lt 2 ]; then
        echo "Low memory detected (${MEMORY_GB}GB), reducing workers to 1"
        export WORKERS=1
    elif [ "$MEMORY_GB" -lt 4 ]; then
        echo "Limited memory detected (${MEMORY_GB}GB), setting workers to 2"
        export WORKERS=2
    fi
fi

# Port configuration based on common server setups
if [ "$USER" != "root" ] && [ "${BIND_ADDRESS#*:}" -lt 1024 ] 2>/dev/null; then
    echo "Non-root user detected, using port 8000 instead of privileged port"
    export BIND_ADDRESS="${BIND_ADDRESS%:*}:8000"
fi

# Display final configuration
echo ""
echo "=== Environment Configuration ==="
echo "App Name: $APP_NAME"
echo "Bind Address: $BIND_ADDRESS"
echo "Workers: $WORKERS"
echo "Timeout: $TIMEOUT"
echo "User: $USER"
echo "================================="
echo ""

# Export environment variables for use by deployment scripts
export APP_NAME BIND_ADDRESS WORKERS TIMEOUT
