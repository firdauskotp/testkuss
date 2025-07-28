#!/usr/bin/env python3
"""
HTTP test for the login functionality
"""
import requests
import sys
from bs4 import BeautifulSoup

def test_http_login():
    base_url = "http://127.0.0.1:5001"
    session = requests.Session()
    
    print("🌐 HTTP Login Test")
    print("=" * 30)
    
    # First get the login page to extract CSRF token
    print("1. Getting login page and CSRF token...")
    response = session.get(f"{base_url}/")
    if response.status_code != 200:
        print(f"   ❌ Failed to get login page: {response.status_code}")
        return False
    
    # Parse the HTML to extract CSRF token
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_token = None
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    if csrf_input:
        csrf_token = csrf_input.get('value')
        print(f"   ✅ CSRF token found: {csrf_token[:20]}...")
    else:
        print("   ❌ CSRF token not found in form")
        return False
    
    # Test login with CSRF token
    print("\n2. Attempting login with CSRF token...")
    login_data = {
        'login_input': 'ahmed',
        'password': 'IQZEIY1KFn3j',
        'csrf_token': csrf_token
    }
    
    response = session.post(f"{base_url}/", data=login_data, allow_redirects=False)
    print(f"   Status: {response.status_code}")
    print(f"   Location: {response.headers.get('Location', 'None')}")
    
    # Check cookies
    print(f"   Cookies: {dict(session.cookies)}")
    
    if response.status_code == 302 and response.headers.get('Location') == '/dashboard':
        print("   ✅ Login successful - redirected to dashboard")
    else:
        print("   ❌ Login failed or unexpected redirect")
    
    # Test dashboard access
    print("\n3. Testing dashboard access...")
    response = session.get(f"{base_url}/dashboard", allow_redirects=False)
    print(f"   Status: {response.status_code}")
    print(f"   Location: {response.headers.get('Location', 'None')}")
    
    if response.status_code == 200:
        print("   ✅ Dashboard accessible - LOGIN WORKING!")
        return True
    else:
        print("   ❌ Dashboard not accessible - session issue")
    
    # Test debug endpoint
    print("\n4. Checking debug endpoint...")
    response = session.get(f"{base_url}/debug-auth")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
    return False

if __name__ == "__main__":
    success = test_http_login()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}: Login test {'passed' if success else 'failed'}")
    sys.exit(0 if success else 1)
