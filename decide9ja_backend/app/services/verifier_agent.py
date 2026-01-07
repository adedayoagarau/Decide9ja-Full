"""
Verifier Agent for Decide9ja/Tade Chatbot.

A dedicated agent for verifying information with:
1. Curated source whitelist with trust tiers
2. Cross-checking against knowledge base
3. Balanced framing requirements
4. Honest acknowledgment of gaps

The verifier acts as a guardrail layer before any information reaches users,
ensuring factual accuracy, balanced presentation, and source transparency.

Author: Decide9ja Team
Created: January 2025
"""
import os
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum

logger = logging.getLogger(__name__)


# =============================================================================
# SOURCE TRUST TIERS
# =============================================================================

class TrustTier(IntEnum):
    """Trust levels for information sources."""
    OFFICIAL = 5      # Government sources, official records
    WATCHDOG = 4      # Civil society orgs, verified watchdogs
    VETTED_NEWS = 3   # Established, reputable news outlets
    NEWS = 2          # General news sources
    UNVERIFIED = 1    # User-generated, unverified sources
    BLOCKED = 0       # Blocked/untrusted sources


class SourceCategory(str, Enum):
    """Categories of information sources."""
    GOVERNMENT = "government"
    ELECTORAL = "electoral"
    FINANCIAL = "financial"
    CIVIL_SOCIETY = "civil_society"
    NEWS_TIER1 = "news_tier1"      # Premium news
    NEWS_TIER2 = "news_tier2"      # Established news
    ACADEMIC = "academic"
    INTERNATIONAL = "international"
    BLOCKED = "blocked"


# =============================================================================
# CURATED SOURCE WHITELIST
# =============================================================================

