"""
Chatbot Enhancement Features for Decide9ja.

Adds:
1. Daily Briefing - Personalized morning news summary
2. Quiz Mode - Political awareness quiz with scoring
3. Guided Exploration - Step-by-step topic exploration
4. Explain Like I'm 5 (ELI5) - Simplified explanations with analogies

Usage:
    from app.services.chatbot_enhancements import (
        get_daily_briefing,
        start_quiz,
        get_guided_exploration,
        explain_eli5
    )

    briefing = get_daily_briefing(phone_hash)
    quiz = start_quiz(phone_hash, category="general")
"""

import json
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from app.database import (
    SessionLocal, User, NewsArticle, Issue, Politician,
    UserSubscription
)

logger = logging.getLogger(__name__)


# =============================================================================
# Daily Briefing
# =============================================================================

@dataclass
class BriefingItem:
    """Single item in daily briefing."""
    category: str  # news, issue, politician, election
    title: str
    summary: str
    relevance: str  # Why this matters to the user
    action: Optional[str] = None  # Follow-up action user can take


@dataclass
class DailyBriefing:
    """Complete daily briefing for a user."""
    greeting: str
    date: str
    items: List[BriefingItem]
    quick_stats: Dict[str, Any]
    suggested_questions: List[str]


def get_daily_briefing(phone_hash: str) -> DailyBriefing:
    """
    Generate personalized daily briefing.

    Includes:
    - Top news relevant to user's interests
    - Updates on followed politicians
    - Active issues in user's state
    - Election countdown and updates
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_hash == phone_hash).first()
        items = []

        # Get time-appropriate greeting
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        if user and user.name:
            greeting = f"{greeting}, {user.name}!"
        else:
            greeting = f"{greeting}!"

        # 1. Top news (general or personalized)
        news_items = _get_relevant_news(db, user)
        for news in news_items[:3]:
            items.append(BriefingItem(
                category="news",
                title=news.title,
                summary=news.excerpt or news.title,
                relevance="This is a top story today",
                action=f"Say 'tell me more about {news.title[:30]}' for details"
            ))

        # 2. Updates on followed politicians
        if user:
            followed = _get_followed_politicians_updates(db, phone_hash)
            for update in followed[:2]:
                items.append(BriefingItem(
                    category="politician",
                    title=update["title"],
                    summary=update["summary"],
                    relevance=f"About {update['politician_name']} - someone you follow",
                    action=f"Say 'more about {update['politician_name']}' for details"
                ))

        # 3. Active issues in user's state
        if user and user.state:
            issues = _get_state_issues(db, user.state)
            for issue in issues[:2]:
                items.append(BriefingItem(
                    category="issue",
                    title=issue.title,
                    summary=issue.summary or f"Active {issue.domain} issue in {user.state}",
                    relevance=f"Affecting {user.state}",
                    action=f"Say 'issue update {issue.issue_id}' for details"
                ))

        # 4. Election countdown
        election_date = datetime(2027, 2, 25)
        days_to_election = (election_date - datetime.now()).days
        if days_to_election > 0:
            items.append(BriefingItem(
                category="election",
                title=f"2027 Election: {days_to_election} days away",
                summary="The presidential election is approaching. Have you registered to vote?",
                relevance="Civic duty reminder",
                action="Say 'election updates' for the latest"
            ))

        # Quick stats
        quick_stats = {
            "days_to_election": days_to_election if days_to_election > 0 else None,
            "active_issues_count": db.query(Issue).filter(Issue.status == "active").count(),
            "news_today": db.query(NewsArticle).filter(
                NewsArticle.scraped_at >= datetime.now() - timedelta(days=1)
            ).count()
        }

        # Suggested questions based on user profile
        suggested_questions = [
            "What's happening in the National Assembly?",
            "Tell me about the fuel subsidy",
            "How is [politician name] doing?",
            "What are the main issues in my state?"
        ]
        if user and user.state:
            suggested_questions[3] = f"What are the main issues in {user.state}?"

        return DailyBriefing(
            greeting=greeting,
            date=datetime.now().strftime("%A, %B %d, %Y"),
            items=items,
            quick_stats=quick_stats,
            suggested_questions=suggested_questions
        )

    finally:
        db.close()


def _get_relevant_news(db, user: Optional[User]) -> List[NewsArticle]:
    """Get news relevant to user's interests."""
    query = db.query(NewsArticle).filter(
        NewsArticle.scraped_at >= datetime.now() - timedelta(days=1)
    )

    if user:
        # Get user's interests
        prefs = {}
        if user.preferences_json:
            try:
                prefs = json.loads(user.preferences_json)
            except:
                pass

        interests = prefs.get("interests", {})
        topics = interests.get("topics", [])

        # Filter by topics if available
        if topics:
            for topic in topics:
                query = query.filter(NewsArticle.topics_json.contains(topic))

    return query.order_by(NewsArticle.scraped_at.desc()).limit(5).all()


