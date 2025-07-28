# Deployment Scripts Documentation

This directory contains portable deployment scripts that automatically adapt to different server environments.

## Scripts Overview

### 1. `deploy-simple.sh` - Simple Production Deployment
- **Purpose**: Streamlined deployment for production servers
- **Features**: Auto-detects directory, creates virtual environment, installs dependencies, starts Gunicorn
- **Best for**: Production servers, CI/CD pipelines

### 2. `deploy.sh` - Full-Featured Deployment Manager
- **Purpose**: Complete application lifecycle management
- **Features**: Start/stop/restart/status/logs management with daemon mode
- **Best for**: Development, staging, and managed production environments

### 3. `test-venv.sh` - Virtual Environment Tester
- **Purpose**: Verify virtual environment setup and dependencies
- **Features**: Tests activation, checks Flask installation, validates environment

### 4. `config-env.sh` - Environment Configuration
- **Purpose**: Auto-configure deployment settings based on server environment
- **Features**: OS detection, memory-based worker adjustment, port configuration

## Portability Features

### Automatic Directory Detection
All scripts automatically detect their location and work from there:
```bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

### Environment Variable Support
Scripts use environment variables with sensible defaults:
```bash
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0:5000}"
WORKERS="${WORKERS:-4}"
```

### Cross-Platform Compatibility
- Works on Linux (Ubuntu, CentOS, Amazon Linux, etc.)
- Works on macOS for development
- Automatically adjusts settings based on detected OS

## Usage Examples

### Basic Deployment (Any Server)
```bash
# Copy scripts to your server
scp deploy-simple.sh user@yourserver:/path/to/app/

# Run deployment
./deploy-simple.sh
```

### With Environment Configuration
```bash
# Configure for your environment first
source ./config-env.sh

# Then deploy
./deploy-simple.sh
```

### Custom Configuration
```bash
# Set custom values
export WORKERS=8
export BIND_ADDRESS="0.0.0.0:8080"

# Deploy with custom settings
./deploy-simple.sh
```

### Full Management (Development/Staging)
```bash
# Initial setup
./deploy.sh setup

# Start application
./deploy.sh start

# Check status
./deploy.sh status

# View logs
./deploy.sh logs

# Restart after changes
./deploy.sh restart
```

## Environment-Specific Optimizations

### Low Memory Servers (< 2GB RAM)
- Automatically reduces workers to 1
- Detected by `config-env.sh`

### Non-Root Users
- Automatically uses port 8000 instead of privileged ports
- Prevents permission errors

### macOS Development
- Uses localhost instead of 0.0.0.0
- Reduces worker count for development

## Server Migration Guide

### Moving to a New Server

1. **Copy your application files**:
   ```bash
   rsync -av --exclude='venv/' --exclude='__pycache__/' \
         /old/path/ user@newserver:/new/path/
   ```

2. **Make scripts executable**:
   ```bash
   chmod +x *.sh
   ```

3. **Test environment**:
   ```bash
   ./test-venv.sh
   ```

4. **Deploy**:
   ```bash
   ./deploy-simple.sh
   ```

### No Configuration Changes Needed!
The scripts automatically:
- ✅ Detect the new directory path
- ✅ Create virtual environment in the correct location
- ✅ Adjust settings for the new server's resources
- ✅ Handle different OS environments

## Troubleshooting

### Permission Issues
```bash
# If you get permission errors
chmod +x *.sh
```

### Port Already in Use
```bash
# Use different port
export BIND_ADDRESS="0.0.0.0:8080"
./deploy-simple.sh
```

### Memory Issues
```bash
# Reduce workers manually
export WORKERS=1
./deploy-simple.sh
```

### Check Virtual Environment
```bash
# Test if venv is working
./test-venv.sh
```

## File Structure After Deployment
```
your-app-directory/
├── deploy.sh              # Full deployment manager
├── deploy-simple.sh       # Simple deployment
├── test-venv.sh          # Environment tester
├── config-env.sh         # Environment configuration
├── venv/                 # Virtual environment (auto-created)
├── logs/                 # Application logs (auto-created)
│   ├── gunicorn.log
│   ├── access.log
│   └── error.log
├── static/uploads/       # Upload directory (auto-created)
└── gunicorn.pid         # Process ID file (when running)
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | testkuss | Application name |
| `BIND_ADDRESS` | 0.0.0.0:5000 | IP and port to bind |
| `WORKERS` | 4 | Number of Gunicorn workers |
| `TIMEOUT` | 120 | Request timeout in seconds |

These scripts provide a robust, portable deployment solution that works across different servers without modification!
