"""
ResearchOrchestratorAgent Prompt
================================
No LLM prompts needed - this agent uses pure database queries
to determine research priorities.

This file exists for documentation purposes.
"""

# Priority calculation logic (documented here for reference)
PRIORITY_RULES = """
Research Task Prioritization:

PRIORITY 1 - Highest
- Politicians on priority list with NO cache entry
- Reason: Core knowledge gap

PRIORITY 2 - High
- Politicians with stale data (>48 hours old)
- Politicians users asked about (cache misses)
- Reason: Refresh needed or user demand

PRIORITY 3 - Medium
- Trending topics from user queries
- Topics with high cache miss rates
- Reason: Emerging user interest

PRIORITY 4 - Low
- Background refresh of non-priority politicians
- Historical data updates
- Reason: Completeness

Cost Control:
- Maximum 10 tasks per 6-hour cycle
- Full profiles are expensive (LLM extraction)
- Refreshes are cheaper (incremental updates)
- Topic research is cheapest (news crawl only)
"""

# Priority list management (documented)
PRIORITY_LIST_CRITERIA = """
Politicians on the Priority List:

1. 2027 Presidential Candidates
   - APC, PDP, LP, NNPP candidates
   - Vice presidential candidates

2. Current Administration
   - President and VP
   - Key cabinet members
   - Ministers with high visibility

3. Legislative Leadership
   - Senate President, Deputy
   - Speaker, Deputy Speaker
   - Key committee chairs

4. State Governors
   - All 36 governors
   - Priority to: Lagos, Rivers, Kano, FCT

5. Party Leadership
   - National chairmen
   - Key strategists

Update this list quarterly or when major political changes occur.
"""
