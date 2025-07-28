import logging
import requests
import json
import os
from flask import current_app

class TelegramHandler(logging.Handler):
    """
    A custom logging handler that sends log messages to a Telegram chat.
    """
    
    def __init__(self, bot_token=None, chat_id=None):
        """
        Initialize the Telegram handler.
        
        Args:
            bot_token (str): Telegram bot token
            chat_id (str): Telegram chat ID where messages will be sent
        """
        super().__init__()
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")
        if not self.chat_id:
            raise ValueError("Telegram chat ID is required")
            
        self.telegram_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
    
    def emit(self, record):
        """
        Emit a log record by sending it to Telegram.
        
        Args:
            record (logging.LogRecord): The log record to emit
        """
        try:
            # Only send ERROR and CRITICAL level messages
            if record.levelno < logging.ERROR:
                return
                
            # Ensure the record has all necessary attributes
            if not hasattr(record, 'asctime'):
                record.asctime = getattr(record, 'created', 'N/A')
            if not hasattr(record, 'name'):
                record.name = 'Unknown'
            if not hasattr(record, 'pathname'):
                record.pathname = 'Unknown'
            if not hasattr(record, 'lineno'):
                record.lineno = 'N/A'
            if not hasattr(record, 'funcName'):
                record.funcName = 'Unknown'
            if not hasattr(record, 'message'):
                record.message = record.getMessage()
            if not hasattr(record, 'levelname'):
                record.levelname = 'ERROR'
            if not hasattr(record, 'exc_text'):
                record.exc_text = 'No traceback available'
                
            # Create a more detailed message for Telegram
            telegram_message = f"""
🚨 *ERROR ALERT* 🚨

*Level:* {record.levelname}
*Time:* {record.asctime}
*Logger:* {record.name}
*Message:* {record.message}

*Path:* {record.pathname}:{record.lineno}
*Function:* {record.funcName}

```
{record.exc_text if record.exc_info else 'No traceback available'}
```
            """
            
            # Send message to Telegram
            payload = {
                'chat_id': self.chat_id,
                'text': telegram_message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(self.telegram_url, data=payload, timeout=10)
            
            # Log if Telegram message sending failed
            if response.status_code != 200:
                # Use print instead of logger to avoid recursion
                print(
                    f"WARNING: Failed to send message to Telegram. Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                
        except Exception as e:
            # Don't let logging errors break the application
            # Use print instead of logger to avoid recursion
            print(f"ERROR: Failed to send log to Telegram: {e}")

# Convenience function to add Telegram handler to app logger
def add_telegram_handler(app, bot_token=None, chat_id=None):
    """
    Add Telegram logging handler to the Flask app logger.
    
    Args:
        app (Flask): Flask application instance
        bot_token (str): Telegram bot token (optional, will use env var if not provided)
        chat_id (str): Telegram chat ID (optional, will use env var if not provided)
    """
    try:
        # Create Telegram handler
        telegram_handler = TelegramHandler(bot_token=bot_token, chat_id=chat_id)
        
        # Set level to ERROR to only send error messages
        telegram_handler.setLevel(logging.ERROR)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        telegram_handler.setFormatter(formatter)
        
        # Add handler to app logger
        app.logger.addHandler(telegram_handler)
        
        app.logger.info("Telegram logging handler added successfully")
        
    except Exception as e:
        app.logger.warning(f"Failed to add Telegram logging handler: {e}")