def _get_followed_politicians_updates(db, phone_hash: str) -> List[Dict]:
    """Get updates on followed politicians."""
    updates = []

    # Get followed politicians
    subs = db.query(UserSubscription).filter(
        UserSubscription.user_hash == phone_hash,
        UserSubscription.subscription_type == "politician",
        UserSubscription.is_active == True
    ).all()

    for sub in subs[:3]:
        # Get recent news mentioning this politician
        news = db.query(NewsArticle).filter(
            NewsArticle.politicians_json.contains(sub.target_id),
            NewsArticle.scraped_at >= datetime.now() - timedelta(days=2)
        ).order_by(NewsArticle.scraped_at.desc()).first()

        if news:
            updates.append({
                "politician_slug": sub.target_id,
                "politician_name": sub.target_name,
                "title": news.title,
                "summary": news.excerpt or news.title
            })

    return updates


def _get_state_issues(db, state: str) -> List[Issue]:
    """Get active issues in a state."""
    return db.query(Issue).filter(
        Issue.status == "active",
        Issue.states_json.contains(state)
    ).order_by(Issue.last_updated.desc()).limit(3).all()


def format_briefing_for_whatsapp(briefing: DailyBriefing) -> str:
    """Format briefing for WhatsApp message."""
    lines = [
        f"📰 *DAILY BRIEFING*",
        f"_{briefing.date}_",
        "",
        briefing.greeting,
        ""
    ]

    for i, item in enumerate(briefing.items, 1):
        emoji = {
            "news": "📰",
            "politician": "👤",
            "issue": "⚠️",
            "election": "🗳️"
        }.get(item.category, "📌")

        lines.append(f"{emoji} *{item.title}*")
        lines.append(f"   {item.summary[:100]}...")
        if item.action:
            lines.append(f"   _{item.action}_")
        lines.append("")

    if briefing.quick_stats.get("days_to_election"):
        lines.append(f"🗓️ *{briefing.quick_stats['days_to_election']} days to 2027 Election*")
        lines.append("")

    lines.append("💬 *Try asking:*")
    for q in briefing.suggested_questions[:3]:
        lines.append(f"• {q}")

    return "\n".join(lines)


# =============================================================================
# Quiz Mode
# =============================================================================

class QuizCategory(str, Enum):
    GENERAL = "general"
    POLITICIANS = "politicians"
    CONSTITUTION = "constitution"
    CURRENT_AFFAIRS = "current_affairs"
    STATES = "states"
    ELECTIONS = "elections"


@dataclass
class QuizQuestion:
    """A single quiz question."""
    question_id: str
    question: str
    options: List[str]
    correct_index: int
    explanation: str
    category: str
    difficulty: str  # easy, medium, hard
    points: int = 10


@dataclass
class QuizSession:
    """Active quiz session for a user."""
    session_id: str
    phone_hash: str
    category: str
    questions: List[QuizQuestion]
    current_index: int
    score: int
    answers: List[Dict]
    started_at: datetime
    completed: bool = False


