"""
Issue Pipeline Service
Processes news articles through the issue extraction agent and stores results.
"""
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.database import SessionLocal, Issue, IssueEvent, PoliticianIssue, NewsArticle, Politician
from app.services.issue_agent import (
    extract_issue_sync,
    generate_issue_id,
    generate_event_id,
    find_similar_issue,
    match_politician_name,
)

logger = logging.getLogger(__name__)


def get_all_politicians() -> List[Dict]:
    """Get all politicians for name matching."""
    db = SessionLocal()
    try:
        politicians = db.query(Politician).all()
        return [
            {
                "slug": p.slug,
                "name": p.name,
                "aliases": json.loads(p.data_json or "{}").get("aliases", [])
            }
            for p in politicians
        ]
    finally:
        db.close()


def get_active_issues(domain: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Get active issues for similarity matching."""
    db = SessionLocal()
    try:
        query = db.query(Issue).filter(Issue.status == "active")
        if domain:
            query = query.filter(Issue.domain == domain)
        
        issues = query.order_by(Issue.last_updated.desc()).limit(limit).all()
        return [
            {
                "issue_id": i.issue_id,
                "title": i.title,
                "domain": i.domain,
                "location": i.location,
            }
            for i in issues
        ]
    finally:
        db.close()


def store_issue(issue_data: Dict, extraction: Dict) -> str:
    """
    Store or update an issue from extraction results.
    
    Args:
        issue_data: Issue dict from extraction
        extraction: Full extraction result
        
    Returns:
        issue_id of stored/updated issue
    """
    db = SessionLocal()
    try:
        # Check for similar existing issue
        existing_issues = get_active_issues(domain=issue_data.get("domain"))
        
        import asyncio
        similar_id = asyncio.run(find_similar_issue(
            title=issue_data.get("title", ""),
            domain=issue_data.get("domain", ""),
            location=issue_data.get("location", ""),
            summary=issue_data.get("summary", ""),
            keywords=extraction.get("similar_issue_keywords", []),
            existing_issues=existing_issues,
        ))
        
        if similar_id:
            # Update existing issue
            issue = db.query(Issue).filter(Issue.issue_id == similar_id).first()
            if issue:
                issue.event_count = (issue.event_count or 0) + 1
                issue.source_count = (issue.source_count or 0) + 1
                issue.last_updated = datetime.now()
                
                # Update confidence (weighted average)
                new_conf = extraction.get("confidence", 0.5)
                issue.confidence = (issue.confidence * 0.7) + (new_conf * 0.3)
                
                db.commit()
                return similar_id
        
        # Create new issue
        issue_id = generate_issue_id(
            title=issue_data.get("title", "Unknown Issue"),
            domain=issue_data.get("domain", "governance"),
        )
        
        new_issue = Issue(
            issue_id=issue_id,
            title=issue_data.get("title", "Unknown Issue"),
            domain=issue_data.get("domain", "governance"),
            severity=issue_data.get("severity", "moderate"),
            status="active",
            location=issue_data.get("location"),
            states_json=json.dumps(issue_data.get("states", [])),
            summary=issue_data.get("summary"),
            first_reported=datetime.now(),
            confidence=extraction.get("confidence", 0.5),
            event_count=1,
            source_count=1,
        )
        
        db.add(new_issue)
        db.commit()
        
        logger.info(f"Created new issue: {issue_id} - {new_issue.title}")
        return issue_id
        
    except Exception as e:
        logger.error(f"Failed to store issue: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def store_event(
    issue_id: str,
    event_data: Dict,
    article: NewsArticle,
    politicians: List[Dict],
    confidence: float = 0.5,
) -> str:
    """
    Store an event linked to an issue.
    
    Args:
        issue_id: ID of parent issue
        event_data: Event dict from extraction
        article: Source article
        politicians: List of politician dicts from extraction
        confidence: Confidence score
        
    Returns:
        event_id of stored event
    """
    db = SessionLocal()
    try:
        event_id = generate_event_id(issue_id, article.url)
        
        # Check if event already exists
        existing = db.query(IssueEvent).filter(IssueEvent.event_id == event_id).first()
        if existing:
            return event_id
        
        # Extract politician slugs
        all_politicians = get_all_politicians()
        politician_slugs = []
        
        for pol in politicians:
            import asyncio
            slug = asyncio.run(match_politician_name(pol.get("name", ""), all_politicians))
            if slug:
                politician_slugs.append(slug)
                
                # Create politician-issue link
                link_politician_to_issue(slug, issue_id, pol.get("role", "mentioned"))
        
        new_event = IssueEvent(
            event_id=event_id,
            issue_id=issue_id,
            title=event_data.get("title", article.title),
            description=event_data.get("description"),
            event_date=datetime.now(),  # Could parse from article
            event_type=event_data.get("event_type", "news"),
            source_url=article.url,
            source_name=article.source_name,
            article_id=article.article_id,
            politicians_json=json.dumps(politician_slugs),
            confidence=confidence,
        )
        
        db.add(new_event)
        db.commit()
        
        logger.info(f"Stored event: {event_id} for issue {issue_id}")
        return event_id
        
    except Exception as e:
        logger.error(f"Failed to store event: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def link_politician_to_issue(politician_slug: str, issue_id: str, role: str = "mentioned"):
    """Create or update politician-issue link."""
    db = SessionLocal()
    try:
        # Check existing link
        existing = db.query(PoliticianIssue).filter(
            PoliticianIssue.politician_slug == politician_slug,
            PoliticianIssue.issue_id == issue_id,
        ).first()
        
        if existing:
            existing.mention_count = (existing.mention_count or 1) + 1
            existing.last_mentioned = datetime.now()
            # Upgrade role if more significant
            role_priority = {"responsible": 4, "responding": 3, "affected": 2, "mentioned": 1}
            if role_priority.get(role, 1) > role_priority.get(existing.role, 1):
                existing.role = role
        else:
            new_link = PoliticianIssue(
                politician_slug=politician_slug,
                issue_id=issue_id,
                role=role,
            )
            db.add(new_link)
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to link politician: {e}")
        db.rollback()
    finally:
        db.close()


def process_article_for_issues(article: NewsArticle) -> Optional[str]:
    """
    Process a single news article through the issue extraction pipeline.
    
    Args:
        article: NewsArticle to process
        
    Returns:
        issue_id if issue was created/updated, None otherwise
    """
    try:
        # Extract issue data using Claude
        extraction = extract_issue_sync(
            headline=article.title,
            text=article.full_text or article.excerpt or "",
            source=article.source_name,
            date=article.published_date,
        )
        
        if not extraction.get("is_trackable"):
            logger.debug(f"Article not trackable: {article.title[:50]}... - {extraction.get('reason')}")
            # Still mark as processed
            db = SessionLocal()
            try:
                db_article = db.query(NewsArticle).filter(NewsArticle.article_id == article.article_id).first()
                if db_article:
                    db_article.is_processed = True
                    db.commit()
            finally:
                db.close()
            return None
        
        # Handle both old format (nested issue) and new format (flat)
        if "issue" in extraction:
            issue_data = extraction.get("issue", {})
        else:
            # New format - data is at root level
            issue_data = {
                "title": extraction.get("title", article.title),
                "domain": extraction.get("domain", "governance"),
                "severity": extraction.get("severity", "moderate"),
                "location": extraction.get("location"),
                "states": extraction.get("states", []),
                "summary": extraction.get("summary", ""),
            }
        
        event_data = extraction.get("event", {"title": article.title})
        politicians = extraction.get("politicians", [])
        confidence = extraction.get("confidence", 0.5)
        
        # Store issue
        issue_id = store_issue(issue_data, extraction)
        
        # Store event
        store_event(issue_id, event_data, article, politicians, confidence)
        
        # Mark article as processed
        db = SessionLocal()
        try:
            db_article = db.query(NewsArticle).filter(NewsArticle.article_id == article.article_id).first()
            if db_article:
                db_article.is_processed = True
                db.commit()
        finally:
            db.close()
        
        return issue_id
        
    except Exception as e:
        logger.error(f"Failed to process article {article.article_id}: {e}")
        return None


def run_issue_extraction_pipeline(limit: int = 50):
    """
    Run issue extraction on unprocessed articles.
    Called by scheduler.
    """
    db = SessionLocal()
    try:
        # Get unprocessed articles (either full_text or excerpt is enough)
        from sqlalchemy import or_
        articles = db.query(NewsArticle).filter(
            NewsArticle.is_processed == False,
            or_(NewsArticle.full_text.isnot(None), NewsArticle.excerpt.isnot(None)),
        ).order_by(NewsArticle.scraped_at.desc()).limit(limit).all()
        
        logger.info(f"Processing {len(articles)} articles for issues")
        
        created_issues = []
        for article in articles:
            issue_id = process_article_for_issues(article)
            if issue_id:
                created_issues.append(issue_id)
        
        logger.info(f"Extracted {len(created_issues)} issues from {len(articles)} articles")
        return created_issues
        
    finally:
        db.close()


def get_issue_with_events(issue_id: str) -> Optional[Dict]:
    """Get issue with full event timeline."""
    db = SessionLocal()
    try:
        issue = db.query(Issue).filter(Issue.issue_id == issue_id).first()
        if not issue:
            return None
        
        events = db.query(IssueEvent).filter(
            IssueEvent.issue_id == issue_id
        ).order_by(IssueEvent.event_date.desc()).all()
        
        # Get linked politicians
        links = db.query(PoliticianIssue).filter(
            PoliticianIssue.issue_id == issue_id
        ).all()
        
        politician_data = []
        for link in links:
            pol = db.query(Politician).filter(Politician.slug == link.politician_slug).first()
            if pol:
                politician_data.append({
                    "slug": pol.slug,
                    "name": pol.name,
                    "party": pol.party,
                    "position": pol.position,
                    "role": link.role,
                    "mention_count": link.mention_count,
                })
        
        return {
            "issue_id": issue.issue_id,
            "title": issue.title,
            "domain": issue.domain,
            "severity": issue.severity,
            "status": issue.status,
            "location": issue.location,
            "states": json.loads(issue.states_json or "[]"),
            "summary": issue.summary,
            "confidence": issue.confidence,
            "verified": issue.verified,
            "event_count": issue.event_count,
            "first_reported": issue.first_reported.isoformat() if issue.first_reported else None,
            "last_updated": issue.last_updated.isoformat() if issue.last_updated else None,
            "events": [
                {
                    "event_id": e.event_id,
                    "title": e.title,
                    "description": e.description,
                    "event_date": e.event_date.isoformat() if e.event_date else None,
                    "event_type": e.event_type,
                    "source_url": e.source_url,
                    "source_name": e.source_name,
                }
                for e in events
            ],
            "politicians": politician_data,
        }
        
    finally:
        db.close()


def list_issues(
    domain: Optional[str] = None,
    state: Optional[str] = None,
    severity: Optional[str] = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """List issues with optional filters."""
    db = SessionLocal()
    try:
        query = db.query(Issue)
        
        if status:
            query = query.filter(Issue.status == status)
        if domain:
            query = query.filter(Issue.domain == domain)
        if severity:
            query = query.filter(Issue.severity == severity)
        if state:
            query = query.filter(Issue.states_json.contains(state))
        
        issues = query.order_by(Issue.last_updated.desc()).offset(offset).limit(limit).all()
        
        return [
            {
                "issue_id": i.issue_id,
                "title": i.title,
                "domain": i.domain,
                "severity": i.severity,
                "status": i.status,
                "location": i.location,
                "event_count": i.event_count,
                "confidence": i.confidence,
                "verified": i.verified,
                "last_updated": i.last_updated.isoformat() if i.last_updated else None,
            }
            for i in issues
        ]
        
    finally:
        db.close()


def get_issues_for_politician(politician_slug: str) -> List[Dict]:
    """Get all issues linked to a politician."""
    db = SessionLocal()
    try:
        links = db.query(PoliticianIssue).filter(
            PoliticianIssue.politician_slug == politician_slug
        ).order_by(PoliticianIssue.last_mentioned.desc()).all()
        
        issues = []
        for link in links:
            issue = db.query(Issue).filter(Issue.issue_id == link.issue_id).first()
            if issue:
                issues.append({
                    "issue_id": issue.issue_id,
                    "title": issue.title,
                    "domain": issue.domain,
                    "severity": issue.severity,
                    "role": link.role,
                    "mention_count": link.mention_count,
                    "last_updated": issue.last_updated.isoformat() if issue.last_updated else None,
                })
        
        return issues
        
    finally:
        db.close()
