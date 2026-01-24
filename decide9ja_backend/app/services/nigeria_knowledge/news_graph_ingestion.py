"""
News Graph Ingestion Service

Integrates news articles into the Nigeria Knowledge Graph, creating
NEWSPAPER_ARTICLE entities and MENTIONED_IN relationships to politicians.

This enables graph-based queries like:
- "What news mentions Tinubu?" → Traverse MENTIONED_IN edges
- "Who is mentioned in news about elections?" → Pattern matching
- "News about Lagos politicians" → Geographic + political traversal
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any

from app.database import NewsArticle, ArticlePoliticianMention, Politician, SessionLocal
from app.services.nigeria_knowledge.knowledge_graph import (
    NigeriaKnowledgeGraph,
    Entity,
    EntityType,
    Relationship,
    RelationType,
)

logger = logging.getLogger(__name__)


def get_or_create_politician_entity(
    kg: NigeriaKnowledgeGraph,
    politician: Politician
) -> str:
    """
    Ensure a politician exists in the knowledge graph.
    Returns the entity ID.
    """
    entity_id = f"politician_{politician.slug}"

    # Check if already exists
    existing = kg.get_entity(entity_id)
    if existing:
        return entity_id

    # Parse additional data from data_json if available
    properties = {
        "party": politician.party,
        "position": politician.position,
        "state": politician.state,
        "constituency": politician.constituency,
    }

    # Add data from JSON if available
    if politician.data_json:
        try:
            import json
            extra_data = json.loads(politician.data_json)
            properties.update({
                k: v for k, v in extra_data.items()
                if k not in properties and v is not None
            })
        except (json.JSONDecodeError, TypeError):
            pass

    # Create entity
    entity = Entity(
        id=entity_id,
        name=politician.name,
        entity_type=EntityType.POLITICIAN,
        properties=properties,
        aliases=[politician.slug, politician.name.lower()],
        sources=["database"],
        confidence=0.95,
    )

    kg.add_entity(entity)
    logger.debug(f"Added politician to KG: {politician.name}")

    return entity_id


def ingest_article_to_graph(
    article: NewsArticle,
    mentions: List[ArticlePoliticianMention],
    kg: NigeriaKnowledgeGraph,
    db=None
) -> Dict[str, Any]:
    """
    Add a news article to the knowledge graph with politician relationships.

    Args:
        article: NewsArticle database object
        mentions: List of ArticlePoliticianMention linking to politicians
        kg: NigeriaKnowledgeGraph instance
        db: Database session (for politician lookup)

    Returns:
        Dict with ingestion stats
    """
    stats = {
        "article_added": False,
        "relationships_added": 0,
        "politicians_linked": [],
        "errors": [],
    }

    # Create article entity ID
    article_entity_id = f"news_{article.article_id}"

    # Check if already in graph
    if kg.get_entity(article_entity_id):
        stats["article_added"] = False
        return stats

    # Parse publication date
    pub_date = None
    if article.scraped_at:
        pub_date = article.scraped_at.date() if isinstance(article.scraped_at, datetime) else article.scraped_at

    # Create article entity
    article_entity = Entity(
        id=article_entity_id,
        name=article.title or f"Article {article.article_id}",
        entity_type=EntityType.NEWSPAPER_ARTICLE,
        properties={
            "source": article.source,
            "source_name": article.source_name,
            "url": article.url,
            "excerpt": article.excerpt[:500] if article.excerpt else None,
            "published_date": pub_date.isoformat() if pub_date else None,
        },
        aliases=[article.article_id],
        start_date=pub_date,
        sources=[article.source_name or article.source or "news"],
        confidence=0.9,
    )

    kg.add_entity(article_entity)
    stats["article_added"] = True

    # Create relationships to mentioned politicians
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        for mention in mentions:
            try:
                # Get politician from database
                politician = db.query(Politician).filter(
                    Politician.slug == mention.politician_slug
                ).first()

                if not politician:
                    stats["errors"].append(f"Politician not found: {mention.politician_slug}")
                    continue

                # Ensure politician is in graph
                politician_entity_id = get_or_create_politician_entity(kg, politician)

                # Create MENTIONED_IN relationship (politician -> article)
                relationship = Relationship(
                    source_id=politician_entity_id,
                    target_id=article_entity_id,
                    relation_type=RelationType.MENTIONED_IN,
                    properties={
                        "mention_type": mention.mention_type,
                        "confidence": mention.confidence,
                        "matched_name": mention.matched_name,
                        "extraction_method": mention.extraction_method,
                    },
                    start_date=pub_date,
                    sources=[article.source_name or "news"],
                    confidence=mention.confidence or 0.8,
                )

                if kg.add_relationship(relationship):
                    stats["relationships_added"] += 1
                    stats["politicians_linked"].append(mention.politician_slug)

            except Exception as e:
                stats["errors"].append(f"Error linking {mention.politician_slug}: {str(e)}")

    finally:
        if close_db:
            db.close()

    return stats


def ingest_articles_batch(
    articles: List[NewsArticle],
    kg: NigeriaKnowledgeGraph,
    db=None
) -> Dict[str, Any]:
    """
    Ingest a batch of articles into the knowledge graph.

    Args:
        articles: List of NewsArticle objects
        kg: NigeriaKnowledgeGraph instance
        db: Optional database session

    Returns:
        Batch ingestion stats
    """
    batch_stats = {
        "total_articles": len(articles),
        "articles_added": 0,
        "relationships_added": 0,
        "errors": [],
    }

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        for article in articles:
            # Get mentions for this article
            mentions = db.query(ArticlePoliticianMention).filter(
                ArticlePoliticianMention.article_id == article.article_id
            ).all()

            # Ingest article
            result = ingest_article_to_graph(article, mentions, kg, db)

            if result["article_added"]:
                batch_stats["articles_added"] += 1
            batch_stats["relationships_added"] += result["relationships_added"]
            batch_stats["errors"].extend(result["errors"])

    finally:
        if close_db:
            db.close()

    logger.info(
        f"Batch ingestion complete: {batch_stats['articles_added']}/{batch_stats['total_articles']} "
        f"articles, {batch_stats['relationships_added']} relationships"
    )

    return batch_stats


def get_news_for_politician_from_graph(
    politician_slug: str,
    kg: NigeriaKnowledgeGraph,
    limit: int = 10
) -> List[Dict]:
    """
    Get news articles mentioning a politician from the knowledge graph.

    This uses graph traversal instead of database queries.

    Args:
        politician_slug: Politician's slug identifier
        kg: NigeriaKnowledgeGraph instance
        limit: Maximum articles to return

    Returns:
        List of article info dicts
    """
    politician_entity_id = f"politician_{politician_slug}"

    # Check if politician exists in graph
    if not kg.get_entity(politician_entity_id):
        return []

    # Get MENTIONED_IN relationships (outgoing from politician)
    relationships = kg.get_relationships(
        politician_entity_id,
        relation_type=RelationType.MENTIONED_IN,
        direction="outgoing"
    )

    articles = []
    for source_id, target_id, data in relationships[:limit]:
        article_entity = kg.get_entity(target_id)
        if article_entity:
            articles.append({
                "article_id": target_id.replace("news_", ""),
                "title": article_entity.name,
                "source": article_entity.properties.get("source_name"),
                "url": article_entity.properties.get("url"),
                "excerpt": article_entity.properties.get("excerpt"),
                "published_date": article_entity.properties.get("published_date"),
                "mention_type": data.get("mention_type", "mentioned"),
                "confidence": data.get("confidence", 0.8),
            })

    # Sort by date (most recent first)
    articles.sort(
        key=lambda x: x.get("published_date") or "",
        reverse=True
    )

    return articles[:limit]


def get_co_mentioned_politicians_from_graph(
    politician_slug: str,
    kg: NigeriaKnowledgeGraph,
    limit: int = 10
) -> List[Dict]:
    """
    Find politicians frequently mentioned alongside a given politician.

    Uses graph traversal:
    Politician1 -> MENTIONED_IN -> Article <- MENTIONED_IN <- Politician2

    Args:
        politician_slug: Source politician's slug
        kg: NigeriaKnowledgeGraph instance
        limit: Maximum co-mentions to return

    Returns:
        List of co-mentioned politician info with count
    """
    politician_entity_id = f"politician_{politician_slug}"

    if not kg.get_entity(politician_entity_id):
        return []

    # Get all articles mentioning this politician
    relationships = kg.get_relationships(
        politician_entity_id,
        relation_type=RelationType.MENTIONED_IN,
        direction="outgoing"
    )

    article_ids = {target_id for _, target_id, _ in relationships}

    # For each article, find other politicians mentioned
    co_mentions = {}
    for article_id in article_ids:
        # Get incoming MENTIONED_IN edges to this article
        incoming = kg.get_relationships(
            article_id,
            relation_type=RelationType.MENTIONED_IN,
            direction="incoming"
        )

        for source_id, _, data in incoming:
            if source_id != politician_entity_id and source_id.startswith("politician_"):
                slug = source_id.replace("politician_", "")
                if slug not in co_mentions:
                    co_mentions[slug] = {"count": 0, "entity": kg.get_entity(source_id)}
                co_mentions[slug]["count"] += 1

    # Sort by count and format results
    sorted_mentions = sorted(
        co_mentions.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:limit]

    return [
        {
            "politician_slug": slug,
            "name": data["entity"].name if data["entity"] else slug,
            "co_mention_count": data["count"],
            "party": data["entity"].properties.get("party") if data["entity"] else None,
        }
        for slug, data in sorted_mentions
    ]


def sync_database_to_graph(
    kg: NigeriaKnowledgeGraph,
    days_back: int = 30,
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Sync recent news articles from database to knowledge graph.

    Call this periodically to keep the graph up to date with new articles.

    Args:
        kg: NigeriaKnowledgeGraph instance
        days_back: How many days of articles to sync
        limit: Maximum articles to process

    Returns:
        Sync statistics
    """
    from datetime import timedelta

    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days_back)

        # Get recent articles with politician mentions
        articles = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff
        ).order_by(
            NewsArticle.scraped_at.desc()
        ).limit(limit).all()

        logger.info(f"Syncing {len(articles)} articles to knowledge graph")

        return ingest_articles_batch(articles, kg, db)

    finally:
        db.close()


# Convenience function for single article ingestion
def ingest_single_article(article_id: str, kg: NigeriaKnowledgeGraph) -> Dict:
    """
    Ingest a single article by ID.

    Args:
        article_id: NewsArticle.article_id
        kg: NigeriaKnowledgeGraph instance

    Returns:
        Ingestion result
    """
    db = SessionLocal()
    try:
        article = db.query(NewsArticle).filter(
            NewsArticle.article_id == article_id
        ).first()

        if not article:
            return {"error": f"Article not found: {article_id}"}

        mentions = db.query(ArticlePoliticianMention).filter(
            ArticlePoliticianMention.article_id == article_id
        ).all()

        return ingest_article_to_graph(article, mentions, kg, db)

    finally:
        db.close()