# Quiz question bank
QUIZ_QUESTIONS = {
    "general": [
        QuizQuestion(
            question_id="gen-1",
            question="Who is the current President of Nigeria?",
            options=["Muhammadu Buhari", "Bola Tinubu", "Goodluck Jonathan", "Olusegun Obasanjo"],
            correct_index=1,
            explanation="Bola Ahmed Tinubu was inaugurated as Nigeria's 16th President on May 29, 2023.",
            category="general",
            difficulty="easy"
        ),
        QuizQuestion(
            question_id="gen-2",
            question="How many states does Nigeria have?",
            options=["30", "32", "36", "37"],
            correct_index=2,
            explanation="Nigeria has 36 states plus the Federal Capital Territory (FCT), Abuja.",
            category="general",
            difficulty="easy"
        ),
        QuizQuestion(
            question_id="gen-3",
            question="What is the name of Nigeria's legislative body?",
            options=["Parliament", "Congress", "National Assembly", "Legislature"],
            correct_index=2,
            explanation="The National Assembly consists of the Senate and House of Representatives.",
            category="general",
            difficulty="easy"
        ),
        QuizQuestion(
            question_id="gen-4",
            question="Which political party won the 2023 presidential election?",
            options=["PDP", "APC", "LP", "NNPP"],
            correct_index=1,
            explanation="The All Progressives Congress (APC) won with Bola Tinubu as candidate.",
            category="general",
            difficulty="easy"
        ),
        QuizQuestion(
            question_id="gen-5",
            question="What percentage of votes is needed to win the presidential election?",
            options=["Simple majority", "25% in 24 states + overall majority", "Two-thirds majority", "50%+1"],
            correct_index=1,
            explanation="A candidate must win overall majority and at least 25% in 24 states (2/3 of 36 states).",
            category="general",
            difficulty="medium"
        ),
    ],
    "constitution": [
        QuizQuestion(
            question_id="con-1",
            question="When was Nigeria's current constitution adopted?",
            options=["1960", "1979", "1999", "2011"],
            correct_index=2,
            explanation="The 1999 Constitution came into effect on May 29, 1999, marking return to democracy.",
            category="constitution",
            difficulty="medium"
        ),
        QuizQuestion(
            question_id="con-2",
            question="What is the term length for the Nigerian President?",
            options=["4 years, unlimited terms", "4 years, max 2 terms", "5 years, max 2 terms", "6 years, one term"],
            correct_index=1,
            explanation="The President serves 4-year terms with a maximum of 2 terms (8 years total).",
            category="constitution",
            difficulty="easy"
        ),
        QuizQuestion(
            question_id="con-3",
            question="How many senators represent each state in the Senate?",
            options=["1", "2", "3", "4"],
            correct_index=2,
            explanation="Each state has 3 senators, plus 1 from the FCT, totaling 109 senators.",
            category="constitution",
            difficulty="medium"
        ),
    ],
    "politicians": [
        QuizQuestion(
            question_id="pol-1",
            question="Who is the current Vice President of Nigeria?",
            options=["Yemi Osinbajo", "Kashim Shettima", "Atiku Abubakar", "Peter Obi"],
            correct_index=1,
            explanation="Kashim Shettima became Vice President on May 29, 2023.",
            category="politicians",
            difficulty="easy"
        ),
        QuizQuestion(
            question_id="pol-2",
            question="Who is the current President of the Senate?",
            options=["Ahmad Lawan", "Bukola Saraki", "Godswill Akpabio", "David Mark"],
            correct_index=2,
            explanation="Godswill Akpabio became Senate President in June 2023.",
            category="politicians",
            difficulty="medium"
        ),
    ],
    "states": [
        QuizQuestion(
            question_id="sta-1",
            question="Which state is known as the 'Centre of Excellence'?",
            options=["Abuja", "Lagos", "Rivers", "Kano"],
            correct_index=1,
            explanation="Lagos is nicknamed 'Centre of Excellence' - Nigeria's commercial capital.",
            category="states",
            difficulty="easy"
        ),
        QuizQuestion(
            question_id="sta-2",
            question="Which state has the largest land area in Nigeria?",
            options=["Borno", "Niger", "Taraba", "Bauchi"],
            correct_index=1,
            explanation="Niger State is the largest by land area at about 76,363 square kilometers.",
            category="states",
            difficulty="hard"
        ),
    ],
}

# Store active quiz sessions (in production, use Redis)
_quiz_sessions: Dict[str, QuizSession] = {}


def start_quiz(
    phone_hash: str,
    category: str = "general",
    num_questions: int = 5
) -> Dict[str, Any]:
    """
    Start a new quiz session.
    """
    # Get questions for category
    available = QUIZ_QUESTIONS.get(category, QUIZ_QUESTIONS["general"])
    selected = random.sample(available, min(num_questions, len(available)))

    session_id = f"quiz-{phone_hash}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    session = QuizSession(
        session_id=session_id,
        phone_hash=phone_hash,
        category=category,
        questions=selected,
        current_index=0,
        score=0,
        answers=[],
        started_at=datetime.now()
    )

    _quiz_sessions[phone_hash] = session

    return {
        "session_id": session_id,
        "category": category,
        "total_questions": len(selected),
        "first_question": _format_question(selected[0], 1, len(selected))
    }


