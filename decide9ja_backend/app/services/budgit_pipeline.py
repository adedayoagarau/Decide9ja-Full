"""
BudgIT State Budget Pipeline
=============================
Scrapes state budget data from openstates.ng (BudgIT's open data platform)
for all 36 Nigerian states + FCT.

Data flows into the Budget table for financial intelligence queries.

Sources:
- https://openstates.ng/{state}/data — state datasets
- BudgIT PDF reports (fallback)

Creative Commons CC BY-ND 3.0 — attribution required.
"""

import os
import re
import json
import time
import logging
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# All 36 states + FCT
NIGERIAN_STATES = [
    'abia', 'adamawa', 'akwa-ibom', 'anambra', 'bauchi', 'bayelsa', 'benue',
    'borno', 'cross-river', 'delta', 'ebonyi', 'edo', 'ekiti', 'enugu', 'gombe',
    'imo', 'jigawa', 'kaduna', 'kano', 'katsina', 'kebbi', 'kogi', 'kwara',
    'lagos', 'nasarawa', 'niger', 'ogun', 'ondo', 'osun', 'oyo', 'plateau',
    'rivers', 'sokoto', 'taraba', 'yobe', 'zamfara'
]

BASE_URL = "https://openstates.ng"

# BudgIT State of States report URLs (PDF fallbacks for aggregate data)
BUDGIT_REPORTS = {
    2025: "https://budgit.org/wp-content/uploads/2025/10/StateofStates2025SEIIWEB.pdf",
    2024: "https://budgit.org/wp-content/uploads/2024/05/Open-Budget-Nigeria-Report-.pdf",
}

HEADERS = {
    'User-Agent': 'Decide9ja-Bot/1.0 (civic-tech; budget-transparency)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def _get_db():
    """Get database session."""
    from app.database import SessionLocal
    return SessionLocal()


def _state_display_name(slug: str) -> str:
    """Convert slug to display name: 'akwa-ibom' → 'Akwa Ibom'"""
    return slug.replace('-', ' ').title()


def _scrape_state_overview(state_slug: str) -> Dict[str, Any]:
    """
    Scrape the overview page for a state from openstates.ng.
    Extracts key fiscal figures: IGR, total revenue, budget size, debt.
    """
    url = f"{BASE_URL}/{state_slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        data = {
            'state': _state_display_name(state_slug),
            'slug': state_slug,
            'url': url,
            'scraped_at': datetime.utcnow().isoformat(),
            'metrics': {},
            'datasets': [],
        }

        # Extract key metric cards (IGR, revenue, budget, debt)
        metric_cards = soup.find_all(['div', 'span', 'p'], class_=re.compile(r'metric|stat|figure|value|amount', re.I))
        for card in metric_cards:
            text = card.get_text(strip=True)
            # Try to extract amounts like ₦123.4B or N123,456,789
            amount_match = re.search(r'[₦N]\s*([\d,.]+)\s*(B|M|T|billion|million|trillion)?', text, re.I)
            if amount_match:
                label_el = card.find_previous(['h3', 'h4', 'label', 'span'])
                label = label_el.get_text(strip=True) if label_el else 'unknown'
                data['metrics'][label] = text

        # Extract dataset links
        data_links = soup.find_all('a', href=re.compile(r'/data|/dataset|download', re.I))
        for link in data_links:
            href = link.get('href', '')
            if not href.startswith('http'):
                href = BASE_URL + href
            data['datasets'].append({
                'title': link.get_text(strip=True),
                'url': href,
            })

        return data

    except Exception as e:
        logger.warning(f"Failed to scrape {state_slug}: {e}")
        return {'state': _state_display_name(state_slug), 'slug': state_slug, 'error': str(e)}


