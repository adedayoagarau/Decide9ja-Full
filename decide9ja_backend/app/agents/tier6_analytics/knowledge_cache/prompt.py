"""
KnowledgeCacheAgent Prompt
==========================
No LLM prompts - this agent only does database operations.

This file documents the cache schema and strategies.
"""

# Cache schema documentation
CACHE_SCHEMA = """
Knowledge Cache Schema
======================

1. knowledge_cache (main entity storage)
   - entity_type: 'politician', 'party', 'bill', etc.
   - entity_name: Searchable name
   - data: JSONB with all extracted information
   - sources: Array of source URLs
   - created_at: First cached
   - updated_at: Last refresh

2. promises_cache (denormalized for fast lookup)
   - politician_name: Who made the promise
   - promise_text: The promise itself
   - topic: Categorized topic
   - status: pending, in_progress, kept, broken, unknown
   - status_evidence: Why we assigned this status
   - source_url: Where we found it
   - date_made: When promised
   - created_at, updated_at

3. news_cache (recent articles)
   - politician_name: Who it's about
   - headline: Article headline
   - summary: 2-3 sentence summary
   - source: News outlet name
   - url: UNIQUE - for deduplication
   - published_date: When published
   - sentiment: positive, negative, neutral
   - topic: Categorized topic
   - created_at

4. cache_misses (research prioritization)
   - query_text: What user asked
   - intent_topic: Classified intent
   - query_entity: Specific entity if identified
   - created_at

Indexes:
- knowledge_cache: (entity_type, entity_name), updated_at
- promises_cache: politician_name, topic, status
- news_cache: url (unique), politician_name, published_date
- cache_misses: intent_topic, created_at
"""

# Cache freshness strategy
FRESHNESS_STRATEGY = """
Cache Freshness Strategy
========================

POLITICIAN PROFILES (48 hours)
- Refresh every 2 days
- Basic bio rarely changes
- Position/party changes are newsworthy → caught in news crawl

PROMISES (1 week)
- Status can change based on news
- Check weekly against recent articles
- Keep historical record of status changes

NEWS (6 hours)
- News is time-sensitive
- Don't serve news older than 6 hours as "current"
- Archive for historical reference

CACHE MISSES (24 hours)
- Aggregate daily for research prioritization
- High-frequency misses = high priority research
- Clear older than 30 days
"""

# Query optimization
QUERY_PATTERNS = """
Optimized Query Patterns
========================

1. Politician Lookup
   - First: exact match on entity_name
   - Fallback: regex case-insensitive
   - Index: entity_type + entity_name

2. Promise Search
   - Common: by politician + topic
   - Index: politician_name, topic

3. News Timeline
   - Common: recent by politician
   - Index: politician_name, published_date DESC

4. Cache Miss Aggregation
   - Aggregate by intent_topic
   - Time-windowed (last 24h)
   - Index: intent_topic, created_at
"""