def answer_quiz(phone_hash: str, answer: int) -> Dict[str, Any]:
    """
    Submit answer for current question.
    """
    session = _quiz_sessions.get(phone_hash)
    if not session or session.completed:
        return {"error": "No active quiz. Say 'start quiz' to begin."}

    current_q = session.questions[session.current_index]
    is_correct = answer == current_q.correct_index

    if is_correct:
        session.score += current_q.points

    session.answers.append({
        "question_id": current_q.question_id,
        "user_answer": answer,
        "correct_answer": current_q.correct_index,
        "is_correct": is_correct,
        "points_earned": current_q.points if is_correct else 0
    })

    # Move to next question
    session.current_index += 1

    # Check if quiz complete
    if session.current_index >= len(session.questions):
        session.completed = True
        return {
            "is_correct": is_correct,
            "explanation": current_q.explanation,
            "quiz_complete": True,
            "final_score": session.score,
            "total_possible": sum(q.points for q in session.questions),
            "correct_answers": sum(1 for a in session.answers if a["is_correct"]),
            "total_questions": len(session.questions),
            "summary": _get_quiz_summary(session)
        }

    # Get next question
    next_q = session.questions[session.current_index]
    return {
        "is_correct": is_correct,
        "explanation": current_q.explanation,
        "current_score": session.score,
        "next_question": _format_question(
            next_q,
            session.current_index + 1,
            len(session.questions)
        )
    }


def _format_question(q: QuizQuestion, num: int, total: int) -> Dict[str, Any]:
    """Format a question for display."""
    return {
        "question_id": q.question_id,
        "number": num,
        "total": total,
        "question": q.question,
        "options": [f"{i+1}. {opt}" for i, opt in enumerate(q.options)],
        "difficulty": q.difficulty,
        "points": q.points
    }


def _get_quiz_summary(session: QuizSession) -> str:
    """Generate quiz summary text."""
    correct = sum(1 for a in session.answers if a["is_correct"])
    total = len(session.questions)
    percentage = (correct / total) * 100

    if percentage >= 80:
        grade = "Excellent! 🏆"
        message = "You're a political expert!"
    elif percentage >= 60:
        grade = "Good job! 👍"
        message = "You know your politics well."
    elif percentage >= 40:
        grade = "Not bad! 📚"
        message = "Keep learning with Decide9ja!"
    else:
        grade = "Keep learning! 💪"
        message = "Decide9ja is here to help you learn more."

    return f"{grade} You scored {correct}/{total} ({percentage:.0f}%). {message}"


def format_quiz_for_whatsapp(data: Dict[str, Any]) -> str:
    """Format quiz data for WhatsApp."""
    lines = []

    if "first_question" in data:
        # Starting quiz
        lines.append("🎯 *POLITICAL QUIZ*")
        lines.append(f"Category: {data['category'].title()}")
        lines.append(f"Questions: {data['total_questions']}")
        lines.append("")
        q = data["first_question"]
        lines.append(f"*Question {q['number']}/{q['total']}*")
        lines.append(f"_{q['difficulty'].title()} - {q['points']} points_")
        lines.append("")
        lines.append(q["question"])
        lines.append("")
        for opt in q["options"]:
            lines.append(opt)
        lines.append("")
        lines.append("_Reply with the number (1-4)_")

    elif "quiz_complete" in data and data["quiz_complete"]:
        # Quiz complete
        lines.append("🏁 *QUIZ COMPLETE!*")
        lines.append("")
        lines.append(data["summary"])
        lines.append("")
        lines.append(f"Final Score: {data['final_score']}/{data['total_possible']}")
        lines.append("")
        lines.append("Say 'start quiz' to play again!")

    elif "next_question" in data:
        # Answered question, showing next
        emoji = "✅" if data["is_correct"] else "❌"
        lines.append(f"{emoji} {'Correct!' if data['is_correct'] else 'Wrong!'}")
        lines.append(f"_{data['explanation']}_")
        lines.append(f"Current score: {data['current_score']}")
        lines.append("")
        q = data["next_question"]
        lines.append(f"*Question {q['number']}/{q['total']}*")
        lines.append(f"_{q['difficulty'].title()} - {q['points']} points_")
        lines.append("")
        lines.append(q["question"])
        lines.append("")
        for opt in q["options"]:
            lines.append(opt)
        lines.append("")
        lines.append("_Reply with the number (1-4)_")

    return "\n".join(lines)


