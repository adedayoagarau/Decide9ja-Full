"""
Legislative Records Service for Decide9ja.

Handles queries about:
- Bills sponsored by politicians
- Voting records
- Committee assignments
- Legislative activity summaries
"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class Bill:
    """Represents a legislative bill."""
    id: int
    bill_number: str
    title: str
    short_title: Optional[str]
    sponsor_id: Optional[int]
    sponsor_name: Optional[str]
    sponsor_party: Optional[str]
    chamber: str
    status: str
    category: Optional[str]
    introduced_date: Optional[date]
    summary: Optional[str]


@dataclass
class Vote:
    """Represents a politician's vote on a bill."""
    bill_id: int
    bill_title: str
    politician_id: int
    politician_name: str
    vote: str  # Yes, No, Abstain, Absent
    vote_date: Optional[date]


@dataclass
class LegislativeSummary:
    """Summary of a politician's legislative activity."""
    politician_id: int
    politician_name: str
    party: str
    bills_sponsored: int
    bills_passed: int
    votes_cast: int
    yes_votes: int
    no_votes: int
    committees: List[str]


class LegislativeService:
    """Service for querying legislative records."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy load database engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            import os
            self._engine = create_engine(os.getenv('DATABASE_URL'))
        return self._engine

    def get_bills_by_sponsor(
        self,
        politician_id: int = None,
        politician_name: str = None,
        limit: int = 10
    ) -> List[Bill]:
        """
        Get bills sponsored by a politician.

        Args:
            politician_id: Direct ID lookup
            politician_name: Fuzzy name match
            limit: Max results

        Returns:
            List of Bill objects
        """
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                if politician_id:
                    result = conn.execute(text('''
                        SELECT b.id, b.bill_number, b.title, b.short_title,
                               b.sponsor_id, p.name, p.party, b.chamber,
                               b.status, b.category, b.introduced_date, b.summary
                        FROM bills b
                        LEFT JOIN politicians p ON b.sponsor_id = p.id
                        WHERE b.sponsor_id = :pid
                        ORDER BY b.introduced_date DESC
                        LIMIT :limit
                    '''), {'pid': politician_id, 'limit': limit})
                elif politician_name:
                    result = conn.execute(text('''
                        SELECT b.id, b.bill_number, b.title, b.short_title,
                               b.sponsor_id, p.name, p.party, b.chamber,
                               b.status, b.category, b.introduced_date, b.summary
                        FROM bills b
                        LEFT JOIN politicians p ON b.sponsor_id = p.id
                        WHERE p.name ILIKE :name_pattern
                        ORDER BY b.introduced_date DESC
                        LIMIT :limit
                    '''), {'name_pattern': f'%{politician_name}%', 'limit': limit})
                else:
                    return []

                bills = []
                for row in result:
                    bills.append(Bill(
                        id=row[0],
                        bill_number=row[1],
                        title=row[2],
                        short_title=row[3],
                        sponsor_id=row[4],
                        sponsor_name=row[5],
                        sponsor_party=row[6],
                        chamber=row[7],
                        status=row[8],
                        category=row[9],
                        introduced_date=row[10],
                        summary=row[11]
                    ))
                return bills

        except Exception as e:
            logger.warning(f"Failed to get bills by sponsor: {e}")
            return []

    def get_bill_by_title(self, title_query: str, limit: int = 5) -> List[Bill]:
        """Search for bills by title."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT b.id, b.bill_number, b.title, b.short_title,
                           b.sponsor_id, p.name, p.party, b.chamber,
                           b.status, b.category, b.introduced_date, b.summary
                    FROM bills b
                    LEFT JOIN politicians p ON b.sponsor_id = p.id
                    WHERE b.title ILIKE :pattern
                       OR b.short_title ILIKE :pattern
                       OR b.summary ILIKE :pattern
                    ORDER BY b.introduced_date DESC
                    LIMIT :limit
                '''), {'pattern': f'%{title_query}%', 'limit': limit})

                return [Bill(
                    id=row[0], bill_number=row[1], title=row[2],
                    short_title=row[3], sponsor_id=row[4],
                    sponsor_name=row[5], sponsor_party=row[6],
                    chamber=row[7], status=row[8], category=row[9],
                    introduced_date=row[10], summary=row[11]
                ) for row in result]

        except Exception as e:
            logger.warning(f"Failed to search bills: {e}")
            return []

    def get_voting_record(
        self,
        politician_id: int = None,
        politician_name: str = None,
        limit: int = 20
    ) -> List[Vote]:
        """Get a politician's voting record."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                if politician_id:
                    result = conn.execute(text('''
                        SELECT v.bill_id, b.title, v.politician_id,
                               p.name, v.vote, v.vote_date
                        FROM votes v
                        JOIN bills b ON v.bill_id = b.id
                        JOIN politicians p ON v.politician_id = p.id
                        WHERE v.politician_id = :pid
                        ORDER BY v.vote_date DESC
                        LIMIT :limit
                    '''), {'pid': politician_id, 'limit': limit})
                elif politician_name:
                    result = conn.execute(text('''
                        SELECT v.bill_id, b.title, v.politician_id,
                               p.name, v.vote, v.vote_date
                        FROM votes v
                        JOIN bills b ON v.bill_id = b.id
                        JOIN politicians p ON v.politician_id = p.id
                        WHERE p.name ILIKE :name_pattern
                        ORDER BY v.vote_date DESC
                        LIMIT :limit
                    '''), {'name_pattern': f'%{politician_name}%', 'limit': limit})
                else:
                    return []

                return [Vote(
                    bill_id=row[0], bill_title=row[1], politician_id=row[2],
                    politician_name=row[3], vote=row[4], vote_date=row[5]
                ) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get voting record: {e}")
            return []

    def get_legislative_summary(
        self,
        politician_id: int = None,
        politician_name: str = None
    ) -> Optional[LegislativeSummary]:
        """Get a summary of a politician's legislative activity."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                if politician_id:
                    result = conn.execute(text('''
                        SELECT politician_id, name, party,
                               bills_sponsored, bills_passed,
                               votes_cast, yes_votes, no_votes
                        FROM politician_legislative_summary
                        WHERE politician_id = :pid
                    '''), {'pid': politician_id})
                elif politician_name:
                    result = conn.execute(text('''
                        SELECT politician_id, name, party,
                               bills_sponsored, bills_passed,
                               votes_cast, yes_votes, no_votes
                        FROM politician_legislative_summary
                        WHERE name ILIKE :name_pattern
                        LIMIT 1
                    '''), {'name_pattern': f'%{politician_name}%'})
                else:
                    return None

                row = result.fetchone()
                if not row:
                    return None

                # Get committees
                committees_result = conn.execute(text('''
                    SELECT DISTINCT committee_name
                    FROM committee_assignments
                    WHERE politician_id = :pid
                    AND (end_date IS NULL OR end_date > NOW())
                '''), {'pid': row[0]})

                committees = [r[0] for r in committees_result]

                return LegislativeSummary(
                    politician_id=row[0],
                    politician_name=row[1],
                    party=row[2],
                    bills_sponsored=row[3] or 0,
                    bills_passed=row[4] or 0,
                    votes_cast=row[5] or 0,
                    yes_votes=row[6] or 0,
                    no_votes=row[7] or 0,
                    committees=committees
                )

        except Exception as e:
            logger.warning(f"Failed to get legislative summary: {e}")
            return None

    def get_recent_bills(self, chamber: str = None, limit: int = 10) -> List[Bill]:
        """Get recently introduced bills."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                if chamber:
                    result = conn.execute(text('''
                        SELECT b.id, b.bill_number, b.title, b.short_title,
                               b.sponsor_id, p.name, p.party, b.chamber,
                               b.status, b.category, b.introduced_date, b.summary
                        FROM bills b
                        LEFT JOIN politicians p ON b.sponsor_id = p.id
                        WHERE b.chamber = :chamber
                        ORDER BY b.introduced_date DESC
                        LIMIT :limit
                    '''), {'chamber': chamber, 'limit': limit})
                else:
                    result = conn.execute(text('''
                        SELECT b.id, b.bill_number, b.title, b.short_title,
                               b.sponsor_id, p.name, p.party, b.chamber,
                               b.status, b.category, b.introduced_date, b.summary
                        FROM bills b
                        LEFT JOIN politicians p ON b.sponsor_id = p.id
                        ORDER BY b.introduced_date DESC
                        LIMIT :limit
                    '''), {'limit': limit})

                return [Bill(
                    id=row[0], bill_number=row[1], title=row[2],
                    short_title=row[3], sponsor_id=row[4],
                    sponsor_name=row[5], sponsor_party=row[6],
                    chamber=row[7], status=row[8], category=row[9],
                    introduced_date=row[10], summary=row[11]
                ) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get recent bills: {e}")
            return []

    def format_bill_response(self, bill: Bill) -> str:
        """Format a bill for display."""
        response = f"📜 *{bill.short_title or bill.title}*\n"
        if bill.bill_number:
            response += f"Bill: {bill.bill_number}\n"
        response += f"Chamber: {bill.chamber}\n"
        response += f"Status: {bill.status}\n"
        if bill.sponsor_name:
            response += f"Sponsor: {bill.sponsor_name} ({bill.sponsor_party or 'N/A'})\n"
        if bill.introduced_date:
            response += f"Introduced: {bill.introduced_date.strftime('%B %d, %Y')}\n"
        if bill.summary:
            summary = bill.summary[:200] + "..." if len(bill.summary) > 200 else bill.summary
            response += f"\n{summary}"
        return response

    def format_bills_list(self, bills: List[Bill], title: str = "Bills") -> str:
        """Format a list of bills for display."""
        if not bills:
            return "No bills found."

        response = f"📋 *{title}*\n\n"
        for i, bill in enumerate(bills[:5], 1):
            status_emoji = {
                'Introduced': '📝',
                'Committee': '🔍',
                'Second Reading': '📖',
                'Third Reading': '📚',
                'Passed': '✅',
                'Signed': '✍️',
                'Rejected': '❌'
            }.get(bill.status, '📄')

            response += f"{i}. {status_emoji} {bill.short_title or bill.title[:50]}\n"
            response += f"   Status: {bill.status}\n\n"

        if len(bills) > 5:
            response += f"_...and {len(bills) - 5} more_"

        return response

    def format_legislative_summary(self, summary: LegislativeSummary) -> str:
        """Format a legislative summary for display."""
        response = f"📊 *Legislative Record: {summary.politician_name}*\n"
        response += f"Party: {summary.party}\n\n"

        response += "📜 *Bills*\n"
        response += f"• Sponsored: {summary.bills_sponsored}\n"
        response += f"• Passed into law: {summary.bills_passed}\n\n"

        response += "🗳️ *Voting Record*\n"
        response += f"• Total votes cast: {summary.votes_cast}\n"
        if summary.votes_cast > 0:
            yes_pct = (summary.yes_votes / summary.votes_cast) * 100
            response += f"• Yes votes: {summary.yes_votes} ({yes_pct:.0f}%)\n"
            response += f"• No votes: {summary.no_votes}\n\n"

        if summary.committees:
            response += "🏛️ *Committees*\n"
            for committee in summary.committees[:5]:
                response += f"• {committee}\n"

        return response


# Singleton instance
legislative_service = LegislativeService()


def get_bills_by_politician(name: str) -> str:
    """Convenience function for message handler."""
    bills = legislative_service.get_bills_by_sponsor(politician_name=name)
    return legislative_service.format_bills_list(
        bills,
        title=f"Bills sponsored by {name}"
    )


def get_politician_record(name: str) -> str:
    """Convenience function for legislative record queries."""
    summary = legislative_service.get_legislative_summary(politician_name=name)
    if summary:
        return legislative_service.format_legislative_summary(summary)
    return f"I don't have legislative records for {name} yet."


def search_bills(query: str) -> str:
    """Convenience function for bill searches."""
    bills = legislative_service.get_bill_by_title(query)
    return legislative_service.format_bills_list(bills, title=f"Bills matching '{query}'")
