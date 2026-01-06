"""
Voting Record & Bill Tracking Service for Decide9ja.

Provides comprehensive tracking of:
- Legislative bills and their progress
- Individual politician voting records
- Voting sessions and results
- Party loyalty analysis

Usage:
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()
    bills = service.get_bills(chamber="senate", status="committee")
    record = service.get_politician_voting_record("godswill-akpabio")
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
import hashlib

from app.database import (
    SessionLocal, Bill, Vote, VotingSession, PoliticianVotingRecord,
    Politician
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BillSummary:
    """Summary of a bill for listing."""
    bill_id: str
    title: str
    short_title: Optional[str]
    chamber: str
    status: str
    sponsor_name: Optional[str]
    sponsor_slug: Optional[str]
    category: Optional[str]
    introduced_date: Optional[str]
    last_action: Optional[str]
    last_action_date: Optional[str]


@dataclass
class BillDetail:
    """Full bill details."""
    bill_id: str
    title: str
    short_title: Optional[str]
    description: Optional[str]
    bill_type: Optional[str]
    chamber: str
    originating_chamber: Optional[str]
    sponsor_name: Optional[str]
    sponsor_slug: Optional[str]
    co_sponsors: List[str] = field(default_factory=list)
    status: str = "introduced"
    current_stage: Optional[str] = None
    introduced_date: Optional[str] = None
    last_action_date: Optional[str] = None
    last_action: Optional[str] = None
    timeline: List[Dict] = field(default_factory=list)
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    full_text_url: Optional[str] = None
    # Voting results
    ayes_count: Optional[int] = None
    nays_count: Optional[int] = None
    abstentions_count: Optional[int] = None
    vote_date: Optional[str] = None


@dataclass
class VoteRecord:
    """Single vote record."""
    vote_id: str
    bill_id: Optional[str]
    bill_title: Optional[str]
    motion_title: Optional[str]
    chamber: str
    vote_date: str
    vote_cast: str  # aye, nay, abstain, absent
    voted_with_party: Optional[bool]


@dataclass
class PoliticianVotingSummary:
    """Politician's voting record summary."""
    politician_slug: str
    politician_name: str
    party: Optional[str]
    position: Optional[str]
    # Stats
    total_votes: int = 0
    attendance_rate: Optional[float] = None
    participation_rate: Optional[float] = None
    party_loyalty_rate: Optional[float] = None
    # Breakdown
    ayes: int = 0
    nays: int = 0
    abstentions: int = 0
    absent: int = 0
    # Bills
    bills_sponsored: int = 0
    bills_co_sponsored: int = 0
    bills_passed: int = 0
    # Recent votes
    recent_votes: List[VoteRecord] = field(default_factory=list)
    # Notable votes
    notable_votes: List[Dict] = field(default_factory=list)


@dataclass
class VotingSessionSummary:
    """Summary of a voting session."""
    session_id: str
    chamber: str
    session_date: str
    bill_id: Optional[str]
    bill_title: Optional[str]
    motion_title: Optional[str]
    vote_type: Optional[str]
    ayes: int
    nays: int
    abstentions: int
    absent: int
    result: str
    party_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)


# =============================================================================
# Bill Status Constants
# =============================================================================

BILL_STATUS_ORDER = [
    "introduced",
    "first_reading",
    "second_reading",
    "committee",
    "third_reading",
    "passed",
    "presidential_assent",
    "enacted"
]

BILL_STATUS_DESCRIPTIONS = {
    "introduced": "Bill has been introduced to the chamber",
    "first_reading": "Bill has passed first reading",
    "second_reading": "Bill is undergoing second reading debates",
    "committee": "Bill is under committee review",
    "third_reading": "Bill is undergoing final reading",
    "passed": "Bill passed by chamber, awaiting other chamber or assent",
    "presidential_assent": "Awaiting Presidential signature",
    "enacted": "Bill has been signed into law",
    "rejected": "Bill was rejected",
    "withdrawn": "Bill was withdrawn by sponsor"
}


# =============================================================================
# Service Class
# =============================================================================