# =============================================================================
# Guided Exploration
# =============================================================================

@dataclass
class ExplorationStep:
    """A single step in guided exploration."""
    step_number: int
    title: str
    content: str
    questions_to_ask: List[str]
    related_topics: List[str]


@dataclass
class GuidedExploration:
    """Complete guided exploration on a topic."""
    topic: str
    description: str
    steps: List[ExplorationStep]
    total_steps: int


EXPLORATION_PATHS = {
    "how-bills-become-law": GuidedExploration(
        topic="How Bills Become Law in Nigeria",
        description="Learn the legislative process step by step",
        steps=[
            ExplorationStep(
                step_number=1,
                title="Introduction of a Bill",
                content="""
A bill can be introduced by:
• A member of the National Assembly (private member's bill)
• The Executive/President (executive bill)

The bill is first read (First Reading) - just the title is announced. No debate happens yet.
                """,
                questions_to_ask=["Who introduces most bills?", "What's the difference between executive and private bills?"],
                related_topics=["National Assembly", "Executive powers"]
            ),
            ExplorationStep(
                step_number=2,
                title="Second Reading & Debate",
                content="""
This is where the real action happens! The bill is debated in full.

Members discuss:
• The principles behind the bill
• Whether it's needed
• Its potential impact

If it passes second reading, it goes to a committee for detailed review.
                """,
                questions_to_ask=["How long do debates take?", "Can bills be rejected at this stage?"],
                related_topics=["Committee system", "Parliamentary procedure"]
            ),
            ExplorationStep(
                step_number=3,
                title="Committee Stage",
                content="""
A committee examines the bill clause by clause.

They can:
• Invite experts and stakeholders
• Propose amendments
• Hold public hearings

This is where the technical details get sorted out.
                """,
                questions_to_ask=["What committees exist?", "Can the public participate?"],
                related_topics=["Standing committees", "Public hearings"]
            ),
            ExplorationStep(
                step_number=4,
                title="Third Reading & Passage",
                content="""
The bill (possibly amended) comes back to the full house.

Final vote is taken. If it passes:
• It goes to the other chamber (Senate ↔ House)
• Same process repeats there

Both chambers must pass identical versions.
                """,
                questions_to_ask=["What if chambers disagree?", "How many votes needed to pass?"],
                related_topics=["Conference committee", "Voting procedures"]
            ),
            ExplorationStep(
                step_number=5,
                title="Presidential Assent",
                content="""
Once both chambers pass the bill, it goes to the President.

The President can:
• Sign it (becomes law)
• Refuse to sign (veto)
• Do nothing for 30 days (becomes law automatically)

If vetoed, the National Assembly can override with 2/3 majority in both houses.
                """,
                questions_to_ask=["Has a veto ever been overridden?", "What recent bills were signed?"],
                related_topics=["Presidential powers", "Veto override"]
            ),
        ],
        total_steps=5
    ),
    "understanding-budget": GuidedExploration(
        topic="Understanding Nigeria's Budget",
        description="Learn how the national budget works",
        steps=[
            ExplorationStep(
                step_number=1,
                title="What is the National Budget?",
                content="""
The budget is the government's financial plan for the year.

It shows:
• How much money the government expects to receive (revenue)
• How it plans to spend that money (expenditure)

Nigeria's budget is usually in trillions of Naira!
                """,
                questions_to_ask=["How big is this year's budget?", "Where does the money come from?"],
                related_topics=["Revenue sources", "Budget size"]
            ),
            ExplorationStep(
                step_number=2,
                title="Budget Preparation",
                content="""
The budget is prepared by the Executive branch.

The Ministry of Finance and Budget Office:
• Collect requests from all ministries
• Estimate expected revenue
• Balance requests with available funds

The President then presents it to the National Assembly.
                """,
                questions_to_ask=["When is the budget presented?", "Who decides the priorities?"],
                related_topics=["Budget Office", "MTEF"]
            ),
            ExplorationStep(
                step_number=3,
                title="Budget Defense & Approval",
                content="""
Ministers and agency heads "defend" their budget requests before committees.

They explain:
• Why they need the money
• What they achieved with last year's budget
• Their plans for the coming year

After debates and amendments, the National Assembly votes to approve.
                """,
                questions_to_ask=["Can the Assembly change the budget?", "What if it's not approved?"],
                related_topics=["Budget committees", "Appropriation Act"]
            ),
        ],
        total_steps=3
    ),
}

