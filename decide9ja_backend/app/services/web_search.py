"""
Web Search Service for Decide9ja.
Uses Serper API for real-time search, with DuckDuckGo as fallback.
"""
import os
import logging
import requests
import aiohttp
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Serper API configuration
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPER_URL = "https://google.serper.dev/search"

# Keywords indicating need for real-time info
REALTIME_KEYWORDS = [
    "today", "yesterday", "this week", "latest", "recent",
    "current", "now", "2024", "2025", "news", "update",
    "just", "happening", "announced", "breaking",
    "this month", "last week"
]

# Trusted Nigerian news sources
TRUSTED_DOMAINS = [
    "premiumtimesng.com", "punchng.com", "thecable.ng",
    "channelstv.com", "vanguardngr.com", "guardian.ng",
    "dailytrust.com", "thenationonlineng.net", "tribuneonlineng.com",
    "leadership.ng", "businessday.ng", "thisdaylive.com"
]


def needs_search(query: str) -> bool:
    """Check if query needs real-time web search."""
    query_lower = query.lower()
    return any(kw in query_lower for kw in REALTIME_KEYWORDS)


def search_sync(query: str, num_results: int = 3) -> str:
    """
    Synchronous web search using Serper API.
    Returns formatted string of results for LLM context.
    """
    if not SERPER_API_KEY:
        logger.warning("Serper API key not configured")
        return ""
    
    try:
        response = requests.post(
            SERPER_URL,
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "q": f"{query} Nigeria politics news",
                "num": num_results + 2,  # Get a few extra to filter
                "gl": "ng",  # Nigeria
                "hl": "en"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"Serper API error: {response.status_code}")
            return ""
        
        data = response.json()
        results = []
        
        for item in data.get("organic", [])[:num_results]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")[:200]
            link = item.get("link", "")
            
            # Prefer trusted sources
            is_trusted = any(domain in link for domain in TRUSTED_DOMAINS)
            source_tag = " ✓" if is_trusted else ""
            
            results.append(f"• {title}{source_tag}: {snippet}")
        
        if results:
            return "*Recent news from the web:*\n" + "\n".join(results)
        
        return ""
        
    except Exception as e:
        logger.error(f"Serper search error: {e}")
        return ""


async def search_async(query: str, num_results: int = 3) -> str:
    """
    Async web search using Serper API.
    """
    if not SERPER_API_KEY:
        return ""
    
    try:
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                SERPER_URL,
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "q": f"{query} Nigeria politics news",
                    "num": num_results + 2,
                    "gl": "ng",
                    "hl": "en"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return ""
                
                data = await response.json()
                results = []
                
                for item in data.get("organic", [])[:num_results]:
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")[:200]
                    results.append(f"• {title}: {snippet}")
                
                if results:
                    return "*Recent news from the web:*\n" + "\n".join(results)
                
                return ""
                
    except Exception as e:
        logger.error(f"Async Serper search error: {e}")
        return ""


def search_news(topic: str) -> str:
    """Search for latest news on a specific topic."""
    return search_sync(f"latest {topic} news", num_results=3)


def search_politician(name: str) -> str:
    """Search for recent news about a politician."""
    return search_sync(f"{name} Nigeria politician news", num_results=3)


def search_tax_news() -> str:
    """Search for latest Tax Reform Bills news."""
    queries = [
        "Nigeria Tax Reform Bill 2024 latest news",
        "VAT derivation bill Northern governors",
        "Tinubu tax bill National Assembly"
    ]
    all_results = []
    for q in queries:
        result = search_sync(q, num_results=2)
        if result:
            all_results.append(result)
    return "\n\n".join(all_results) if all_results else ""


def is_configured() -> bool:
    """Check if web search is properly configured."""
    return bool(SERPER_API_KEY)
