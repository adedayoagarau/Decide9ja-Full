"""
Cabinet & Ministers Service for Decide9ja.

Handles queries about:
- Current ministers and their portfolios
- Ministry information
- Cabinet structure
"""
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Minister:
    """Represents a minister."""
    politician_id: int
    name: str
    party: str
    state_of_origin: str
    ministry: str
    ministry_short: str
    sector: str
    position: str
    start_date: Optional[str]


@dataclass
class Ministry:
    """Represents a ministry."""
    id: int
    name: str
    short_name: str
    sector: str
    description: Optional[str]
    current_minister: Optional[str]
    minister_party: Optional[str]


class CabinetService:
    """Service for querying cabinet and ministry information."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy load database engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            import os
            self._engine = create_engine(os.getenv('DATABASE_URL'))
        return self._engine

    def get_minister_by_ministry(self, ministry_query: str) -> Optional[Minister]:
        """Find the minister for a given ministry."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT politician_id, name, party, state_of_origin,
                           ministry, ministry_short, sector, position, start_date
                    FROM current_ministers
                    WHERE ministry ILIKE :pattern
                       OR ministry_short ILIKE :pattern
                    LIMIT 1
                '''), {'pattern': f'%{ministry_query}%'})

                row = result.fetchone()
                if row:
                    return Minister(
                        politician_id=row[0],
                        name=row[1],
                        party=row[2],
                        state_of_origin=row[3],
                        ministry=row[4],
                        ministry_short=row[5],
                        sector=row[6],
                        position=row[7],
                        start_date=str(row[8]) if row[8] else None
                    )
        except Exception as e:
            logger.warning(f"Failed to get minister: {e}")
        return None

    def get_all_ministers(self, sector: str = None) -> List[Minister]:
        """Get all current ministers, optionally filtered by sector."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                if sector:
                    result = conn.execute(text('''
                        SELECT politician_id, name, party, state_of_origin,
                               ministry, ministry_short, sector, position, start_date
                        FROM current_ministers
                        WHERE sector ILIKE :sector
                        ORDER BY ministry
                    '''), {'sector': f'%{sector}%'})
                else:
                    result = conn.execute(text('''
                        SELECT politician_id, name, party, state_of_origin,
                               ministry, ministry_short, sector, position, start_date
                        FROM current_ministers
                        ORDER BY ministry
                    '''))

                return [Minister(
                    politician_id=row[0], name=row[1], party=row[2],
                    state_of_origin=row[3], ministry=row[4],
                    ministry_short=row[5], sector=row[6],
                    position=row[7], start_date=str(row[8]) if row[8] else None
                ) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get ministers: {e}")
            return []

    def get_ministry_info(self, ministry_query: str) -> Optional[Ministry]:
        """Get information about a ministry."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT m.id, m.name, m.short_name, m.sector, m.description,
                           p.name as minister_name, p.party
                    FROM ministries m
                    LEFT JOIN minister_appointments ma ON m.id = ma.ministry_id AND ma.is_current = TRUE
                    LEFT JOIN politicians p ON ma.politician_id = p.id
                    WHERE m.name ILIKE :pattern
                       OR m.short_name ILIKE :pattern
                    LIMIT 1
                '''), {'pattern': f'%{ministry_query}%'})

                row = result.fetchone()
                if row:
                    return Ministry(
                        id=row[0],
                        name=row[1],
                        short_name=row[2],
                        sector=row[3],
                        description=row[4],
                        current_minister=row[5],
                        minister_party=row[6]
                    )
        except Exception as e:
            logger.warning(f"Failed to get ministry: {e}")
        return None

    def get_ministers_by_state(self, state: str) -> List[Minister]:
        """Get ministers from a particular state."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT politician_id, name, party, state_of_origin,
                           ministry, ministry_short, sector, position, start_date
                    FROM current_ministers
                    WHERE state_of_origin ILIKE :state
                    ORDER BY ministry
                '''), {'state': f'%{state}%'})

                return [Minister(
                    politician_id=row[0], name=row[1], party=row[2],
                    state_of_origin=row[3], ministry=row[4],
                    ministry_short=row[5], sector=row[6],
                    position=row[7], start_date=str(row[8]) if row[8] else None
                ) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get ministers by state: {e}")
            return []

    def format_minister_response(self, minister: Minister) -> str:
        """Format a minister for display."""
        response = f"🏛️ *{minister.ministry}*\n\n"
        response += f"👤 *{minister.position}:* {minister.name}\n"
        response += f"🎗️ Party: {minister.party}\n"
        response += f"🗺️ State of Origin: {minister.state_of_origin}\n"
        response += f"📁 Sector: {minister.sector}\n"
        if minister.start_date:
            response += f"📅 Appointed: {minister.start_date}\n"
        return response

    def format_ministers_list(self, ministers: List[Minister], title: str = "Ministers") -> str:
        """Format a list of ministers for display."""
        if not ministers:
            return "No ministers found."

        response = f"🏛️ *{title}*\n\n"
        for m in ministers[:10]:
            response += f"• *{m.ministry_short}*: {m.name} ({m.party})\n"

        if len(ministers) > 10:
            response += f"\n_...and {len(ministers) - 10} more_"

        return response


# Singleton instance
cabinet_service = CabinetService()


def get_minister_of(ministry: str) -> str:
    """Convenience function for message handler."""
    minister = cabinet_service.get_minister_by_ministry(ministry)
    if minister:
        return cabinet_service.format_minister_response(minister)
    return f"I don't have information about the Minister of {ministry}."


def list_cabinet(sector: str = None) -> str:
    """Convenience function to list cabinet members."""
    ministers = cabinet_service.get_all_ministers(sector)
    title = f"{sector.title()} Ministers" if sector else "Federal Cabinet"
    return cabinet_service.format_ministers_list(ministers, title)
