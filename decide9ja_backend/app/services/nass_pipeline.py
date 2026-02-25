"""
NASS Bill Tracker Pipeline
===========================
Scrapes the National Assembly website (nass.gov.ng) for bills,
their statuses, sponsors, and progression through chambers.

Data flows into the Bill table + RAG documents for Tade to answer
questions like "What bills has my senator sponsored?" or "What's
happening with the petroleum industry bill?"

Sources:
- https://nass.gov.ng/legislation/bills — bill listings
- https://nass.gov.ng/documents/bill/{id} — individual bill pages
- https://placbillstrack.org/ — PLAC bills tracker (fallback)
"""

import os
import re
import json
import time
import logging
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://nass.gov.ng"

# Known bill listing pages
BILL_PAGES = [
    f"{BASE_URL}/legislation/bills",
    f"{BASE_URL}/documents/bills",
]

# RSS/news sources for NASS legislative updates
NASS_NEWS_FEEDS = [
    "https://punchng.com/topics/national-assembly/",
    "https://www.premiumtimesng.com/tag/national-assembly",
]

HEADERS = {
    'User-Agent': 'Decide9ja-Bot/1.0 (civic-tech; legislative-transparency)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# Bill status progression
STATUS_ORDER = [
    'introduced', 'first_reading', 'second_reading', 'committee',
    'third_reading', 'passed', 'concurrence', 'presidential_assent', 'enacted'
]


def _get_db():
    """Get database session."""
    from app.database import SessionLocal
    return SessionLocal()


def _scrape_bill_listings() -> List[Dict[str, Any]]:
    """
    Scrape the NASS website for bill listings.
    Returns list of bill stubs (id, title, chamber, date, detail_url).
    """
    all_bills = []

    for page_url in BILL_PAGES:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                logger.info(f"NASS page not available: {page_url} (HTTP {resp.status_code})")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Strategy 1: Look for bill links with /documents/bill/ pattern
            bill_links = soup.find_all('a', href=re.compile(r'/documents/bill/\d+'))
            for link in bill_links:
                href = link.get('href', '')
                if not href.startswith('http'):
                    href = BASE_URL + href

                # Extract bill ID from URL
                id_match = re.search(r'/bill/(\d+)', href)
                bill_nass_id = id_match.group(1) if id_match else None

                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    # Try parent element
                    parent = link.find_parent(['div', 'li', 'td'])
                    if parent:
                        title = parent.get_text(strip=True)

                # Try to detect chamber from context
                parent_text = ''
                parent_el = link.find_parent(['div', 'li', 'tr'])
                if parent_el:
                    parent_text = parent_el.get_text(strip=True).lower()

                chamber = 'senate' if 'senate' in parent_text else 'house' if 'house' in parent_text else 'unknown'

                # Try to extract date
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', parent_text)
                date_str = date_match.group(1) if date_match else None

                if bill_nass_id and title:
                    all_bills.append({
                        'nass_id': bill_nass_id,
                        'title': title[:1000],
                        'chamber': chamber,
                        'date': date_str,
                        'detail_url': href,
                    })

            # Strategy 2: Look for table rows with bill data
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:
                        continue

                    # Look for a link to bill detail
                    link = row.find('a', href=re.compile(r'/documents/bill/|/bill/'))
                    if link:
                        href = link.get('href', '')
                        if not href.startswith('http'):
                            href = BASE_URL + href

                        id_match = re.search(r'/bill/(\d+)', href)
                        bill_nass_id = id_match.group(1) if id_match else None

                        cell_texts = [c.get_text(strip=True) for c in cells]
                        title = cell_texts[0] if cell_texts else link.get_text(strip=True)

                        if bill_nass_id and title:
                            all_bills.append({
                                'nass_id': bill_nass_id,
                                'title': title[:1000],
                                'chamber': 'unknown',
                                'date': None,
                                'detail_url': href,
                            })

            logger.info(f"Found {len(all_bills)} bills from {page_url}")

        except Exception as e:
            logger.warning(f"Failed to scrape {page_url}: {e}")

    # Deduplicate by nass_id
    seen = set()
    unique_bills = []
    for bill in all_bills:
        if bill['nass_id'] not in seen:
            seen.add(bill['nass_id'])
            unique_bills.append(bill)

    return unique_bills


def _scrape_bill_detail(detail_url: str) -> Dict[str, Any]:
    """
    Scrape individual bill page for full details.
    Returns enriched bill data with description, sponsor, status, etc.
    """
    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return {'error': f'HTTP {resp.status_code}'}

        soup = BeautifulSoup(resp.text, 'html.parser')
        data = {'detail_url': detail_url}

        # Extract full title — NASS puts actual bill title in <strong> or <p> with
        # "A BILL FOR AN ACT..." pattern, NOT in the <h1> (which is just "Bill Tracker")
        bill_title = None

        # Strategy 1: Find "A BILL FOR AN ACT..." text
        for el in soup.find_all(['strong', 'p', 'b', 'div']):
            text = el.get_text(strip=True)
            if text and re.match(r'^A BILL', text, re.I) and len(text) > 30:
                bill_title = text
                break

        # Strategy 2: Find any long text containing "act" or "bill"
        if not bill_title:
            for el in soup.find_all(['strong', 'b']):
                text = el.get_text(strip=True)
                if text and len(text) > 40 and any(kw in text.lower() for kw in ['act', 'bill', 'amendment']):
                    bill_title = text
                    break

        # Strategy 3: Fall back to h1 but skip generic "Bill Tracker"
        if not bill_title:
            for el in soup.find_all(['h1', 'h2']):
                text = el.get_text(strip=True)
                if text and text.lower() not in ['bill tracker', 'bills', 'legislation']:
                    bill_title = text
                    break

        if bill_title:
            data['full_title'] = bill_title[:1000]

        # Extract bill body/description — look for the main content block
        # On NASS pages, the description is often the same as the title for simple bills
        content_el = soup.find(['div', 'article'], class_=re.compile(r'content|body|description|text', re.I))
        if content_el:
            content_text = content_el.get_text(strip=True)
            # Don't use if it's just navigation text
            if len(content_text) > 50 and 'bill tracker' not in content_text.lower()[:20]:
                data['description'] = content_text[:2000]

        # If no description found, use the title itself as description
        if not data.get('description') and bill_title:
            data['description'] = bill_title[:2000]

        # Look for metadata fields (sponsor, status, date, chamber)
        # NASS pages often use label-value pairs
        labels = soup.find_all(['dt', 'label', 'strong', 'b'])
        for label in labels:
            label_text = label.get_text(strip=True).lower()
            value_el = label.find_next(['dd', 'span', 'p', 'td'])
            if not value_el:
                continue
            value = value_el.get_text(strip=True)

            if 'sponsor' in label_text:
                data['sponsor_name'] = value
            elif 'status' in label_text or 'stage' in label_text:
                data['status'] = _normalize_status(value)
            elif 'chamber' in label_text:
                data['chamber'] = value.lower() if 'senate' in value.lower() else 'house'
            elif 'date' in label_text and 'introduced' in label_text:
                data['introduced_date'] = value
            elif 'type' in label_text:
                data['bill_type'] = value.lower()
            elif 'committee' in label_text:
                data['committee'] = value

        # Look for PDF download link
        pdf_link = soup.find('a', href=re.compile(r'\.pdf($|\?)', re.I))
        if pdf_link:
            href = pdf_link.get('href', '')
            if not href.startswith('http'):
                href = BASE_URL + href
            data['full_text_url'] = href

        return data

    except Exception as e:
        logger.warning(f"Failed to scrape bill detail {detail_url}: {e}")
        return {'error': str(e)}


def _normalize_status(status_text: str) -> str:
    """Normalize bill status text to standard enum values."""
    s = status_text.lower().strip()

    if any(k in s for k in ['enacted', 'signed', 'assented']):
        return 'enacted'
    elif any(k in s for k in ['presidential', 'assent']):
        return 'presidential_assent'
    elif any(k in s for k in ['passed', 'approved']):
        return 'passed'
    elif 'concurrence' in s:
        return 'concurrence'
    elif 'third' in s and 'reading' in s:
        return 'third_reading'
    elif 'committee' in s:
        return 'committee'
    elif 'second' in s and 'reading' in s:
        return 'second_reading'
    elif 'first' in s and 'reading' in s:
        return 'first_reading'
    elif any(k in s for k in ['introduced', 'filed', 'submitted']):
        return 'introduced'
    elif any(k in s for k in ['rejected', 'defeated']):
        return 'rejected'
    elif 'withdrawn' in s:
        return 'withdrawn'

    return 'introduced'  # Default


def _scrape_nass_news_for_bills() -> List[Dict[str, Any]]:
    """
    Fallback: scrape news sites for National Assembly legislative updates.
    Extract bill mentions from recent news articles.
    """
    articles = []
    keywords = ['bill', 'legislation', 'senate', 'house of representatives', 'national assembly',
                'first reading', 'second reading', 'third reading', 'passed', 'assent']

    for feed_url in NASS_NEWS_FEEDS:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find article links
            links = soup.find_all('a', href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                if not title or len(title) < 20:
                    continue

                # Check if this is a bill-related article
                title_lower = title.lower()
                if any(kw in title_lower for kw in keywords):
                    articles.append({
                        'title': title[:500],
                        'url': href if href.startswith('http') else feed_url.split('/')[0] + '//' + feed_url.split('/')[2] + href,
                        'source': 'news',
                    })

            logger.info(f"Found {len(articles)} legislative news articles from {feed_url}")

        except Exception as e:
            logger.warning(f"Failed to scrape NASS news from {feed_url}: {e}")

    return articles[:20]  # Cap at 20


def _store_bills(bills: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Store scraped bills in the database.
    Returns (new_count, updated_count).
    """
    db = _get_db()
    new_count = 0
    updated_count = 0

    try:
        from app.database import Bill

        for bill_data in bills:
            try:
                nass_id = bill_data.get('nass_id')
                if not nass_id:
                    continue

                bill_id = f"NASS-{nass_id}"

                existing = db.query(Bill).filter(Bill.bill_id == bill_id).first()

                if existing:
                    # Update if we have new info
                    changed = False
                    if bill_data.get('status') and bill_data['status'] != existing.status:
                        existing.status = bill_data['status']
                        existing.last_action = f"Status updated to {bill_data['status']}"
                        existing.last_action_date = datetime.utcnow()
                        changed = True
                    if bill_data.get('description') and not existing.description:
                        existing.description = bill_data['description'][:2000]
                        changed = True
                    if bill_data.get('sponsor_name') and not existing.sponsor_name:
                        existing.sponsor_name = bill_data['sponsor_name']
                        changed = True
                    if bill_data.get('full_text_url') and not existing.full_text_url:
                        existing.full_text_url = bill_data['full_text_url']
                        changed = True
                    if changed:
                        db.commit()
                        updated_count += 1
                else:
                    # Create new bill
                    title = bill_data.get('full_title') or bill_data.get('title', 'Untitled Bill')
                    chamber = bill_data.get('chamber', 'unknown')
                    if chamber == 'unknown':
                        # Try to infer from title
                        if 'senate' in title.lower():
                            chamber = 'senate'
                        elif 'house' in title.lower():
                            chamber = 'house'

                    # Parse introduced date
                    introduced_date = None
                    date_str = bill_data.get('introduced_date') or bill_data.get('date')
                    if date_str:
                        try:
                            introduced_date = datetime.strptime(date_str, '%Y-%m-%d')
                        except (ValueError, TypeError):
                            try:
                                introduced_date = datetime.strptime(date_str, '%d/%m/%Y')
                            except (ValueError, TypeError):
                                pass

                    bill = Bill(
                        bill_id=bill_id,
                        title=title[:1000],
                        short_title=title[:200] if len(title) > 200 else None,
                        description=bill_data.get('description', '')[:2000] if bill_data.get('description') else None,
                        bill_type=bill_data.get('bill_type', 'unknown'),
                        chamber=chamber,
                        originating_chamber=chamber,
                        sponsor_name=bill_data.get('sponsor_name'),
                        status=bill_data.get('status', 'introduced'),
                        introduced_date=introduced_date,
                        last_action_date=datetime.utcnow(),
                        last_action='Scraped from NASS website',
                        full_text_url=bill_data.get('full_text_url'),
                        category=_categorize_bill(title),
                    )
                    db.add(bill)
                    db.commit()
                    new_count += 1

            except Exception as e:
                db.rollback()
                logger.debug(f"Failed to store bill {bill_data.get('nass_id')}: {e}")
                continue

    finally:
        db.close()

    return new_count, updated_count


def _store_legislative_news(articles: List[Dict[str, Any]]) -> int:
    """Store legislative news as RAG documents."""
    db = _get_db()
    stored = 0

    try:
        from app.database import Document

        for article in articles:
            try:
                doc_key = f"nass-news-{hashlib.md5(article['url'].encode()).hexdigest()[:12]}"

                existing = db.query(Document).filter(Document.doc_id == doc_key).first()
                if existing:
                    continue

                doc = Document(
                    doc_id=doc_key,
                    doc_type="legislation_news",
                    title=article['title'][:500],
                    content=article['title'],
                    category="nass",
                    metadata_json=json.dumps({
                        'url': article['url'],
                        'source': article.get('source', 'news'),
                        'scraped_at': datetime.utcnow().isoformat(),
                    }),
                )
                db.add(doc)
                db.commit()
                stored += 1

            except Exception as e:
                db.rollback()
                continue

    finally:
        db.close()

    return stored


def _categorize_bill(title: str) -> str:
    """Categorize a bill based on its title."""
    t = title.lower()

    categories = {
        'finance': ['bank', 'financial', 'tax', 'revenue', 'budget', 'appropriation', 'fiscal', 'monetary', 'insurance', 'pension'],
        'security': ['security', 'police', 'military', 'defence', 'terrorism', 'armed', 'prison', 'firearm'],
        'education': ['education', 'university', 'school', 'student', 'teacher', 'academic', 'polytechnic'],
        'health': ['health', 'medical', 'hospital', 'pharmaceutical', 'drug', 'disease', 'epidemic'],
        'infrastructure': ['road', 'bridge', 'railway', 'power', 'electricity', 'water', 'housing', 'construction'],
        'oil_gas': ['petroleum', 'oil', 'gas', 'nnpc', 'refinery', 'pipeline', 'mining'],
        'technology': ['digital', 'technology', 'cyber', 'internet', 'data', 'telecoms', 'ict'],
        'governance': ['constitution', 'electoral', 'governance', 'public service', 'civil service', 'judicial'],
        'agriculture': ['agriculture', 'farming', 'food', 'livestock', 'fisheries', 'irrigation'],
        'environment': ['environment', 'climate', 'pollution', 'waste', 'conservation', 'forest'],
        'trade': ['trade', 'export', 'import', 'commerce', 'industry', 'manufacturing'],
        'labour': ['labour', 'employment', 'worker', 'minimum wage', 'industrial'],
    }

    for category, keywords in categories.items():
        if any(kw in t for kw in keywords):
            return category

    return 'general'


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_nass_pipeline() -> Dict[str, Any]:
    """
    Main pipeline: scrape NASS website for bills and legislative activity.

    Flow:
    1. Scrape bill listing pages for bill stubs
    2. For each new bill, scrape detail page
    3. Store bills in Bill table
    4. Scrape legislative news as fallback/supplement
    5. Store news as RAG documents

    Returns:
        Stats dict
    """
    logger.info("NASS bill tracker pipeline starting")

    stats = {
        'started_at': datetime.utcnow().isoformat(),
        'bills_found': 0,
        'bills_new': 0,
        'bills_updated': 0,
        'bills_detail_scraped': 0,
        'news_articles_found': 0,
        'news_stored': 0,
        'errors': [],
    }

    # 1. Scrape bill listings
    try:
        bill_stubs = _scrape_bill_listings()
        stats['bills_found'] = len(bill_stubs)
        logger.info(f"Found {len(bill_stubs)} bills from NASS website")
    except Exception as e:
        logger.error(f"Bill listing scrape failed: {e}")
        stats['errors'].append(f"Bill listing: {str(e)}")
        bill_stubs = []

    # 2. Scrape detail pages for bills we don't already have
    enriched_bills = []
    for stub in bill_stubs:
        try:
            # Check if we already have full details
            from app.database import SessionLocal, Bill
            db = SessionLocal()
            try:
                bill_id = f"NASS-{stub['nass_id']}"
                existing = db.query(Bill).filter(Bill.bill_id == bill_id).first()
                needs_detail = not existing or not existing.description
            finally:
                db.close()

            if needs_detail and stub.get('detail_url'):
                detail = _scrape_bill_detail(stub['detail_url'])
                stub.update(detail)
                stats['bills_detail_scraped'] += 1
                time.sleep(1.5)  # Rate limit

            enriched_bills.append(stub)

        except Exception as e:
            stats['errors'].append(f"Detail scrape {stub.get('nass_id')}: {str(e)}")
            enriched_bills.append(stub)

    # 3. Store bills
    if enriched_bills:
        try:
            new_count, updated_count = _store_bills(enriched_bills)
            stats['bills_new'] = new_count
            stats['bills_updated'] = updated_count
            logger.info(f"Stored {new_count} new bills, updated {updated_count}")
        except Exception as e:
            stats['errors'].append(f"Bill storage: {str(e)}")

    # 4. Scrape legislative news as supplement
    try:
        news_articles = _scrape_nass_news_for_bills()
        stats['news_articles_found'] = len(news_articles)

        if news_articles:
            stored = _store_legislative_news(news_articles)
            stats['news_stored'] = stored
            logger.info(f"Stored {stored} legislative news articles")
    except Exception as e:
        stats['errors'].append(f"News scrape: {str(e)}")

    stats['completed_at'] = datetime.utcnow().isoformat()
    logger.info(
        f"NASS pipeline complete: {stats['bills_found']} found, "
        f"{stats['bills_new']} new, {stats['bills_updated']} updated, "
        f"{stats['news_stored']} news articles"
    )

    return stats


# =============================================================================
# RAG HELPER — Get bill data for Tade
# =============================================================================

def get_bill_data_for_rag(query: str, limit: int = 5) -> Optional[str]:
    """
    Search bills for RAG context.
    Used by orchestrator's check_election_info or search_rag tools.
    """
    db = _get_db()
    try:
        from app.database import Bill
        from sqlalchemy import or_

        keywords = [w.strip() for w in query.lower().split() if len(w.strip()) > 2]
        if not keywords:
            return None

        filters = []
        for kw in keywords[:5]:
            filters.append(Bill.title.ilike(f"%{kw}%"))
            filters.append(Bill.description.ilike(f"%{kw}%"))
            filters.append(Bill.sponsor_name.ilike(f"%{kw}%"))
            filters.append(Bill.category.ilike(f"%{kw}%"))

        bills = db.query(Bill).filter(or_(*filters)).order_by(
            Bill.last_action_date.desc().nullslast()
        ).limit(limit).all()

        if not bills:
            return None

        parts = []
        for b in bills:
            status_display = b.status.replace('_', ' ').title() if b.status else 'Unknown'
            line = f"[BILL {b.bill_id}] {b.title}"
            line += f"\n  Chamber: {b.chamber} | Status: {status_display}"
            if b.sponsor_name:
                line += f" | Sponsor: {b.sponsor_name}"
            if b.category:
                line += f" | Category: {b.category}"
            if b.introduced_date:
                line += f"\n  Introduced: {b.introduced_date.strftime('%Y-%m-%d')}"
            if b.description:
                line += f"\n  Summary: {b.description[:200]}"
            parts.append(line)

        return "\n\n".join(parts)

    except Exception as e:
        logger.warning(f"Bill RAG lookup failed: {e}")
        return None
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stats = run_nass_pipeline()
    print(json.dumps(stats, indent=2))
