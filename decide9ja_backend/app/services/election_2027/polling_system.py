"""
Polling System
==============

Constituency-based polling system for 2027 elections.

Features:
1. Create polls targeted to specific constituencies
2. Push polls to relevant users
3. Collect and store responses (anonymized)
4. Compute and display results
5. Track trends over time

Poll Types:
- Voting Intention: "Who will you vote for president?"
- Approval Rating: "How would you rate Governor X's performance?"
- Issue Importance: "What's the most important issue for you?"
- Prediction: "Who do you think will win the Lagos governorship?"
"""
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json


@dataclass
class PollOption:
    """A poll option/choice."""
    id: str
    text: str
    candidate_id: Optional[int] = None
    emoji: str = ""


@dataclass
class PollDefinition:
    """A poll definition."""
    id: str
    title: str
    question: str
    poll_type: str  # voting_intention, approval, issue, prediction
    options: List[PollOption]

    # Targeting
    target_level: str = "national"  # national, state, senatorial, etc.
    target_values: List[str] = field(default_factory=list)

    # For position-specific polls
    position: Optional[str] = None  # president, governor, senator
    position_state: Optional[str] = None
    position_constituency: Optional[str] = None

    # Timing
    is_active: bool = True
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None


@dataclass
class PollResult:
    """Computed poll results."""
    poll_id: str
    total_responses: int
    results: Dict[str, float]  # option_id -> percentage
    results_by_state: Dict[str, Dict[str, float]] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)


# === SAMPLE POLLS FOR 2027 ===

SAMPLE_POLLS = {
    "pres_intention_jan2026": PollDefinition(
        id="pres_intention_jan2026",
        title="2027 Presidential Voting Intention - January 2026",
        question="If the 2027 presidential election were held today, who would you vote for?",
        poll_type="voting_intention",
        options=[
            PollOption("tinubu", "Bola Tinubu (APC)", emoji="🟢"),
            PollOption("atiku", "Atiku Abubakar (PDP)", emoji="🔴"),
            PollOption("obi", "Peter Obi (LP)", emoji="🟡"),
            PollOption("kwankwaso", "Rabiu Kwankwaso (NNPP)", emoji="🔵"),
            PollOption("other", "Other / Undecided", emoji="⚪"),
        ],
        position="president",
        target_level="national"
    ),

    "tinubu_approval_jan2026": PollDefinition(
        id="tinubu_approval_jan2026",
        title="President Tinubu Approval Rating - January 2026",
        question="How would you rate President Tinubu's performance so far?",
        poll_type="approval",
        options=[
            PollOption("excellent", "Excellent", emoji="🌟"),
            PollOption("good", "Good", emoji="👍"),
            PollOption("average", "Average", emoji="😐"),
            PollOption("poor", "Poor", emoji="👎"),
            PollOption("very_poor", "Very Poor", emoji="❌"),
        ],
        target_level="national"
    ),

    "top_issue_2027": PollDefinition(
        id="top_issue_2027",
        title="Most Important Issue for 2027",
        question="What is the MOST important issue for you in the 2027 elections?",
        poll_type="issue",
        options=[
            PollOption("economy", "Economy/Cost of Living", emoji="💰"),
            PollOption("security", "Security/Safety", emoji="🛡️"),
            PollOption("education", "Education", emoji="📚"),
            PollOption("health", "Healthcare", emoji="🏥"),
            PollOption("corruption", "Fighting Corruption", emoji="⚖️"),
            PollOption("infrastructure", "Infrastructure", emoji="🏗️"),
            PollOption("employment", "Jobs/Employment", emoji="💼"),
        ],
        target_level="national"
    ),

    "lagos_gov_prediction": PollDefinition(
        id="lagos_gov_prediction",
        title="Lagos 2027 Governorship Prediction",
        question="Who do you think will win the Lagos State governorship in 2027?",
        poll_type="prediction",
        options=[
            PollOption("apc", "APC Candidate", emoji="🟢"),
            PollOption("pdp", "PDP Candidate", emoji="🔴"),
            PollOption("lp", "Labour Party Candidate", emoji="🟡"),
            PollOption("unsure", "Too early to say", emoji="❓"),
        ],
        position="governor",
        position_state="Lagos",
        target_level="state",
        target_values=["Lagos"]
    ),
}


