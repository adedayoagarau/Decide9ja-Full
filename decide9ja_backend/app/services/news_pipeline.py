"""
News Pipeline Service for Decide9ja.
Handles storing, indexing, and retrieving news articles.
"""
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal, NewsArticle, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def store_articles(articles: List[dict], db: Session = None) -> int:
    """
    Store scraped articles in database.
    Returns number of new articles stored.
    
    Handles duplicates gracefully by:
    1. Deduplicating within the batch
    2. Inserting one-by-one with individual error handling
    """
    from sqlalchemy.exc import IntegrityError
    
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    new_count = 0
    skipped_count = 0
    
    try:
        # Deduplicate within the batch by article_id
        seen_ids = set()
        unique_articles = []
        for article_data in articles:
            article_id = article_data.get("id")
            if article_id and article_id not in seen_ids:
                seen_ids.add(article_id)
                unique_articles.append(article_data)
        
        for article_data in unique_articles:
            article_id = article_data.get("id")
            
            # Skip if no ID
            if not article_id:
                continue
            
            try:
                # Check if already exists (fast path)
                existing = db.query(NewsArticle).filter(
                    NewsArticle.article_id == article_id
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create new article
                article = NewsArticle(
                    article_id=article_id,
                    title=article_data.get("title"),
                    url=article_data.get("url"),
                    source=article_data.get("source"),
                    source_name=article_data.get("source_name"),
                    excerpt=article_data.get("excerpt"),
                    full_text=article_data.get("full_text"),
                    politicians_json=json.dumps(article_data.get("politicians_mentioned", [])),
                    topics_json=json.dumps(article_data.get("topics", [])),
                    published_date=article_data.get("published_date"),
                    is_processed=False,
                    is_indexed=False
                )
                
                db.add(article)
                db.flush()  # Flush to catch constraint errors immediately
                new_count += 1

                # Link politicians to this article
                try:
                    from app.services.politician_mention_service import extract_and_link_politicians
                    extract_and_link_politicians(article, db)
                except Exception as link_error:
                    logger.warning(f"Error linking politicians for {article_id}: {link_error}")

                # Ingest into knowledge graph (if available)
                try:
                    from app.services.nigeria_knowledge.news_graph_ingestion import ingest_single_article
                    from app.services.nigeria_knowledge.knowledge_graph import get_knowledge_graph
                    kg = get_knowledge_graph()
                    ingest_single_article(article_id, kg)
                except Exception as kg_error:
                    logger.debug(f"Knowledge graph ingestion skipped: {kg_error}")

            except IntegrityError:
                # Duplicate detected during insert (race condition) - skip gracefully
                db.rollback()
                skipped_count += 1
                logger.debug(f"Skipped duplicate article: {article_id}")
                continue
            except Exception as e:
                # Other errors - rollback this article but continue
                db.rollback()
                logger.warning(f"Error storing article {article_id}: {e}")
                continue
        
        # Final commit for any pending articles
        db.commit()
        logger.info(f"Stored {new_count} new articles (skipped {skipped_count} duplicates)")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in store_articles: {e}")
        raise
    finally:
        if close_db:
            db.close()
    
    return new_count


def index_articles_for_rag(db: Session = None, batch_size: int = 20) -> int:
    """
    Generate embeddings for unindexed articles and mark as indexed.
    Returns number of articles indexed.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        from app.services.embeddings import get_embedding
        
        # Get unindexed articles
        articles = db.query(NewsArticle).filter(
            NewsArticle.is_indexed == False
        ).limit(batch_size).all()
        
        if not articles:
            logger.info("No articles to index")
            return 0
        
        indexed_count = 0
        
        for article in articles:
            try:
                # Generate embedding from title + excerpt
                text = f"{article.title}\n\n{article.excerpt or ''}"
                embedding = get_embedding(text)
                
                if embedding:
                    article.embedding_json = json.dumps(embedding)
                    article.is_indexed = True
                    article.is_processed = True
                    indexed_count += 1
                    
            except Exception as e:
                logger.warning(f"Error indexing article {article.article_id}: {e}")
                continue
        
        db.commit()
        logger.info(f"Indexed {indexed_count} articles for RAG")
        return indexed_count
        
    finally:
        if close_db:
            db.close()


def get_recent_news(
    db: Session = None,
    hours: int = 24,
    limit: int = 10,
    politician: str = None,
    topic: str = None
) -> List[dict]:
    """
    Get recent news articles optionally filtered by politician or topic.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        query = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff
        )
        
        # Filter by politician if specified
        if politician:
            query = query.filter(
                NewsArticle.politicians_json.ilike(f'%{politician}%')
            )
        
        # Filter by topic if specified
        if topic:
            query = query.filter(
                NewsArticle.topics_json.ilike(f'%{topic}%')
            )
        
        articles = query.order_by(NewsArticle.scraped_at.desc()).limit(limit).all()
        
        return [
            {
                "id": a.article_id,
                "title": a.title,
                "url": a.url,
                "source": a.source_name,
                "excerpt": a.excerpt,
                "politicians": json.loads(a.politicians_json or "[]"),
                "topics": json.loads(a.topics_json or "[]"),
                "scraped_at": a.scraped_at.isoformat() if a.scraped_at else None
            }
            for a in articles
        ]
        
    finally:
        if close_db:
            db.close()


