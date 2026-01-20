"""
ClassifierAgent
===============
Classifies user intent and extracts entities.

COST OPTIMIZATION:
- Use rules for obvious intents (greetings, help, etc.) - FREE
- Use small/fast model for ambiguous cases - CHEAP
- Cache classification results
"""

from typing import Tuple, Dict, List
import re
import logging

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


class Intent:
    """All possible intents"""
    # Greetings & Basic
    GREETING = "greeting"
    HELP = "help"
    THANKS = "thanks"
    GOODBYE = "goodbye"

    # Representation
    REP_LOOKUP = "rep_lookup"
    POLITICIAN_INFO = "politician_info"
    POLITICIAN_CONTACT = "politician_contact"
    POLITICIAN_NEWS = "politician_news"

    # Promises
    PROMISE_LOOKUP = "promise_lookup"
    PROMISE_STATUS = "promise_status"
    PROMISE_COMPARE = "promise_compare"

    # Elections 2027
    CANDIDATE_SEARCH = "candidate_search"
    CANDIDATE_FOLLOW = "candidate_follow"
    CANDIDATE_UNFOLLOW = "candidate_unfollow"
    CANDIDATE_COMPARE = "candidate_compare"
    MY_CANDIDATES = "my_candidates"
    ELECTION_INFO = "election_info"
    VOTER_REGISTRATION = "voter_registration"
    POLLING_UNIT = "polling_unit"

    # News & Trending
    NEWS_QUERY = "news_query"
    TRENDING = "trending"

    # Issues
    REPORT_ISSUE = "report_issue"
    TRACK_ISSUE = "track_issue"
    MY_ISSUES = "my_issues"

    # Location-based
    LOCATION_SHARED = "location_shared"
    FIND_NEARBY = "find_nearby"

    # Engagement
    MY_POINTS = "my_points"
    LEADERBOARD = "leaderboard"
    SUBSCRIBE_DIGEST = "subscribe_digest"
    UNSUBSCRIBE_DIGEST = "unsubscribe_digest"

    # Verification
    FACT_CHECK = "fact_check"

    # Unknown
    UNKNOWN = "unknown"


