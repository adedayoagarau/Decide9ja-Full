#!/usr/bin/env python3
"""
Debug Download OpenStates (Adamawa Only)
"""
import requests
import re

STATE = "adamawa"
BASE_URL = "https://openstates.ng"
SEARCH_URL = f"{BASE_URL}/{STATE}/data?search_term=Approved%20Budget"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

print(f"🔍 Debugging {STATE} at {SEARCH_URL}")
headers = {"User-Agent": USER_AGENT}
resp = requests.get(SEARCH_URL, headers=headers)

if resp.status_code != 200:
    print(f"Failed: {resp.status_code}")
else:
    html = resp.text
    print(f"HTML Length: {len(html)}")
    
    # Print first 20 lines of HTML to see structure
    print("\n--- HTML SNIPPET ---")
    print("\n".join(html.split('\n')[:20]))
    
    # Try to find ANY dataset link
    # Pattern: /adamawa/dataset/
    links = re.findall(r'href="([^"]*/dataset/[^"]*)"', html)
    print(f"\nFound {len(links)} dataset links:")
    for l in links[:5]:
        print(f" - {l}")
        
    # Check for "2026" in the whole HTML
    print(f"\n'2026' count in HTML: {html.count('2026')}")
