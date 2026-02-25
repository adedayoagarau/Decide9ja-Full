"""
OpenTreasury Daily Pipeline
============================
Crawl + ingest daily Federal Government payment reports from opentreasury.gov.ng.
Downloads XLSX in memory, parses, and inserts directly into the transactions table.

Designed to run as a scheduled job — no local file storage needed.
"""

import re
import io
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

BASE_URL = "https://opentreasury.gov.ng"

# Year index pages
YEAR_PAGES = {
    2024: "/index.php/component/content/article/157-2024/10532-2024-daily-payment-report-fgn",
    2025: "/index.php/component/content/article/175-y-2025/12396-2025-daily-payment-report-fgn",
    2026: "/index.php/component/content/article/175-y-2025/12396-2025-daily-payment-report-fgn",  # fallback to 2025 until 2026 page exists
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = False
    return session


def _discover_xlsx_urls(session: requests.Session, year: int) -> List[str]:
    """Find all XLSX download links from the year's index page."""
    page_path = YEAR_PAGES.get(year)
    if not page_path:
        logger.warning(f"No OpenTreasury page configured for {year}")
        return []

    url = BASE_URL + page_path
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        # Find all file links
        pattern = r'/images/[^"\']+\.(?:xlsx|xls)'
        files = re.findall(pattern, resp.text)
        # Deduplicate preserving order
        seen = set()
        unique = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique.append(f)
        logger.info(f"OpenTreasury: Found {len(unique)} files for {year}")
        return unique
    except Exception as e:
        logger.error(f"OpenTreasury: Failed to fetch index for {year}: {e}")
        return []


def _parse_amount(text) -> float:
    try:
        return float(str(text).replace(',', '').replace('₦', '').replace(' ', '').strip())
    except (ValueError, TypeError):
        return 0.0


def _download_and_parse_xlsx(session: requests.Session, file_path: str) -> List[Dict]:
    """Download an XLSX file into memory and parse it into transaction records."""
    url = BASE_URL + file_path
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"OpenTreasury: Failed to download {file_path}: {e}")
        return []

    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if len(rows) < 2:
            return []

        # Find the header row (contains 'AMOUNT' and 'BENEFICIARY')
        header_idx = 0
        for i, row in enumerate(rows):
            row_str = ' '.join(str(c or '').upper() for c in row)
            if 'AMOUNT' in row_str and ('BENEFICIARY' in row_str or 'RECEIVER' in row_str):
                header_idx = i
                break

        headers = [str(c or '').strip().lower() for c in rows[header_idx]]
        data_rows = rows[header_idx + 1:]

        # Build column index mapping
        col_map = {}
        for i, h in enumerate(headers):
            h_clean = h.replace('.', '').strip()
            if 'payment' in h_clean and 'no' in h_clean:
                col_map['payment_no'] = i
            elif h_clean in ('no', 'no.', 's/n', 's/no'):
                col_map.setdefault('payment_no', i)
            elif 'payer' in h_clean or 'organization' in h_clean or 'mda' in h_clean:
                col_map['payer'] = i
            elif 'beneficiary' in h_clean or 'receiver' in h_clean:
                col_map['receiver'] = i
            elif 'amount' in h_clean:
                col_map['amount'] = i
            elif 'date' in h_clean:
                col_map['date'] = i
            elif 'description' in h_clean or 'purpose' in h_clean or 'narration' in h_clean:
                col_map['description'] = i

        # Extract date from filename as fallback (e.g., "25-02-05.xlsx" → "2025-02-05")
        import os
        filename = os.path.basename(file_path)
        fallback_date = None
        date_match = re.match(r'(\d{2})-(\d{2})-(\d{2})', filename)
        if date_match:
            y, m, d = date_match.groups()
            fallback_date = f"20{y}-{m}-{d}"

        records = []
        for row in data_rows:
            if not row or all(c is None for c in row):
                continue

            payer = str(row[col_map['payer']] or 'Federal Government') if 'payer' in col_map else 'Federal Government'
            receiver = str(row[col_map['receiver']] or 'Unknown') if 'receiver' in col_map else 'Unknown'
            amount = _parse_amount(row[col_map['amount']]) if 'amount' in col_map else 0.0
            description = str(row[col_map['description']] or '') if 'description' in col_map else ''

            if amount <= 0:
                continue

            # Date handling
            payment_date = fallback_date or datetime.now().strftime('%Y-%m-%d')
            if 'date' in col_map and row[col_map['date']]:
                raw_date = row[col_map['date']]
                if isinstance(raw_date, datetime):
                    payment_date = raw_date.strftime('%Y-%m-%d')
                else:
                    payment_date = str(raw_date)[:10]

            # Generate unique ID from content hash
            id_str = f"{payment_date}_{payer}_{receiver}_{amount}_{description[:50]}"
            record_id = hashlib.md5(id_str.encode()).hexdigest()[:20]

            records.append({
                "id": record_id,
                "payment_date": payment_date,
                "payer": payer[:200],
                "receiver": receiver[:200],
                "amount": amount,
                "description": description[:2000] if description else f"Payment from {payer} to {receiver}",
                "source_url": url,
                "state": "Federal",
            })

        return records

    except ImportError:
        # openpyxl not installed — try pandas
        try:
            import pandas as pd
            raw_df = pd.read_excel(io.BytesIO(resp.content), header=None)

            # Find header row
            header_idx = 0
            for idx, row in raw_df.iterrows():
                row_str = str(row.values).upper()
                if 'AMOUNT' in row_str and ('BENEFICIARY' in row_str or 'NO' in row_str):
                    header_idx = idx
                    break

            df = pd.read_excel(io.BytesIO(resp.content), header=header_idx)
            df.columns = [str(c).lower().strip() for c in df.columns]

            import os
            filename = os.path.basename(file_path)
            fallback_date = None
            date_match = re.match(r'(\d{2})-(\d{2})-(\d{2})', filename)
            if date_match:
                y, m, d = date_match.groups()
                fallback_date = f"20{y}-{m}-{d}"

            records = []
            for _, row in df.iterrows():
                try:
                    payment_no = row.get('payment no', '') or row.get('payment_no', '') or row.get('no.', '') or row.get('no', '')
                    receiver = str(row.get('beneficiary', '') or row.get('receiver', '') or 'Unknown')
                    payer = str(row.get('payer', '') or row.get('organisation', '') or row.get('mda', '') or 'Federal Government')
                    amount = _parse_amount(row.get('amount', 0))
                    description = str(row.get('description', '') or row.get('purpose', '') or row.get('narration', '') or '')

                    if amount <= 0:
                        continue

                    id_str = f"{fallback_date}_{payer}_{receiver}_{amount}_{description[:50]}"
                    record_id = hashlib.md5(id_str.encode()).hexdigest()[:20]

                    records.append({
                        "id": record_id,
                        "payment_date": fallback_date or datetime.now().strftime('%Y-%m-%d'),
                        "payer": payer[:200],
                        "receiver": receiver[:200],
                        "amount": amount,
                        "description": description[:2000] if description else f"Payment to {receiver}",
                        "source_url": BASE_URL + file_path,
                        "state": "Federal",
                    })
                except Exception:
                    continue

            return records
        except Exception as e:
            logger.error(f"OpenTreasury: pandas parse failed for {file_path}: {e}")
            return []

    except Exception as e:
        logger.error(f"OpenTreasury: Parse failed for {file_path}: {e}")
        return []


