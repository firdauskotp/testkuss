#!/usr/bin/env python3
"""
Test script to verify Telegram logging handler functionality
"""
import sys
import os
import logging

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_handler import TelegramHandler
from dotenv import load_dotenv
from flask import Flask

def test_telegram_handler():
    """Test Telegram handler functionality"""
    print("Testing Telegram handler configuration...")
    
    # Load environment variables
    load_dotenv()
    
    # Get Telegram configuration
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    print(bot_token)

    print(f"TELEGRAM_BOT_TOKEN: {'SET' if bot_token and bot_token != 'your_telegram_bot_token_here' else 'NOT SET'}")
    print(f"TELEGRAM_CHAT_ID: {'SET' if chat_id and chat_id != 'your_telegram_chat_id_here' else 'NOT SET'}")
    
    # Check if configuration is complete
    if not bot_token or bot_token == 'your_telegram_bot_token_here':
        print("❌ Telegram bot token is not set!")
        return False
    
    if not chat_id or chat_id == 'your_telegram_chat_id_here':
        print("❌ Telegram chat ID is not set!")
        return False
    
    try:
        # Create a Flask app for context
        app = Flask(__name__)
        
        # Create Telegram handler
        telegram_handler = TelegramHandler(bot_token=bot_token, chat_id=chat_id)
        
        # Create a test logger
        logger = logging.getLogger('test_telegram')
        logger.setLevel(logging.ERROR)
        logger.addHandler(telegram_handler)
        
        # Test sending a message within app context
        print("Attempting to send test message to Telegram...")
        with app.app_context():
            # Create a proper log record with all attributes
            try:
                raise Exception("Test exception for Telegram integration")
            except Exception:
                logger.exception("This is a test error message from the KUSS system to verify Telegram integration.")
        
        print("✅ Telegram handler configured successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to configure Telegram handler: {e}")
        return False

if __name__ == "__main__":
    print("Telegram Handler Test")
    print("=" * 30)
    
    success = test_telegram_handler()
    
    if success:
        print("\n🎉 Telegram handler is configured correctly!")
        print("Note: Check your Telegram chat to confirm the test message was received.")
    else:
        print("\n💥 Telegram handler configuration has issues.")
        print("Please check your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the .env file.")