def get_news_context_for_rag(query: str, db: Session = None, limit: int = 5) -> str:
    """
    Get formatted news context for RAG responses.
    Searches recent news relevant to the query.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        # Simple keyword search in title and excerpt
        query_lower = query.lower()
        keywords = query_lower.split()
        
        # Get recent articles
        cutoff = datetime.now() - timedelta(hours=72)  # Last 3 days
        
        articles = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff,
            NewsArticle.is_indexed == True
        ).order_by(NewsArticle.scraped_at.desc()).limit(50).all()
        
        # Score by keyword matches
        scored = []
        for article in articles:
            score = 0
            text = f"{article.title} {article.excerpt or ''}".lower()
            
            for keyword in keywords:
                if len(keyword) > 3 and keyword in text:
                    score += 1
            
            if score > 0:
                scored.append((article, score))
        
        # Sort by score and take top results
        scored.sort(key=lambda x: x[1], reverse=True)
        top_articles = [a for a, _ in scored[:limit]]
        
        if not top_articles:
            return ""
        
        # Format for LLM context
        parts = ["*Recent News:*"]
        for article in top_articles:
            parts.append(f"• {article.title} ({article.source_name})")
            if article.excerpt:
                parts.append(f"  {article.excerpt[:200]}...")
        
        return "\n".join(parts)
        
    finally:
        if close_db:
            db.close()


def run_news_pipeline(extract_issues: bool = True, issue_limit: int = 20):
    """
    Complete pipeline: scrape, store, index, and optionally extract issues.
    Called by scheduler.

    Args:
        extract_issues: Whether to run issue extraction on new articles
        issue_limit: Max articles to process for issue extraction per run

    Returns:
        Dict with pipeline results
    """
    try:
        # Try resilient scraper first, fall back to original if unavailable
        try:
            from app.services.news_scraper_resilient import scrape_all_sources, get_source_health
            logger.info("Using resilient news scraper...")
            use_resilient = True
        except ImportError:
            from app.services.news_scraper import scrape_all_sources
            logger.info("Using standard news scraper (resilient scraper not available)...")
            use_resilient = False

        logger.info("Starting news pipeline...")

        # 1. Scrape
        articles = scrape_all_sources(max_per_source=10)
        logger.info(f"Scraped {len(articles)} articles")

        # Log source health if using resilient scraper
        if use_resilient:
            try:
                health = get_source_health()
                unhealthy = [k for k, v in health.items() if not v.get("is_healthy", True)]
                if unhealthy:
                    logger.warning(f"Unhealthy sources: {', '.join(unhealthy)}")
            except Exception:
                pass

        # 2. Store
        article_dicts = [a.to_dict() for a in articles]
        new_count = store_articles(article_dicts)
        logger.info(f"Stored {new_count} new articles")

        # 3. Index for RAG
        indexed = index_articles_for_rag(batch_size=50)
        logger.info(f"Indexed {indexed} articles")

        # 4. Extract issues from new articles (if enabled)
        issues_extracted = 0
        if extract_issues and new_count > 0:
            try:
                from app.services.issue_pipeline import run_issue_extraction_pipeline
                issues = run_issue_extraction_pipeline(limit=issue_limit)
                issues_extracted = len(issues)
                logger.info(f"Extracted {issues_extracted} issues from new articles")
            except ImportError:
                logger.warning("Issue pipeline not available, skipping issue extraction")
            except Exception as e:
                logger.error(f"Issue extraction failed: {e}")

        logger.info("News pipeline complete!")
        return {
            "scraped": len(articles),
            "stored": new_count,
            "indexed": indexed,
            "issues_extracted": issues_extracted
        }

    except Exception as e:
        logger.error(f"News pipeline error: {e}")
        return {"error": str(e)}


def run_news_pipeline_with_worker():
    """
    Run news pipeline with integrated NewsAgent worker.
    This provides continuous processing capability.
    """
    import asyncio

    try:
        from app.services.news_agent import NewsAgent

        # Run standard pipeline first
        result = run_news_pipeline(extract_issues=False)

        # Then use NewsAgent to process articles for issues
        async def process_with_agent():
            with NewsAgent() as agent:
                stats = await agent.process_unprocessed_articles(limit=30)
                return stats

        agent_stats = asyncio.run(process_with_agent())
        result["agent_processed"] = agent_stats.get("processed", 0)
        result["agent_issues"] = agent_stats.get("issues_created", 0)

        return result

    except ImportError:
        logger.warning("NewsAgent not available, using standard pipeline")
        return run_news_pipeline(extract_issues=True)
    except Exception as e:
        logger.error(f"News pipeline with worker error: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="News pipeline operations")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--run", action="store_true", help="Run full pipeline")
    parser.add_argument("--index", action="store_true", help="Index unindexed articles")
    parser.add_argument("--recent", action="store_true", help="Show recent news")
    
    args = parser.parse_args()
    
    if args.init:
        init_db()
        print("Database initialized!")
    
    if args.run:
        result = run_news_pipeline()
        print(f"Pipeline result: {result}")
    
    if args.index:
        count = index_articles_for_rag()
        print(f"Indexed {count} articles")
    
    if args.recent:
        news = get_recent_news(hours=48, limit=10)
        for article in news:
            print(f"\n📰 {article['title']}")
            print(f"   Source: {article['source']}")
