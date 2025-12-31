"""
Issue Extraction Agent v2
Uses Claude to extract structured issue data from news articles.
Includes retry logic, fallback prompts, and chunking for long articles.
"""
import os
import json
import hashlib
import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Domain categories
ISSUE_DOMAINS = [
    "power", "roads", "security", "water", "health", 
    "education", "economy", "governance", "environment", "transport"
]


def generate_issue_id(title: str, domain: str, date: Optional[datetime] = None) -> str:
    """Generate unique issue ID from title and domain."""
    date_str = (date or datetime.now()).strftime("%Y-%m")
    slug = title.lower().replace(" ", "-")[:30]
    hash_input = f"{domain}-{slug}-{date_str}"
    short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"{domain}-{short_hash}"


def generate_event_id(issue_id: str, source_url: str) -> str:
    """Generate unique event ID."""
    hash_input = f"{issue_id}-{source_url}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]


# ===========================================
# PROMPTS - Simplified and focused
# ===========================================

SIMPLE_EXTRACTION_PROMPT = """Analyze this Nigerian news article and extract issue data.

HEADLINE: {headline}
SOURCE: {source}

TEXT (first 2000 chars):
{text}

---

Is this a trackable political/governance issue? Trackable issues include:
- Infrastructure problems (power outages, bad roads, water shortage)
- Security incidents (kidnapping, terrorism, crime)
- Government failures or policy changes affecting citizens
- Economic crises (fuel scarcity, price hikes)
- Corruption allegations

NOT trackable: pure opinion pieces, campaign speeches, sports, entertainment.

Respond with ONLY this JSON (no markdown, no explanation):
{{"is_trackable": true or false, "domain": "power|roads|security|water|health|education|economy|governance|environment|transport", "severity": "low|moderate|severe", "title": "short issue title max 80 chars", "location": "affected area", "summary": "2 sentence summary", "politicians": [{{"name": "Name", "role": "responsible|responding|mentioned"}}], "confidence": 0.0-1.0}}

If not trackable, respond: {{"is_trackable": false, "reason": "why"}}"""


FALLBACK_PROMPT = """Read this news headline and first paragraph. Extract basic info.

HEADLINE: {headline}

TEXT: {text}

Is this about a Nigerian political/governance issue that affects citizens?

Reply with ONLY JSON:
{{"is_trackable": true/false, "domain": "governance", "title": "short title", "severity": "moderate"}}"""


# ===========================================
# EXTRACTION FUNCTIONS
# ===========================================

def extract_json_from_response(response_text: str) -> Optional[Dict]:
    """Extract JSON from Claude response with multiple strategies."""
    text = response_text.strip()
    
    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract from markdown code block
    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Find first JSON object in text
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Strategy 4: Fix common issues and retry
    # Replace Python-style booleans
    fixed = text.replace("True", "true").replace("False", "false").replace("None", "null")
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    return None


def truncate_text_smartly(text: str, max_chars: int = 2000) -> str:
    """Truncate text at sentence boundary to preserve context."""
    if len(text) <= max_chars:
        return text
    
    # Find last sentence end before max_chars
    truncated = text[:max_chars]
    last_period = truncated.rfind('. ')
    if last_period > max_chars * 0.7:
        return truncated[:last_period + 1]
    return truncated + "..."