def _scrape_state_budget_data(state_slug: str) -> List[Dict[str, Any]]:
    """
    Scrape budget dataset page for a state.
    Looks for budget tables, downloadable CSVs, and embedded data.
    """
    url = f"{BASE_URL}/{state_slug}/data"
    records = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            # Try alternate URL patterns
            for alt in [f"{BASE_URL}/{state_slug}/budget", f"{BASE_URL}/{state_slug}/data?search_term=Budget"]:
                resp = requests.get(alt, headers=HEADERS, timeout=30)
                if resp.status_code == 200:
                    break

        if resp.status_code != 200:
            logger.info(f"No budget data page for {state_slug} (HTTP {resp.status_code})")
            return records

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Strategy 1: Look for HTML tables with budget data
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue

            # Get headers
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
            if not headers:
                continue

            # Find relevant columns
            mda_col = next((i for i, h in enumerate(headers) if any(k in h for k in ['mda', 'ministry', 'agency', 'department', 'organization'])), None)
            amount_col = next((i for i, h in enumerate(headers) if any(k in h for k in ['amount', 'budget', 'allocation', 'approved', 'total'])), None)
            project_col = next((i for i, h in enumerate(headers) if any(k in h for k in ['project', 'item', 'description', 'programme'])), None)

            if amount_col is None:
                continue

            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if len(cells) <= amount_col:
                    continue

                amount_text = cells[amount_col]
                amount = _parse_amount(amount_text)
                if amount is None or amount == 0:
                    continue

                record = {
                    'state': _state_display_name(state_slug),
                    'mda': cells[mda_col] if mda_col is not None and mda_col < len(cells) else None,
                    'project': cells[project_col] if project_col is not None and project_col < len(cells) else amount_text,
                    'amount': amount,
                    'source_url': url,
                }
                records.append(record)

        # Strategy 2: Look for downloadable CSV/XLSX links
        download_links = soup.find_all('a', href=re.compile(r'\.(csv|xlsx|xls)($|\?)', re.I))
        for link in download_links:
            href = link.get('href', '')
            if not href.startswith('http'):
                href = BASE_URL + href
            title = link.get_text(strip=True)
            if any(kw in title.lower() for kw in ['budget', 'allocation', 'revenue', 'expenditure']):
                # Download and parse the file
                file_records = _download_and_parse_budget_file(href, state_slug)
                records.extend(file_records)

        # Strategy 3: Look for embedded Datawrapper charts (extract data)
        iframes = soup.find_all('iframe', src=re.compile(r'datawrapper', re.I))
        for iframe in iframes:
            src = iframe.get('src', '')
            logger.info(f"Found Datawrapper chart for {state_slug}: {src}")
            # Datawrapper data extraction would need additional parsing

        logger.info(f"Scraped {len(records)} budget records for {state_slug}")
        return records

    except Exception as e:
        logger.warning(f"Failed to scrape budget data for {state_slug}: {e}")
        return records


def _download_and_parse_budget_file(url: str, state_slug: str) -> List[Dict[str, Any]]:
    """Download and parse a CSV/XLSX budget file."""
    records = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        if resp.status_code != 200:
            return records

        content_type = resp.headers.get('content-type', '')

        if 'csv' in url.lower() or 'csv' in content_type:
            import csv
            import io
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                amount = None
                mda = None
                project = None
                for key, val in row.items():
                    key_lower = key.lower()
                    if any(k in key_lower for k in ['amount', 'budget', 'allocation', 'approved']):
                        amount = _parse_amount(val)
                    elif any(k in key_lower for k in ['mda', 'ministry', 'agency']):
                        mda = val
                    elif any(k in key_lower for k in ['project', 'item', 'description']):
                        project = val

                if amount and amount > 0:
                    records.append({
                        'state': _state_display_name(state_slug),
                        'mda': mda,
                        'project': project or str(row),
                        'amount': amount,
                        'source_url': url,
                    })

        elif any(ext in url.lower() for ext in ['.xlsx', '.xls']):
            import openpyxl
            import io
            wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True)
            for ws in wb.worksheets:
                header_row = None
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i == 0 or header_row is None:
                        # Try to find header row
                        if row and any(str(c or '').lower() in ['mda', 'amount', 'budget', 'project', 'ministry'] for c in row):
                            header_row = [str(c or '').lower() for c in row]
                            continue
                    if header_row and row:
                        row_dict = dict(zip(header_row, row))
                        amount = None
                        for k, v in row_dict.items():
                            if any(kw in k for kw in ['amount', 'budget', 'allocation']):
                                amount = _parse_amount(str(v)) if v else None
                                break
                        if amount and amount > 0:
                            records.append({
                                'state': _state_display_name(state_slug),
                                'mda': row_dict.get('mda') or row_dict.get('ministry'),
                                'project': row_dict.get('project') or row_dict.get('item') or row_dict.get('description'),
                                'amount': amount,
                                'source_url': url,
                            })

        logger.info(f"Parsed {len(records)} records from {url}")

    except Exception as e:
        logger.warning(f"Failed to parse budget file {url}: {e}")

    return records


def _parse_amount(text: str) -> Optional[float]:
    """Parse Nigerian currency amounts: '₦1,234,567.89', '1.5B', '₦500M'"""
    if not text:
        return None
    text = str(text).strip()

    # Remove currency symbols
    text = re.sub(r'[₦N$]', '', text).strip()

    # Handle suffixes
    multiplier = 1.0
    suffix_match = re.search(r'(B|billion|T|trillion|M|million|K|thousand)', text, re.I)
    if suffix_match:
        s = suffix_match.group(1).upper()[0]
        if s == 'T':
            multiplier = 1_000_000_000_000
        elif s == 'B':
            multiplier = 1_000_000_000
        elif s == 'M':
            multiplier = 1_000_000
        elif s == 'K':
            multiplier = 1_000
        text = text[:suffix_match.start()].strip()

    # Remove commas, extract number
    text = text.replace(',', '').strip()
    num_match = re.search(r'[\d.]+', text)
    if num_match:
        try:
            return float(num_match.group()) * multiplier
        except ValueError:
            return None
    return None


