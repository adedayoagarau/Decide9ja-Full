#!/usr/bin/env python3
"""
OpenTreasury.gov.ng Daily Payment Crawler
Crawls and downloads daily payment reports from the Federal Treasury Portal.

Data contains: MDA, beneficiary, purpose, and amount for payments >= ₦10M
"""

import os
import re
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
import json

# Disable SSL warnings for the government site
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://opentreasury.gov.ng"
OUTPUT_DIR = Path(__file__).parent.parent / "raw_data" / "opentreasury"

# Year index pages - maps year to article URL
YEAR_PAGES = {
    2018: "/index.php/component/content/article/11-dpr/29-daily-payment-report-2",
    2019: "/index.php/component/content/article/11-dpr/2759-daily-payment-report-fgn-2019",
    2020: "/index.php/component/content/article/11-dpr/3015-2020-daily-payment",
    2021: "/index.php/component/content/article/105-2021/4976-2021-daily-payment-report-fgn",
    2022: "/index.php/component/content/article/117-2022/8107-2022-daily-payment-report-fgn",
    2023: "/index.php/component/content/article/11-dpr/9959-2023-daily-payment-report-fgn",
    2024: "/index.php/component/content/article/157-2024/10532-2024-daily-payment-report-fgn",
    2025: "/index.php/component/content/article/175-y-2025/12396-2025-daily-payment-report-fgn",
}

# Report types available
REPORT_TYPES = {
    "daily_payment": "Daily Payment Reports (payments >= ₦10M)",
    "daily_treasury": "Daily Treasury Statement",
}


def get_session() -> requests.Session:
    """Create a session with proper headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    session.verify = False  # Government SSL cert issues
    return session


def discover_files_from_page(session: requests.Session, year: int) -> List[str]:
    """Scrape the year page to find all downloadable files."""
    if year not in YEAR_PAGES:
        print(f"  No page configured for {year}")
        return []

    url = BASE_URL + YEAR_PAGES[year]
    print(f"  Fetching index page for {year}...")

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()

        # Find all file links (xlsx, xls, csv)
        pattern = r'/images/[^"\']+\.(?:xlsx|xls|csv)'
        files = re.findall(pattern, response.text)

        # Deduplicate while preserving order
        seen = set()
        unique_files = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        print(f"  Found {len(unique_files)} files for {year}")
        return unique_files

    except Exception as e:
        print(f"  Error fetching {year}: {e}")
        return []


def download_file(session: requests.Session, file_path: str, output_dir: Path) -> Optional[Dict]:
    """Download a single file."""
    url = BASE_URL + file_path
    filename = os.path.basename(file_path)

    # Extract year and month from path
    parts = file_path.split('/')
    year = parts[2] if len(parts) > 2 else "unknown"
    month = parts[4] if len(parts) > 4 else "unknown"

    # Create output directory
    dest_dir = output_dir / year / month
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / filename

    # Skip if already downloaded
    if dest_file.exists():
        return {"file": str(dest_file), "status": "skipped", "size": dest_file.stat().st_size}

    try:
        response = session.get(url, timeout=60)
        response.raise_for_status()

        with open(dest_file, 'wb') as f:
            f.write(response.content)

        return {
            "file": str(dest_file),
            "status": "downloaded",
            "size": len(response.content),
            "url": url
        }

    except Exception as e:
        return {"file": file_path, "status": "error", "error": str(e)}


def crawl_year(year: int, output_dir: Path, max_workers: int = 5) -> Dict:
    """Crawl all daily payment files for a given year."""
    print(f"\n{'='*60}")
    print(f"CRAWLING YEAR: {year}")
    print(f"{'='*60}")

    session = get_session()
    files = discover_files_from_page(session, year)

    if not files:
        return {
            "year": year, 
            "files": 0, 
            "downloaded": 0, 
            "skipped": 0, 
            "errors": 0, 
            "details": []
        }

    results = {"year": year, "files": len(files), "downloaded": 0, "skipped": 0, "errors": 0, "details": []}

    print(f"  Downloading {len(files)} files...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_file, session, f, output_dir): f for f in files}

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            results["details"].append(result)

            if result["status"] == "downloaded":
                results["downloaded"] += 1
            elif result["status"] == "skipped":
                results["skipped"] += 1
            else:
                results["errors"] += 1

            if (i + 1) % 20 == 0:
                print(f"    Progress: {i+1}/{len(files)}")

    print(f"  Year {year}: {results['downloaded']} downloaded, {results['skipped']} skipped, {results['errors']} errors")

    return results


def crawl_all(years: List[int] = None, output_dir: Path = None) -> Dict:
    """Crawl all years or specified years."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    if years is None:
        years = list(YEAR_PAGES.keys())

    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("OPEN TREASURY DAILY PAYMENT CRAWLER")
    print("="*60)
    print(f"Output directory: {output_dir}")
    print(f"Years to crawl: {years}")

    all_results = {
        "started_at": datetime.now().isoformat(),
        "output_dir": str(output_dir),
        "years": {}
    }

    for year in sorted(years):
        results = crawl_year(year, output_dir)
        all_results["years"][year] = results
        time.sleep(1)  # Be nice to the server

    all_results["completed_at"] = datetime.now().isoformat()

    # Summary
    total_files = sum(r["files"] for r in all_results["years"].values())
    total_downloaded = sum(r["downloaded"] for r in all_results["years"].values())
    total_skipped = sum(r["skipped"] for r in all_results["years"].values())
    total_errors = sum(r["errors"] for r in all_results["years"].values())

    print("\n" + "="*60)
    print("CRAWL COMPLETE")
    print("="*60)
    print(f"Total files found: {total_files}")
    print(f"Downloaded: {total_downloaded}")
    print(f"Skipped (already exists): {total_skipped}")
    print(f"Errors: {total_errors}")

    # Save manifest
    manifest_file = output_dir / "crawl_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nManifest saved to: {manifest_file}")

    return all_results


def crawl_recent(days: int = 30, output_dir: Path = None) -> Dict:
    """Crawl only recent files (useful for daily updates)."""
    current_year = datetime.now().year
    return crawl_all(years=[current_year], output_dir=output_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crawl OpenTreasury daily payment reports")
    parser.add_argument("--years", nargs="+", type=int, help="Specific years to crawl")
    parser.add_argument("--output", type=str, help="Output directory")
    parser.add_argument("--recent", action="store_true", help="Only crawl current year")

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else OUTPUT_DIR

    if args.recent:
        crawl_recent(output_dir=output_dir)
    elif args.years:
        crawl_all(years=args.years, output_dir=output_dir)
    else:
        crawl_all(output_dir=output_dir)
