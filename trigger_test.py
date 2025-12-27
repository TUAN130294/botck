"""
Simple script to trigger a test trading opportunity
"""

import requests
import json
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 70)
print("TRIGGERING TEST OPPORTUNITY")
print("=" * 70)
print()

# Trigger test opportunity for ACB
url = "http://localhost:8001/api/test/opportunity?symbol=ACB"

print(f"Sending POST request to: {url}")
print()

try:
    response = requests.post(url)

    if response.status_code == 200:
        data = response.json()
        print("SUCCESS! Test opportunity triggered!")
        print()
        print(f"   Symbol: {data.get('symbol')}")
        print(f"   Expected Return: {data.get('expected_return')}")
        print(f"   Confidence: {data.get('confidence')}")
        print()
        print("Check the dashboard to see:")
        print("   1. Agent conversations starting")
        print("   2. Chief making decision")
        print("   3. Order being placed")
        print("   4. Position being opened")
        print()
        print("Dashboard: http://localhost:8001/autonomous")
    else:
        print(f"ERROR: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"ERROR: {e}")
    print()
    print("Make sure the server is running:")
    print("   python run_autonomous_paper_trading.py")

print()
print("=" * 70)
