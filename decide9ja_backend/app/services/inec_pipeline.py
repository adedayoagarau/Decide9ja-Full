"""
INEC Election Data Pipeline
=============================
Scrapes INEC website + news sources for up-to-date election information.
Stores structured election data that the ElectionInfoAgent can query.

Data collected:
- Election timetable / key dates
- Voter registration status and updates
- Candidate declarations (as announced)
- INEC announcements and press releases

Uses a `election_data` table to store structured JSON records.
Falls back to web search when INEC site is unavailable.
"""

import re
import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# INEC Sources
INEC_BASE = "https://www.inecnigeria.org"
INEC_NEWS_URLS = [
    f"{INEC_BASE}/news/",
    f"{INEC_BASE}/press-releases/",
]

# Nigerian political news RSS for INEC-related stories
NEWS_RSS_FEEDS = [
    ("Premium Times", "https://www.premiumtimesng.com/feed"),
    ("Punch", "https://punchng.com/feed/"),
    ("Vanguard", "https://www.vanguardngr.com/feed/"),
    ("Channels TV", "https://www.channelstv.com/feed/"),
]

INEC_KEYWORDS = [
    "inec", "election", "voter registration", "pvc", "cvr",
    "electoral", "ballot", "polling", "2027 election",
    "candidate", "primary", "gubernatorial", "senatorial",
    "election timetable", "inec chairman", "mahmood yakubu",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _scrape_inec_website() -> List[Dict]:
    """
    Scrape INEC's website for press releases and announcements.
    Returns list of structured records.
    """
    records = []
    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = False

    for url in INEC_NEWS_URLS:
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"INEC scrape: {url} returned {resp.status_code}")
                continue

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            # INEC site structure varies — try common patterns
            articles = soup.find_all('article') or soup.find_all('div', class_=re.compile(r'post|entry|news|item'))

            for article in articles[:15]:  # Limit per page
                title_el = article.find(['h2', 'h3', 'h4'])
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                link_el = title_el.find('a') or article.find('a')
                link = link_el['href'] if link_el and link_el.get('href') else ''
                if link and not link.startswith('http'):
                    link = INEC_BASE + link

                # Get excerpt
                excerpt_el = article.find('p') or article.find('div', class_=re.compile(r'excerpt|summary'))
                excerpt = excerpt_el.get_text(strip=True)[:500] if excerpt_el else ''

                # Get date
                date_el = article.find('time') or article.find(class_=re.compile(r'date|time'))
                pub_date = date_el.get_text(strip=True) if date_el else datetime.now().strftime('%Y-%m-%d')

                if title:
                    record_id = hashlib.md5(f"inec_{title}".encode()).hexdigest()[:20]
                    records.append({
                        "id": record_id,
                        "source": "inec_official",
                        "category": _categorize_inec_content(title + ' ' + excerpt),
                        "title": title[:300],
                        "content": excerpt,
                        "url": link,
                        "published_date": pub_date,
                        "scraped_at": datetime.now().isoformat(),
                    })

        except Exception as e:
            logger.error(f"INEC scrape failed for {url}: {e}")

    logger.info(f"INEC website: scraped {len(records)} items")
    return records


def _scrape_inec_news_from_rss() -> List[Dict]:
    """
    Search Nigerian news RSS feeds for INEC/election-related stories.
    """
    records = []

    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser not installed — skipping RSS INEC news")
        return records

    for source_name, rss_url in NEWS_RSS_FEEDS:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:20]:
                title = entry.get('title', '').lower()
                summary = entry.get('summary', '').lower()
                combined = title + ' ' + summary

                # Only keep INEC/election related
                if any(kw in combined for kw in INEC_KEYWORDS):
                    record_id = hashlib.md5(f"news_{entry.get('link', '')}".encode()).hexdigest()[:20]
                    records.append({
                        "id": record_id,
                        "source": f"news_{source_name.lower().replace(' ', '_')}",
                        "category": _categorize_inec_content(combined),
                        "title": entry.get('title', '')[:300],
                        "content": entry.get('summary', '')[:1000],
                        "url": entry.get('link', ''),
                        "published_date": entry.get('published', datetime.now().strftime('%Y-%m-%d')),
                        "scraped_at": datetime.now().isoformat(),
                    })
        except Exception as e:
            logger.warning(f"RSS INEC news failed for {source_name}: {e}")

    logger.info(f"INEC RSS news: found {len(records)} election-related articles")
    return records


