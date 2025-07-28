#!/usr/bin/env python3
"""
Simple HTTP test without CSRF token
"""
import requests

def test_simple_login():
    base_url = "http://127.0.0.1:5001"
    session = requests.Session()
    
    print("🌐 Simple Login Test (No CSRF)")
    print("=" * 40)
    
    # Test login without CSRF token
    print("1. Attempting login without CSRF token...")
    login_data = {
        'login_input': 'ahmed',
        'password': 'IQZEIY1KFn3j'
    }
    
    response = session.post(f"{base_url}/", data=login_data, allow_redirects=False)
    print(f"   Status: {response.status_code}")
    print(f"   Location: {response.headers.get('Location', 'None')}")
    print(f"   Cookies: {dict(session.cookies)}")
    
    if response.status_code == 302 and response.headers.get('Location') == '/dashboard':
        print("   ✅ Login successful!")
        
        # Test dashboard access
        print("\n2. Testing dashboard access...")
        response = session.get(f"{base_url}/dashboard", allow_redirects=False)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ Dashboard accessible - AUTHENTICATION WORKING!")
            return True
        else:
            print(f"   ❌ Dashboard returned: {response.status_code}")
    else:
        print("   ❌ Login failed")
    
    # Check debug info
    print("\n3. Debug info...")
    response = session.get(f"{base_url}/debug-auth")
    print(f"   {response.text}")
    
    return False

if __name__ == "__main__":
    success = test_simple_login()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
