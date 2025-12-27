"""
Direct trade trigger - bypasses agents for instant demo
Shows full system working: Order placement → Position tracking → Dashboard update
"""

import requests
import sys

# Set UTF-8 encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 70)
print("DIRECT TRADE TEST (Bypass Agents)")
print("=" * 70)
print()

# Trigger direct trade
url = "http://localhost:8001/api/test/trade?symbol=ACB&action=BUY"

print(f"Sending POST request to: {url}")
print()

try:
    response = requests.post(url)

    if response.status_code == 200:
        data = response.json()

        if data.get('status') == 'success':
            print("SUCCESS! Trade executed!")
            print()
            print(f"   Action: {data.get('action')}")
            print(f"   Symbol: {data.get('symbol')}")
            print(f"   Quantity: {data.get('quantity'):,}")
            print(f"   Price: {data.get('price'):,.0f} VND")
            print(f"   Total Value: {data.get('value'):,.0f} VND")
            print()
            print("Check the dashboard NOW:")
            print("   1. Order appears in ORDERS HISTORY")
            print("   2. Position appears in POSITIONS panel")
            print("   3. Active Positions count updated")
            print()
            print("Dashboard: http://localhost:8001/autonomous")
        else:
            print(f"ERROR: {data}")
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
