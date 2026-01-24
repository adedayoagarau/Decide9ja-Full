"""
Politician Mention Service
==========================
Handles extraction and storage of politician mentions in news articles.

Features:
- Extract politician mentions from article text
- Fuzzy match names to Politician.slug
- Create ArticlePoliticianMention records
- Query articles by politician efficiently
- Migration utilities for existing data
"""

import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import (
    SessionLocal,
    NewsArticle,
    Politician,
    ArticlePoliticianMention
)

logger = logging.getLogger(__name__)


def extract_and_link_politicians(
    article: NewsArticle,
    db: Session = None,
    use_claude: bool = False
) -> List[Dict]:
    """
    Extract politician mentions from article and create proper links.

    1. Parse existing politicians_json
    2. Fuzzy match each name to Politician.slug
    3. Create ArticlePoliticianMention records
    4. Return list of matched politicians

    Args:
        article: The NewsArticle to process
        db: Database session (optional, will create if not provided)
        use_claude: Whether to use Claude for enhanced extraction (more expensive)

    Returns:
        List of matched politicians with confidence scores
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        mentions = []

        # Get raw politician names from JSON
        raw_names = []
        if article.politicians_json:
            try:
                raw_names = json.loads(article.politicians_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid politicians_json for article {article.article_id}")
                raw_names = []

        if not raw_names:
            return []

        # Get all politicians for matching
        all_politicians = db.query(Politician).all()
        if not all_politicians:
            logger.warning("No politicians in database, cannot link mentions")
            return []

        # Build lookup structures
        politician_by_slug = {p.slug: p for p in all_politicians}
        politician_by_name_lower = {p.name.lower(): p for p in all_politicians}

        # Import fuzzy matching
        try:
            from app.services.fuzzy_match import fuzzy_find_politician
            has_fuzzy = True
        except ImportError:
            has_fuzzy = False
            logger.warning("Fuzzy matching not available, using exact match only")

        for raw_name in raw_names:
            # Skip empty names
            if not raw_name or len(str(raw_name).strip()) < 3:
                continue

            raw_name = str(raw_name).strip()
            matched_politician = None
            match_confidence = 0.0
            extraction_method = "exact"

            # Try exact match first (fast path)
            if raw_name.lower() in politician_by_name_lower:
                matched_politician = politician_by_name_lower[raw_name.lower()]
                match_confidence = 1.0
                extraction_method = "exact"

            # Try fuzzy match
            elif has_fuzzy:
                candidates = [
                    {"slug": p.slug, "name": p.name, "party": p.party}
                    for p in all_politicians
                ]
                match_result = fuzzy_find_politician(raw_name, candidates)

                if match_result:
                    politician_data, score, _ = match_result
                    if score >= 70:  # Threshold for acceptance
                        matched_politician = politician_by_slug.get(politician_data["slug"])
                        match_confidence = score / 100.0
                        extraction_method = "fuzzy"

            if matched_politician:
                # Check if mention already exists
                existing = db.query(ArticlePoliticianMention).filter(
                    ArticlePoliticianMention.article_id == article.article_id,
                    ArticlePoliticianMention.politician_slug == matched_politician.slug
                ).first()

                if existing:
                    # Update existing mention
                    existing.mention_count += 1
                    if match_confidence > existing.confidence:
                        existing.confidence = match_confidence
                else:
                    # Create new mention record
                    mention = ArticlePoliticianMention(
                        article_id=article.article_id,
                        politician_slug=matched_politician.slug,
                        mention_type="mentioned",
                        confidence=match_confidence,
                        matched_name=raw_name,
                        extraction_method=extraction_method,
                        mention_count=1
                    )
                    db.add(mention)

                mentions.append({
                    "slug": matched_politician.slug,
                    "name": matched_politician.name,
                    "matched_from": raw_name,
                    "confidence": match_confidence,
                    "method": extraction_method
                })

        db.commit()
        return mentions

    except Exception as e:
        logger.error(f"Error extracting politicians from article {article.article_id}: {e}")
        db.rollback()
        return []

    finally:
        if close_db:
            db.close()


def migrate_existing_articles(
    batch_size: int = 100,
    limit: int = None
) -> Dict:
    """
    Migrate existing articles' politicians_json to ArticlePoliticianMention table.

    Idempotent: skips articles that already have mentions.

    Args:
        batch_size: Process this many articles at a time
        limit: Maximum articles to process (None for all)

    Returns:
        Stats dictionary with counts
    """
    db = SessionLocal()

    try:
        # Get articles with politicians_json that haven't been migrated
        query = db.query(NewsArticle).filter(
            NewsArticle.politicians_json.isnot(None),
            NewsArticle.politicians_json != "[]",
            NewsArticle.politicians_json != ""
        )

        if limit:
            query = query.limit(limit)

        articles = query.all()

        stats = {
            "total_articles": len(articles),
            "processed": 0,
            "mentions_created": 0,
            "skipped": 0,
            "errors": 0
        }

        for article in articles:
            try:
                # Check if already has mentions
                existing_count = db.query(ArticlePoliticianMention).filter(
                    ArticlePoliticianMention.article_id == article.article_id
                ).count()

                if existing_count > 0:
                    stats["skipped"] += 1
                    continue

                mentions = extract_and_link_politicians(article, db)
                stats["mentions_created"] += len(mentions)
                stats["processed"] += 1

            except Exception as e:
                logger.error(f"Error migrating article {article.article_id}: {e}")
                stats["errors"] += 1

        return stats

    finally:
        db.close()


def get_articles_for_politician(
    politician_slug: str,
    days: int = 30,
    limit: int = 20,
    db: Session = None
) -> List[Dict]:
    """
    Get articles mentioning a politician using the join table.
    Much more efficient than LIKE queries on JSON.

    Args:
        politician_slug: The politician's slug
        days: How far back to look
        limit: Maximum articles to return
        db: Database session (optional)

    Returns:
        List of article dictionaries
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        cutoff = datetime.now() - timedelta(days=days)

        # Query via join table
        mentions = db.query(ArticlePoliticianMention).filter(
            ArticlePoliticianMention.politician_slug == politician_slug
        ).order_by(ArticlePoliticianMention.created_at.desc()).limit(limit * 2).all()

        articles = []
        for m in mentions:
            article = db.query(NewsArticle).filter(
                NewsArticle.article_id == m.article_id,
                NewsArticle.scraped_at >= cutoff
            ).first()

            if article:
                articles.append({
                    "article_id": article.article_id,
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "source_name": article.source_name,
                    "excerpt": article.excerpt[:200] if article.excerpt else None,
                    "mention_type": m.mention_type,
                    "mention_count": m.mention_count,
                    "confidence": m.confidence,
                    "scraped_at": article.scraped_at.isoformat() if article.scraped_at else None
                })

                if len(articles) >= limit:
                    break

        return articles

    finally:
        if close_db:
            db.close()


