"""
Fact-Check Service for Decide9ja.

Enables users to verify political claims via WhatsApp:
- Submit claims for verification
- Get verdicts with evidence
- Track misinformation patterns
- Alert users to common false claims

All responses are WhatsApp-optimized.
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class Verdict(str, Enum):
    """Fact-check verdict levels."""
    TRUE = "true"                    # Claim is accurate
    MOSTLY_TRUE = "mostly_true"      # Claim is mostly accurate with minor issues
    HALF_TRUE = "half_true"          # Claim is partially true
    MOSTLY_FALSE = "mostly_false"    # Claim contains significant falsehoods
    FALSE = "false"                  # Claim is false
    UNVERIFIABLE = "unverifiable"    # Cannot be verified with available data
    SATIRE = "satire"                # Claim is satire/parody
    OUTDATED = "outdated"            # Was true but no longer accurate


class ClaimCategory(str, Enum):
    """Categories of claims."""
    ELECTION = "election"            # Election-related claims
    POLITICIAN = "politician"        # Claims about politicians
    POLICY = "policy"                # Policy-related claims
    ECONOMY = "economy"              # Economic claims
    SECURITY = "security"            # Security-related claims
    STATISTICS = "statistics"        # Statistical claims
    QUOTE = "quote"                  # Did someone say this?
    VIRAL = "viral"                  # Viral claims/rumours


class SourceCredibility(str, Enum):
    """Source credibility levels."""
    HIGH = "high"                    # Official sources, verified journalists
    MEDIUM = "medium"                # Established media, some verification
    LOW = "low"                      # Unverified sources, social media
    UNKNOWN = "unknown"              # Cannot determine credibility


@dataclass
class FactCheckSource:
    """A source used in fact-checking."""
    name: str
    url: Optional[str] = None
    credibility: SourceCredibility = SourceCredibility.MEDIUM
    date_accessed: datetime = field(default_factory=datetime.utcnow)
    quote: Optional[str] = None


@dataclass
class FactCheck:
    """A completed fact-check."""
    id: str
    claim: str                           # Original claim text
    claim_hash: str                      # Hash for deduplication
    verdict: Verdict
    explanation: str                     # WhatsApp-friendly explanation
    sources: List[FactCheckSource] = field(default_factory=list)
    category: ClaimCategory = ClaimCategory.POLITICIAN
    # Context
    claimant: Optional[str] = None       # Who made the claim
    claim_date: Optional[datetime] = None
    context: Optional[str] = None
    # Metadata
    checked_at: datetime = field(default_factory=datetime.utcnow)
    checked_by: str = "system"
    times_queried: int = 1
    # Tracking
    is_viral: bool = False
    alert_level: str = "normal"          # normal, elevated, critical


@dataclass
class FactCheckRequest:
    """A user's fact-check request."""
    id: str
    user_hash: str
    claim: str
    submitted_at: datetime
    status: str = "pending"              # pending, processing, completed
    result_id: Optional[str] = None


# =============================================================================
# Known False Claims Database
# =============================================================================

KNOWN_FALSE_CLAIMS = [
    {
        "pattern": "nigeria.*largest.*economy.*africa",
        "verdict": Verdict.OUTDATED,
        "explanation": "Nigeria was Africa's largest economy until 2023. As of 2024, South Africa has reclaimed this position due to naira devaluation.",
        "sources": ["IMF World Economic Outlook 2024"]
    },
    {
        "pattern": "(vote|voting).*rigged.*2023",
        "verdict": Verdict.UNVERIFIABLE,
        "explanation": "Claims of rigging in 2023 elections were disputed. Courts upheld results, though some observers noted irregularities. Specific evidence should be evaluated case by case.",
        "sources": ["INEC Official Results", "Election Tribunal Rulings"]
    },
    {
        "pattern": "fuel.*subsidy.*removal.*illegal",
        "verdict": Verdict.FALSE,
        "explanation": "The fuel subsidy removal was enacted by executive order and backed by the Petroleum Industry Act. Courts have not ruled it illegal.",
        "sources": ["Petroleum Industry Act 2021", "Supreme Court rulings"]
    }
]


