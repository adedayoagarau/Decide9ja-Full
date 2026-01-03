"""
Historical Elections Service for Decide9ja.

Handles queries about:
- Past election results
- State-by-state comparisons
- Party performance history
"""
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ElectionResult:
    """Represents an election result."""
    year: int
    election_type: str
    state: Optional[str]
    constituency: Optional[str]
    winner_name: str
    winner_party: str
    winner_votes: int
    winner_percentage: float
    total_votes: int
    runner_up_name: Optional[str] = None
    runner_up_party: Optional[str] = None
    runner_up_votes: Optional[int] = None


@dataclass
class CandidateResult:
    """Represents a candidate's result in an election."""
    candidate_name: str
    party: str
    votes: int
    vote_percentage: float
    position: int
    is_winner: bool


class ElectionsService:
    """Service for querying historical election data."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy load database engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            import os
            self._engine = create_engine(os.getenv('DATABASE_URL'))
        return self._engine

    def get_presidential_results(self, year: int) -> List[CandidateResult]:
        """Get presidential election results for a year."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT er.candidate_name, er.party, er.votes,
                           er.vote_percentage, er.position, er.is_winner
                    FROM election_results er
                    JOIN elections e ON er.election_id = e.id
                    WHERE e.year = :year
                      AND e.election_type = 'Presidential'
                    ORDER BY er.position
                '''), {'year': year})

                return [CandidateResult(
                    candidate_name=row[0], party=row[1], votes=row[2],
                    vote_percentage=row[3] or 0, position=row[4] or 0,
                    is_winner=row[5] or False
                ) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get presidential results: {e}")
            return []

    def get_state_results(
        self,
        state: str,
        year: int = None,
        election_type: str = None
    ) -> List[ElectionResult]:
        """Get election results for a state."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT e.year, e.election_type, e.state, e.constituency,
                           e.total_votes_cast,
                           er.candidate_name, er.party, er.votes, er.vote_percentage
                    FROM elections e
                    JOIN election_results er ON e.id = er.election_id
                    WHERE e.state ILIKE :state
                      AND er.is_winner = TRUE
                '''
                params = {'state': f'%{state}%'}

                if year:
                    query += ' AND e.year = :year'
                    params['year'] = year

                if election_type:
                    query += ' AND e.election_type ILIKE :etype'
                    params['etype'] = f'%{election_type}%'

                query += ' ORDER BY e.year DESC, e.election_type'

                result = conn.execute(text(query), params)

                return [ElectionResult(
                    year=row[0], election_type=row[1], state=row[2],
                    constituency=row[3], total_votes=row[4] or 0,
                    winner_name=row[5], winner_party=row[6],
                    winner_votes=row[7], winner_percentage=row[8] or 0
                ) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get state results: {e}")
            return []

    def get_party_performance(
        self,
        party: str,
        year: int = None,
        election_type: str = 'Presidential'
    ) -> Dict[str, any]:
        """Get party performance across states."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT e.state, er.votes, er.vote_percentage, er.is_winner
                    FROM election_results er
                    JOIN elections e ON er.election_id = e.id
                    WHERE er.party ILIKE :party
                      AND e.election_type = :etype
                '''
                params = {'party': f'%{party}%', 'etype': election_type}

                if year:
                    query += ' AND e.year = :year'
                    params['year'] = year
                else:
                    # Default to most recent
                    query += ' AND e.year = (SELECT MAX(year) FROM elections WHERE election_type = :etype)'

                query += ' ORDER BY er.votes DESC'

                result = conn.execute(text(query), params)

                states_won = []
                total_votes = 0
                for row in result:
                    total_votes += row[1] or 0
                    if row[3]:  # is_winner
                        states_won.append(row[0])

                return {
                    'party': party.upper(),
                    'states_won': states_won,
                    'total_votes': total_votes,
                    'states_count': len(states_won)
                }

        except Exception as e:
            logger.warning(f"Failed to get party performance: {e}")
            return {'party': party, 'states_won': [], 'total_votes': 0}

    def compare_elections(self, year1: int, year2: int) -> Dict[str, any]:
        """Compare results between two elections."""
        results1 = self.get_presidential_results(year1)
        results2 = self.get_presidential_results(year2)

        comparison = {
            'year1': year1,
            'year2': year2,
            'results1': results1[:3] if results1 else [],
            'results2': results2[:3] if results2 else []
        }

        return comparison

    def format_presidential_results(
        self,
        results: List[CandidateResult],
        year: int
    ) -> str:
        """Format presidential results for display."""
        if not results:
            return f"I don't have results for the {year} presidential election."

        response = f"🗳️ *{year} Presidential Election Results*\n\n"

        for i, r in enumerate(results[:5], 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            winner_badge = " ✅" if r.is_winner else ""
            response += f"{emoji} *{r.candidate_name}* ({r.party}){winner_badge}\n"
            response += f"   {r.votes:,} votes ({r.vote_percentage:.1f}%)\n\n"

        return response

    def format_state_results(
        self,
        results: List[ElectionResult],
        state: str
    ) -> str:
        """Format state results for display."""
        if not results:
            return f"I don't have election results for {state}."

        response = f"🗳️ *Election Results in {state}*\n\n"

        for r in results[:5]:
            response += f"*{r.year} {r.election_type}*\n"
            response += f"Winner: {r.winner_name} ({r.winner_party})\n"
            response += f"Votes: {r.winner_votes:,} ({r.winner_percentage:.1f}%)\n\n"

        return response

    def format_party_performance(self, perf: Dict) -> str:
        """Format party performance for display."""
        response = f"📊 *{perf['party']} Performance*\n\n"
        response += f"States won: {perf['states_count']}\n"
        response += f"Total votes: {perf['total_votes']:,}\n"

        if perf['states_won']:
            response += f"\n*States:*\n"
            for state in perf['states_won'][:10]:
                response += f"• {state}\n"

        return response


# Singleton instance
elections_service = ElectionsService()


def get_election_results(year: int = 2023, election_type: str = "Presidential") -> str:
    """Convenience function for message handler."""
    if election_type.lower() == "presidential":
        results = elections_service.get_presidential_results(year)
        return elections_service.format_presidential_results(results, year)
    return f"I don't have {election_type} results for {year} yet."


def get_state_election_results(state: str, year: int = None) -> str:
    """Convenience function for state results."""
    results = elections_service.get_state_results(state, year)
    return elections_service.format_state_results(results, state)


def get_party_results(party: str, year: int = 2023) -> str:
    """Convenience function for party performance."""
    perf = elections_service.get_party_performance(party, year)
    return elections_service.format_party_performance(perf)