SOURCE_WHITELIST: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # TIER 5: OFFICIAL GOVERNMENT SOURCES
    # =========================================================================
    "inec": {
        "name": "Independent National Electoral Commission (INEC)",
        "domain": "inecnigeria.org",
        "urls": ["https://inecnigeria.org", "https://www.inecnigeria.org"],
        "trust_tier": TrustTier.OFFICIAL,
        "category": SourceCategory.ELECTORAL,
        "data_types": ["election_results", "voter_registration", "electoral_calendar"],
        "api_available": False,
        "notes": "Primary source for all electoral data in Nigeria"
    },
    "nbs": {
        "name": "National Bureau of Statistics",
        "domain": "nigerianstat.gov.ng",
        "urls": ["https://nigerianstat.gov.ng", "https://www.nigerianstat.gov.ng"],
        "trust_tier": TrustTier.OFFICIAL,
        "category": SourceCategory.GOVERNMENT,
        "data_types": ["gdp", "inflation", "unemployment", "trade", "poverty_stats"],
        "api_available": True,
        "notes": "Official statistics agency - primary source for economic data"
    },
    "cbn": {
        "name": "Central Bank of Nigeria",
        "domain": "cbn.gov.ng",
        "urls": ["https://www.cbn.gov.ng", "https://cbn.gov.ng"],
        "trust_tier": TrustTier.OFFICIAL,
        "category": SourceCategory.FINANCIAL,
        "data_types": ["exchange_rate", "interest_rate", "monetary_policy", "inflation"],
        "api_available": True,
        "notes": "Official monetary authority - primary source for financial data"
    },
    "budget_office": {
        "name": "Budget Office of the Federation",
        "domain": "budgetoffice.gov.ng",
        "urls": ["https://budgetoffice.gov.ng"],
        "trust_tier": TrustTier.OFFICIAL,
        "category": SourceCategory.FINANCIAL,
        "data_types": ["federal_budget", "mda_allocations", "capital_expenditure"],
        "api_available": False,
        "notes": "Official source for federal budget documents"
    },
    "nass": {
        "name": "National Assembly",
        "domain": "nassnig.org",
        "urls": ["https://nassnig.org", "https://placng.org"],
        "trust_tier": TrustTier.OFFICIAL,
        "category": SourceCategory.GOVERNMENT,
        "data_types": ["bills", "laws", "legislative_proceedings", "voting_records"],
        "api_available": False,
        "notes": "Official legislative records"
    },
    "state_house": {
        "name": "State House Nigeria",
        "domain": "statehouse.gov.ng",
        "urls": ["https://statehouse.gov.ng"],
        "trust_tier": TrustTier.OFFICIAL,
        "category": SourceCategory.GOVERNMENT,
        "data_types": ["presidential_speeches", "executive_orders", "appointments"],
        "api_available": False,
        "notes": "Official presidential communications"
    },
    "efcc": {
        "name": "Economic and Financial Crimes Commission",
        "domain": "efcc.gov.ng",
        "urls": ["https://efcc.gov.ng"],
        "trust_tier": TrustTier.OFFICIAL,
        "category": SourceCategory.GOVERNMENT,
        "data_types": ["corruption_cases", "convictions", "asset_recovery"],
        "api_available": False,
        "notes": "Anti-corruption agency official records"
    },

    # =========================================================================
    # TIER 4: CIVIL SOCIETY WATCHDOGS
    # =========================================================================
    "budgit": {
        "name": "BudgIT",
        "domain": "yourbudgit.com",
        "urls": ["https://yourbudgit.com", "https://budgit.org"],
        "trust_tier": TrustTier.WATCHDOG,
        "category": SourceCategory.CIVIL_SOCIETY,
        "data_types": ["budget_analysis", "constituency_projects", "state_finances"],
        "api_available": True,
        "notes": "Respected budget transparency org - verified data on public finances"
    },
    "cislac": {
        "name": "Civil Society Legislative Advocacy Centre",
        "domain": "cislac.org",
        "urls": ["https://cislac.org"],
        "trust_tier": TrustTier.WATCHDOG,
        "category": SourceCategory.CIVIL_SOCIETY,
        "data_types": ["legislative_tracking", "corruption_reports", "governance"],
        "api_available": False,
        "notes": "Transparency International Nigeria partner"
    },
    "serap": {
        "name": "Socio-Economic Rights and Accountability Project",
        "domain": "serap-nigeria.org",
        "urls": ["https://serap-nigeria.org"],
        "trust_tier": TrustTier.WATCHDOG,
        "category": SourceCategory.CIVIL_SOCIETY,
        "data_types": ["human_rights", "foi_requests", "court_cases"],
        "api_available": False,
        "notes": "Legal advocacy and FOI-based verification"
    },
    "code": {
        "name": "Connected Development (CODE)",
        "domain": "connecteddevelopment.org",
        "urls": ["https://connecteddevelopment.org"],
        "trust_tier": TrustTier.WATCHDOG,
        "category": SourceCategory.CIVIL_SOCIETY,
        "data_types": ["project_tracking", "community_monitoring"],
        "api_available": False,
        "notes": "Follow The Money - tracks government projects"
    },
    "civic_hive": {
        "name": "Civic Hive",
        "domain": "civichive.org",
        "urls": ["https://civichive.org"],
        "trust_tier": TrustTier.WATCHDOG,
        "category": SourceCategory.CIVIL_SOCIETY,
        "data_types": ["civic_data", "election_monitoring"],
        "api_available": False,
        "notes": "Civic data and democracy monitoring"
    },

    # =========================================================================
    # TIER 3: VETTED NEWS OUTLETS (Tier 1 - Premium)
    # =========================================================================
    "premium_times": {
        "name": "Premium Times",
        "domain": "premiumtimesng.com",
        "urls": ["https://www.premiumtimesng.com"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER1,
        "data_types": ["news", "investigations", "politics"],
        "api_available": False,
        "rss_url": "https://www.premiumtimesng.com/feed",
        "notes": "Award-winning investigative journalism"
    },
    "punch": {
        "name": "Punch Newspapers",
        "domain": "punchng.com",
        "urls": ["https://punchng.com"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER1,
        "data_types": ["news", "politics", "business"],
        "api_available": False,
        "rss_url": "https://punchng.com/feed/",
        "notes": "Nigeria's most widely read newspaper"
    },
    "thecable": {
        "name": "TheCable",
        "domain": "thecable.ng",
        "urls": ["https://www.thecable.ng"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER1,
        "data_types": ["news", "politics", "fact_checks"],
        "api_available": False,
        "rss_url": "https://www.thecable.ng/feed",
        "notes": "Fact-checking arm (TheCable Index)"
    },
    "channels_tv": {
        "name": "Channels Television",
        "domain": "channelstv.com",
        "urls": ["https://www.channelstv.com"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER1,
        "data_types": ["news", "politics", "broadcast"],
        "api_available": False,
        "rss_url": "https://www.channelstv.com/feed/",
        "notes": "Leading TV news station"
    },

    # =========================================================================
    # TIER 3: VETTED NEWS (Tier 2 - Established)
    # =========================================================================
    "guardian_ng": {
        "name": "The Guardian Nigeria",
        "domain": "guardian.ng",
        "urls": ["https://guardian.ng"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER2,
        "data_types": ["news", "politics", "opinion"],
        "api_available": False,
        "rss_url": "https://guardian.ng/feed/",
        "notes": "Established broadsheet"
    },
    "vanguard": {
        "name": "Vanguard",
        "domain": "vanguardngr.com",
        "urls": ["https://www.vanguardngr.com"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER2,
        "data_types": ["news", "politics"],
        "api_available": False,
        "rss_url": "https://www.vanguardngr.com/feed/",
        "notes": "Major daily newspaper"
    },
    "daily_trust": {
        "name": "Daily Trust",
        "domain": "dailytrust.com",
        "urls": ["https://dailytrust.com"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER2,
        "data_types": ["news", "politics"],
        "api_available": False,
        "rss_url": "https://dailytrust.com/feed/",
        "notes": "Northern Nigeria focused"
    },
    "thisday": {
        "name": "ThisDay",
        "domain": "thisdaylive.com",
        "urls": ["https://www.thisdaylive.com"],
        "trust_tier": TrustTier.VETTED_NEWS,
        "category": SourceCategory.NEWS_TIER2,
        "data_types": ["news", "politics", "business"],
        "api_available": False,
        "notes": "Business-focused broadsheet"
    },

    # =========================================================================
    # TIER 4: INTERNATIONAL SOURCES
    # =========================================================================
    "bbc_africa": {
        "name": "BBC Africa",
        "domain": "bbc.com",
        "urls": ["https://www.bbc.com/news/world/africa"],
        "trust_tier": TrustTier.WATCHDOG,
        "category": SourceCategory.INTERNATIONAL,
        "data_types": ["news", "analysis"],
        "api_available": False,
        "notes": "International perspective, fact-checked"
    },
    "reuters_africa": {
        "name": "Reuters Africa",
        "domain": "reuters.com",
        "urls": ["https://www.reuters.com/places/africa"],
        "trust_tier": TrustTier.WATCHDOG,
        "category": SourceCategory.INTERNATIONAL,
        "data_types": ["news", "financial"],
        "api_available": True,
        "notes": "Wire service, highly reliable"
    },

    # =========================================================================
    # TIER 2: GENERAL NEWS (Require Extra Verification)
    # =========================================================================
    "sahara_reporters": {
        "name": "Sahara Reporters",
        "domain": "saharareporters.com",
        "urls": ["https://saharareporters.com"],
        "trust_tier": TrustTier.NEWS,
        "category": SourceCategory.NEWS_TIER2,
        "data_types": ["news", "investigations"],
        "api_available": False,
        "rss_url": "https://saharareporters.com/rss.xml",
        "notes": "Activist journalism - verify claims independently",
        "requires_verification": True
    },

    # =========================================================================
    # BLOCKED SOURCES
    # =========================================================================
    "fake_news_sites": {
        "name": "Blocked - Fake News",
        "domain": "*.fake, *.hoax",
        "urls": [],
        "trust_tier": TrustTier.BLOCKED,
        "category": SourceCategory.BLOCKED,
        "data_types": [],
        "notes": "Placeholder for blocked domains"
    }
}


# =============================================================================
# VERIFICATION RESULT CLASSES
# =============================================================================

class VerificationStatus(str, Enum):
    """Status of verification check."""
    VERIFIED = "verified"           # Confirmed by multiple sources
    PARTIALLY_VERIFIED = "partial"  # Some claims verified
    UNVERIFIED = "unverified"       # Cannot confirm
    CONTRADICTED = "contradicted"   # Evidence contradicts claim
    INSUFFICIENT_DATA = "insufficient"  # Not enough data to verify
    OPINION = "opinion"             # Subjective claim, not verifiable


@dataclass
class VerificationCheck:
    """Single verification check result."""
    claim: str
    status: VerificationStatus
    sources_checked: List[str]
    supporting_sources: List[str]
    contradicting_sources: List[str]
    confidence: float  # 0-1
    notes: str = ""


@dataclass
class VerificationResult:
    """Complete verification result."""
    original_content: str
    overall_status: VerificationStatus
    checks: List[VerificationCheck]
    trust_score: float  # 0-1
    source_tier: TrustTier
    balanced_framing: str  # Rewritten with balance
    gaps_acknowledged: List[str]  # What we don't know
    sources_cited: List[Dict[str, str]]
    verification_timestamp: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        result = asdict(self)
        result["overall_status"] = self.overall_status.value
        result["source_tier"] = int(self.source_tier)
        result["checks"] = [
            {**asdict(c), "status": c.status.value}
            for c in self.checks
        ]
        return result


# =============================================================================
# VERIFIER AGENT
# =============================================================================

class VerifierAgent:
    """
    Agent for verifying information before it reaches users.

    Responsibilities:
    1. Check source trust tier
    2. Cross-reference claims against knowledge base
    3. Ensure balanced framing
    4. Acknowledge gaps honestly
    5. Provide source citations
    """

    def __init__(self):
        """Initialize verifier agent."""
        self._anthropic_client = None
        self._kg = None

    def _get_client(self):
        """Get Anthropic client."""
        if self._anthropic_client is None:
            from anthropic import Anthropic
            self._anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._anthropic_client

    def _get_knowledge_graph(self):
        """Get knowledge graph for cross-referencing."""
        if self._kg is None:
            try:
                from app.services.nigeria_knowledge import get_knowledge_graph
                self._kg = get_knowledge_graph()
            except ImportError:
                logger.warning("Knowledge graph not available")
        return self._kg

    # =========================================================================
    # SOURCE VERIFICATION
    # =========================================================================

    def get_source_trust(self, url: str) -> Tuple[TrustTier, Optional[Dict]]:
        """
        Get trust tier for a source URL.

        Returns:
            Tuple of (TrustTier, source_info or None)
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")

        for key, source in SOURCE_WHITELIST.items():
            if source["trust_tier"] == TrustTier.BLOCKED:
                continue

            source_domain = source.get("domain", "").lower().replace("www.", "")
            if source_domain and (domain == source_domain or domain.endswith("." + source_domain)):
                return source["trust_tier"], source

        # Unknown source
        return TrustTier.UNVERIFIED, None

    def is_source_allowed(self, url: str, min_tier: TrustTier = TrustTier.NEWS) -> bool:
        """Check if source meets minimum trust tier."""
        tier, _ = self.get_source_trust(url)
        return tier >= min_tier

    def get_whitelisted_sources(
        self,
        category: Optional[SourceCategory] = None,
        min_tier: TrustTier = TrustTier.NEWS
    ) -> List[Dict]:
        """Get list of whitelisted sources matching criteria."""
        sources = []
        for key, source in SOURCE_WHITELIST.items():
            if source["trust_tier"] < min_tier:
                continue
            if category and source.get("category") != category:
                continue
            sources.append({
                "key": key,
                **source
            })
        return sorted(sources, key=lambda x: -x["trust_tier"])

    # =========================================================================
    # CLAIM EXTRACTION
    # =========================================================================

    async def extract_claims(self, content: str) -> List[str]:
        """
        Extract verifiable claims from content using Claude.

        Returns list of factual claims that can be verified.
        """
        client = self._get_client()

        prompt = f"""Extract factual claims from this content that can be verified.
Focus on:
- Statistics and numbers
- Events and dates
- Statements attributed to people
- Policy claims
- Comparisons

Ignore:
- Opinions and subjective statements
- Future predictions
- Vague generalizations

Content:
{content[:3000]}

Return JSON array of claims:
[
  "Claim 1...",
  "Claim 2...",
  ...
]

Only return the JSON array, nothing else."""

        try:
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()

            # Parse JSON
            import re
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                return json.loads(match.group(0))
            return []

        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            return []

    # =========================================================================
    # CROSS-CHECKING
    # =========================================================================

    async def cross_check_claim(
        self,
        claim: str,
        sources_to_check: Optional[List[str]] = None
    ) -> VerificationCheck:
        """
        Cross-check a claim against knowledge base and sources.

        Returns VerificationCheck with status and sources.
        """
        supporting = []
        contradicting = []
        checked = []

        # 1. Check against knowledge graph
        kg = self._get_knowledge_graph()
        if kg:
            try:
                from app.services.nigeria_knowledge import query_knowledge
                result = query_knowledge(claim)
                if result and result.success:
                    checked.append("knowledge_graph")
                    # Simple heuristic: if we found relevant data, it's supporting
                    supporting.append("Decide9ja Knowledge Base")
            except Exception as e:
                logger.debug(f"KG check failed: {e}")

        # 2. Check against local database
        try:
            from app.database import SessionLocal, Document
            db = SessionLocal()
            try:
                # Search for relevant documents
                docs = db.query(Document).filter(
                    Document.content.ilike(f'%{claim[:50]}%')
                ).limit(3).all()

                if docs:
                    checked.append("document_db")
                    for doc in docs:
                        supporting.append(f"DB: {doc.title}")
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"DB check failed: {e}")

        # 3. Determine status
        if supporting and not contradicting:
            status = VerificationStatus.VERIFIED
            confidence = min(0.9, 0.5 + (len(supporting) * 0.1))
        elif supporting and contradicting:
            status = VerificationStatus.PARTIALLY_VERIFIED
            confidence = 0.5
        elif contradicting:
            status = VerificationStatus.CONTRADICTED
            confidence = 0.7
        elif checked:
            status = VerificationStatus.UNVERIFIED
            confidence = 0.3
        else:
            status = VerificationStatus.INSUFFICIENT_DATA
            confidence = 0.1

        return VerificationCheck(
            claim=claim,
            status=status,
            sources_checked=checked,
            supporting_sources=supporting,
            contradicting_sources=contradicting,
            confidence=confidence
        )

    # =========================================================================
    # BALANCED FRAMING
    # =========================================================================

    async def create_balanced_framing(
        self,
        content: str,
        verification_checks: List[VerificationCheck]
    ) -> Tuple[str, List[str]]:
        """
        Rewrite content with balanced framing and acknowledge gaps.

        Returns:
            Tuple of (balanced_content, list_of_gaps)
        """
        client = self._get_client()

        # Build context about what was verified
        verified_claims = [c.claim for c in verification_checks if c.status == VerificationStatus.VERIFIED]
        unverified_claims = [c.claim for c in verification_checks if c.status in [
            VerificationStatus.UNVERIFIED, VerificationStatus.INSUFFICIENT_DATA
        ]]
        contradicted_claims = [c.claim for c in verification_checks if c.status == VerificationStatus.CONTRADICTED]

        prompt = f"""You are a neutral political information assistant for Nigeria. Rewrite this content with:

1. BALANCED FRAMING: Present all perspectives fairly. If discussing a politician or policy, include both supporters' and critics' views if known.

2. VERIFIED CLAIMS: These claims have been verified - present them confidently:
{json.dumps(verified_claims, indent=2) if verified_claims else "None verified yet"}

3. UNVERIFIED CLAIMS: These claims could not be verified - use hedging language ("reportedly", "according to..."):
{json.dumps(unverified_claims, indent=2) if unverified_claims else "None"}

4. CONTRADICTED CLAIMS: These claims have contradicting evidence - note the disagreement:
{json.dumps(contradicted_claims, indent=2) if contradicted_claims else "None"}

5. GAPS TO ACKNOWLEDGE: List what information is missing or uncertain.

ORIGINAL CONTENT:
{content[:2000]}

Return JSON:
{{
  "balanced_content": "Rewritten content with balanced framing...",
  "gaps": ["Gap 1...", "Gap 2..."]
}}

Be concise. Maintain factual accuracy. No partisan bias."""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()

            # Parse JSON
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                result = json.loads(match.group(0))
                return result.get("balanced_content", content), result.get("gaps", [])

            return content, ["Could not determine information gaps"]

        except Exception as e:
            logger.error(f"Balanced framing failed: {e}")
            return content, ["Verification process encountered an error"]

    # =========================================================================
    # MAIN VERIFICATION METHOD
    # =========================================================================

    async def verify(
        self,
        content: str,
        source_url: Optional[str] = None,
        source_name: Optional[str] = None
    ) -> VerificationResult:
        """
        Complete verification of content.

        Args:
            content: The content to verify
            source_url: URL of the source
            source_name: Name of the source

        Returns:
            VerificationResult with full verification details
        """
        # 1. Check source trust
        if source_url:
            source_tier, source_info = self.get_source_trust(source_url)
        else:
            source_tier = TrustTier.UNVERIFIED
            source_info = None

        warnings = []

        # Warn if source is low tier
        if source_tier <= TrustTier.NEWS:
            warnings.append(f"Source has trust tier {source_tier.name} - extra verification recommended")

        if source_tier == TrustTier.BLOCKED:
            return VerificationResult(
                original_content=content,
                overall_status=VerificationStatus.UNVERIFIED,
                checks=[],
                trust_score=0.0,
                source_tier=source_tier,
                balanced_framing="[BLOCKED SOURCE - Content not displayed]",
                gaps_acknowledged=["Source is blocked due to trust concerns"],
                sources_cited=[],
                verification_timestamp=datetime.now().isoformat(),
                warnings=["Source is on blocked list"]
            )

        # 2. Extract claims
        claims = await self.extract_claims(content)

        # 3. Cross-check each claim
        checks = []
        for claim in claims[:10]:  # Limit to 10 claims
            check = await self.cross_check_claim(claim)
            checks.append(check)

        # 4. Calculate overall status
        if not checks:
            overall_status = VerificationStatus.INSUFFICIENT_DATA
        else:
            verified_count = sum(1 for c in checks if c.status == VerificationStatus.VERIFIED)
            contradicted_count = sum(1 for c in checks if c.status == VerificationStatus.CONTRADICTED)

            if contradicted_count > 0:
                overall_status = VerificationStatus.CONTRADICTED
            elif verified_count == len(checks):
                overall_status = VerificationStatus.VERIFIED
            elif verified_count > 0:
                overall_status = VerificationStatus.PARTIALLY_VERIFIED
            else:
                overall_status = VerificationStatus.UNVERIFIED

        # 5. Create balanced framing
        balanced_content, gaps = await self.create_balanced_framing(content, checks)

        # 6. Calculate trust score
        base_score = source_tier / TrustTier.OFFICIAL  # 0-1 based on tier
        verification_score = sum(c.confidence for c in checks) / max(len(checks), 1)
        trust_score = (base_score * 0.4) + (verification_score * 0.6)

        # 7. Build sources cited
        sources_cited = []
        if source_info:
            sources_cited.append({
                "name": source_info["name"],
                "tier": source_tier.name,
                "category": source_info.get("category", "unknown")
            })

        for check in checks:
            for source in check.supporting_sources:
                if source not in [s["name"] for s in sources_cited]:
                    sources_cited.append({
                        "name": source,
                        "tier": "KNOWLEDGE_BASE",
                        "category": "internal"
                    })

        return VerificationResult(
            original_content=content,
            overall_status=overall_status,
            checks=checks,
            trust_score=trust_score,
            source_tier=source_tier,
            balanced_framing=balanced_content,
            gaps_acknowledged=gaps,
            sources_cited=sources_cited,
            verification_timestamp=datetime.now().isoformat(),
            warnings=warnings
        )

    # =========================================================================
    # QUICK VERIFICATION (for real-time use)
    # =========================================================================

    def quick_verify_source(self, url: str) -> Dict[str, Any]:
        """
        Quick source verification without full content check.
        Use for real-time filtering.
        """
        tier, info = self.get_source_trust(url)

        return {
            "allowed": tier >= TrustTier.NEWS,
            "trust_tier": tier.name,
            "trust_score": tier / TrustTier.OFFICIAL,
            "source_name": info["name"] if info else "Unknown",
            "category": info.get("category", "unknown") if info else "unknown",
            "requires_verification": info.get("requires_verification", True) if info else True
        }


# =============================================================================
# VERIFICATION PROMPTS FOR SOT
# =============================================================================

VERIFICATION_GUARDRAILS = """
<verification_guardrails>
## Information Verification Standards

### Source Trust Hierarchy (check before citing):
1. TIER 5 - OFFICIAL: INEC, NBS, CBN, Budget Office, NASS (cite confidently)
2. TIER 4 - WATCHDOG: BudgIT, CISLAC, SERAP, BBC, Reuters (cite with credit)
3. TIER 3 - VETTED NEWS: Premium Times, Punch, TheCable, Channels (cite with source)
4. TIER 2 - NEWS: General news outlets (verify before citing)
5. TIER 1 - UNVERIFIED: Social media, blogs (do not cite without verification)

### Before Presenting Information:
1. CHECK SOURCE: Is it from the whitelist? What tier?
2. CROSS-CHECK: Does our knowledge base support this?
3. BALANCE: Are all perspectives represented?
4. GAPS: What don't we know? Be honest.

### Balanced Framing Rules:
- Never present one-sided political views as fact
- Include "supporters say..." AND "critics argue..." when applicable
- Use hedging for unverified claims: "reportedly", "according to sources"
- Distinguish between FACTS, CLAIMS, and OPINIONS

### Honest Gap Acknowledgment:
When information is incomplete, say:
- "I don't have verified data on [X]"
- "This claim hasn't been independently verified"
- "There are conflicting reports about [X]"
- "More recent data may be available from [official source]"

### Citation Format (WhatsApp):
- Official: "According to INEC..."
- Watchdog: "BudgIT reports that..."
- News: "Premium Times reports..." (with note if unverified)
</verification_guardrails>
"""


# =============================================================================
# SINGLETON & TOOL FUNCTION
# =============================================================================

_verifier: Optional[VerifierAgent] = None


def get_verifier() -> VerifierAgent:
    """Get singleton VerifierAgent."""
    global _verifier
    if _verifier is None:
        _verifier = VerifierAgent()
    return _verifier


async def verify_content(
    content: str,
    source_url: Optional[str] = None,
    source_name: Optional[str] = None
) -> VerificationResult:
    """Convenience function for verification."""
    verifier = get_verifier()
    return await verifier.verify(content, source_url, source_name)


def quick_verify_source(url: str) -> Dict[str, Any]:
    """Convenience function for quick source check."""
    verifier = get_verifier()
    return verifier.quick_verify_source(url)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Verifier Agent CLI")
    parser.add_argument("--check-source", type=str, help="Check source trust tier")
    parser.add_argument("--list-sources", action="store_true", help="List whitelisted sources")
    parser.add_argument("--verify", type=str, help="Verify content from file")

    args = parser.parse_args()

    if args.check_source:
        result = quick_verify_source(args.check_source)
        print(json.dumps(result, indent=2))

    elif args.list_sources:
        sources = get_verifier().get_whitelisted_sources()
        print(f"{'Source':<30} {'Tier':<15} {'Category':<20}")
        print("-" * 65)
        for s in sources:
            print(f"{s['name']:<30} {TrustTier(s['trust_tier']).name:<15} {s.get('category', 'N/A'):<20}")

    elif args.verify:
        with open(args.verify, 'r') as f:
            content = f.read()

        async def run_verification():
            result = await verify_content(content)
            print(json.dumps(result.to_dict(), indent=2))

        asyncio.run(run_verification())