# =============================================================================
# Fact-Check Service
# =============================================================================

class FactCheckService:
    """
    Service for fact-checking political claims.

    Features:
    - Submit claims for verification
    - Get instant verdicts for known claims
    - Queue new claims for investigation
    - Track misinformation patterns
    - Generate WhatsApp-friendly responses
    """

    def __init__(self):
        self._fact_checks: Dict[str, FactCheck] = {}
        self._pending_requests: Dict[str, FactCheckRequest] = {}
        self._claim_index: Dict[str, str] = {}  # claim_hash -> fact_check_id
        self._viral_claims: List[str] = []

        # Initialize with some known fact-checks
        self._init_known_claims()

    def _init_known_claims(self):
        """Load known fact-checked claims."""
        known_checks = [
            FactCheck(
                id="fc_001",
                claim="The fuel subsidy removal saved Nigeria N8 trillion",
                claim_hash=self._hash_claim("The fuel subsidy removal saved Nigeria N8 trillion"),
                verdict=Verdict.HALF_TRUE,
                explanation="The government claims subsidy removal saves about N8 trillion annually. However, exact savings are disputed — some analysts put the figure lower. The savings also depend on crude oil prices.",
                sources=[
                    FactCheckSource(name="Federal Ministry of Finance", credibility=SourceCredibility.HIGH),
                    FactCheckSource(name="NNPC Financial Reports", credibility=SourceCredibility.HIGH)
                ],
                category=ClaimCategory.ECONOMY,
                is_viral=True
            ),
            FactCheck(
                id="fc_002",
                claim="Nigeria has 36 states",
                claim_hash=self._hash_claim("Nigeria has 36 states"),
                verdict=Verdict.TRUE,
                explanation="Nigeria has 36 states plus the Federal Capital Territory (FCT), Abuja. This has been the case since 1996 when 6 new states were created from existing ones.",
                sources=[
                    FactCheckSource(name="1999 Constitution of Nigeria", credibility=SourceCredibility.HIGH)
                ],
                category=ClaimCategory.STATISTICS
            ),
            FactCheck(
                id="fc_003",
                claim="President Tinubu attended Chicago State University",
                claim_hash=self._hash_claim("President Tinubu attended Chicago State University"),
                verdict=Verdict.TRUE,
                explanation="Chicago State University confirmed that Bola Ahmed Tinubu attended and graduated in 1979. The university provided certified documents to Nigerian courts during election tribunals.",
                sources=[
                    FactCheckSource(name="Chicago State University Official Statement", credibility=SourceCredibility.HIGH),
                    FactCheckSource(name="Presidential Election Tribunal", credibility=SourceCredibility.HIGH)
                ],
                category=ClaimCategory.POLITICIAN
            ),
            FactCheck(
                id="fc_004",
                claim="Minimum wage in Nigeria is N70,000",
                claim_hash=self._hash_claim("Minimum wage in Nigeria is N70,000"),
                verdict=Verdict.MOSTLY_TRUE,
                explanation="The new minimum wage of N70,000 was signed into law in July 2024. However, implementation varies — some states are still negotiating. Federal workers receive it; state implementation is ongoing.",
                sources=[
                    FactCheckSource(name="National Minimum Wage Act 2024", credibility=SourceCredibility.HIGH),
                    FactCheckSource(name="Nigeria Labour Congress", credibility=SourceCredibility.HIGH)
                ],
                category=ClaimCategory.POLICY
            ),
            FactCheck(
                id="fc_005",
                claim="INEC is planning to cancel PVCs for 2027",
                claim_hash=self._hash_claim("INEC is planning to cancel PVCs for 2027"),
                verdict=Verdict.FALSE,
                explanation="INEC has not announced any plan to cancel PVCs. This is misinformation. PVC remains the valid voter card for 2027 elections. Always verify electoral news from INEC's official channels.",
                sources=[
                    FactCheckSource(name="INEC Official Website", credibility=SourceCredibility.HIGH),
                    FactCheckSource(name="INEC Press Releases", credibility=SourceCredibility.HIGH)
                ],
                category=ClaimCategory.ELECTION,
                is_viral=True,
                alert_level="elevated"
            )
        ]

        for fc in known_checks:
            self._fact_checks[fc.id] = fc
            self._claim_index[fc.claim_hash] = fc.id
            if fc.is_viral:
                self._viral_claims.append(fc.id)

    # -------------------------------------------------------------------------
    # Claim Submission
    # -------------------------------------------------------------------------

    def check_claim(
        self,
        claim: str,
        user_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check a claim and return verdict.

        Args:
            claim: The claim text to verify
            user_hash: Optional user identifier for tracking

        Returns:
            Dict with verdict, explanation, and sources
        """
        # Normalize and hash claim
        normalized = self._normalize_claim(claim)
        claim_hash = self._hash_claim(normalized)

        # Check if we have this claim already
        if claim_hash in self._claim_index:
            fc_id = self._claim_index[claim_hash]
            fc = self._fact_checks[fc_id]
            fc.times_queried += 1
            return self._format_verdict(fc)

        # Check against known patterns
        pattern_match = self._check_patterns(claim)
        if pattern_match:
            return pattern_match

        # Check for similar claims (fuzzy matching)
        similar = self._find_similar_claim(normalized)
        if similar:
            similar.times_queried += 1
            return self._format_verdict(similar, is_similar=True)

        # No match - queue for manual review
        request_id = self._queue_for_review(claim, user_hash)

        return {
            "verdict": "pending",
            "explanation": "I haven't verified this specific claim before. I've logged it for review. In the meantime, check official sources or ask about a related topic.",
            "request_id": request_id,
            "tips": [
                "Check if this comes from a verified source",
                "Look for the original statement/document",
                "Be wary of screenshots without sources"
            ]
        }

    def _normalize_claim(self, claim: str) -> str:
        """Normalize claim text for matching."""
        import re
        # Lowercase
        claim = claim.lower()
        # Remove extra whitespace
        claim = re.sub(r'\s+', ' ', claim).strip()
        # Remove punctuation except key ones
        claim = re.sub(r'[^\w\s\-\%\$₦]', '', claim)
        return claim

    def _hash_claim(self, claim: str) -> str:
        """Generate hash for claim deduplication."""
        normalized = self._normalize_claim(claim)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _check_patterns(self, claim: str) -> Optional[Dict]:
        """Check claim against known false claim patterns."""
        import re

        claim_lower = claim.lower()

        for pattern_info in KNOWN_FALSE_CLAIMS:
            if re.search(pattern_info["pattern"], claim_lower):
                return {
                    "verdict": pattern_info["verdict"].value,
                    "verdict_label": self._get_verdict_label(pattern_info["verdict"]),
                    "explanation": pattern_info["explanation"],
                    "sources": pattern_info["sources"],
                    "matched_pattern": True
                }

        return None

    def _find_similar_claim(self, normalized: str) -> Optional[FactCheck]:
        """Find similar claims using fuzzy matching."""
        from difflib import SequenceMatcher

        best_match = None
        best_score = 0.0

        for fc in self._fact_checks.values():
            fc_normalized = self._normalize_claim(fc.claim)
            score = SequenceMatcher(None, normalized, fc_normalized).ratio()

            if score > 0.7 and score > best_score:
                best_score = score
                best_match = fc

        return best_match

    def _queue_for_review(self, claim: str, user_hash: Optional[str]) -> str:
        """Queue a new claim for manual review."""
        request_id = f"req_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._pending_requests)}"

        request = FactCheckRequest(
            id=request_id,
            user_hash=user_hash or "anonymous",
            claim=claim,
            submitted_at=datetime.utcnow()
        )

        self._pending_requests[request_id] = request
        logger.info(f"Queued fact-check request: {request_id}")

        return request_id

    # -------------------------------------------------------------------------
    # Verdict Formatting
    # -------------------------------------------------------------------------

    def _format_verdict(
        self,
        fc: FactCheck,
        is_similar: bool = False
    ) -> Dict[str, Any]:
        """Format fact-check result for API response."""
        return {
            "verdict": fc.verdict.value,
            "verdict_label": self._get_verdict_label(fc.verdict),
            "verdict_emoji": self._get_verdict_emoji(fc.verdict),
            "explanation": fc.explanation,
            "sources": [
                {"name": s.name, "credibility": s.credibility.value}
                for s in fc.sources
            ],
            "category": fc.category.value,
            "claimant": fc.claimant,
            "checked_at": fc.checked_at.isoformat(),
            "is_similar_match": is_similar,
            "is_viral": fc.is_viral,
            "alert_level": fc.alert_level
        }

    def _get_verdict_label(self, verdict: Verdict) -> str:
        """Get human-readable verdict label."""
        labels = {
            Verdict.TRUE: "True",
            Verdict.MOSTLY_TRUE: "Mostly True",
            Verdict.HALF_TRUE: "Half True",
            Verdict.MOSTLY_FALSE: "Mostly False",
            Verdict.FALSE: "False",
            Verdict.UNVERIFIABLE: "Unverifiable",
            Verdict.SATIRE: "Satire",
            Verdict.OUTDATED: "Outdated"
        }
        return labels.get(verdict, "Unknown")

    def _get_verdict_emoji(self, verdict: Verdict) -> str:
        """Get emoji for verdict."""
        emojis = {
            Verdict.TRUE: "✅",
            Verdict.MOSTLY_TRUE: "✔️",
            Verdict.HALF_TRUE: "⚠️",
            Verdict.MOSTLY_FALSE: "⚠️",
            Verdict.FALSE: "❌",
            Verdict.UNVERIFIABLE: "❓",
            Verdict.SATIRE: "😏",
            Verdict.OUTDATED: "⏰"
        }
        return emojis.get(verdict, "❓")

    def format_whatsapp_response(self, result: Dict) -> str:
        """Format fact-check result for WhatsApp."""
        if result.get("verdict") == "pending":
            return f"""🔍 *Fact-Check Pending*

I haven't verified this specific claim yet. I've logged it for review.

*Tips for now:*
• Check if this comes from a verified source
• Look for the original statement
• Be cautious of screenshots without sources

Reply "status {result.get('request_id', '')}" to check later."""

        emoji = result.get("verdict_emoji", "❓")
        label = result.get("verdict_label", "Unknown")
        explanation = result.get("explanation", "")

        sources = result.get("sources", [])
        source_text = ", ".join([s["name"] for s in sources[:3]]) if sources else "Multiple sources"

        response = f"""{emoji} *Verdict: {label}*

{explanation}

📚 Sources: {source_text}"""

        if result.get("is_viral"):
            response += "\n\n⚠️ This claim is being widely shared. Help stop misinformation — share this fact-check."

        response += "\n\n— Tade, Decide9ja"

        return response

    # -------------------------------------------------------------------------
    # Viral Claims & Alerts
    # -------------------------------------------------------------------------

    def get_viral_claims(self, limit: int = 5) -> List[Dict]:
        """Get currently viral claims."""
        viral = []
        for fc_id in self._viral_claims[:limit]:
            fc = self._fact_checks.get(fc_id)
            if fc:
                viral.append({
                    "claim": fc.claim[:100],
                    "verdict": fc.verdict.value,
                    "verdict_label": self._get_verdict_label(fc.verdict),
                    "times_queried": fc.times_queried,
                    "alert_level": fc.alert_level
                })
        return viral

    def get_misinformation_alert(self) -> Optional[str]:
        """Get current misinformation alert if any."""
        # Find critical alerts
        for fc in self._fact_checks.values():
            if fc.alert_level == "critical" and fc.is_viral:
                return f"""🚨 *Misinformation Alert*

A false claim is spreading: "{fc.claim[:80]}..."

{self._get_verdict_emoji(fc.verdict)} This is *{self._get_verdict_label(fc.verdict)}*.

{fc.explanation[:150]}...

Please don't share unverified claims. Reply "verify [claim]" to check any statement.
— Tade"""

        return None

    # -------------------------------------------------------------------------
    # Admin Functions
    # -------------------------------------------------------------------------

    def add_fact_check(
        self,
        claim: str,
        verdict: Verdict,
        explanation: str,
        sources: List[Dict],
        category: ClaimCategory = ClaimCategory.POLITICIAN,
        claimant: Optional[str] = None,
        is_viral: bool = False,
        alert_level: str = "normal"
    ) -> FactCheck:
        """Add a new fact-check (admin function)."""
        fc_id = f"fc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._fact_checks)}"
        claim_hash = self._hash_claim(claim)

        source_objects = [
            FactCheckSource(
                name=s.get("name", "Unknown"),
                url=s.get("url"),
                credibility=SourceCredibility(s.get("credibility", "medium"))
            )
            for s in sources
        ]

        fc = FactCheck(
            id=fc_id,
            claim=claim,
            claim_hash=claim_hash,
            verdict=verdict,
            explanation=explanation,
            sources=source_objects,
            category=category,
            claimant=claimant,
            is_viral=is_viral,
            alert_level=alert_level
        )

        self._fact_checks[fc_id] = fc
        self._claim_index[claim_hash] = fc_id

        if is_viral:
            self._viral_claims.insert(0, fc_id)

        return fc

    def get_pending_requests(self, limit: int = 50) -> List[FactCheckRequest]:
        """Get pending fact-check requests."""
        pending = [r for r in self._pending_requests.values() if r.status == "pending"]
        pending.sort(key=lambda r: r.submitted_at, reverse=True)
        return pending[:limit]

    def complete_request(
        self,
        request_id: str,
        verdict: Verdict,
        explanation: str,
        sources: List[Dict]
    ) -> Optional[FactCheck]:
        """Complete a pending fact-check request."""
        request = self._pending_requests.get(request_id)
        if not request:
            return None

        fc = self.add_fact_check(
            claim=request.claim,
            verdict=verdict,
            explanation=explanation,
            sources=sources
        )

        request.status = "completed"
        request.result_id = fc.id

        return fc

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get fact-checking statistics."""
        verdicts = {}
        for fc in self._fact_checks.values():
            v = fc.verdict.value
            verdicts[v] = verdicts.get(v, 0) + 1

        return {
            "total_fact_checks": len(self._fact_checks),
            "pending_requests": len([r for r in self._pending_requests.values() if r.status == "pending"]),
            "viral_claims": len(self._viral_claims),
            "verdicts_breakdown": verdicts,
            "most_queried": self._get_most_queried(5)
        }

    def _get_most_queried(self, limit: int) -> List[Dict]:
        """Get most frequently queried claims."""
        sorted_fcs = sorted(
            self._fact_checks.values(),
            key=lambda fc: fc.times_queried,
            reverse=True
        )

        return [
            {
                "claim": fc.claim[:80],
                "verdict": fc.verdict.value,
                "times_queried": fc.times_queried
            }
            for fc in sorted_fcs[:limit]
        ]


# =============================================================================
# Singleton Instance
# =============================================================================

_fact_check_service: Optional[FactCheckService] = None


def get_fact_check_service() -> FactCheckService:
    """Get singleton fact-check service instance."""
    global _fact_check_service
    if _fact_check_service is None:
        _fact_check_service = FactCheckService()
    return _fact_check_service
