"""
Tade Learning Service
=====================
Makes Tade smarter over time by learning from every conversation.

Three learning loops:
1. USER MEMORY — Tracks per-user preferences, topics, tone, and interests
2. FEEDBACK SIGNALS — Detects implicit satisfaction/confusion from conversation patterns
3. KNOWLEDGE GAPS — Tracks what users ask about but Tade can't answer

All learning is privacy-preserving (phone hashes only, no PII stored in learning tables).
"""

import json
import logging
import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


# =============================================================================
# 1. USER MEMORY — Per-user preference tracking
# =============================================================================

class UserMemory:
    """
    Tracks what each user cares about across conversations.
    Stored in the users table via a JSON column, loaded into Redis for fast access.

    Tracks:
    - Top topics (budget, election, politician X, state Y)
    - Preferred tone (pidgin-heavy, formal, mixed)
    - Query patterns (always asks about their state, focuses on corruption, etc.)
    - Last N topic summaries for continuity
    """

    # Topic extraction keywords
    TOPIC_CATEGORIES = {
        'budget': ['budget', 'allocation', 'spending', 'appropriation', 'faac'],
        'corruption': ['corruption', 'audit', 'padding', 'fraud', 'misappropriation', 'fishy', 'stealing'],
        'election': ['election', 'vote', 'inec', 'pvc', 'register', 'polling', '2027', 'candidate'],
        'treasury': ['treasury', 'payment', 'contractor', 'opentreasury', 'disbursement'],
        'education': ['education', 'school', 'asuu', 'university', 'student', 'teacher'],
        'security': ['security', 'boko haram', 'bandit', 'kidnap', 'military', 'police'],
        'health': ['health', 'hospital', 'doctor', 'nhis', 'epidemic'],
        'infrastructure': ['road', 'bridge', 'power', 'electricity', 'water', 'infrastructure'],
        'oil': ['oil', 'nnpc', 'petroleum', 'fuel', 'subsidy', 'refinery'],
    }

    @staticmethod
    def extract_topics(text: str) -> List[str]:
        """Extract topic categories from a user message."""
        text_lower = text.lower()
        topics = []
        for category, keywords in UserMemory.TOPIC_CATEGORIES.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(category)
        return topics

    @staticmethod
    def extract_mentioned_entities(text: str) -> Dict[str, List[str]]:
        """Extract named entities (states, politicians, MDAs) from text."""
        entities = {'states': [], 'politicians': [], 'mdas': []}

        # Nigerian states
        states = [
            'abia', 'adamawa', 'akwa ibom', 'anambra', 'bauchi', 'bayelsa', 'benue',
            'borno', 'cross river', 'delta', 'ebonyi', 'edo', 'ekiti', 'enugu', 'gombe',
            'imo', 'jigawa', 'kaduna', 'kano', 'katsina', 'kebbi', 'kogi', 'kwara',
            'lagos', 'nasarawa', 'niger', 'ogun', 'ondo', 'osun', 'oyo', 'plateau',
            'rivers', 'sokoto', 'taraba', 'yobe', 'zamfara', 'fct', 'abuja'
        ]
        text_lower = text.lower()
        for state in states:
            if state in text_lower:
                entities['states'].append(state.title())

        # Common politician names
        politicians = [
            'tinubu', 'obi', 'atiku', 'kwankwaso', 'buhari', 'osinbajo',
            'shettima', 'wike', 'el-rufai', 'sanwo-olu', 'soludo', 'fubara'
        ]
        for pol in politicians:
            if pol in text_lower:
                entities['politicians'].append(pol.title())

        return entities

    @staticmethod
    def detect_tone_preference(text: str) -> str:
        """Detect if user prefers pidgin, formal, or mixed tone."""
        pidgin_markers = [
            'wetin', 'abeg', 'abi', 'shey', 'wahala', 'omo', 'bros', 'guy',
            'no be', 'na so', 'e be like', 'make i', 'dey', 'dem', 'una',
            'no dey', 'wey', 'chop', 'jare', 'sef', 'sha', 'o!', ' o '
        ]
        text_lower = text.lower()
        pidgin_count = sum(1 for m in pidgin_markers if m in text_lower)

        if pidgin_count >= 3:
            return 'pidgin'
        elif pidgin_count >= 1:
            return 'mixed'
        return 'formal'

    @staticmethod
    def build_user_memory_prompt(memory: Dict[str, Any]) -> str:
        """
        Build a memory injection for the system prompt.
        This tells Tade what it remembers about this user.
        """
        parts = []

        # Top topics
        top_topics = memory.get('top_topics', [])
        if top_topics:
            topic_str = ', '.join(top_topics[:5])
            parts.append(f"This user frequently asks about: {topic_str}.")

        # States of interest
        states = memory.get('states_of_interest', [])
        if states:
            parts.append(f"They focus on: {', '.join(states[:3])}.")

        # Politicians tracked
        politicians = memory.get('politicians_tracked', [])
        if politicians:
            parts.append(f"Politicians they follow: {', '.join(politicians[:5])}.")

        # Tone preference
        tone = memory.get('tone_preference', 'mixed')
        if tone == 'pidgin':
            parts.append("They prefer pidgin — match their energy.")
        elif tone == 'formal':
            parts.append("They prefer formal English — keep it clean.")

        # Engagement level
        msg_count = memory.get('total_queries', 0)
        if msg_count > 50:
            parts.append("Power user — they know the ropes, skip the basics.")
        elif msg_count > 20:
            parts.append("Regular user — engaged and curious.")
        elif msg_count > 5:
            parts.append("Getting familiar — still exploring what you can do.")

        # Last conversation context
        last_topics = memory.get('last_session_topics', [])
        if last_topics:
            parts.append(f"Last time, you discussed: {', '.join(last_topics[:3])}.")

        if not parts:
            return ""

        return "\n=== What You Remember About This User ===\n" + "\n".join(parts) + "\n"