def get_politician_news_stats(
    politician_slug: str,
    days: int = 7,
    db: Session = None
) -> Dict:
    """
    Get statistics about a politician's news presence.

    Args:
        politician_slug: The politician's slug
        days: How far back to analyze
        db: Database session (optional)

    Returns:
        Dictionary with mention statistics
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        cutoff = datetime.now() - timedelta(days=days)

        # Total mentions in period
        total = db.query(ArticlePoliticianMention).join(
            NewsArticle,
            NewsArticle.article_id == ArticlePoliticianMention.article_id
        ).filter(
            ArticlePoliticianMention.politician_slug == politician_slug,
            NewsArticle.scraped_at >= cutoff
        ).count()

        # By mention type
        by_type = db.query(
            ArticlePoliticianMention.mention_type,
            func.count(ArticlePoliticianMention.id)
        ).join(
            NewsArticle,
            NewsArticle.article_id == ArticlePoliticianMention.article_id
        ).filter(
            ArticlePoliticianMention.politician_slug == politician_slug,
            NewsArticle.scraped_at >= cutoff
        ).group_by(ArticlePoliticianMention.mention_type).all()

        # By source
        by_source = db.query(
            NewsArticle.source_name,
            func.count(ArticlePoliticianMention.id)
        ).join(
            ArticlePoliticianMention,
            NewsArticle.article_id == ArticlePoliticianMention.article_id
        ).filter(
            ArticlePoliticianMention.politician_slug == politician_slug,
            NewsArticle.scraped_at >= cutoff
        ).group_by(NewsArticle.source_name).all()

        return {
            "politician_slug": politician_slug,
            "days": days,
            "total_mentions": total,
            "by_type": {t: c for t, c in by_type},
            "by_source": {s: c for s, c in by_source}
        }

    finally:
        if close_db:
            db.close()


def get_co_mentioned_politicians(
    politician_slug: str,
    days: int = 30,
    limit: int = 10,
    db: Session = None
) -> List[Dict]:
    """
    Find politicians frequently mentioned alongside another.

    Args:
        politician_slug: The primary politician's slug
        days: How far back to analyze
        limit: Maximum co-mentions to return
        db: Database session (optional)

    Returns:
        List of co-mentioned politicians with frequency
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        cutoff = datetime.now() - timedelta(days=days)

        # Get articles mentioning the primary politician
        primary_articles = db.query(ArticlePoliticianMention.article_id).join(
            NewsArticle,
            NewsArticle.article_id == ArticlePoliticianMention.article_id
        ).filter(
            ArticlePoliticianMention.politician_slug == politician_slug,
            NewsArticle.scraped_at >= cutoff
        ).subquery()

        # Find other politicians in those articles
        co_mentions = db.query(
            ArticlePoliticianMention.politician_slug,
            func.count(ArticlePoliticianMention.id).label('count')
        ).filter(
            ArticlePoliticianMention.article_id.in_(primary_articles),
            ArticlePoliticianMention.politician_slug != politician_slug
        ).group_by(
            ArticlePoliticianMention.politician_slug
        ).order_by(
            func.count(ArticlePoliticianMention.id).desc()
        ).limit(limit).all()

        # Get politician details
        results = []
        for slug, count in co_mentions:
            politician = db.query(Politician).filter(
                Politician.slug == slug
            ).first()

            if politician:
                results.append({
                    "slug": slug,
                    "name": politician.name,
                    "party": politician.party,
                    "co_mention_count": count
                })

        return results

    finally:
        if close_db:
            db.close()


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Politician Mention Service")
    parser.add_argument("--migrate", action="store_true", help="Migrate existing articles")
    parser.add_argument("--limit", type=int, default=None, help="Limit articles to process")
    parser.add_argument("--stats", type=str, help="Get stats for politician slug")

    args = parser.parse_args()

    if args.migrate:
        print("Starting migration...")
        stats = migrate_existing_articles(limit=args.limit)
        print(f"\nMigration complete:")
        print(f"  Total articles: {stats['total_articles']}")
        print(f"  Processed: {stats['processed']}")
        print(f"  Mentions created: {stats['mentions_created']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Errors: {stats['errors']}")

    elif args.stats:
        print(f"\nStats for {args.stats}:")
        stats = get_politician_news_stats(args.stats)
        print(f"  Total mentions (7 days): {stats['total_mentions']}")
        print(f"  By type: {stats['by_type']}")
        print(f"  By source: {stats['by_source']}")

    else:
        parser.print_help()
