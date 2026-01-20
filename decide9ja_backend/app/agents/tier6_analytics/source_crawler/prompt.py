"""
SourceCrawlerAgent Prompt
=========================
No LLM prompts needed - this agent just crawls web pages.

This file documents the crawling strategy.
"""

# Source credibility ratings
CREDIBILITY_RATINGS = """
Source Credibility System:

OFFICIAL (Highest Trust)
- INEC (inecnigeria.org) - Election commission
- NASS (nass.gov.ng) - National Assembly
- State government sites
- Use verbatim for election data, official statements

HIGH (Reliable)
- Premium Times - Investigative journalism, fact-based
- Punch - Established newspaper, good fact-checking
- Channels TV - Broadcast journalism standards
- ThisDay - Quality business/political coverage
- The Guardian Nigeria - Balanced reporting

MEDIUM (Use with Caution)
- Vanguard - Good coverage but occasional sensationalism
- The Nation - APC-leaning editorial
- The Sun - Tabloid tendencies
- Use for breaking news, verify claims

LOW (Verify All Claims)
- Blogs and opinion sites
- Social media
- Anonymous sources
- Never use as sole source

Aggregation Rule:
- Single source → mark as "unverified"
- Two high-credibility sources → "likely accurate"
- Official + high source → "verified"
- Contradicting sources → "disputed"
"""

# Content extraction rules
EXTRACTION_RULES = """
Content Extraction Guidelines:

1. Article Detection
   - Look for <article> tags first
   - Fall back to .post, .entry-content, main
   - Skip: navigation, footer, sidebar, ads

2. Text Cleaning
   - Remove script/style tags
   - Strip excessive whitespace
   - Preserve paragraph breaks
   - Limit to 10,000 characters

3. Date Parsing
   - Prefer ISO format (YYYY-MM-DD)
   - Handle Nigerian date formats
   - Mark as null if uncertain

4. Political Filtering
   - Include: politicians, parties, elections, policy
   - Exclude: entertainment, sports (unless political)
   - Gray area: business (include if government-related)

5. Rate Limiting
   - 2 seconds between requests
   - Max 10 articles per source per crawl
   - Respect robots.txt
"""
