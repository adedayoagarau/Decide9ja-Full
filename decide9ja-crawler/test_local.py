#!/usr/bin/env python3
"""
Local test script for Decide9ja News Crawler.
Tests scraping, sentiment, and database without Azure Functions runtime.
"""
import os
import sys
import logging
import importlib.util

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Set environment variable
os.environ['DATABASE_URL'] = 'postgresql+psycopg://azureuser:Decide9jaDB2024%21@decide9ja-db.postgres.database.azure.com:5432/postgres?sslmode=require'

# Import modules directly (bypassing __init__.py which needs azure.functions)
def import_module_directly(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base_dir = os.path.dirname(os.path.abspath(__file__))
scraper = import_module_directly("scraper", os.path.join(base_dir, "news_crawler", "scraper.py"))
sentiment = import_module_directly("sentiment", os.path.join(base_dir, "news_crawler", "sentiment.py"))
database = import_module_directly("database", os.path.join(base_dir, "news_crawler", "database.py"))

def main():
    print("=" * 50)
    print("🗞️ DECIDE9JA NEWS CRAWLER TEST")
    print("=" * 50)
    
    # Test 1: Scrape from one source using the backend scraper format
    print("\n📰 Testing scraper (Punch only)...")
    articles = scraper.scrape_source('punch', max_articles=5, fetch_full=False)
    print(f"   Scraped {len(articles)} articles")
    
    if not articles:
        print("   ⚠️ No articles found - site may have changed")
        return
    
    # Test 2: Sentiment analysis
    print("\n🔍 Testing sentiment analysis...")
    article = articles[0]
    text = article.title + ' ' + (article.excerpt or '')
    sent, score = sentiment.analyze_sentiment_simple(text)
    politicians = sentiment.extract_politicians(text)
    topics = sentiment.extract_topics(text)
    
    print(f"   Title: {article.title[:60]}...")
    print(f"   Sentiment: {sent} (score: {score:.2f})")
    print(f"   Politicians: {politicians or 'None'}")
    print(f"   Topics: {topics or 'None'}")
    
    # Test 3: Save to database
    print("\n💾 Testing database save...")
    enriched = []
    for article in articles[:5]:
        text = article.title + ' ' + (article.excerpt or '')
        sent, score = sentiment.analyze_sentiment_simple(text)
        
        enriched.append({
            'id': article.id,
            'headline': article.title,
            'excerpt': article.excerpt or '',
            'source': article.source,
            'source_name': article.source_name,
            'url': article.url,
            'date': article.published_date,
            'sentiment': sent,
            'sentiment_score': score,
            'politicians_mentioned': sentiment.extract_politicians(text),
            'topics': sentiment.extract_topics(text)
        })
    
    saved = database.save_articles(enriched)
    total = database.get_article_count()
    
    print(f"   New articles saved: {saved}")
    print(f"   Total articles in DB: {total}")
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED!")
    print("=" * 50)

if __name__ == "__main__":
    main()