async def extract_issue_from_article(
    headline: str,
    text: str,
    source: str = "Unknown",
    date: str = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    Extract structured issue data from a news article.
    Uses simplified prompt and retry logic.
    
    Args:
        headline: Article headline
        text: Article text (will be truncated if too long)
        source: News source name
        date: Publication date
        max_retries: Number of retry attempts
        
    Returns:
        Dict with extracted issue data or {"is_trackable": False}
    """
    from app.services.json_utils import extract_json, ISSUE_EXTRACTION_DEFAULTS
    
    # Truncate text smartly
    truncated_text = truncate_text_smartly(text, 2000)
    
    prompts = [
        # Try 1: Simple extraction prompt
        SIMPLE_EXTRACTION_PROMPT.format(
            headline=headline,
            source=source,
            text=truncated_text
        ),
        # Try 2: Even simpler fallback
        FALLBACK_PROMPT.format(
            headline=headline,
            text=truncated_text[:800]
        ),
    ]
    
    for attempt, prompt in enumerate(prompts[:max_retries]):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0,  # More deterministic
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Use unified JSON parser
            result = extract_json(response_text, default=None)
            
            if result:
                # Validate and normalize result
                result = normalize_extraction_result(result, headline)
                if result.get("is_trackable"):
                    logger.info(f"Extraction success (attempt {attempt + 1}): {result.get('title', headline)[:50]}")
                return result
                
        except Exception as e:
            logger.warning(f"Extraction attempt {attempt + 1} failed: {e}")
            continue
    
    # All attempts failed
    return {"is_trackable": False, "reason": "Extraction failed after retries"}


def normalize_extraction_result(result: Dict, headline: str) -> Dict:
    """Normalize and validate extraction result."""
    if not result.get("is_trackable"):
        return result
    
    # Ensure required fields exist
    result.setdefault("domain", "governance")
    result.setdefault("severity", "moderate")
    result.setdefault("title", headline[:80])
    result.setdefault("location", "Nigeria")
    result.setdefault("summary", "")
    result.setdefault("politicians", [])
    result.setdefault("confidence", 0.5)
    
    # Validate domain
    if result["domain"] not in ISSUE_DOMAINS:
        result["domain"] = "governance"
    
    # Validate severity
    if result["severity"] not in ["low", "moderate", "severe"]:
        result["severity"] = "moderate"
    
    # Normalize politicians list
    if isinstance(result["politicians"], list):
        normalized_pols = []
        for p in result["politicians"]:
            if isinstance(p, dict) and p.get("name"):
                normalized_pols.append({
                    "name": p["name"],
                    "role": p.get("role", "mentioned"),
                    "context": p.get("context", "")
                })
            elif isinstance(p, str):
                normalized_pols.append({"name": p, "role": "mentioned", "context": ""})
        result["politicians"] = normalized_pols
    
    return result


def extract_issue_sync(
    headline: str,
    text: str,
    source: str = "Unknown",
    date: str = None,
) -> Dict[str, Any]:
    """Synchronous version of extract_issue_from_article."""
    import asyncio
    return asyncio.run(extract_issue_from_article(headline, text, source, date))


# ===========================================
# POLITICIAN MATCHING
# ===========================================

async def match_politician_name(name: str, politicians_list: List[Dict]) -> Optional[str]:
    """Match a mentioned name to a politician in the database."""
    name_lower = name.lower()
    
    for pol in politicians_list:
        # Exact match
        if pol["name"].lower() == name_lower:
            return pol["slug"]
        
        # Partial match (last name)
        name_parts = name_lower.split()
        pol_parts = pol["name"].lower().split()
        
        if name_parts and pol_parts and name_parts[-1] in pol_parts:
            return pol["slug"]
        
        # Check aliases if available
        for alias in pol.get("aliases", []):
            if alias.lower() in name_lower or name_lower in alias.lower():
                return pol["slug"]
    
    return None


# ===========================================
# SIMILAR ISSUE DETECTION
# ===========================================

SIMILAR_ISSUE_PROMPT = """Are these the same issue? Reply ONLY with JSON: {{"same": true/false, "merge_id": "id or null"}}

EXISTING ISSUES:
{existing_issues}

NEW ISSUE:
Title: {title}
Domain: {domain}
Location: {location}"""


async def find_similar_issue(
    title: str,
    domain: str,
    location: str,
    summary: str,
    keywords: List[str],
    existing_issues: List[Dict],
) -> Optional[str]:
    """Check if a new issue should be merged with an existing one."""
    if not existing_issues:
        return None
    
    # Filter to same domain only
    same_domain = [i for i in existing_issues if i.get("domain") == domain][:5]
    if not same_domain:
        return None
    
    issues_text = "\n".join([
        f"- ID: {i['issue_id']}, Title: {i['title']}"
        for i in same_domain
    ])
    
    try:
        prompt = SIMILAR_ISSUE_PROMPT.format(
            existing_issues=issues_text,
            title=title,
            domain=domain,
            location=location
        )
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = extract_json_from_response(response.content[0].text)
        
        if result and result.get("same") and result.get("merge_id"):
            return result["merge_id"]
        
        return None
        
    except Exception as e:
        logger.warning(f"Similar issue check failed: {e}")
        return None


# ===========================================
# TEST
# ===========================================

if __name__ == "__main__":
    test_article = """
    Nigeria's national power grid collapsed for the seventh time this year on Sunday, 
    plunging most parts of the country into darkness. The Transmission Company of Nigeria (TCN) 
    confirmed the incident, blaming it on "system disturbance." Power Minister Adebayo Adelabu 
    said the government is working to restore supply. The Nigerian Electricity Regulatory 
    Commission (NERC) said it would investigate the cause. Millions of Nigerians have been 
    affected by the blackout, with businesses and hospitals running on generators.
    """
    
    result = extract_issue_sync(
        headline="National Grid Collapses Again, Plunging Nigeria Into Darkness",
        text=test_article,
        source="Punch NG",
        date="2024-12-29"
    )
    
    print(json.dumps(result, indent=2))