def run_opentreasury_pipeline(year: int = None, max_files: int = 50) -> Dict:
    """
    Main pipeline: discover → download → parse → ingest.

    Args:
        year: Year to crawl (default: current year)
        max_files: Max files to process per run (to limit runtime)

    Returns:
        Stats dict with counts
    """
    from app.database import SessionLocal, Transaction
    from sqlalchemy.dialects.postgresql import insert

    if year is None:
        year = datetime.now().year

    logger.info(f"OpenTreasury Pipeline: Starting for {year}")
    session_http = _get_session()

    # Discover all files for the year
    all_file_urls = _discover_xlsx_urls(session_http, year)
    if not all_file_urls:
        logger.warning(f"OpenTreasury Pipeline: No files found for {year}")
        return {"year": year, "files_found": 0, "records_ingested": 0}

    # Check which files we've already ingested (by source_url)
    db = SessionLocal()
    try:
        existing_urls = set()
        for url in all_file_urls:
            full_url = BASE_URL + url
            count = db.query(Transaction).filter(
                Transaction.source_url == full_url
            ).limit(1).count()
            if count > 0:
                existing_urls.add(url)
    finally:
        db.close()

    # Filter to new files only
    new_files = [f for f in all_file_urls if f not in existing_urls]
    logger.info(f"OpenTreasury Pipeline: {len(new_files)} new files (of {len(all_file_urls)} total)")

    if not new_files:
        return {"year": year, "files_found": len(all_file_urls), "new_files": 0, "records_ingested": 0}

    # Process limited batch
    files_to_process = new_files[:max_files]
    total_ingested = 0
    files_processed = 0
    errors = 0

    db = SessionLocal()
    try:
        for file_url in files_to_process:
            records = _download_and_parse_xlsx(session_http, file_url)
            if records:
                try:
                    stmt = insert(Transaction).values(records).on_conflict_do_nothing(index_elements=['id'])
                    result = db.execute(stmt)
                    db.commit()
                    ingested = len(records)
                    total_ingested += ingested
                    files_processed += 1
                    logger.info(f"  Ingested {ingested} records from {file_url.split('/')[-1]}")
                except Exception as e:
                    db.rollback()
                    errors += 1
                    logger.error(f"  DB error for {file_url}: {e}")
            else:
                errors += 1

            # Rate limit
            import time
            time.sleep(1)
    finally:
        db.close()

    stats = {
        "year": year,
        "files_found": len(all_file_urls),
        "new_files": len(new_files),
        "files_processed": files_processed,
        "records_ingested": total_ingested,
        "errors": errors,
    }
    logger.info(f"OpenTreasury Pipeline complete: {stats}")
    return stats