# Store user exploration progress
_exploration_sessions: Dict[str, Dict] = {}


def start_exploration(phone_hash: str, topic: str) -> Dict[str, Any]:
    """Start a guided exploration on a topic."""
    exploration = EXPLORATION_PATHS.get(topic)

    if not exploration:
        available = list(EXPLORATION_PATHS.keys())
        return {
            "error": f"Topic not found. Available: {', '.join(available)}"
        }

    _exploration_sessions[phone_hash] = {
        "topic": topic,
        "current_step": 0
    }

    first_step = exploration.steps[0]
    return {
        "topic": exploration.topic,
        "description": exploration.description,
        "total_steps": exploration.total_steps,
        "step": _format_exploration_step(first_step, exploration.total_steps)
    }


def continue_exploration(phone_hash: str) -> Dict[str, Any]:
    """Continue to next step in exploration."""
    session = _exploration_sessions.get(phone_hash)
    if not session:
        return {"error": "No active exploration. Say 'explore [topic]' to start."}

    exploration = EXPLORATION_PATHS.get(session["topic"])
    current = session["current_step"]

    if current >= exploration.total_steps - 1:
        # Completed
        del _exploration_sessions[phone_hash]
        return {
            "completed": True,
            "topic": exploration.topic,
            "message": f"You've completed the exploration of '{exploration.topic}'!",
            "related_explorations": _get_related_explorations(session["topic"])
        }

    # Move to next step
    session["current_step"] = current + 1
    next_step = exploration.steps[session["current_step"]]

    return {
        "topic": exploration.topic,
        "step": _format_exploration_step(next_step, exploration.total_steps)
    }


def _format_exploration_step(step: ExplorationStep, total: int) -> Dict[str, Any]:
    """Format an exploration step."""
    return {
        "number": step.step_number,
        "total": total,
        "title": step.title,
        "content": step.content.strip(),
        "questions_to_ask": step.questions_to_ask,
        "related_topics": step.related_topics
    }


def _get_related_explorations(current_topic: str) -> List[str]:
    """Get related exploration topics."""
    return [t for t in EXPLORATION_PATHS.keys() if t != current_topic][:3]


def get_available_explorations() -> List[Dict[str, str]]:
    """Get list of available exploration topics."""
    return [
        {"id": topic, "title": exp.topic, "description": exp.description}
        for topic, exp in EXPLORATION_PATHS.items()
    ]


def format_exploration_for_whatsapp(data: Dict[str, Any]) -> str:
    """Format exploration data for WhatsApp."""
    if "error" in data:
        return f"❌ {data['error']}"

    if data.get("completed"):
        lines = [
            "🎉 *EXPLORATION COMPLETE*",
            "",
            f"You've finished learning about: *{data['topic']}*",
            "",
            "Want to explore more? Try:",
        ]
        for topic in data.get("related_explorations", []):
            lines.append(f"• explore {topic}")
        return "\n".join(lines)

    step = data["step"]
    lines = [
        f"📚 *{data['topic']}*",
        f"Step {step['number']}/{step['total']}: *{step['title']}*",
        "",
        step['content'],
        "",
        "💬 *Try asking:*"
    ]
    for q in step.get("questions_to_ask", [])[:2]:
        lines.append(f"• {q}")

    lines.append("")
    lines.append("_Say 'next' to continue or 'menu' to exit_")

    return "\n".join(lines)


# =============================================================================
# Explain Like I'm 5 (ELI5)
# =============================================================================

