"""
Poll Results Service for Decide9ja.

Provides:
- Results aggregation
- Segmented results (by state, age, gender)
- Cross-tabulation
- Minimum sample handling
- User-facing result formatting
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Minimum responses needed to show breakdown
MIN_SAMPLE_SIZE = 30
MIN_SEGMENT_SIZE = 10


@dataclass
class PollOptionResult:
    """Result for a single poll option."""
    option: str
    count: int
    percentage: float


@dataclass
class PollResults:
    """Aggregated poll results."""
    poll_id: int
    question: str
    total_responses: int
    options: List[PollOptionResult]
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class SegmentedResult:
    """Results for a specific segment."""
    segment_name: str
    segment_value: str
    total_responses: int
    options: List[PollOptionResult]
    has_enough_data: bool = True


class PollResultsService:
    """Service for poll results and analytics."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy load database engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            import os
            self._engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./decide9ja.db'))
        return self._engine

    # =========================================
    # Basic Results Aggregation
    # =========================================

    def get_poll_results(self, poll_id: int) -> Optional[PollResults]:
        """Get aggregated results for a poll."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                # Get poll question
                poll_result = conn.execute(text('''
                    SELECT question FROM polls WHERE id = :poll_id
                '''), {'poll_id': poll_id})
                poll_row = poll_result.fetchone()

                if not poll_row:
                    return None

                # Get response counts
                result = conn.execute(text('''
                    SELECT response, COUNT(*) as count
                    FROM poll_responses
                    WHERE poll_id = :poll_id
                    GROUP BY response
                    ORDER BY count DESC
                '''), {'poll_id': poll_id})

                rows = result.fetchall()
                total = sum(row[1] for row in rows)

                if total == 0:
                    return PollResults(
                        poll_id=poll_id,
                        question=poll_row[0],
                        total_responses=0,
                        options=[]
                    )

                options = [
                    PollOptionResult(
                        option=row[0],
                        count=row[1],
                        percentage=round(row[1] / total * 100, 1)
                    )
                    for row in rows
                ]

                return PollResults(
                    poll_id=poll_id,
                    question=poll_row[0],
                    total_responses=total,
                    options=options
                )

        except Exception as e:
            logger.error(f"Failed to get poll results: {e}")
            return None

    # =========================================
    # Segmented Results
    # =========================================

    def get_results_by_state(self, poll_id: int) -> List[SegmentedResult]:
        """Get poll results broken down by state."""
        return self._get_segmented_results(poll_id, 'user_state', 'State')

    def get_results_by_age(self, poll_id: int) -> List[SegmentedResult]:
        """Get poll results broken down by age range."""
        return self._get_segmented_results(poll_id, 'user_age_range', 'Age Range')

    def get_results_by_gender(self, poll_id: int) -> List[SegmentedResult]:
        """Get poll results broken down by gender."""
        return self._get_segmented_results(poll_id, 'user_gender', 'Gender')

    def _get_segmented_results(
        self,
        poll_id: int,
        segment_column: str,
        segment_name: str
    ) -> List[SegmentedResult]:
        """Get results segmented by a specific column."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                # Get unique segment values with counts
                result = conn.execute(text(f'''
                    SELECT {segment_column}, response, COUNT(*) as count
                    FROM poll_responses
                    WHERE poll_id = :poll_id
                      AND {segment_column} IS NOT NULL
                    GROUP BY {segment_column}, response
                    ORDER BY {segment_column}, count DESC
                '''), {'poll_id': poll_id})

                rows = result.fetchall()

                # Group by segment
                segments: Dict[str, List[Tuple[str, int]]] = {}
                for row in rows:
                    segment_val = row[0]
                    if segment_val not in segments:
                        segments[segment_val] = []
                    segments[segment_val].append((row[1], row[2]))

                results = []
                for segment_val, options_data in segments.items():
                    total = sum(opt[1] for opt in options_data)
                    has_enough = total >= MIN_SEGMENT_SIZE

                    options = [
                        PollOptionResult(
                            option=opt[0],
                            count=opt[1],
                            percentage=round(opt[1] / total * 100, 1) if has_enough else 0
                        )
                        for opt in options_data
                    ]

                    results.append(SegmentedResult(
                        segment_name=segment_name,
                        segment_value=segment_val,
                        total_responses=total,
                        options=options,
                        has_enough_data=has_enough
                    ))

                return sorted(results, key=lambda x: x.total_responses, reverse=True)

        except Exception as e:
            logger.error(f"Failed to get segmented results: {e}")
            return []

    def get_results_for_user_location(
        self,
        poll_id: int,
        user_state: str = None,
        user_lga: str = None
    ) -> Optional[SegmentedResult]:
        """Get poll results for user's location (state or LGA)."""
        if not user_state:
            return None

        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                # Try LGA first if provided
                if user_lga:
                    result = conn.execute(text('''
                        SELECT response, COUNT(*) as count
                        FROM poll_responses
                        WHERE poll_id = :poll_id
                          AND user_state = :state
                          AND user_lga = :lga
                        GROUP BY response
                        ORDER BY count DESC
                    '''), {'poll_id': poll_id, 'state': user_state, 'lga': user_lga})

                    rows = result.fetchall()
                    total = sum(row[1] for row in rows)

                    if total >= MIN_SEGMENT_SIZE:
                        return self._build_segment_result(
                            f"In {user_lga}, {user_state}",
                            user_lga,
                            rows,
                            total
                        )

                # Fall back to state level
                result = conn.execute(text('''
                    SELECT response, COUNT(*) as count
                    FROM poll_responses
                    WHERE poll_id = :poll_id
                      AND user_state = :state
                    GROUP BY response
                    ORDER BY count DESC
                '''), {'poll_id': poll_id, 'state': user_state})

                rows = result.fetchall()
                total = sum(row[1] for row in rows)

                if total >= MIN_SEGMENT_SIZE:
                    return self._build_segment_result(
                        f"In {user_state}",
                        user_state,
                        rows,
                        total
                    )

                return None

        except Exception as e:
            logger.error(f"Failed to get location results: {e}")
            return None

    def _build_segment_result(
        self,
        name: str,
        value: str,
        rows: List[Tuple[str, int]],
        total: int
    ) -> SegmentedResult:
        """Build a SegmentedResult from query rows."""
        options = [
            PollOptionResult(
                option=row[0],
                count=row[1],
                percentage=round(row[1] / total * 100, 1)
            )
            for row in rows
        ]

        return SegmentedResult(
            segment_name=name,
            segment_value=value,
            total_responses=total,
            options=options,
            has_enough_data=True
        )

    # =========================================
    # Cross-Tabulation
    # =========================================

    def get_cross_tabulation(
        self,
        poll_id: int,
        segment1: str,
        segment2: str
    ) -> Dict[str, Dict[str, List[PollOptionResult]]]:
        """
        Get cross-tabulated results (e.g., age × state).

        Returns nested dict: segment1_value -> segment2_value -> options
        """
        valid_segments = ['user_state', 'user_age_range', 'user_gender', 'user_lga']

        if segment1 not in valid_segments or segment2 not in valid_segments:
            return {}

        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text(f'''
                    SELECT {segment1}, {segment2}, response, COUNT(*) as count
                    FROM poll_responses
                    WHERE poll_id = :poll_id
                      AND {segment1} IS NOT NULL
                      AND {segment2} IS NOT NULL
                    GROUP BY {segment1}, {segment2}, response
                    ORDER BY {segment1}, {segment2}, count DESC
                '''), {'poll_id': poll_id})

                rows = result.fetchall()

                # Build nested structure
                cross_tab: Dict[str, Dict[str, Dict[str, int]]] = {}
                for row in rows:
                    seg1_val, seg2_val, response, count = row

                    if seg1_val not in cross_tab:
                        cross_tab[seg1_val] = {}
                    if seg2_val not in cross_tab[seg1_val]:
                        cross_tab[seg1_val][seg2_val] = {}

                    cross_tab[seg1_val][seg2_val][response] = count

                # Convert to PollOptionResult
                result_dict: Dict[str, Dict[str, List[PollOptionResult]]] = {}

                for seg1_val, seg2_dict in cross_tab.items():
                    result_dict[seg1_val] = {}

                    for seg2_val, responses in seg2_dict.items():
                        total = sum(responses.values())

                        if total >= MIN_SEGMENT_SIZE:
                            result_dict[seg1_val][seg2_val] = [
                                PollOptionResult(
                                    option=opt,
                                    count=cnt,
                                    percentage=round(cnt / total * 100, 1)
                                )
                                for opt, cnt in sorted(
                                    responses.items(),
                                    key=lambda x: x[1],
                                    reverse=True
                                )
                            ]

                return result_dict

        except Exception as e:
            logger.error(f"Failed to get cross-tabulation: {e}")
            return {}

    # =========================================
    # Formatting for Users
    # =========================================

    def format_results_for_user(
        self,
        poll_id: int,
        user_state: str = None,
        user_lga: str = None,
        show_local: bool = True
    ) -> str:
        """Format poll results for display to user after voting."""
        results = self.get_poll_results(poll_id)

        if not results or results.total_responses == 0:
            return "No responses recorded yet."

        message = "📊 *Current Results*\n\n"

        # Overall results
        for opt in results.options:
            bar = self._make_bar(opt.percentage)
            message += f"{opt.option}: {opt.percentage}% {bar}\n"

        message += f"\n_Based on {results.total_responses:,} responses_"

        # Local breakdown if available and enough data
        if show_local and user_state:
            local_results = self.get_results_for_user_location(
                poll_id, user_state, user_lga
            )

            if local_results and local_results.has_enough_data:
                message += f"\n\n📍 *{local_results.segment_name}:*\n"

                for opt in local_results.options:
                    message += f"  {opt.option}: {opt.percentage}%\n"

        return message

    def _make_bar(self, percentage: float, width: int = 10) -> str:
        """Create a text-based progress bar."""
        filled = int(percentage / 100 * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    def format_results_summary(self, poll_id: int) -> str:
        """Format a summary of poll results for admin."""
        results = self.get_poll_results(poll_id)

        if not results:
            return "Poll not found."

        message = f"📊 *{results.question}*\n\n"
        message += f"Total Responses: {results.total_responses:,}\n\n"

        for opt in results.options:
            bar = self._make_bar(opt.percentage, 15)
            message += f"{opt.option}\n"
            message += f"  {bar} {opt.percentage}% ({opt.count:,})\n\n"

        # Top states
        state_results = self.get_results_by_state(poll_id)[:5]
        if state_results:
            message += "\n*Top States by Response:*\n"
            for sr in state_results:
                if sr.has_enough_data:
                    message += f"  {sr.segment_value}: {sr.total_responses:,} responses\n"

        return message


# Singleton instance
poll_results_service = PollResultsService()


# Convenience functions
def get_poll_results(poll_id: int) -> Optional[PollResults]:
    """Get aggregated poll results."""
    return poll_results_service.get_poll_results(poll_id)


def format_user_results(
    poll_id: int,
    user_state: str = None,
    user_lga: str = None
) -> str:
    """Format results for user after voting."""
    return poll_results_service.format_results_for_user(
        poll_id, user_state, user_lga
    )
