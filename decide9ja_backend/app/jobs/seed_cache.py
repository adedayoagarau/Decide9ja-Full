"""
Initial Cache Seeding - Comprehensive 2027 Stakeholder List
============================================================
Run ONCE (or periodically) to populate base data for Nigerian politicians.

Usage:
    # Dry run - just show the list
    python -m app.jobs.seed_cache --dry-run

    # Full seed (~2-3 hours for 101 politicians)
    python -m app.jobs.seed_cache

    # Seed specific category only
    python -m app.jobs.seed_cache --category governors_current

    # Limit number (for testing)
    python -m app.jobs.seed_cache --limit 10
"""

import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# COMPREHENSIVE 2027 STAKEHOLDER LIST
# =============================================================================

SEED_LIST: Dict[str, List[str]] = {
    "executive_federal": [
        "Bola Ahmed Tinubu",
        "Kashim Shettima",
    ],

    "legislature_leadership": [
        "Godswill Akpabio",
        "Barau Jibrin",
        "Tajudeen Abbas",
        "Benjamin Kalu",
        "Michael Opeyemi Bamidele",
        "Julius Ihonvbere",
        "Kingsley Chinda",
    ],

    "former_presidents": [
        "Muhammadu Buhari",
        "Goodluck Ebele Jonathan",
        "Olusegun Obasanjo",
        "Abdulsalami Abubakar",
        "Ibrahim Badamasi Babangida",
    ],

    "presidential_candidates_2023": [
        "Atiku Abubakar",
        "Peter Obi",
        "Rabiu Musa Kwankwaso",
    ],

    "potential_2027_candidates": [
        "Yemi Osinbajo",
        "Femi Gbajabiamila",
        "Babatunde Raji Fashola",
        "Rotimi Amaechi",
        "Nasir Ahmad El-Rufai",
        "Kayode Fayemi",
        "Bukola Saraki",
        "Ahmed Lawan",
        "Orji Uzor Kalu",
        "Rochas Okorocha",
        "Adams Oshiomhole",
        "Abdullahi Umar Ganduje",
        "Nyesom Wike",
        "Aminu Waziri Tambuwal",
        "Omoyele Sowore",
    ],

    "cabinet_key": [
        "Yusuf Maitama Tuggar",
        "Wale Edun",
        "Prof. Nentawe Goshwe Yilwatda",
        "Lai Mohammed",
        "Festus Keyamo",
        "Boss Mustapha",
        "Abubakar Malami",
        "Rauf Aregbesola",
    ],

    "party_chairmen": [
        "Amb. Iliya Umar Damagun",
        "Barrister Julius Abure",
        "Dr Ajuji Ahmed",
        "Barrister Sylvester Ezeokenwa",
        "Barr. Maxwell Mgbudem",
        "Alh. Shehu Gabam",
        "Mallam Falalu Bello",
        "Engr. Yabagi Yusuf Sani",
        "Uchenna Nnadi",
        "Yusuf Mamman Dantalle",
        "Adekunle Rufai Omoaje",
        "Chief Dan Nwanyanwu",
        "Comrade Bishop Amakiri",
        "Dr Umar Muhammed",
        "Prince (Dr) Chinedu Obi",
    ],

    "governors_current": [
        # South East
        "Alex Otti",
        "Charles Soludo",
        "Hope Uzodinma",
        "Peter Mbah",
        "Francis Nwifuru",

        # South South
        "Umo Eno",
        "Douye Diri",
        "Sheriff Oborevwori",
        "Monday Okpebholo",
        "Bassey Otu",
        "Siminalayi Fubara",

        # South West
        "Babajide Sanwo-Olu",
        "Dapo Abiodun",
        "Lucky Aiyedatiwa",
        "Ademola Adeleke",
        "Seyi Makinde",
        "Biodun Oyebanji",

        # North Central
        "Bala Muhammed",
        "Hyacinth Alia",
        "AbdulRahman AbdulRazaq",
        "Abdullahi Sule",
        "Mohammed Umar Bago",
        "Caleb Mutfwang",
        "Ahmed Usman Ododo",

        # North East
        "Ahmadu Umaru Fintiri",
        "Babagana Umara Zulum",
        "Muhammad Inuwa Yahaya",
        "Umar Namadi",
        "Agbu Kefas",
        "Mai Mala Buni",

        # North West
        "Uba Sani",
        "Abba Kabir Yusuf",
        "Dikko Umaru Radda",
        "Nasir Idris",
        "Ahmad Aliyu",
        "Dauda Lawal",
        "Abdullahi Umar Ganduje",
    ],

    "former_governors_influential": [
        "Okezie Ikpeazu",
        "Ifeanyi Okowa",
        "Samuel Ortom",
        "Yahaya Bello",
        "Seriake Dickson",
        "Peter Ayodele Fayose",
        "Gboyega Oyetola",
        "David B. Mark",
        "Bode George",
    ],
}