def _categorize_inec_content(text: str) -> str:
    """Categorize INEC content into election topics."""
    text = text.lower()
    if any(w in text for w in ['register', 'cvr', 'pvc', 'voter card', 'voter registration']):
        return 'voter_registration'
    if any(w in text for w in ['timetable', 'schedule', 'date', 'calendar', 'postpone']):
        return 'election_timetable'
    if any(w in text for w in ['candidate', 'primary', 'aspirant', 'declaration', 'running mate']):
        return 'candidates'
    if any(w in text for w in ['result', 'collation', 'winner', 'tribunal']):
        return 'results'
    if any(w in text for w in ['polling', 'unit', 'bvas', 'irev']):
        return 'polling'
    return 'general_election'


def _get_static_election_data() -> List[Dict]:
    """
    Provide baseline election data that we know is accurate.
    Updated manually when INEC makes official announcements.
    """
    now = datetime.now().isoformat()
    return [
        {
            "id": "static_2027_general",
            "source": "static_baseline",
            "category": "election_timetable",
            "title": "2027 Nigerian General Elections - Key Dates",
            "content": json.dumps({
                "presidential_date": "February 2027 (exact date TBD by INEC)",
                "governorship_date": "March 2027 (exact date TBD by INEC)",
                "state_assembly_date": "March 2027 (exact date TBD by INEC)",
                "note": "INEC typically announces the official timetable 12 months before elections."
            }),
            "url": "https://www.inecnigeria.org",
            "published_date": "2025-01-01",
            "scraped_at": now,
        },
        {
            "id": "static_registration",
            "source": "static_baseline",
            "category": "voter_registration",
            "title": "How to Register to Vote in Nigeria (2025-2027)",
            "content": json.dumps({
                "method": "Continuous Voter Registration (CVR)",
                "where": "Visit your nearest INEC Local Government office",
                "requirements": [
                    "Valid ID (NIN, Passport, Driver's License)",
                    "Proof of address (utility bill or bank statement)",
                    "Must be 18+ years old",
                    "Must be a Nigerian citizen"
                ],
                "steps": [
                    "Visit INEC LGA office during registration hours",
                    "Present valid identification",
                    "Complete biometric capture (photo + fingerprints)",
                    "Collect PVC at the same office (usually 2-4 weeks later)"
                ],
                "online_pre_registration": "https://cvr.inecnigeria.org",
                "cost": "FREE — registration is completely free",
                "helpline": "09-2348577",
                "deadline": "INEC typically suspends CVR 60-90 days before elections"
            }),
            "url": "https://cvr.inecnigeria.org",
            "published_date": "2025-01-01",
            "scraped_at": now,
        },
        {
            "id": "static_candidates_2027",
            "source": "static_baseline",
            "category": "candidates",
            "title": "2027 Presidential Race - Expected Candidates",
            "content": json.dumps({
                "confirmed": [],
                "expected": [
                    {"name": "Bola Tinubu", "party": "APC", "status": "Incumbent President — may seek re-election", "state": "Lagos"},
                    {"name": "Atiku Abubakar", "party": "PDP", "status": "Expected contender", "state": "Adamawa"},
                    {"name": "Peter Obi", "party": "LP", "status": "Expected contender", "state": "Anambra"},
                    {"name": "Rabiu Kwankwaso", "party": "NNPP", "status": "Expected contender", "state": "Kano"},
                ],
                "note": "Official candidate lists will be confirmed after party primaries (expected late 2026)"
            }),
            "url": "https://www.inecnigeria.org",
            "published_date": "2025-01-01",
            "scraped_at": now,
        },
        {
            "id": "static_pvc_info",
            "source": "static_baseline",
            "category": "voter_registration",
            "title": "PVC Collection and Status Check",
            "content": json.dumps({
                "collection_status": "Ongoing at INEC LGA offices nationwide",
                "how_to_check": "Visit voters.inecnigeria.org with your VIN (Voter ID Number)",
                "what_to_bring": "Valid ID matching your registration",
                "office_hours": "Monday-Friday, 9AM-3PM (varies by state)",
                "note": "Uncollected PVCs from previous registrations are also available"
            }),
            "url": "https://voters.inecnigeria.org",
            "published_date": "2025-01-01",
            "scraped_at": now,
        }
    ]