class VotingRecordService:
    """
    Service for tracking bills and voting records.
    """

    def __init__(self):
        pass

    # =========================================================================
    # Bill Methods
    # =========================================================================

    def get_bills(
        self,
        chamber: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        sponsor_slug: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get list of bills with filters.
        """
        db = SessionLocal()
        try:
            query = db.query(Bill)

            if chamber:
                query = query.filter(Bill.chamber == chamber.lower())

            if status:
                query = query.filter(Bill.status == status)

            if category:
                query = query.filter(Bill.category == category)

            if sponsor_slug:
                query = query.filter(Bill.sponsor_slug == sponsor_slug)

            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (Bill.title.ilike(search_term)) |
                    (Bill.short_title.ilike(search_term)) |
                    (Bill.description.ilike(search_term))
                )

            # Get total count
            total = query.count()

            # Get bills with pagination
            bills = query.order_by(
                Bill.last_action_date.desc().nullsfirst(),
                Bill.introduced_date.desc().nullsfirst()
            ).offset(offset).limit(limit).all()

            return {
                "bills": [
                    BillSummary(
                        bill_id=b.bill_id,
                        title=b.title,
                        short_title=b.short_title,
                        chamber=b.chamber,
                        status=b.status,
                        sponsor_name=b.sponsor_name,
                        sponsor_slug=b.sponsor_slug,
                        category=b.category,
                        introduced_date=b.introduced_date.isoformat() if b.introduced_date else None,
                        last_action=b.last_action,
                        last_action_date=b.last_action_date.isoformat() if b.last_action_date else None
                    ).__dict__
                    for b in bills
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }

        finally:
            db.close()

    def get_bill(self, bill_id: str) -> Optional[BillDetail]:
        """
        Get detailed information about a specific bill.
        """
        db = SessionLocal()
        try:
            bill = db.query(Bill).filter(Bill.bill_id == bill_id).first()

            if not bill:
                return None

            # Parse JSON fields
            co_sponsors = []
            if bill.co_sponsors_json:
                try:
                    co_sponsors = json.loads(bill.co_sponsors_json)
                except:
                    pass

            timeline = []
            if bill.timeline_json:
                try:
                    timeline = json.loads(bill.timeline_json)
                except:
                    pass

            tags = []
            if bill.tags_json:
                try:
                    tags = json.loads(bill.tags_json)
                except:
                    pass

            return BillDetail(
                bill_id=bill.bill_id,
                title=bill.title,
                short_title=bill.short_title,
                description=bill.description,
                bill_type=bill.bill_type,
                chamber=bill.chamber,
                originating_chamber=bill.originating_chamber,
                sponsor_name=bill.sponsor_name,
                sponsor_slug=bill.sponsor_slug,
                co_sponsors=co_sponsors,
                status=bill.status,
                current_stage=bill.current_stage,
                introduced_date=bill.introduced_date.isoformat() if bill.introduced_date else None,
                last_action_date=bill.last_action_date.isoformat() if bill.last_action_date else None,
                last_action=bill.last_action,
                timeline=timeline,
                summary=bill.summary,
                category=bill.category,
                tags=tags,
                full_text_url=bill.full_text_url,
                ayes_count=bill.ayes_count,
                nays_count=bill.nays_count,
                abstentions_count=bill.abstentions_count,
                vote_date=bill.vote_date.isoformat() if bill.vote_date else None
            )

        finally:
            db.close()

    def get_bill_votes(self, bill_id: str) -> List[Dict[str, Any]]:
        """
        Get all votes cast on a specific bill.
        """
        db = SessionLocal()
        try:
            votes = db.query(Vote).filter(
                Vote.bill_id == bill_id
            ).order_by(Vote.vote_date.desc()).all()

            return [
                {
                    "politician_slug": v.politician_slug,
                    "politician_name": v.politician_name,
                    "party": v.politician_party,
                    "state": v.politician_state,
                    "vote_cast": v.vote_cast,
                    "voted_with_party": v.voted_with_party,
                    "vote_date": v.vote_date.isoformat() if v.vote_date else None
                }
                for v in votes
            ]

        finally:
            db.close()

    def create_bill(self, bill_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new bill record.
        """
        db = SessionLocal()
        try:
            # Generate bill_id if not provided
            bill_id = bill_data.get("bill_id")
            if not bill_id:
                chamber_prefix = "SB" if bill_data.get("chamber") == "senate" else "HB"
                year = datetime.now().year
                # Generate unique number
                count = db.query(Bill).filter(Bill.bill_id.like(f"{chamber_prefix}%{year}%")).count()
                bill_id = f"{chamber_prefix}.{count + 1}.{year}"

            bill = Bill(
                bill_id=bill_id,
                title=bill_data["title"],
                short_title=bill_data.get("short_title"),
                description=bill_data.get("description"),
                bill_type=bill_data.get("bill_type"),
                chamber=bill_data.get("chamber", "house").lower(),
                originating_chamber=bill_data.get("originating_chamber"),
                sponsor_slug=bill_data.get("sponsor_slug"),
                sponsor_name=bill_data.get("sponsor_name"),
                co_sponsors_json=json.dumps(bill_data.get("co_sponsors", [])),
                status=bill_data.get("status", "introduced"),
                current_stage=bill_data.get("current_stage"),
                introduced_date=datetime.fromisoformat(bill_data["introduced_date"]) if bill_data.get("introduced_date") else datetime.now(),
                last_action=bill_data.get("last_action", "Bill introduced"),
                last_action_date=datetime.now(),
                timeline_json=json.dumps([{
                    "date": datetime.now().isoformat(),
                    "action": "Bill introduced",
                    "chamber": bill_data.get("chamber", "house"),
                    "details": bill_data.get("description", "")
                }]),
                summary=bill_data.get("summary"),
                category=bill_data.get("category"),
                tags_json=json.dumps(bill_data.get("tags", [])),
                full_text_url=bill_data.get("full_text_url"),
                source_url=bill_data.get("source_url")
            )

            db.add(bill)
            db.commit()

            logger.info(f"Created bill: {bill_id}")
            return bill_id

        except Exception as e:
            logger.error(f"Failed to create bill: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    def update_bill_status(
        self,
        bill_id: str,
        new_status: str,
        action_description: str,
        vote_result: Optional[Dict] = None
    ) -> bool:
        """
        Update bill status and add to timeline.
        """
        db = SessionLocal()
        try:
            bill = db.query(Bill).filter(Bill.bill_id == bill_id).first()
            if not bill:
                return False

            # Update status
            bill.status = new_status
            bill.current_stage = BILL_STATUS_DESCRIPTIONS.get(new_status, new_status)
            bill.last_action = action_description
            bill.last_action_date = datetime.now()

            # Add to timeline
            timeline = []
            if bill.timeline_json:
                try:
                    timeline = json.loads(bill.timeline_json)
                except:
                    pass

            timeline.append({
                "date": datetime.now().isoformat(),
                "action": action_description,
                "status": new_status,
                "chamber": bill.chamber
            })
            bill.timeline_json = json.dumps(timeline)

            # Update vote results if provided
            if vote_result:
                bill.ayes_count = vote_result.get("ayes")
                bill.nays_count = vote_result.get("nays")
                bill.abstentions_count = vote_result.get("abstentions")
                bill.vote_date = datetime.now()

            db.commit()
            logger.info(f"Updated bill {bill_id} to status: {new_status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update bill: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    # =========================================================================
    # Voting Record Methods
    # =========================================================================

    def get_politician_voting_record(self, slug: str) -> Optional[PoliticianVotingSummary]:
        """
        Get comprehensive voting record for a politician.
        """
        db = SessionLocal()
        try:
            # Get politician info
            politician = db.query(Politician).filter(
                Politician.slug == slug
            ).first()

            if not politician:
                return None

            # Get pre-calculated record
            record = db.query(PoliticianVotingRecord).filter(
                PoliticianVotingRecord.politician_slug == slug
            ).first()

            # Get recent votes
            recent_votes = db.query(Vote).filter(
                Vote.politician_slug == slug
            ).order_by(Vote.vote_date.desc()).limit(10).all()

            # Get bills sponsored
            bills_sponsored = db.query(Bill).filter(
                Bill.sponsor_slug == slug
            ).count()

            recent_vote_records = []
            for v in recent_votes:
                # Get bill title if available
                bill_title = None
                if v.bill_id:
                    bill = db.query(Bill).filter(Bill.bill_id == v.bill_id).first()
                    if bill:
                        bill_title = bill.short_title or bill.title

                recent_vote_records.append(VoteRecord(
                    vote_id=v.vote_id,
                    bill_id=v.bill_id,
                    bill_title=bill_title,
                    motion_title=v.motion_title,
                    chamber=v.chamber,
                    vote_date=v.vote_date.isoformat() if v.vote_date else "",
                    vote_cast=v.vote_cast,
                    voted_with_party=v.voted_with_party
                ).__dict__)

            # Parse notable votes
            notable_votes = []
            if record and record.notable_votes_json:
                try:
                    notable_votes = json.loads(record.notable_votes_json)
                except:
                    pass

            return PoliticianVotingSummary(
                politician_slug=slug,
                politician_name=politician.name,
                party=politician.party,
                position=politician.position,
                total_votes=record.total_votes if record else 0,
                attendance_rate=record.attendance_rate if record else None,
                participation_rate=record.participation_rate if record else None,
                party_loyalty_rate=record.party_loyalty_rate if record else None,
                ayes=record.total_ayes if record else 0,
                nays=record.total_nays if record else 0,
                abstentions=record.total_abstentions if record else 0,
                absent=record.total_absent if record else 0,
                bills_sponsored=bills_sponsored,
                bills_co_sponsored=record.bills_co_sponsored if record else 0,
                bills_passed=record.bills_passed if record else 0,
                recent_votes=recent_vote_records,
                notable_votes=notable_votes
            )

        finally:
            db.close()

    def record_vote(
        self,
        politician_slug: str,
        vote_cast: str,
        vote_date: datetime,
        chamber: str,
        bill_id: Optional[str] = None,
        motion_title: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Record an individual vote.
        """
        db = SessionLocal()
        try:
            # Get politician info
            politician = db.query(Politician).filter(
                Politician.slug == politician_slug
            ).first()

            if not politician:
                logger.warning(f"Politician not found: {politician_slug}")
                return None

            # Generate vote_id
            date_str = vote_date.strftime("%Y-%m-%d")
            subject = bill_id or motion_title or "unknown"
            vote_id = f"vote-{subject[:20]}-{politician_slug[:30]}-{date_str}"

            # Check if vote already exists
            existing = db.query(Vote).filter(Vote.vote_id == vote_id).first()
            if existing:
                logger.info(f"Vote already recorded: {vote_id}")
                return vote_id

            vote = Vote(
                vote_id=vote_id,
                bill_id=bill_id,
                motion_title=motion_title,
                session_id=session_id,
                chamber=chamber.lower(),
                vote_date=vote_date,
                politician_slug=politician_slug,
                politician_name=politician.name,
                politician_party=politician.party,
                politician_state=politician.state,
                vote_cast=vote_cast.lower()
            )

            db.add(vote)
            db.commit()

            # Trigger record recalculation (async)
            self._queue_record_update(politician_slug)

            logger.info(f"Recorded vote: {vote_id}")
            return vote_id

        except Exception as e:
            logger.error(f"Failed to record vote: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    def recalculate_voting_record(self, politician_slug: str) -> bool:
        """
        Recalculate aggregate voting statistics for a politician.
        """
        db = SessionLocal()
        try:
            # Get all votes for politician
            votes = db.query(Vote).filter(
                Vote.politician_slug == politician_slug
            ).all()

            if not votes:
                return False

            # Calculate stats
            total = len(votes)
            ayes = sum(1 for v in votes if v.vote_cast == "aye")
            nays = sum(1 for v in votes if v.vote_cast == "nay")
            abstentions = sum(1 for v in votes if v.vote_cast == "abstain")
            absent = sum(1 for v in votes if v.vote_cast in ["absent", "excused"])

            attendance_rate = ((total - absent) / total * 100) if total > 0 else None
            participation_rate = ((ayes + nays) / total * 100) if total > 0 else None

            # Party loyalty
            with_party = sum(1 for v in votes if v.voted_with_party is True)
            party_votes = sum(1 for v in votes if v.voted_with_party is not None)
            party_loyalty_rate = (with_party / party_votes * 100) if party_votes > 0 else None

            # Get or create record
            record = db.query(PoliticianVotingRecord).filter(
                PoliticianVotingRecord.politician_slug == politician_slug
            ).first()

            if not record:
                record = PoliticianVotingRecord(politician_slug=politician_slug)
                db.add(record)

            record.total_votes = total
            record.total_ayes = ayes
            record.total_nays = nays
            record.total_abstentions = abstentions
            record.total_absent = absent
            record.attendance_rate = attendance_rate
            record.participation_rate = participation_rate
            record.party_loyalty_rate = party_loyalty_rate
            record.last_calculated = datetime.now()

            # Count bills
            bills_sponsored = db.query(Bill).filter(
                Bill.sponsor_slug == politician_slug
            ).count()
            record.bills_sponsored = bills_sponsored

            db.commit()
            logger.info(f"Recalculated voting record for: {politician_slug}")
            return True

        except Exception as e:
            logger.error(f"Failed to recalculate voting record: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def _queue_record_update(self, politician_slug: str):
        """Queue voting record recalculation (placeholder for async processing)."""
        # In production, this would add to a task queue
        # For now, we'll do it synchronously
        self.recalculate_voting_record(politician_slug)

    # =========================================================================
    # Voting Session Methods
    # =========================================================================

    def get_voting_sessions(
        self,
        chamber: Optional[str] = None,
        bill_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20
    ) -> List[VotingSessionSummary]:
        """
        Get voting sessions with filters.
        """
        db = SessionLocal()
        try:
            query = db.query(VotingSession)

            if chamber:
                query = query.filter(VotingSession.chamber == chamber.lower())

            if bill_id:
                query = query.filter(VotingSession.bill_id == bill_id)

            if start_date:
                query = query.filter(VotingSession.session_date >= start_date)

            if end_date:
                query = query.filter(VotingSession.session_date <= end_date)

            sessions = query.order_by(
                VotingSession.session_date.desc()
            ).limit(limit).all()

            results = []
            for s in sessions:
                # Get bill title if available
                bill_title = None
                if s.bill_id:
                    bill = db.query(Bill).filter(Bill.bill_id == s.bill_id).first()
                    if bill:
                        bill_title = bill.short_title or bill.title

                # Parse party breakdown
                party_breakdown = {}
                if s.party_breakdown_json:
                    try:
                        party_breakdown = json.loads(s.party_breakdown_json)
                    except:
                        pass

                results.append(VotingSessionSummary(
                    session_id=s.session_id,
                    chamber=s.chamber,
                    session_date=s.session_date.isoformat() if s.session_date else "",
                    bill_id=s.bill_id,
                    bill_title=bill_title,
                    motion_title=s.motion_title,
                    vote_type=s.vote_type,
                    ayes=s.ayes or 0,
                    nays=s.nays or 0,
                    abstentions=s.abstentions or 0,
                    absent=s.absent or 0,
                    result=s.result or "unknown",
                    party_breakdown=party_breakdown
                ).__dict__)

            return results

        finally:
            db.close()

    def record_voting_session(
        self,
        chamber: str,
        session_date: datetime,
        bill_id: Optional[str] = None,
        motion_title: Optional[str] = None,
        vote_type: str = "motion",
        votes: List[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Record a complete voting session with individual votes.
        """
        db = SessionLocal()
        try:
            # Generate session_id
            date_str = session_date.strftime("%Y%m%d%H%M")
            subject = bill_id or motion_title or "session"
            session_id = f"session-{chamber}-{date_str}-{hashlib.md5(subject.encode()).hexdigest()[:8]}"

            # Calculate totals
            ayes = sum(1 for v in (votes or []) if v.get("vote_cast") == "aye")
            nays = sum(1 for v in (votes or []) if v.get("vote_cast") == "nay")
            abstentions = sum(1 for v in (votes or []) if v.get("vote_cast") == "abstain")
            absent = sum(1 for v in (votes or []) if v.get("vote_cast") in ["absent", "excused"])
            total = ayes + nays + abstentions + absent

            # Determine result
            result = "passed" if ayes > nays else "rejected" if nays > ayes else "tied"

            # Calculate party breakdown
            party_breakdown = {}
            for v in (votes or []):
                party = v.get("party", "Unknown")
                if party not in party_breakdown:
                    party_breakdown[party] = {"aye": 0, "nay": 0, "abstain": 0, "absent": 0}
                vote_cast = v.get("vote_cast", "absent").lower()
                if vote_cast in party_breakdown[party]:
                    party_breakdown[party][vote_cast] += 1

            session = VotingSession(
                session_id=session_id,
                chamber=chamber.lower(),
                session_date=session_date,
                bill_id=bill_id,
                motion_title=motion_title,
                vote_type=vote_type,
                total_votes=total,
                ayes=ayes,
                nays=nays,
                abstentions=abstentions,
                absent=absent,
                result=result,
                party_breakdown_json=json.dumps(party_breakdown)
            )

            db.add(session)

            # Record individual votes
            for v in (votes or []):
                self.record_vote(
                    politician_slug=v["politician_slug"],
                    vote_cast=v["vote_cast"],
                    vote_date=session_date,
                    chamber=chamber,
                    bill_id=bill_id,
                    motion_title=motion_title,
                    session_id=session_id
                )

            db.commit()
            logger.info(f"Recorded voting session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to record voting session: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    # =========================================================================
    # Statistics Methods
    # =========================================================================

    def get_bill_statistics(self) -> Dict[str, Any]:
        """
        Get overall bill statistics.
        """
        db = SessionLocal()
        try:
            total_bills = db.query(Bill).count()

            # By status
            by_status = {}
            for status in BILL_STATUS_ORDER + ["rejected", "withdrawn"]:
                count = db.query(Bill).filter(Bill.status == status).count()
                if count > 0:
                    by_status[status] = count

            # By chamber
            senate = db.query(Bill).filter(Bill.chamber == "senate").count()
            house = db.query(Bill).filter(Bill.chamber == "house").count()

            # By category
            by_category = {}
            categories = db.query(Bill.category).distinct().all()
            for (cat,) in categories:
                if cat:
                    count = db.query(Bill).filter(Bill.category == cat).count()
                    by_category[cat] = count

            # Recent activity
            week_ago = datetime.now() - timedelta(days=7)
            recent_updates = db.query(Bill).filter(
                Bill.last_action_date >= week_ago
            ).count()

            return {
                "total_bills": total_bills,
                "by_status": by_status,
                "by_chamber": {"senate": senate, "house": house},
                "by_category": by_category,
                "recent_updates": recent_updates,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            db.close()

    def get_voting_statistics(self) -> Dict[str, Any]:
        """
        Get overall voting statistics.
        """
        db = SessionLocal()
        try:
            total_votes = db.query(Vote).count()
            total_sessions = db.query(VotingSession).count()

            # By chamber
            senate_sessions = db.query(VotingSession).filter(
                VotingSession.chamber == "senate"
            ).count()
            house_sessions = db.query(VotingSession).filter(
                VotingSession.chamber == "house"
            ).count()

            # Recent sessions
            week_ago = datetime.now() - timedelta(days=7)
            recent_sessions = db.query(VotingSession).filter(
                VotingSession.session_date >= week_ago
            ).count()

            # Pass/reject ratio
            passed = db.query(VotingSession).filter(
                VotingSession.result == "passed"
            ).count()
            rejected = db.query(VotingSession).filter(
                VotingSession.result == "rejected"
            ).count()

            return {
                "total_votes": total_votes,
                "total_sessions": total_sessions,
                "by_chamber": {
                    "senate": senate_sessions,
                    "house": house_sessions
                },
                "recent_sessions": recent_sessions,
                "outcomes": {
                    "passed": passed,
                    "rejected": rejected
                },
                "timestamp": datetime.now().isoformat()
            }

        finally:
            db.close()


# =============================================================================
# Helper Functions
# =============================================================================

def get_voting_service() -> VotingRecordService:
    """Get singleton voting record service instance."""
    return VotingRecordService()


def get_bills_by_politician(slug: str, limit: int = 20) -> List[Dict]:
    """Get bills sponsored by a politician."""
    service = VotingRecordService()
    result = service.get_bills(sponsor_slug=slug, limit=limit)
    return result.get("bills", [])


def get_politician_votes(slug: str, limit: int = 20) -> Optional[Dict]:
    """Get voting record summary for a politician."""
    service = VotingRecordService()
    record = service.get_politician_voting_record(slug)
    return asdict(record) if record else None
