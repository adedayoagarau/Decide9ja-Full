#!/usr/bin/env python3
"""
Download 2026 State Budgets from OpenStates.ng
Using discovered API endpoint: /api/{state}/dataset/drill
"""
import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Configuration
YEAR = "2026"
BASE_URL = "https://openstates.ng"
S3_BASE_URL = "https://s3.eu-west-2.amazonaws.com/openstates.ng.storage/"
OUTPUT_DIR = "/Volumes/Crucial X10/Decide9ja/data/raw_pdfs/2026"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# List of states (normalized for URL)
STATES = [
    "abia", "adamawa", "akwa-ibom", "anambra", "bauchi", "bayelsa", "benue", "borno", 
    "cross-river", "delta", "ebonyi", "edo", "ekiti", "enugu", "gombe", "imo", 
    "jigawa", "kaduna", "kano", "katsina", "kebbi", "kogi", "kwara", "lagos", 
    "nasarawa", "niger", "ogun", "ondo", "osun", "oyo", "plateau", "rivers", 
    "sokoto", "taraba", "yobe", "zamfara"
]

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def download_file(url, filepath):
    try:
        if os.path.exists(filepath):
            print(f"  ⏭️  Skipping {os.path.basename(filepath)} (already exists)")
            return True

        print(f"  ⬇️  Downloading to {os.path.basename(filepath)}...")
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"  ✅ Saved {os.path.basename(filepath)}")
        return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return False

def process_state(state):
    print(f"\n🔍 Checking {state.title()} (via API)...")
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    
    # Use the discovered API endpoint
    # Note: search_term=Approved%20Budget matches the user's successful browser search
    api_url = f"{BASE_URL}/api/{state}/dataset/drill?page=1&locale=en&search_term=Approved%20Budget"
    
    try:
        resp = requests.get(api_url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  ⚠️  API Error {resp.status_code} for {state}")
            return
        
        try:
            data = resp.json()
        except ValueError:
            print(f"  ⚠️  Invalid JSON response for {state}")
            return

        # Navigate JSON structure: dataset -> data -> list
        datasets = data.get('dataset', {}).get('data', [])
        
        found_2026 = False
        for ds in datasets:
            title = ds.get('title', '').lower()
            year = str(ds.get('year', ''))
            
            # Check for 2026 and Budget
            if "2026" in title or year == "2026":
                # Found a candidate!
                # Check files
                files = ds.get('files', [])
                for file_info in files:
                    file_url = file_info.get('url')
                    if not file_url:
                        continue
                        
                    # Construct full URL
                    # API returns distinct paths sometimes, but usually relative to S3 root
                    if file_url.startswith("http"):
                        download_url = file_url
                    else:
                        # Clean leading slash if present
                        clean_path = file_url.lstrip('/')
                        download_url = f"{S3_BASE_URL}{clean_path}"
                    
                    filename = f"{state}_2026_budget.pdf"
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    
                    print(f"  🎯 Found 2026 Budget: {ds.get('title')}")
                    if download_file(download_url, filepath):
                        found_2026 = True
                        break # Stop checking files for this dataset
                
                if found_2026:
                    break # Stop checking datasets for this state

        if not found_2026:
            print(f"  ❌ No 2026 Budget found for {state}")

    except Exception as e:
        print(f"  ❌ Error processing {state}: {e}")

def main():
    ensure_dir(OUTPUT_DIR)
    print(f"🚀 Starting OpenStates.ng API Crawl for Year {YEAR}")
    print(f"📂 Output Directory: {OUTPUT_DIR}")
    
    # Use threads
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_state, STATES)
    
    print("\n✨ Download process complete.")

if __name__ == "__main__":
    main()