# Priority order for seeding (most important first)
PRIORITY_ORDER = [
    "executive_federal",
    "presidential_candidates_2023",
    "potential_2027_candidates",
    "legislature_leadership",
    "governors_current",
    "cabinet_key",
    "former_presidents",
    "party_chairmen",
    "former_governors_influential",
]


def get_seed_list_with_categories() -> List[Dict]:
    """Flatten the seed list with category tags"""
    result = []
    for category, names in SEED_LIST.items():
        for name in names:
            result.append({"name": name, "category": category})
    return result


def get_priority(item: Dict) -> int:
    """Get priority index for sorting"""
    try:
        return PRIORITY_ORDER.index(item["category"])
    except ValueError:
        return 999


async def seed_cache(
    category_filter: str = None,
    limit: int = None,
    skip_existing: bool = True
):
    """
    Seed cache with 2027 stakeholders - prioritized.

    Args:
        category_filter: Only seed this category
        limit: Maximum politicians to process
        skip_existing: Skip politicians already in cache
    """
    from app.agents.registry import registry

    # Import to register agents
    from app.agents.tier6_analytics.source_crawler import SourceCrawlerAgent
    from app.agents.tier6_analytics.data_extractor import DataExtractorAgent
    from app.agents.tier6_analytics.knowledge_cache import KnowledgeCacheAgent

    crawler = registry.get("source_crawler")
    extractor = registry.get("data_extractor")
    cache = registry.get("knowledge_cache")

    if not all([crawler, extractor, cache]):
        logger.error("Failed to load required agents")
        return {"success": 0, "failed": [], "error": "agents_not_loaded"}

    # Get and sort politicians
    all_politicians = get_seed_list_with_categories()
    all_politicians.sort(key=get_priority)

    # Filter by category if specified
    if category_filter:
        all_politicians = [p for p in all_politicians if p["category"] == category_filter]
        if not all_politicians:
            logger.error(f"No politicians in category: {category_filter}")
            return {"success": 0, "failed": [], "error": "invalid_category"}

    # Apply limit
    if limit:
        all_politicians = all_politicians[:limit]

    total = len(all_politicians)
    success = 0
    skipped = 0
    failed = []

    start_time = datetime.utcnow()

    print(f"\n{'='*60}")
    print(f"DECIDE9JA CACHE SEEDING")
    print(f"{'='*60}")
    print(f"Total politicians: {total}")
    print(f"Category filter: {category_filter or 'ALL'}")
    print(f"Skip existing: {skip_existing}")
    print(f"Started: {start_time.isoformat()}")
    print(f"{'='*60}\n")

    current_category = None

    for i, item in enumerate(all_politicians, 1):
        politician = item["name"]
        category = item["category"]

        # Print category header
        if category != current_category:
            current_category = category
            cat_count = len([p for p in all_politicians if p["category"] == category])
            print(f"\n{'='*50}")
            print(f"CATEGORY: {category.upper().replace('_', ' ')} ({cat_count} politicians)")
            print(f"{'='*50}")

        try:
            print(f"\n[{i}/{total}] {politician}")

            # Check if already cached
            if skip_existing:
                existing = await cache.get_politician(politician)
                if existing and not existing.get("is_stale"):
                    print(f"   ⏭️ Already cached (fresh), skipping")
                    skipped += 1
                    continue

            # 1. Crawl sources
            articles = await crawler.crawl_for_entity(politician, max_per_source=3)
            print(f"   📰 Found {len(articles)} articles")

            if not articles:
                print(f"   ⚠️ No articles found")
                failed.append({"name": politician, "category": category, "reason": "no_articles"})
                continue

            # 2. Fetch full content for top 5 articles
            articles_with_content = []
            for article in articles[:5]:
                try:
                    content = await crawler.fetch_article_content(article["url"])
                    if content.get("content") and len(content["content"]) > 100:
                        article["content"] = content["content"]
                        articles_with_content.append(article)
                except Exception as e:
                    logger.debug(f"Failed to fetch {article.get('url')}: {e}")
                    continue

            if not articles_with_content:
                print(f"   ⚠️ No article content extracted")
                failed.append({"name": politician, "category": category, "reason": "no_content"})
                continue

            print(f"   📄 Fetched content from {len(articles_with_content)} articles")

            # 3. Extract structured data with LLM
            print(f"   🤖 Extracting structured data...")
            data = await extractor.extract_politician_data(articles_with_content, politician)

            if not data or not data.get("name"):
                print(f"   ⚠️ Extraction returned empty data")
                failed.append({"name": politician, "category": category, "reason": "extraction_failed"})
                continue

            # Add category metadata
            data["category"] = category
            data["seeded_at"] = datetime.utcnow().isoformat()

            # 4. Save to cache
            sources = [a["url"] for a in articles_with_content]
            await cache.save_politician(politician, data, sources)

            # 5. Save promises separately
            promise_count = 0
            if data.get("promises"):
                await cache.save_promises(politician, data["promises"])
                promise_count = len(data["promises"])

            # 6. Save news items
            news_count = 0
            if data.get("recent_news"):
                for news_item in data["recent_news"]:
                    news_item["politician_name"] = politician
                await cache.save_news(data["recent_news"])
                news_count = len(data["recent_news"])

            print(f"   ✅ Cached: {data.get('party', 'N/A')} | {promise_count} promises | {news_count} news")
            success += 1

            # Rate limiting - be nice to news sites
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Failed to process {politician}: {e}")
            print(f"   ❌ Error: {str(e)[:50]}")
            failed.append({"name": politician, "category": category, "reason": str(e)})
            continue

    # Summary
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*60}")
    print(f"SEEDING COMPLETE")
    print(f"{'='*60}")
    print(f"Duration: {duration/60:.1f} minutes")
    print(f"Success: {success}")
    print(f"Skipped (already cached): {skipped}")
    print(f"Failed: {len(failed)}")
    print(f"Total processed: {success + skipped + len(failed)}/{total}")

    if failed:
        print(f"\n❌ FAILED LIST:")
        for item in failed:
            print(f"   - {item['name']} ({item['category']}): {item['reason']}")

    # Category breakdown
    print(f"\n📊 BY CATEGORY:")
    for category in PRIORITY_ORDER:
        if category_filter and category != category_filter:
            continue
        cat_total = len([p for p in all_politicians if p["category"] == category])
        cat_success = sum(1 for p in all_politicians
                        if p["category"] == category
                        and p["name"] not in [f["name"] for f in failed])
        status = "✅" if cat_success == cat_total else "⚠️"
        print(f"   {status} {category}: {cat_success}/{cat_total}")

    # Get cache stats
    try:
        stats = await cache.get_cache_stats()
        print(f"\n📦 CACHE STATUS:")
        print(f"   Politicians: {stats.get('politicians', {}).get('total', 0)}")
        print(f"   Promises: {stats.get('promises', 0)}")
        print(f"   News: {stats.get('news', 0)}")
    except:
        pass

    return {
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "total": total,
        "duration_seconds": duration
    }


def print_dry_run():
    """Print the full list without seeding"""
    all_politicians = get_seed_list_with_categories()
    all_politicians.sort(key=get_priority)

    total = len(all_politicians)
    print(f"\n{'='*60}")
    print(f"SEED LIST - DRY RUN")
    print(f"{'='*60}")
    print(f"Total politicians: {total}\n")

    for category in PRIORITY_ORDER:
        names = SEED_LIST.get(category, [])
        print(f"{category.upper().replace('_', ' ')} ({len(names)})")
        for name in names:
            print(f"   - {name}")
        print()

    print(f"{'='*60}")
    print(f"CATEGORY COUNTS:")
    for category in PRIORITY_ORDER:
        count = len(SEED_LIST.get(category, []))
        print(f"   {category}: {count}")
    print(f"   TOTAL: {total}")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Decide9ja knowledge cache")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just print the list, don't seed"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=PRIORITY_ORDER,
        help="Only seed this category"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum politicians to process"
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Don't skip already cached politicians"
    )

    args = parser.parse_args()

    if args.dry_run:
        print_dry_run()
    else:
        asyncio.run(seed_cache(
            category_filter=args.category,
            limit=args.limit,
            skip_existing=not args.no_skip
        ))