class PollingSystem:
    """
    Main polling system for managing polls and collecting responses.
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self.polls = SAMPLE_POLLS.copy()
        self.responses = {}  # In-memory for now, would be in DB

    # === POLL MANAGEMENT ===

    def create_poll(self, poll: PollDefinition) -> str:
        """Create a new poll."""
        self.polls[poll.id] = poll
        return poll.id

    def get_poll(self, poll_id: str) -> Optional[PollDefinition]:
        """Get a poll by ID."""
        return self.polls.get(poll_id)

    def get_active_polls(self) -> List[PollDefinition]:
        """Get all active polls."""
        return [p for p in self.polls.values() if p.is_active]

    def get_polls_for_user(
        self,
        user_state: str = None,
        user_lga: str = None,
        user_senatorial: str = None,
        user_federal_const: str = None
    ) -> List[PollDefinition]:
        """
        Get polls relevant to a user based on their location.
        """
        relevant = []

        for poll in self.get_active_polls():
            if poll.target_level == "national":
                relevant.append(poll)

            elif poll.target_level == "state" and user_state:
                if not poll.target_values or user_state in poll.target_values:
                    relevant.append(poll)

            elif poll.target_level == "senatorial" and user_senatorial:
                if not poll.target_values or user_senatorial in poll.target_values:
                    relevant.append(poll)

            elif poll.target_level == "federal_constituency" and user_federal_const:
                if not poll.target_values or user_federal_const in poll.target_values:
                    relevant.append(poll)

            elif poll.target_level == "lga" and user_lga:
                if not poll.target_values or user_lga in poll.target_values:
                    relevant.append(poll)

        return relevant

    # === RESPONSE COLLECTION ===

    def submit_response(
        self,
        poll_id: str,
        option_id: str,
        user_phone_hash: str,
        user_state: str = None,
        user_lga: str = None,
        user_senatorial: str = None,
        user_federal_const: str = None
    ) -> Tuple[bool, str]:
        """
        Submit a poll response.

        Returns:
            (success, message)
        """
        poll = self.get_poll(poll_id)
        if not poll:
            return False, "Poll not found"

        if not poll.is_active:
            return False, "This poll has ended"

        # Check if option is valid
        valid_options = [o.id for o in poll.options]
        if option_id not in valid_options:
            return False, "Invalid option"

        # Check if user already voted
        response_key = f"{poll_id}:{user_phone_hash}"
        if response_key in self.responses:
            return False, "You have already voted in this poll"

        # Store response
        self.responses[response_key] = {
            "poll_id": poll_id,
            "option_id": option_id,
            "user_hash": user_phone_hash,
            "user_state": user_state,
            "user_lga": user_lga,
            "user_senatorial": user_senatorial,
            "user_federal_const": user_federal_const,
            "timestamp": datetime.now().isoformat()
        }

        return True, "Vote recorded! Thank you for participating."

    def has_voted(self, poll_id: str, user_phone_hash: str) -> bool:
        """Check if user has voted in a poll."""
        return f"{poll_id}:{user_phone_hash}" in self.responses

    # === RESULTS COMPUTATION ===

    def compute_results(self, poll_id: str) -> Optional[PollResult]:
        """Compute results for a poll."""
        poll = self.get_poll(poll_id)
        if not poll:
            return None

        # Get all responses for this poll
        poll_responses = [
            r for r in self.responses.values()
            if r["poll_id"] == poll_id
        ]

        total = len(poll_responses)
        if total == 0:
            return PollResult(
                poll_id=poll_id,
                total_responses=0,
                results={o.id: 0.0 for o in poll.options}
            )

        # Count by option
        option_counts = {o.id: 0 for o in poll.options}
        for r in poll_responses:
            option_counts[r["option_id"]] += 1

        # Calculate percentages
        results = {
            opt_id: round((count / total) * 100, 1)
            for opt_id, count in option_counts.items()
        }

        # By state
        results_by_state = {}
        for r in poll_responses:
            state = r.get("user_state", "Unknown")
            if state not in results_by_state:
                results_by_state[state] = {o.id: 0 for o in poll.options}
            results_by_state[state][r["option_id"]] += 1

        # Convert state counts to percentages
        for state, counts in results_by_state.items():
            state_total = sum(counts.values())
            if state_total > 0:
                results_by_state[state] = {
                    opt_id: round((count / state_total) * 100, 1)
                    for opt_id, count in counts.items()
                }

        return PollResult(
            poll_id=poll_id,
            total_responses=total,
            results=results,
            results_by_state=results_by_state
        )

    # === FORMATTING FOR DISPLAY ===

    def format_poll_for_whatsapp(self, poll: PollDefinition, include_numbers: bool = True) -> str:
        """Format a poll for WhatsApp display."""
        text = f"📊 *{poll.title}*\n\n"
        text += f"{poll.question}\n\n"

        for i, option in enumerate(poll.options, 1):
            if include_numbers:
                text += f"{i}. {option.emoji} {option.text}\n"
            else:
                text += f"{option.emoji} {option.text}\n"

        text += "\nReply with the number of your choice."
        return text

    def format_results_for_whatsapp(self, poll_id: str) -> str:
        """Format poll results for WhatsApp display."""
        poll = self.get_poll(poll_id)
        results = self.compute_results(poll_id)

        if not poll or not results:
            return "Results not available."

        text = f"📊 *{poll.title}*\n"
        text += f"Results ({results.total_responses:,} votes)\n\n"

        # Sort by percentage
        sorted_results = sorted(
            results.results.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for opt_id, percentage in sorted_results:
            option = next((o for o in poll.options if o.id == opt_id), None)
            if option:
                bar = "█" * int(percentage / 5)  # Visual bar
                text += f"{option.emoji} {option.text}\n"
                text += f"   {bar} {percentage}%\n\n"

        return text

    def format_results_summary(self, poll_id: str) -> str:
        """Get a brief summary of poll results."""
        poll = self.get_poll(poll_id)
        results = self.compute_results(poll_id)

        if not poll or not results or results.total_responses == 0:
            return "No results yet."

        # Find winner
        winner_id = max(results.results, key=results.results.get)
        winner = next((o for o in poll.options if o.id == winner_id), None)
        winner_pct = results.results[winner_id]

        return f"{winner.emoji} {winner.text} leads with {winner_pct}% ({results.total_responses:,} votes)"


# === CONVENIENCE FUNCTIONS ===

_polling_instance = None

def get_polling_system() -> PollingSystem:
    """Get or create polling system singleton."""
    global _polling_instance
    if _polling_instance is None:
        _polling_instance = PollingSystem()
    return _polling_instance


def get_user_polls(user_state: str, user_lga: str = None) -> List[PollDefinition]:
    """Get polls for a user."""
    ps = get_polling_system()
    return ps.get_polls_for_user(user_state=user_state, user_lga=user_lga)


def submit_vote(poll_id: str, option: str, user_phone: str, user_state: str = None) -> Tuple[bool, str]:
    """Submit a vote."""
    ps = get_polling_system()
    user_hash = hashlib.sha256(user_phone.encode()).hexdigest()
    return ps.submit_response(poll_id, option, user_hash, user_state)


def get_poll_display(poll_id: str) -> str:
    """Get poll for display."""
    ps = get_polling_system()
    poll = ps.get_poll(poll_id)
    if poll:
        return ps.format_poll_for_whatsapp(poll)
    return "Poll not found."


def get_results_display(poll_id: str) -> str:
    """Get results for display."""
    ps = get_polling_system()
    return ps.format_results_for_whatsapp(poll_id)