def _store_budget_records(records: List[Dict], year: int = None) -> int:
    """Store budget records in the database."""
    if not records:
        return 0

    if year is None:
        year = datetime.utcnow().year

    db = _get_db()
    stored = 0
    try:
        from app.database import Budget

        for record in records:
            try:
                # Check for duplicates
                existing = db.query(Budget).filter(
                    Budget.jurisdiction == record['state'],
                    Budget.year == year,
                    Budget.project == (record.get('project') or '')[:500],
                    Budget.amount == record.get('amount', 0),
                ).first()

                if existing:
                    continue

                budget = Budget(
                    year=year,
                    jurisdiction=record['state'],
                    mda=record.get('mda', '')[:200] if record.get('mda') else None,
                    project=(record.get('project') or 'Budget line item')[:500],
                    amount=record.get('amount', 0),
                    source_file=record.get('source_url', 'openstates.ng'),
                )
                db.add(budget)
                db.commit()
                stored += 1

            except Exception as e:
                db.rollback()
                logger.debug(f"Failed to store record: {e}")
                continue

    finally:
        db.close()

    return stored


def _store_state_overview_as_document(overview: Dict[str, Any]) -> bool:
    """Store state fiscal overview as RAG document for search."""
    if not overview or overview.get('error'):
        return False

    db = _get_db()
    try:
        from app.database import Document

        state = overview['state']
        content_parts = [f"State Budget Overview: {state}"]

        if overview.get('metrics'):
            for label, value in overview['metrics'].items():
                content_parts.append(f"  {label}: {value}")

        if overview.get('datasets'):
            content_parts.append(f"\nAvailable datasets: {len(overview['datasets'])}")
            for ds in overview['datasets'][:5]:
                content_parts.append(f"  - {ds['title']}")

        content = "\n".join(content_parts)
        doc_key = f"budgit-overview-{overview['slug']}-{datetime.utcnow().year}"

        existing = db.query(Document).filter(Document.doc_id == doc_key).first()
        if existing:
            existing.content = content
            existing.updated_at = datetime.utcnow()
        else:
            doc = Document(
                doc_id=doc_key,
                doc_type="budget_overview",
                title=f"{state} State Budget Overview",
                content=content,
                category="budgit",
                metadata_json=json.dumps({
                    'state': state,
                    'source': 'openstates.ng',
                    'metrics': overview.get('metrics', {}),
                    'dataset_count': len(overview.get('datasets', [])),
                }),
            )
            db.add(doc)

        db.commit()
        return True

    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to store overview for {overview.get('state')}: {e}")
        return False
    finally:
        db.close()


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_budgit_pipeline(
    states: Optional[List[str]] = None,
    year: int = None,
    max_states: int = 37
) -> Dict[str, Any]:
    """
    Main pipeline: scrape BudgIT openstates.ng for state budget data.

    Args:
        states: List of state slugs to scrape (default: all 36 + FCT)
        year: Budget year (default: current year)
        max_states: Max states to process per run

    Returns:
        Stats dict with records scraped/stored per state
    """
    if year is None:
        year = datetime.utcnow().year

    target_states = states or NIGERIAN_STATES
    target_states = target_states[:max_states]

    logger.info(f"BudgIT pipeline starting: {len(target_states)} states, year={year}")

    stats = {
        'started_at': datetime.utcnow().isoformat(),
        'year': year,
        'states_processed': 0,
        'states_with_data': 0,
        'total_records_scraped': 0,
        'total_records_stored': 0,
        'overviews_stored': 0,
        'errors': [],
    }

    for state_slug in target_states:
        try:
            # 1. Scrape state overview
            overview = _scrape_state_overview(state_slug)
            if not overview.get('error'):
                if _store_state_overview_as_document(overview):
                    stats['overviews_stored'] += 1

            # 2. Scrape budget line items
            records = _scrape_state_budget_data(state_slug)
            stats['total_records_scraped'] += len(records)

            if records:
                stored = _store_budget_records(records, year=year)
                stats['total_records_stored'] += stored
                stats['states_with_data'] += 1
                logger.info(f"  {_state_display_name(state_slug)}: {len(records)} scraped, {stored} new")

            stats['states_processed'] += 1

            # Rate limit: be nice to BudgIT's servers
            time.sleep(2)

        except Exception as e:
            error_msg = f"{_state_display_name(state_slug)}: {str(e)}"
            stats['errors'].append(error_msg)
            logger.error(f"BudgIT pipeline error for {state_slug}: {e}")

    stats['completed_at'] = datetime.utcnow().isoformat()
    logger.info(
        f"BudgIT pipeline complete: {stats['states_processed']} states, "
        f"{stats['total_records_scraped']} scraped, {stats['total_records_stored']} stored, "
        f"{stats['overviews_stored']} overviews"
    )

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stats = run_budgit_pipeline(max_states=3)  # Test with 3 states
    print(json.dumps(stats, indent=2))
