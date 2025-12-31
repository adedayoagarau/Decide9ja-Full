"""
Azure Function: News Crawler Timer Trigger
Runs every 2 hours to scrape Nigerian news and store in Azure PostgreSQL.

COST: $0 (uses free tier Azure Functions + existing Azure PostgreSQL)
"""
import logging
from datetime import datetime

try:
    import azure.functions as func
    AZURE_FUNCTIONS_AVAILABLE = True
except ImportError:
    AZURE_FUNCTIONS_AVAILABLE = False

logger = logging.getLogger(__name__)


def run_crawler():
    """
    Main crawler logic - can be called from Azure Function or locally.
    
    1. Crawl Nigerian news sites
    2. Analyze sentiment (free keyword-based)
    3. Store in Azure PostgreSQL (existing, no extra cost)
    """
    from .scraper import scrape_all_sources
    from .sentiment import analyze_sentiment_simple, extract_politicians, extract_topics
    from .database import save_articles, get_article_count

    start_time = datetime.utcnow()
    logger.info(f'🗞️ News crawler started at {start_time.isoformat()}')
    
    try:
        # Step 1: Scrape news from all sources
        articles = scrape_all_sources(max_per_source=10)
        logger.info(f'📰 Scraped {len(articles)} articles')
        
        if not articles:
            logger.warning('⚠️ No articles scraped')
            return {"scraped": 0, "saved": 0}
        
        # Step 2: Enrich articles with sentiment, politicians, topics
        enriched_articles = []
        for article in articles:
            text = article.title + ' ' + (article.excerpt or '')
            
            # Extract entities
            politicians = extract_politicians(text)
            topics = extract_topics(text)
            
            # Simple sentiment analysis (free, keyword-based)
            sentiment, sentiment_score = analyze_sentiment_simple(text)
            
            enriched_articles.append({
                'id': article.id,
                'headline': article.title,
                'excerpt': article.excerpt or '',
                'source': article.source,
                'source_name': article.source_name,
                'url': article.url,
                'date': article.published_date,
                'crawled_at': datetime.utcnow().isoformat(),
                'sentiment': sentiment,
                'sentiment_score': sentiment_score,
                'politicians_mentioned': politicians,
                'topics': topics
            })
        
        # Step 3: Save to Azure PostgreSQL
        saved_count = save_articles(enriched_articles)
        
        # Stats
        total_articles = get_article_count()
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f'✅ Crawler complete: {saved_count} new articles saved')
        logger.info(f'📊 Total articles in DB: {total_articles}')
        logger.info(f'⏱️ Duration: {duration:.1f} seconds')
        
        return {
            "scraped": len(articles),
            "saved": saved_count,
            "total": total_articles,
            "duration": duration
        }
        
    except Exception as e:
        logger.error(f'❌ Crawler error: {str(e)}')
        raise


# Azure Function entry point
if AZURE_FUNCTIONS_AVAILABLE:
    def main(mytimer: func.TimerRequest) -> None:
        """Azure Function timer trigger - runs every 2 hours."""
        
        if mytimer.past_due:
            logger.info('Timer is past due, running anyway')
        
        run_crawler()
