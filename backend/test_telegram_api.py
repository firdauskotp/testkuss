#!/usr/bin/env python3
"""
Direct test script to verify Telegram API functionality
"""
import sys
import os
import requests

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

def test_telegram_api():
    """Test Telegram API directly"""
    print("Testing Telegram API directly...")
    
    # Load environment variables
    load_dotenv()
    
    # Get Telegram configuration
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    print(f"TELEGRAM_BOT_TOKEN: {'SET' if bot_token else 'NOT SET'}")
    print(f"TELEGRAM_CHAT_ID: {'SET' if chat_id else 'NOT SET'}")
    
    # Check if configuration is complete
    if not bot_token:
        print("❌ Telegram bot token is not set!")
        return False
    
    if not chat_id:
        print("❌ Telegram chat ID is not set!")
        return False
    
    try:
        # Test Telegram API directly
        telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': '🚨 *TEST MESSAGE* 🚨\n\nThis is a direct test message from the KUSS system to verify Telegram API integration.\n\nIf you receive this message, Telegram integration is working correctly!',
            'parse_mode': 'Markdown'
        }
        
        print("Attempting to send direct test message to Telegram...")
        response = requests.post(telegram_url, data=payload, timeout=10)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Telegram API test successful!")
            return True
        else:
            print(f"❌ Telegram API test failed with status code: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Failed to test Telegram API: {e}")
        return False

if __name__ == "__main__":
    print("Telegram API Test")
    print("=" * 30)
    
    success = test_telegram_api()
    
    if success:
        print("\n🎉 Telegram API is working correctly!")
        print("You should have received a test message in your Telegram chat.")
    else:
        print("\n💥 Telegram API test failed.")
        print("Please check your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the .env file.")
        print("Also ensure your bot has permission to send messages to the specified chat.")