@register_agent
class ClassifierAgent(BaseAgent):
    name = "classifier"
    description = "Intent classification and entity extraction"
    tier = AgentTier.ENTRY
    cost_level = CostLevel.CHEAP  # Small model when needed
    handled_intents = ["__all__"]

    # Rule-based patterns (NO LLM needed) - compile for performance
    PATTERNS = {
        Intent.GREETING: [
            r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|yo|sup)\b",
            r"^(wetin dey|how far|bawo ni|kedu|sannu)\b",
        ],
        Intent.HELP: [
            r"^(help|menu|options|what can you do|commands)\b",
            r"^(wetin you fit do|how you work)\b",
        ],
        Intent.THANKS: [
            r"(thank|thanks|cheers|appreciated|dalu|e se|nagode)\b",
        ],
        Intent.GOODBYE: [
            r"^(bye|goodbye|see you|later|quit|exit)\b",
        ],
        Intent.REP_LOOKUP: [
            r"(who\s*(is|are)|find)\s*(my|the|our)?\s*(senator|rep|representative|governor|councillor)",
            r"(who\s*represents?|who\s*governs?)",
            r"(my\s*(rep|senator|governor|representative))",
        ],
        Intent.POLITICIAN_INFO: [
            r"(tell me about|who is|info on|profile of)\s+([A-Z][a-z]+(\s+[A-Z][a-z]+)*)",
        ],
        Intent.ELECTION_INFO: [
            r"(when|what)\s*(is|are)?\s*(the)?\s*(election|voting|vote)",
            r"(2027|next\s*election)",
        ],
        Intent.VOTER_REGISTRATION: [
            r"(how|where)\s*(do|can)?\s*(i|we)?\s*(register|get pvc)",
            r"(voter\s*registration|pvc|inec)",
        ],
        Intent.POLLING_UNIT: [
            r"(polling\s*unit|where\s*(do)?\s*(i|we)?\s*vote)",
        ],
        Intent.CANDIDATE_SEARCH: [
            r"(who|which|what)\s*(is|are)?\s*(running|candidates?)\s*(for)?",
        ],
        Intent.CANDIDATE_FOLLOW: [
            r"^follow\s+",
        ],
        Intent.CANDIDATE_UNFOLLOW: [
            r"^unfollow\s+",
        ],
        Intent.CANDIDATE_COMPARE: [
            r"(compare|vs|versus)\s+([A-Z][a-z]+)\s*(and|vs|versus)?\s*([A-Z][a-z]+)?",
        ],
        Intent.MY_CANDIDATES: [
            r"(my\s*candidates?|who\s*(am|do)\s*i\s*follow)",
        ],
        Intent.PROMISE_LOOKUP: [
            r"(what|which)\s*(did)?\s*([A-Z][a-z]+)?\s*(promise|pledg)",
            r"(promise|manifesto|agenda|plan)\s*(of|for|by)?",
        ],
        Intent.PROMISE_STATUS: [
            r"(did|has)\s+([A-Z][a-z]+)\s*(kept|deliver|fulfill)",
        ],
        Intent.NEWS_QUERY: [
            r"(what|any)\s*(is|are)?\s*(the)?\s*(news|happening)",
            r"(latest|recent|current)\s*(news|updates?|stories?)",
        ],
        Intent.TRENDING: [
            r"(what.*(trending|hot))|trending",
        ],
        Intent.REPORT_ISSUE: [
            r"(report|there\s*is|we\s*have)\s*(a|an)?\s*(problem|issue|bad|no|broken)",
            r"(bad\s*road|no\s*water|no\s*light|flooding|sewage|garbage)",
            r"(i\s*want\s*to\s*report|let\s*me\s*report)",
        ],
        Intent.TRACK_ISSUE: [
            r"(track|status|update)\s*(my|the)?\s*(issue|report)",
        ],
        Intent.MY_ISSUES: [
            r"(my\s*issues?|my\s*reports?)",
        ],
        Intent.FACT_CHECK: [
            r"(is\s*it\s*true|verify|fact[\s-]*check|real\s*or\s*fake)",
            r"(did\s+[A-Z][a-z]+\s+really)",
        ],
        Intent.MY_POINTS: [
            r"(my\s*points?|my\s*score|civic\s*score)",
        ],
        Intent.LEADERBOARD: [
            r"(leaderboard|top\s*citizens?|rankings?)",
        ],
        Intent.SUBSCRIBE_DIGEST: [
            r"(subscribe|sign\s*up|get\s*updates?|daily\s*digest)",
        ],
        Intent.UNSUBSCRIBE_DIGEST: [
            r"(unsubscribe|stop\s*updates?|no\s*more)",
        ],
        Intent.LOCATION_SHARED: [
            r"^(this\s*is\s*my\s*location|here\s*i\s*am|i\s*am\s*here)$",
            r"(my\s*location|where\s*i\s*(am|live))$",
        ],
        Intent.FIND_NEARBY: [
            r"(what|where)\s*(is|are)?\s*(near|around|close\s*to)\s*(me|here)",
            r"(nearby|around\s*me|close\s*by)",
            r"(polling\s*unit|hospital|school|market)\s*(near|around|close)",
        ],
    }

    # Known Nigerian politicians for entity extraction
    KNOWN_POLITICIANS = [
        "tinubu", "atiku", "obi", "sanwo-olu", "wike",
        "el-rufai", "fubara", "shettima", "okowa",
        "kwankwaso", "ayu", "lawan", "gbajabiamila"
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return True

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # 1. Check cache
        cached = await self._check_cache(input)
        if cached:
            return self._tag_analytics(input, cached)

        # Get multimodal context from gatekeeper (if available)
        multimodal_context = input.context.get("multimodal_context", {}) if input.context else {}
        modality = input.context.get("modality", "text") if input.context else "text"

        # Use effective text (transcribed or raw)
        text = input.context.get("effective_text", input.raw_text).strip() if input.context else input.raw_text.strip()

        # 2. Check for multimodal-derived intents (FREE)
        multimodal_intent = self._classify_multimodal(modality, multimodal_context, text)
        if multimodal_intent:
            intent, confidence, entities = multimodal_intent
            output = AgentOutput(
                success=True,
                handoff_to="router",
                data={
                    "intent": intent,
                    "confidence": confidence,
                    "entities": entities,
                    "method": "multimodal",
                    "modality": modality,
                },
                cost_level=CostLevel.FREE
            )
            return self._tag_analytics(input, output)

        # 3. Try rule-based classification (FREE)
        intent, confidence, entities = self._classify_by_rules(text)

        if confidence >= 0.8:
            # High confidence from rules - no LLM needed
            output = AgentOutput(
                success=True,
                handoff_to="router",
                data={
                    "intent": intent,
                    "confidence": confidence,
                    "entities": entities,
                    "method": "rules",
                    "modality": modality,
                },
                cost_level=CostLevel.FREE
            )
            await self._save_cache(input, output)
            return self._tag_analytics(input, output)

        # 4. Low confidence - could use LLM here for ambiguous cases
        # For now, return best guess from rules
        output = AgentOutput(
            success=True,
            handoff_to="router",
            data={
                "intent": intent or Intent.UNKNOWN,
                "confidence": confidence,
                "entities": entities,
                "method": "rules_lowconf",
                "modality": modality,
            },
            cost_level=CostLevel.FREE
        )

        return self._tag_analytics(input, output)

    def _classify_multimodal(
        self,
        modality: str,
        multimodal_context: dict,
        text: str
    ) -> tuple[str, float, dict] | None:
        """
        Classify based on multimodal context.
        Returns (intent, confidence, entities) or None if no clear classification.
        """
        entities = {}

        # Image with issue evidence → REPORT_ISSUE
        if modality in ("image", "image_with_caption"):
            if multimodal_context.get("is_issue_evidence"):
                entities["issue_category"] = multimodal_context.get("issue_category")
                entities["image_description"] = multimodal_context.get("description", "")
                entities["has_image_evidence"] = True
                return Intent.REPORT_ISSUE, 0.9, entities

            # Image of politician → POLITICIAN_INFO
            politicians = multimodal_context.get("politicians_detected", [])
            if politicians:
                entities["politician"] = politicians[0]
                entities["detected_from_image"] = True
                return Intent.POLITICIAN_INFO, 0.85, entities

            # Document image with detected text - analyze the text
            detected_text = multimodal_context.get("detected_text", "")
            if detected_text and len(detected_text) > 20:
                # Check if it's election/voter related document
                text_lower = detected_text.lower()
                if any(kw in text_lower for kw in ["inec", "voter", "election", "pvc", "polling"]):
                    return Intent.ELECTION_INFO, 0.8, {"detected_from_document": True}
                if any(kw in text_lower for kw in ["budget", "allocation", "project"]):
                    return Intent.PROMISE_STATUS, 0.75, {"detected_from_document": True}

        # Location shared without text → LOCATION_SHARED
        if modality == "location":
            is_nigeria = multimodal_context.get("is_nigeria", False)
            entities["latitude"] = multimodal_context.get("latitude")
            entities["longitude"] = multimodal_context.get("longitude")
            entities["state"] = multimodal_context.get("state", "")
            entities["lga"] = multimodal_context.get("lga", "")
            entities["is_nigeria"] = is_nigeria

            # If no meaningful text, it's a pure location share
            if not text or len(text.strip()) < 5:
                return Intent.LOCATION_SHARED, 0.95, entities

            # Location + text mentioning polling/voting → POLLING_UNIT
            text_lower = text.lower()
            if any(kw in text_lower for kw in ["polling", "vote", "where do i vote"]):
                return Intent.POLLING_UNIT, 0.9, entities

            # Location + text mentioning issues → REPORT_ISSUE with location context
            if any(kw in text_lower for kw in ["bad", "broken", "no water", "no light", "problem", "issue"]):
                return Intent.REPORT_ISSUE, 0.85, entities

        # Voice note - already transcribed, will be classified by rules
        # But if transcription failed, we can handle gracefully
        if modality == "voice_note":
            if multimodal_context.get("transcription_error"):
                entities["transcription_failed"] = True
                return Intent.HELP, 0.5, entities

        return None

    def _classify_by_rules(self, text: str) -> Tuple[str, float, Dict]:
        """Rule-based classification - no LLM cost"""
        text_lower = text.lower()
        entities = {}

        # Check each intent's patterns
        for intent, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    # Extract entities based on intent
                    self._extract_entities(text, intent, entities)
                    # Return with high confidence for strong matches
                    return intent, 0.85, entities

        # Check for politician names (might indicate politician_info intent)
        for name in self.KNOWN_POLITICIANS:
            if name in text_lower:
                entities["politician"] = name
                return Intent.POLITICIAN_INFO, 0.75, entities

        # Try to extract any capitalized names as potential entities
        self._extract_potential_names(text, entities)

        # Unknown - low confidence
        return Intent.UNKNOWN, 0.3, entities

    def _extract_entities(self, text: str, intent: str, entities: Dict):
        """Extract entities based on intent type"""
        text_lower = text.lower()

        # Extract politician name
        for name in self.KNOWN_POLITICIANS:
            if name in text_lower:
                entities["politician"] = name
                break

        # Extract office type for rep_lookup
        if intent == Intent.REP_LOOKUP:
            if "senator" in text_lower:
                entities["office"] = "senator"
            elif "governor" in text_lower:
                entities["office"] = "governor"
            elif "rep" in text_lower or "representative" in text_lower:
                entities["office"] = "representative"
            elif "councillor" in text_lower:
                entities["office"] = "councillor"

        # Extract issue type for report_issue
        if intent == Intent.REPORT_ISSUE:
            if "road" in text_lower:
                entities["issue_type"] = "road"
            elif "water" in text_lower:
                entities["issue_type"] = "water"
            elif "light" in text_lower or "electricity" in text_lower or "nepa" in text_lower:
                entities["issue_type"] = "electricity"
            elif "security" in text_lower or "crime" in text_lower:
                entities["issue_type"] = "security"
            elif "sanitation" in text_lower or "garbage" in text_lower:
                entities["issue_type"] = "sanitation"

        # Extract state mentions
        states = [
            "lagos", "abuja", "kano", "rivers", "oyo", "kaduna", "enugu",
            "delta", "edo", "anambra", "imo", "abia", "akwa ibom", "cross river"
        ]
        for state in states:
            if state in text_lower:
                entities["state"] = state.title()
                break

    def _extract_potential_names(self, text: str, entities: Dict):
        """Extract capitalized names as potential entities"""
        matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        # Filter out common words
        common = {"I", "What", "Who", "How", "When", "Where", "Please", "Thanks"}
        names = [m for m in matches if m not in common]
        if names:
            entities["potential_names"] = names