ELI5_TEMPLATES = {
    "budget": {
        "title": "What is the National Budget?",
        "eli5": """
Imagine your family has a big jar of money. At the beginning of the year, your parents sit down and plan:
- How much money will come into the jar (from work, business)
- How will we use this money (food, school fees, rent, savings)

Nigeria does the same thing! The government's "family jar" is the national budget.

The President says "we have X trillion Naira, and here's how we'll spend it." Then the National Assembly (like a big family meeting) discusses and approves it.
        """,
        "simple_terms": {
            "Revenue": "Money coming in (like salary)",
            "Expenditure": "Money going out (like spending)",
            "Deficit": "When you plan to spend more than you have",
            "Appropriation": "Official permission to spend the money"
        }
    },
    "constitution": {
        "title": "What is the Constitution?",
        "eli5": """
Think of your school. There are rules, right? No fighting, come on time, wear uniform. These rules help everyone know what's okay and what's not.

The Constitution is like Nigeria's rule book, but SUPER important. It tells:
- How to choose leaders
- What the President can and can't do
- Rights every Nigerian has (like going to school, speaking freely)

Nobody - not even the President - is bigger than this rule book!
        """,
        "simple_terms": {
            "Fundamental Rights": "Things nobody can take from you (like freedom)",
            "Amendment": "Changing a rule in the Constitution",
            "Federalism": "States and the central government sharing power"
        }
    },
    "fuel_subsidy": {
        "title": "What is Fuel Subsidy?",
        "eli5": """
Imagine you buy bread for ₦500 at the market. But the bakery actually spent ₦800 to make it. Someone is paying the extra ₦300, right?

That's like fuel subsidy! The real price of petrol is higher, but the government was paying part of it so you pay less at the pump.

Recently, the government said "we can't keep paying this extra money" and removed it. That's why fuel prices went up.
        """,
        "simple_terms": {
            "Subsidy": "Government paying part of the cost for you",
            "Removal": "When government stops paying that part",
            "Landing cost": "What fuel actually costs when it arrives in Nigeria"
        }
    },
    "national_assembly": {
        "title": "What is the National Assembly?",
        "eli5": """
You know how in class, students can suggest ideas and vote on them? Like "should we have a party?" and everyone votes yes or no?

The National Assembly is like that, but for all of Nigeria!

It has two parts:
- Senate (109 members, 3 from each state + 1 from FCT)
- House of Representatives (360 members)

They make laws, approve how money is spent, and check that the President is doing their job well.
        """,
        "simple_terms": {
            "Senator": "Member of the Senate",
            "House Member": "Member of the House of Representatives",
            "Bill": "A proposed law being discussed",
            "Plenary": "When all members meet together"
        }
    },
}


def explain_eli5(topic: str) -> Dict[str, Any]:
    """
    Get an ELI5 explanation for a topic.
    """
    # Normalize topic
    topic_key = topic.lower().replace(" ", "_").replace("-", "_")

    # Try exact match
    if topic_key in ELI5_TEMPLATES:
        template = ELI5_TEMPLATES[topic_key]
        return {
            "topic": template["title"],
            "explanation": template["eli5"].strip(),
            "simple_terms": template["simple_terms"]
        }

    # Try partial match
    for key, template in ELI5_TEMPLATES.items():
        if topic_key in key or key in topic_key:
            return {
                "topic": template["title"],
                "explanation": template["eli5"].strip(),
                "simple_terms": template["simple_terms"]
            }

    # Not found - list available
    return {
        "error": "I don't have a simple explanation for that yet.",
        "available_topics": list(ELI5_TEMPLATES.keys())
    }


def format_eli5_for_whatsapp(data: Dict[str, Any]) -> str:
    """Format ELI5 explanation for WhatsApp."""
    if "error" in data:
        lines = [
            f"❓ {data['error']}",
            "",
            "Topics I can explain simply:",
        ]
        for topic in data.get("available_topics", []):
            lines.append(f"• explain {topic.replace('_', ' ')}")
        return "\n".join(lines)

    lines = [
        f"👶 *ELI5: {data['topic']}*",
        "",
        data['explanation'],
        "",
        "📖 *Key Terms:*"
    ]

    for term, meaning in data.get("simple_terms", {}).items():
        lines.append(f"• *{term}*: {meaning}")

    lines.append("")
    lines.append("_Want more details? Just ask!_")

    return "\n".join(lines)


# =============================================================================
# API Helper Functions
# =============================================================================

def get_chatbot_enhancement_status() -> Dict[str, Any]:
    """Get status of chatbot enhancement features."""
    return {
        "features": {
            "daily_briefing": True,
            "quiz_mode": True,
            "guided_exploration": True,
            "eli5_explanations": True
        },
        "quiz_categories": list(QUIZ_QUESTIONS.keys()),
        "exploration_topics": list(EXPLORATION_PATHS.keys()),
        "eli5_topics": list(ELI5_TEMPLATES.keys()),
        "active_quiz_sessions": len(_quiz_sessions),
        "active_explorations": len(_exploration_sessions)
    }