# =============================================================================
# 2. FEEDBACK SIGNALS — Implicit learning from conversation patterns
# =============================================================================

class FeedbackDetector:
    """
    Detects implicit feedback signals from conversation patterns.
    No thumbs-up buttons needed — we read the conversation.

    Signals:
    - REPHRASE: User asks the same thing differently → Tade didn't understand
    - FOLLOW_UP: User digs deeper into same topic → Tade answered well
    - CORRECTION: User says "no, I meant..." → Tade misunderstood
    - ABANDONMENT: User changes topic abruptly → Tade wasn't helpful
    - GRATITUDE: User says thanks/nice → positive signal
    - ESCALATION: User asks same question 3+ times → critical failure
    """

    GRATITUDE_MARKERS = [
        'thanks', 'thank you', 'nice', 'great', 'perfect', 'good job',
        'well done', 'correct', 'exactly', 'yes!', 'nailed it',
        'e correct', 'na so', 'you too much', 'mad o', 'sharp'
    ]

    CORRECTION_MARKERS = [
        'no i meant', 'not what i asked', 'i said', 'i mean',
        'that\'s not', 'wrong', 'no no', 'incorrect', 'actually i',
        'you misunderstood', 'i was asking about', 'no be that',
        'na different thing', 'you no understand'
    ]

    FRUSTRATION_MARKERS = [
        'useless', 'you don\'t know', 'can\'t you', 'forget it',
        'never mind', 'this bot', 'not helpful', 'waste of time',
        'you dey crase', 'nonsense', 'rubbish'
    ]

    @staticmethod
    def detect_signal(
        current_query: str,
        previous_query: Optional[str] = None,
        previous_response: Optional[str] = None,
        history: Optional[List[Dict]] = None
    ) -> Tuple[str, float]:
        """
        Detect feedback signal from the current message.
        Returns (signal_type, confidence).
        """
        q_lower = current_query.lower().strip()

        # Check gratitude
        if any(m in q_lower for m in FeedbackDetector.GRATITUDE_MARKERS):
            return ('gratitude', 0.8)

        # Check correction
        if any(m in q_lower for m in FeedbackDetector.CORRECTION_MARKERS):
            return ('correction', 0.85)

        # Check frustration
        if any(m in q_lower for m in FeedbackDetector.FRUSTRATION_MARKERS):
            return ('frustration', 0.9)

        # Check rephrase (similar question to previous)
        if previous_query:
            similarity = FeedbackDetector._quick_similarity(current_query, previous_query)
            if similarity > 0.5 and len(current_query) > 10:
                return ('rephrase', similarity)

        # Check follow-up (deeper dive into same topic)
        if previous_query and previous_response:
            prev_topics = UserMemory.extract_topics(previous_query)
            curr_topics = UserMemory.extract_topics(current_query)
            if prev_topics and curr_topics and set(prev_topics) & set(curr_topics):
                # Same topic area — user is digging deeper
                deepening_markers = [
                    'what about', 'how about', 'and for', 'break it down',
                    'show me', 'more detail', 'specifics', 'which', 'how much',
                    'wetin about', 'and', 'also', 'compare'
                ]
                if any(m in q_lower for m in deepening_markers):
                    return ('follow_up', 0.7)

        # Check topic abandonment (completely different topic, short message)
        if previous_query and len(current_query) > 5:
            prev_topics = set(UserMemory.extract_topics(previous_query))
            curr_topics = set(UserMemory.extract_topics(current_query))
            if prev_topics and curr_topics and not (prev_topics & curr_topics):
                return ('topic_switch', 0.5)

        return ('neutral', 0.0)

    @staticmethod
    def _quick_similarity(a: str, b: str) -> float:
        """Quick word-overlap similarity (no embeddings needed)."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        # Remove common stop words
        stop = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at',
                'to', 'for', 'of', 'and', 'or', 'but', 'not', 'what', 'who', 'how',
                'i', 'you', 'we', 'they', 'my', 'your', 'me', 'can', 'do', 'does'}
        words_a -= stop
        words_b -= stop
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)


# =============================================================================
# 3. KNOWLEDGE GAP DETECTOR
# =============================================================================

class KnowledgeGapDetector:
    """
    Detects when Tade doesn't have the data to answer a question.
    Tracks gaps so we know what data to prioritize scraping/ingesting.
    """

    NO_DATA_MARKERS = [
        'no matching records',
        'no data found',
        'not found in',
        'no results',
        'i no get that',
        'no information available',
        'error',
        'agent not available',
    ]

    @staticmethod
    def detect_gap(
        query: str,
        tool_results: Dict[str, Any],
        final_response: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a query exposed a knowledge gap.
        Returns gap info dict or None.
        """
        gaps = []

        # Check tool results for empty/error responses
        for tool_name, result in tool_results.items():
            result_str = json.dumps(result) if isinstance(result, dict) else str(result)
            result_lower = result_str.lower()

            if any(m in result_lower for m in KnowledgeGapDetector.NO_DATA_MARKERS):
                gaps.append({
                    'tool': tool_name,
                    'query': query,
                    'gap_type': 'missing_data',
                    'detail': f"Tool '{tool_name}' returned no useful data for: {query}"
                })

        # Check if final response admits ignorance
        resp_lower = final_response.lower()
        ignorance_markers = [
            'i no get that data',
            'don\'t have information',
            'no data available',
            'couldn\'t find',
            'not in my database',
            'i no fit find'
        ]
        if any(m in resp_lower for m in ignorance_markers):
            if not gaps:  # Don't double-count
                gaps.append({
                    'tool': 'general',
                    'query': query,
                    'gap_type': 'admitted_ignorance',
                    'detail': f"Tade admitted not having data for: {query}"
                })

        return gaps[0] if gaps else None

    @staticmethod
    def categorize_gap(query: str) -> str:
        """Categorize what kind of data is missing."""
        q_lower = query.lower()

        if any(kw in q_lower for kw in ['budget', 'allocation', 'spending']):
            return 'budget_data'
        elif any(kw in q_lower for kw in ['election', 'vote', 'candidate', 'inec']):
            return 'election_data'
        elif any(kw in q_lower for kw in ['senator', 'governor', 'rep', 'minister']):
            return 'politician_data'
        elif any(kw in q_lower for kw in ['news', 'latest', 'happening']):
            return 'news_coverage'
        elif any(kw in q_lower for kw in ['payment', 'treasury', 'contractor']):
            return 'treasury_data'
        elif any(kw in q_lower for kw in ['promise', 'pledge', 'commitment']):
            return 'promise_tracking'
        else:
            return 'general'


