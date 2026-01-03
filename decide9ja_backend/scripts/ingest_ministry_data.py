#!/usr/bin/env python3
"""
Ingest crawled ministry and project data into the database.

Run after running the ministry crawler:
    python -m app.scrapers.ministry_crawler
    python scripts/ingest_ministry_data.py

Or run directly (will crawl first):
    python scripts/ingest_ministry_data.py --crawl
"""
import os
import sys
import argparse
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_connection():
    """Get database connection."""
    from sqlalchemy import create_engine
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./decide9ja.db')
    return create_engine(database_url)


def ingest_ministries(engine, ministries: list):
    """Ingest ministry data into the database."""
    from sqlalchemy import text

    inserted = 0
    updated = 0

    with engine.connect() as conn:
        for ministry in ministries:
            try:
                # Check if ministry exists
                result = conn.execute(text('''
                    SELECT id FROM ministries WHERE name ILIKE :name OR short_name ILIKE :short
                '''), {
                    'name': f"%{ministry.get('name', '')}%",
                    'short': f"%{ministry.get('key', '')}%"
                })
                existing = result.fetchone()

                if existing:
                    # Update existing
                    if ministry.get('description'):
                        conn.execute(text('''
                            UPDATE ministries
                            SET description = :desc
                            WHERE id = :id
                        '''), {
                            'desc': ministry.get('description'),
                            'id': existing[0]
                        })
                        updated += 1
                else:
                    # Insert new
                    conn.execute(text('''
                        INSERT INTO ministries (name, short_name, description, sector)
                        VALUES (:name, :short, :desc, :sector)
                        ON CONFLICT (name) DO NOTHING
                    '''), {
                        'name': ministry.get('name', ministry.get('key', 'Unknown')),
                        'short': ministry.get('key', '').replace('_', ' ').title(),
                        'desc': ministry.get('description'),
                        'sector': guess_sector(ministry.get('key', ''))
                    })
                    inserted += 1

            except Exception as e:
                logger.warning(f"Error ingesting ministry {ministry.get('name')}: {e}")

        conn.commit()

    logger.info(f"Ministries: {inserted} inserted, {updated} updated")
    return inserted, updated


def guess_sector(ministry_key: str) -> str:
    """Guess the sector based on ministry key."""
    key = ministry_key.lower()

    if key in ['finance', 'budget', 'trade', 'industry', 'petroleum', 'agriculture']:
        return 'Economy'
    elif key in ['health', 'education', 'labour', 'women', 'youth', 'sports', 'humanitarian']:
        return 'Social'
    elif key in ['works', 'housing', 'transport', 'aviation', 'power', 'water']:
        return 'Infrastructure'
    elif key in ['defence', 'interior', 'police']:
        return 'Security'
    elif key in ['justice', 'foreign_affairs', 'information', 'fct']:
        return 'Governance'
    elif key in ['communications', 'science']:
        return 'Technology'
    elif key in ['environment', 'marine']:
        return 'Environment'
    else:
        return 'Other'


def ingest_projects(engine, projects: list):
    """Ingest project data into the database."""
    from sqlalchemy import text

    inserted = 0
    duplicates = 0

    with engine.connect() as conn:
        for project in projects:
            try:
                # Check for duplicate by title
                result = conn.execute(text('''
                    SELECT id FROM projects WHERE title ILIKE :title LIMIT 1
                '''), {'title': project.get('title', '')[:100]})

                if result.fetchone():
                    duplicates += 1
                    continue

                # Get ministry ID if ministry name provided
                ministry_id = None
                if project.get('ministry'):
                    result = conn.execute(text('''
                        SELECT id FROM ministries
                        WHERE name ILIKE :name OR short_name ILIKE :name
                        LIMIT 1
                    '''), {'name': f"%{project['ministry']}%"})
                    row = result.fetchone()
                    if row:
                        ministry_id = row[0]

                # Insert project
                conn.execute(text('''
                    INSERT INTO projects (
                        title, description, state, budget_amount, status,
                        ministry_id, source, source_url, last_updated
                    ) VALUES (
                        :title, :desc, :state, :budget, :status,
                        :ministry_id, :source, :source_url, :last_updated
                    )
                '''), {
                    'title': project.get('title', 'Unknown')[:500],
                    'desc': project.get('description'),
                    'state': project.get('state'),
                    'budget': project.get('budget'),
                    'status': project.get('status', 'Unknown'),
                    'ministry_id': ministry_id,
                    'source': project.get('source', 'Web Crawler'),
                    'source_url': project.get('source_url'),
                    'last_updated': datetime.now().date()
                })
                inserted += 1

            except Exception as e:
                logger.warning(f"Error ingesting project {project.get('title', '')[:50]}: {e}")

        conn.commit()

    logger.info(f"Projects: {inserted} inserted, {duplicates} duplicates skipped")
    return inserted, duplicates


def run_crawl_and_ingest():
    """Run the crawler and ingest results."""
    logger.info("Starting ministry crawler...")

    try:
        from app.scrapers import run_crawl_sync
        results = run_crawl_sync()
    except Exception as e:
        logger.error(f"Crawler failed: {e}")
        return

    logger.info(f"Crawl complete. Found {results.get('total_ministries', 0)} ministries and {results.get('total_projects', 0)} projects")

    # Get database connection
    engine = get_database_connection()

    # Ingest ministries
    all_ministries = []
    if results.get('osgf', {}).get('ministries'):
        all_ministries.extend(results['osgf']['ministries'])
    if results.get('ministries', {}).get('ministries'):
        all_ministries.extend(results['ministries']['ministries'])

    if all_ministries:
        ingest_ministries(engine, all_ministries)

    # Ingest projects
    all_projects = []
    if results.get('ministries', {}).get('projects'):
        all_projects.extend(results['ministries']['projects'])
    if results.get('alternatives', {}).get('projects'):
        all_projects.extend(results['alternatives']['projects'])

    if all_projects:
        ingest_projects(engine, all_projects)

    logger.info("Ingestion complete!")


def ingest_from_file(filepath: str):
    """Ingest from a JSON file."""
    import json

    logger.info(f"Loading data from {filepath}")

    with open(filepath, 'r') as f:
        results = json.load(f)

    engine = get_database_connection()

    # Ingest ministries
    if results.get('ministries'):
        ingest_ministries(engine, results['ministries'])

    # Ingest projects
    if results.get('projects'):
        ingest_projects(engine, results['projects'])

    logger.info("Ingestion from file complete!")


def main():
    parser = argparse.ArgumentParser(description='Ingest ministry and project data')
    parser.add_argument('--crawl', action='store_true', help='Run crawler before ingesting')
    parser.add_argument('--file', type=str, help='JSON file to ingest from')

    args = parser.parse_args()

    if args.file:
        ingest_from_file(args.file)
    elif args.crawl:
        run_crawl_and_ingest()
    else:
        print("Usage:")
        print("  python scripts/ingest_ministry_data.py --crawl    # Crawl and ingest")
        print("  python scripts/ingest_ministry_data.py --file data.json  # Ingest from file")


if __name__ == '__main__':
    main()
