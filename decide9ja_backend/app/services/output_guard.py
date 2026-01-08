"""
Output Guard - Response validation based on OpenAI Agent Guardrails pattern.

Validates LLM responses BEFORE sending to users to ensure:
1. Political neutrality (no endorsements)
2. Source citations present for factual claims
3. No hallucinated politician information
4. Appropriate tone for civic engagement

Reference: OpenAI "Practical Guide to Building Agents" - Guardrails section
"""
import os
import logging
import re
from typing import Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OutputValidation:
    """Result of output validation."""
    is_valid: bool
    issues: List[str]
    corrected_response: Optional[str] = None
    confidence: float = 1.0


# ===========================================
# POLITICAL NEUTRALITY PATTERNS
# ===========================================

ENDORSEMENT_PATTERNS = [
    r'\b(you should vote for|vote for|support)\s+\w+',
    r'\b(best candidate|best choice|ideal candidate)\b',
    r'\b(don\'t vote for|never vote for|avoid voting)\b',
    r'\b(will win|is winning|bound to win)\b',
    r'\b(corrupt|terrible|worst)\s+(politician|candidate|leader)\b',
    r'\b(amazing|wonderful|best)\s+(politician|candidate|leader)\b',
]

# Phrases that indicate bias
BIASED_PHRASES = [
    "in my opinion",
    "i think you should",
    "the best option is",
    "clearly the winner",
    "obviously superior",
    "definitely vote",
    "must vote for",
    "the right choice",
    "the wrong choice",
]


def check_political_neutrality(response: str) -> Tuple[bool, List[str]]:
    """
    Check if response maintains political neutrality.

    Returns:
        Tuple of (is_neutral, list_of_issues)
    """
    issues = []
    response_lower = response.lower()

    # Check for endorsement patterns
    for pattern in ENDORSEMENT_PATTERNS:
        if re.search(pattern, response_lower):
            issues.append(f"Potential endorsement detected: pattern '{pattern}'")

    # Check for biased phrases
    for phrase in BIASED_PHRASES:
        if phrase in response_lower:
            issues.append(f"Biased phrase detected: '{phrase}'")

    return len(issues) == 0, issues


def check_source_citations(response: str, requires_sources: bool = True) -> Tuple[bool, List[str]]:
    """
    Check if response includes source citations for factual claims.

    Returns:
        Tuple of (has_sources, list_of_issues)
    """
    issues = []

    if not requires_sources:
        return True, issues

    # Source indicators
    source_indicators = [
        r'\(source:',
        r'\bINEC\b',
        r'\bBudgIT\b',
        r'\bWikipedia\b',
        r'\bWikidata\b',
        r'\bofficial\s+records?\b',
        r'\baccording\s+to\b',
        r'\breported\s+by\b',
        r'\bdata\s+from\b',
        r'\bsource:\s*\w+',
        r'📚',  # Source emoji we use
        r'🔗',  # Link emoji
    ]

    has_source = any(re.search(pattern, response, re.IGNORECASE) for pattern in source_indicators)

    # Check if response makes factual claims
    factual_indicators = [
        r'\d{4}',  # Year mentions
        r'\d+\s*(million|billion|percent|%)',  # Numbers
        r'(elected|appointed|won|lost)\s+in',  # Election results
        r'(senator|governor|minister|representative)\s+(of|for)',  # Titles
        r'(budget|allocation|spending)\s+of',  # Financial claims
    ]

    makes_claims = any(re.search(pattern, response, re.IGNORECASE) for pattern in factual_indicators)

    if makes_claims and not has_source:
        issues.append("Response makes factual claims but lacks source citations")

    return len(issues) == 0, issues


def check_hallucination_risk(response: str, known_politicians: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """
    Check for potential hallucination indicators.

    Returns:
        Tuple of (is_safe, list_of_issues)
    """
    issues = []
    response_lower = response.lower()

    # Uncertainty indicators that suggest the model might be guessing
    uncertainty_phrases = [
        "i believe",
        "i think",
        "probably",
        "might be",
        "could be",
        "not entirely sure",
        "if i recall",
        "from what i remember",
    ]

    # These are warning signs, not blockers
    for phrase in uncertainty_phrases:
        if phrase in response_lower:
            issues.append(f"Uncertainty indicator: '{phrase}' - verify facts")

    # Check for impossible dates (future elections, etc.)
    future_year_match = re.search(r'(election|elected|won|victory)\s+in\s+20(2[6-9]|[3-9]\d)', response_lower)
    if future_year_match:
        issues.append(f"Potential hallucination: future event claimed - {future_year_match.group()}")

    return len(issues) == 0, issues


def validate_response(
    response: str,
    check_neutrality: bool = True,
    check_sources: bool = True,
    check_hallucination: bool = True,
    known_politicians: Optional[List[str]] = None
) -> OutputValidation:
    """
    Comprehensive response validation.

    Args:
        response: The LLM response to validate
        check_neutrality: Whether to check for political neutrality
        check_sources: Whether to check for source citations
        check_hallucination: Whether to check for hallucination indicators
        known_politicians: List of known politician names for validation

    Returns:
        OutputValidation with results
    """
    all_issues = []

    if check_neutrality:
        is_neutral, neutrality_issues = check_political_neutrality(response)
        all_issues.extend(neutrality_issues)

    if check_sources:
        has_sources, source_issues = check_source_citations(response)
        all_issues.extend(source_issues)

    if check_hallucination:
        is_safe, hallucination_issues = check_hallucination_risk(response, known_politicians)
        all_issues.extend(hallucination_issues)

    is_valid = len(all_issues) == 0

    # Log any issues found
    if not is_valid:
        logger.warning(f"Output validation issues: {all_issues}")

    return OutputValidation(
        is_valid=is_valid,
        issues=all_issues,
        confidence=1.0 if is_valid else 0.7
    )


def add_source_reminder(response: str) -> str:
    """
    Add a source reminder if response lacks citations.
    """
    _, issues = check_source_citations(response)

    if issues:
        reminder = "\n\n📚 *Note: For official records, verify with INEC, BudgIT, or government sources.*"
        return response + reminder

    return response


# ===========================================
# QUICK VALIDATION (for high-throughput)
# ===========================================

def quick_validate(response: str) -> bool:
    """
    Fast validation check - returns True if response passes basic checks.
    Use for high-throughput scenarios where detailed validation is too slow.
    """
    response_lower = response.lower()

    # Quick endorsement check
    if any(phrase in response_lower for phrase in ["vote for", "best candidate", "don't vote"]):
        return False

    # Quick bias check
    if any(phrase in response_lower for phrase in ["you should vote", "the right choice"]):
        return False

    return True


# ===========================================
# INTEGRATION HELPER
# ===========================================

async def guard_output(response: str, context: Optional[str] = None) -> str:
    """
    Main entry point for output guardrails.

    Validates response and returns either the original or a modified version.

    Args:
        response: The LLM response to validate
        context: Optional context about the query type

    Returns:
        Validated/modified response
    """
    # Determine what checks to apply based on context
    check_sources = True
    if context and any(word in context.lower() for word in ["greeting", "hello", "help", "menu"]):
        check_sources = False  # Don't require sources for greetings

    validation = validate_response(
        response,
        check_neutrality=True,
        check_sources=check_sources,
        check_hallucination=True
    )

    if validation.is_valid:
        return response

    # If issues found, add source reminder for factual responses
    if any("source" in issue.lower() for issue in validation.issues):
        response = add_source_reminder(response)

    # Log for monitoring
    if validation.issues:
        logger.info(f"Output guard applied modifications. Issues: {validation.issues}")

    return response