def run_inec_pipeline() -> Dict:
    """
    Main INEC pipeline: scrape INEC site + news RSS + merge with static data.
    Stores results in the election_data table (or RAG documents as fallback).

    Returns stats dict.
    """
    from app.database import SessionLocal, Document

    logger.info("INEC Pipeline: Starting...")

    # Collect from all sources
    all_records = []

    # 1. Static baseline (always available)
    static_records = _get_static_election_data()
    all_records.extend(static_records)

    # 2. INEC website scrape
    try:
        inec_records = _scrape_inec_website()
        all_records.extend(inec_records)
    except Exception as e:
        logger.error(f"INEC website scrape failed: {e}")

    # 3. News RSS for election stories
    try:
        news_records = _scrape_inec_news_from_rss()
        all_records.extend(news_records)
    except Exception as e:
        logger.error(f"INEC news RSS failed: {e}")

    # Store in RAG documents table for retrieval
    db = SessionLocal()
    stored = 0
    try:
        for record in all_records:
            try:
                doc_id = f"inec_{record['id']}"
                # Check if exists
                existing = db.query(Document).filter(Document.doc_id == doc_id).first()

                content_text = record['title']
                if record.get('content'):
                    content_text += '\n\n' + record['content']

                if existing:
                    existing.content = content_text
                    existing.metadata_json = json.dumps({
                        "source": record.get("source"),
                        "category": record.get("category"),
                        "url": record.get("url"),
                        "published_date": record.get("published_date"),
                    })
                    existing.updated_at = datetime.now()
                else:
                    doc = Document(
                        doc_id=doc_id,
                        doc_type="election_data",
                        title=record['title'][:300],
                        content=content_text,
                        source=record.get('source', 'inec'),
                        metadata_json=json.dumps({
                            "source": record.get("source"),
                            "category": record.get("category"),
                            "url": record.get("url"),
                            "published_date": record.get("published_date"),
                        }),
                    )
                    db.add(doc)
                stored += 1
            except Exception as e:
                logger.warning(f"INEC Pipeline: Failed to store record {record.get('id')}: {e}")
                continue

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"INEC Pipeline: DB commit failed: {e}")
    finally:
        db.close()

    stats = {
        "static_records": len(static_records),
        "inec_website_records": len(all_records) - len(static_records) - len(news_records if 'news_records' in dir() else []),
        "news_rss_records": len(news_records) if 'news_records' in dir() else 0,
        "total_stored": stored,
    }
    logger.info(f"INEC Pipeline complete: {stats}")
    return stats


def get_election_data_for_rag(query: str, limit: int = 5) -> str:
    """
    Retrieve election data matching a query, for use by ElectionInfoAgent.
    Searches the Document table for election_data entries.
    """
    from app.database import SessionLocal, Document
    from sqlalchemy import or_, func

    db = SessionLocal()
    try:
        words = [w.strip().lower() for w in query.split() if len(w.strip()) > 2]
        if not words:
            words = ['election', '2027']

        conditions = []
        for w in words:
            term = f"%{w}%"
            conditions.append(Document.title.ilike(term))
            conditions.append(Document.content.ilike(term))

        results = db.query(Document).filter(
            Document.doc_type == "election_data",
            or_(*conditions)
        ).limit(limit).all()

        if not results:
            # Fallback: return all static baseline data
            results = db.query(Document).filter(
                Document.doc_type == "election_data",
                Document.source == "static_baseline"
            ).all()

        if not results:
            return ""

        parts = []
        for doc in results:
            parts.append(f"### {doc.title}\n{doc.content}")

        return '\n\n---\n\n'.join(parts)

    except Exception as e:
        logger.error(f"Election data retrieval failed: {e}")
        return ""
    finally:
        db.close()
