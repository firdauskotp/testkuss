"""
Configuration classes for the KUSS Flask application.
This module provides configuration classes for different environments:
- Development
- Testing  
- Production
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Base configuration class with common settings."""
    
    # Core Flask Settings
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required")
    
    # Database Configuration
    MONGO_URL = os.getenv('MONGO_URL')
    if not MONGO_URL:
        raise ValueError("MONGO_URL environment variable is required")
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # File Upload Configuration
    UPLOAD_FOLDER = "static/uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Email Configuration (Base)
    MAIL_SERVER = os.getenv('SMTP_GOOGLE_SERVER', 'smtp.gmail.com')
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.getenv('SMTP_TEST_USERNAME')
    MAIL_PASSWORD = os.getenv('SMTP_TEST_APP_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_SENDER_ADDRESS', '').strip("'\"")
    MAIL_SENDER_ADDRESS = os.getenv('MAIL_SENDER_ADDRESS', '').strip("'\"")  # Add explicit mapping
    ADMIN_EMAIL_ADDRESS = os.getenv('ADMIN_EMAIL_ADDRESS', '').strip("'\"")  # Add admin email mapping
    MAIL_ASCII_ATTACHMENTS = False
    
    # Application Mode
    MODE = os.getenv('MODE', 'development')
    
    # Security Headers (Base)
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
    }
    
    # Rate Limiting (Base)
    RATELIMIT_STORAGE_URL = "memory://"
    
    @classmethod
    def validate_email_config(cls):
        """Validate email configuration and return missing variables."""
        email_vars = ['SMTP_GOOGLE_SERVER', 'SMTP_TEST_USERNAME', 'SMTP_TEST_APP_PASSWORD', 'MAIL_SENDER_ADDRESS']
        missing_vars = [var for var in email_vars if not os.getenv(var)]
        return missing_vars
    
    @classmethod
    def get_missing_email_vars(cls):
        """Get list of missing email configuration variables."""
        return cls.validate_email_config()


class DevelopmentConfig(Config):
    """Configuration for development environment."""
    
    DEBUG = True
    TESTING = False
    
    # Session Security (Relaxed for development)
    SESSION_COOKIE_SECURE = False
    
    # Email Configuration
    MAIL_SUPPRESS_SEND = False  # Allow sending emails in development
    
    # Rate Limiting (Lenient for development)
    RATELIMIT_DEFAULT = ["1000 per day", "500 per hour", "50 per minute"]
    
    # Security Headers (Relaxed CSP for development)
    SECURITY_HEADERS = {
        **Config.SECURITY_HEADERS,
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:;"  # Allow WebSocket for development
        )
    }
    
    # Logging Configuration
    LOG_LEVEL = 'DEBUG'
    LOG_FILE = 'backend/logs/development.log'


class TestingConfig(Config):
    """Configuration for testing environment."""
    
    DEBUG = False
    TESTING = True
    
    # Session Security
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    
    # Email Configuration (Suppress emails in testing)
    MAIL_SUPPRESS_SEND = True
    
    # Rate Limiting (Very lenient for testing)
    RATELIMIT_DEFAULT = ["10000 per day", "5000 per hour", "500 per minute"]
    
    # Database (Could use test database)
    MONGO_URL = os.getenv('MONGO_TEST_URL', Config.MONGO_URL)
    
    # Security Headers (Minimal for testing)
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
    }
    
    # Logging Configuration
    LOG_LEVEL = 'WARNING'
    LOG_FILE = 'backend/logs/testing.log'


class ProductionConfig(Config):
    """Configuration for production environment."""
    
    DEBUG = False
    TESTING = False
    
    # Session Security (Strict for production)
    SESSION_COOKIE_SECURE = True  # HTTPS only
    
    # Email Configuration
    MAIL_SUPPRESS_SEND = False
    
    # Rate Limiting (Strict for production)
    RATELIMIT_DEFAULT = ["200 per day", "100 per hour", "20 per minute"]
    
    # Security Headers (Strict for production)
    SECURITY_HEADERS = {
        **Config.SECURITY_HEADERS,
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )
    }
    
    # Additional Production Security
    PREFERRED_URL_SCHEME = 'https'
    
    # Logging Configuration
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'backend/logs/production.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 10


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """
    Get configuration class based on environment.
    
    Args:
        config_name (str): Configuration name ('development', 'testing', 'production')
                          If None, uses MODE environment variable
    
    Returns:
        Config class: The appropriate configuration class
    """
    if config_name is None:
        config_name = os.getenv('MODE', 'development').lower()
    
    return config.get(config_name, DevelopmentConfig)


# Environment validation
def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = ['SECRET_KEY', 'MONGO_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    # Check email configuration
    config_class = get_config()
    missing_email_vars = config_class.get_missing_email_vars()
    
    if missing_email_vars:
        print(f"Warning: Missing email configuration variables: {missing_email_vars}")
        print("Email functionality may not work properly")
    
    return True


if __name__ == "__main__":
    # Quick test/validation when run directly
    try:
        validate_environment()
        current_config = get_config()
        print(f"✅ Configuration loaded successfully: {current_config.__name__}")
        print(f"✅ Mode: {os.getenv('MODE', 'development')}")
        print(f"✅ Debug: {current_config.DEBUG}")
        print(f"✅ Mail Server: {current_config.MAIL_SERVER}")
        print(f"✅ Rate Limits: {current_config.RATELIMIT_DEFAULT}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