# =============================================================================
# MAIN LEARNING SERVICE — Ties it all together
# =============================================================================

class LearningService:
    """
    Central learning service. Called after every interaction.

    Flow:
    1. Before response: Load user memory → inject into system prompt
    2. After response: Analyze interaction → update memory + detect feedback + check gaps
    """

    def __init__(self):
        self._memory_cache: Dict[str, Dict] = {}  # user_id → memory dict

    # ── Pre-response: Load memory for prompt injection ──────────────

    def get_user_memory_for_prompt(self, user_id: str) -> str:
        """Load user memory and format for system prompt injection."""
        memory = self._load_user_memory(user_id)
        if not memory or memory.get('total_queries', 0) < 2:
            return ""  # Not enough data yet
        return UserMemory.build_user_memory_prompt(memory)

    # ── Post-response: Learn from the interaction ───────────────────

    def learn_from_interaction(
        self,
        user_id: str,
        query: str,
        response: str,
        tools_called: Optional[List[str]] = None,
        tool_results: Optional[Dict[str, Any]] = None,
        response_time_ms: Optional[int] = None
    ):
        """
        Main learning function. Called after every interaction.
        Updates user memory, detects feedback, checks knowledge gaps.
        """
        try:
            memory = self._load_user_memory(user_id)

            # 1. Update topic tracking
            topics = UserMemory.extract_topics(query)
            self._update_topic_counts(memory, topics)

            # 2. Update entity tracking
            entities = UserMemory.extract_mentioned_entities(query)
            self._update_entity_tracking(memory, entities)

            # 3. Detect tone preference
            tone = UserMemory.detect_tone_preference(query)
            self._update_tone_preference(memory, tone)

            # 4. Track query count
            memory['total_queries'] = memory.get('total_queries', 0) + 1
            memory['last_query_at'] = datetime.utcnow().isoformat()

            # 5. Update session topics
            if topics:
                session_topics = memory.get('current_session_topics', [])
                for t in topics:
                    if t not in session_topics:
                        session_topics.append(t)
                memory['current_session_topics'] = session_topics[-10:]

            # 6. Detect feedback signal
            prev_query = memory.get('last_query')
            prev_response = memory.get('last_response')
            signal, confidence = FeedbackDetector.detect_signal(
                query, prev_query, prev_response
            )
            if signal != 'neutral' and confidence > 0.5:
                self._record_feedback(memory, signal, confidence, query, response)

            # 7. Check knowledge gaps
            if tool_results:
                gap = KnowledgeGapDetector.detect_gap(query, tool_results, response)
                if gap:
                    self._record_knowledge_gap(user_id, gap)

            # 8. Track tools used (learn which tools are useful)
            if tools_called:
                tool_counts = memory.get('tool_usage', {})
                for tool in tools_called:
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1
                memory['tool_usage'] = tool_counts

            # 9. Store last query/response for next-turn comparison
            memory['last_query'] = query
            memory['last_response'] = response[:500]  # Truncate to save space

            # Save
            self._save_user_memory(user_id, memory)

        except Exception as e:
            logger.error(f"Learning service error: {e}")

    def on_session_end(self, user_id: str):
        """Called when a session times out. Moves session topics to history."""
        try:
            memory = self._load_user_memory(user_id)
            session_topics = memory.get('current_session_topics', [])
            if session_topics:
                memory['last_session_topics'] = session_topics
                memory['current_session_topics'] = []
                self._save_user_memory(user_id, memory)
        except Exception as e:
            logger.error(f"Session end learning error: {e}")

    # ── Analytics: What is Tade learning? ───────────────────────────

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get aggregate learning statistics for dashboard."""
        try:
            from app.database import SessionLocal, Interaction
            from sqlalchemy import func, desc
            db = SessionLocal()
            try:
                # Total interactions
                total = db.query(func.count(Interaction.id)).scalar() or 0

                # Knowledge gaps from DB
                gaps = self._get_top_knowledge_gaps(db)

                # Most common topics across all users
                top_topics = self._get_global_topic_distribution()

                return {
                    'total_interactions': total,
                    'knowledge_gaps': gaps,
                    'top_topics': top_topics,
                    'active_users': len(self._memory_cache)
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Learning stats error: {e}")
            return {}

    # ── Private helpers ─────────────────────────────────────────────

    def _load_user_memory(self, user_id: str) -> Dict[str, Any]:
        """Load user memory from cache or database."""
        # Try cache first
        if user_id in self._memory_cache:
            return self._memory_cache[user_id]

        # Try database
        try:
            from app.database import SessionLocal, User
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.phone_hash == user_id).first()
                if user and hasattr(user, 'interests') and user.interests:
                    # Parse stored interests as initial memory
                    memory = {
                        'top_topics': json.loads(user.interests) if isinstance(user.interests, str) else [],
                        'total_queries': 0,
                        'topic_counts': {},
                        'states_of_interest': [],
                        'politicians_tracked': [],
                        'tone_preference': 'mixed',
                        'feedback_signals': [],
                        'tool_usage': {},
                        'current_session_topics': [],
                        'last_session_topics': [],
                    }
                else:
                    memory = self._empty_memory()

                self._memory_cache[user_id] = memory
                return memory
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not load user memory: {e}")
            memory = self._empty_memory()
            self._memory_cache[user_id] = memory
            return memory

    def _save_user_memory(self, user_id: str, memory: Dict[str, Any]):
        """Save user memory to cache and periodically to database."""
        self._memory_cache[user_id] = memory

        # Persist to DB every 5 queries
        total = memory.get('total_queries', 0)
        if total % 5 == 0 and total > 0:
            self._persist_memory_to_db(user_id, memory)

    def _persist_memory_to_db(self, user_id: str, memory: Dict[str, Any]):
        """Write memory insights back to the User record."""
        try:
            from app.database import SessionLocal, User
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.phone_hash == user_id).first()
                if user:
                    # Store top topics as interests
                    top_topics = memory.get('top_topics', [])
                    if top_topics:
                        user.interests = json.dumps(top_topics[:10])
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not persist memory: {e}")

    def _empty_memory(self) -> Dict[str, Any]:
        """Create empty memory structure."""
        return {
            'top_topics': [],
            'total_queries': 0,
            'topic_counts': {},
            'states_of_interest': [],
            'politicians_tracked': [],
            'tone_preference': 'mixed',
            'feedback_signals': [],
            'tool_usage': {},
            'current_session_topics': [],
            'last_session_topics': [],
            'last_query': None,
            'last_response': None,
        }

    def _update_topic_counts(self, memory: Dict, topics: List[str]):
        """Update topic frequency counts and recompute top topics."""
        counts = memory.get('topic_counts', {})
        for topic in topics:
            counts[topic] = counts.get(topic, 0) + 1
        memory['topic_counts'] = counts

        # Recompute top topics (sorted by frequency)
        sorted_topics = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        memory['top_topics'] = [t[0] for t in sorted_topics[:10]]

    def _update_entity_tracking(self, memory: Dict, entities: Dict[str, List[str]]):
        """Update tracked states and politicians."""
        # States
        states = memory.get('states_of_interest', [])
        for state in entities.get('states', []):
            if state not in states:
                states.append(state)
        memory['states_of_interest'] = states[-10:]  # Keep last 10

        # Politicians
        pols = memory.get('politicians_tracked', [])
        for pol in entities.get('politicians', []):
            if pol not in pols:
                pols.append(pol)
        memory['politicians_tracked'] = pols[-15:]  # Keep last 15

    def _update_tone_preference(self, memory: Dict, tone: str):
        """Update tone preference with decay (recent messages weighted more)."""
        history = memory.get('tone_history', [])
        history.append(tone)
        history = history[-20:]  # Keep last 20 observations
        memory['tone_history'] = history

        # Majority vote
        counts = Counter(history)
        memory['tone_preference'] = counts.most_common(1)[0][0]

    def _record_feedback(
        self, memory: Dict, signal: str, confidence: float,
        query: str, response: str
    ):
        """Record a feedback signal."""
        signals = memory.get('feedback_signals', [])
        signals.append({
            'signal': signal,
            'confidence': confidence,
            'timestamp': datetime.utcnow().isoformat(),
            'query_preview': query[:100]
        })
        # Keep last 50 signals
        memory['feedback_signals'] = signals[-50:]

        # Also persist to AgentFeedback table for aggregate analysis
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                # Map signal to feedback_type
                feedback_type_map = {
                    'gratitude': 'implicit_positive',
                    'follow_up': 'implicit_positive',
                    'correction': 'correction',
                    'rephrase': 'implicit_negative',
                    'frustration': 'explicit_negative',
                    'topic_switch': 'implicit_negative',
                }
                feedback_type = feedback_type_map.get(signal, signal)

                from sqlalchemy import text
                db.execute(text("""
                    INSERT INTO agent_feedback (feedback_id, query, response, feedback_type, created_at)
                    VALUES (:fid, :query, :response, :ftype, NOW())
                    ON CONFLICT (feedback_id) DO NOTHING
                """), {
                    'fid': f"fb-{uuid.uuid4().hex[:12]}",
                    'query': query[:500],
                    'response': response[:500],
                    'ftype': feedback_type,
                })
                db.commit()
            except Exception as e:
                db.rollback()
                logger.debug(f"Could not persist feedback: {e}")
            finally:
                db.close()
        except Exception:
            pass

    def _record_knowledge_gap(self, user_id: str, gap: Dict[str, Any]):
        """Record a knowledge gap for prioritization."""
        try:
            from app.database import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                category = KnowledgeGapDetector.categorize_gap(gap['query'])

                # Upsert: increment count if same topic exists, else create
                db.execute(text("""
                    INSERT INTO agent_knowledge_gaps
                        (gap_id, topic, description, gap_type, sample_queries, query_count, priority, status, created_at)
                    VALUES
                        (:gid, :topic, :desc, :gtype, :samples, 1, 'medium', 'open', NOW())
                    ON CONFLICT (gap_id) DO UPDATE SET
                        query_count = agent_knowledge_gaps.query_count + 1,
                        updated_at = NOW()
                """), {
                    'gid': f"gap-{category}-{gap.get('tool', 'general')}",
                    'topic': category,
                    'desc': gap.get('detail', '')[:500],
                    'gtype': gap.get('gap_type', 'missing_data'),
                    'samples': json.dumps([gap['query'][:200]]),
                })
                db.commit()
            except Exception as e:
                db.rollback()
                logger.debug(f"Could not persist knowledge gap: {e}")
            finally:
                db.close()
        except Exception:
            pass

    def _get_top_knowledge_gaps(self, db) -> List[Dict]:
        """Get most common knowledge gaps."""
        try:
            from sqlalchemy import text
            rows = db.execute(text("""
                SELECT topic, description, query_count, status
                FROM agent_knowledge_gaps
                WHERE status = 'open'
                ORDER BY query_count DESC
                LIMIT 10
            """)).fetchall()
            return [
                {'topic': r[0], 'description': r[1], 'hit_count': r[2], 'status': r[3]}
                for r in rows
            ]
        except Exception:
            return []

    def _get_global_topic_distribution(self) -> Dict[str, int]:
        """Get topic distribution across all active users."""
        global_counts: Dict[str, int] = {}
        for user_id, memory in self._memory_cache.items():
            for topic, count in memory.get('topic_counts', {}).items():
                global_counts[topic] = global_counts.get(topic, 0) + count
        return dict(sorted(global_counts.items(), key=lambda x: x[1], reverse=True)[:10])


# =============================================================================
# SINGLETON
# =============================================================================

_learning_service: Optional[LearningService] = None


def get_learning_service() -> LearningService:
    """Get or create the global learning service instance."""
    global _learning_service
    if _learning_service is None:
        _learning_service = LearningService()
    return _learning_service
