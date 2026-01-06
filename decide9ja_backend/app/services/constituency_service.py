"""
Constituency Service for Decide9ja.

Provides ward-level civic data and engagement:
- Ward representatives (councillors, ward heads)
- Local government projects and budgets
- Constituency development updates
- Local election information
- Infrastructure status by ward

All responses are WhatsApp-optimized.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class ProjectStatus(str, Enum):
    """Government project status."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    DELAYED = "delayed"


class ProjectCategory(str, Enum):
    """Project categories."""
    ROADS = "roads"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    WATER = "water"
    ELECTRICITY = "electricity"
    HOUSING = "housing"
    AGRICULTURE = "agriculture"
    SECURITY = "security"
    SANITATION = "sanitation"
    OTHER = "other"


class InfrastructureType(str, Enum):
    """Infrastructure types to track."""
    HOSPITAL = "hospital"
    SCHOOL = "school"
    POLICE_STATION = "police_station"
    FIRE_STATION = "fire_station"
    MARKET = "market"
    WATER_FACILITY = "water_facility"
    POWER_SUBSTATION = "power_substation"
    ROAD = "road"


@dataclass
class WardRepresentative:
    """A ward-level representative."""
    id: str
    name: str
    position: str  # councillor, ward_head, youth_leader, women_leader
    ward: str
    lga: str
    state: str
    party: Optional[str] = None
    phone: Optional[str] = None  # Public office number only
    email: Optional[str] = None
    term_start: Optional[datetime] = None
    term_end: Optional[datetime] = None
    photo_url: Optional[str] = None


@dataclass
class LocalProject:
    """A constituency development project."""
    id: str
    name: str
    description: str
    category: ProjectCategory
    status: ProjectStatus
    location: str
    ward: str
    lga: str
    state: str
    budget: Optional[float] = None
    contractor: Optional[str] = None
    start_date: Optional[datetime] = None
    expected_completion: Optional[datetime] = None
    actual_completion: Optional[datetime] = None
    funding_source: str = "unknown"  # federal, state, lga, donor
    percentage_complete: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    # Community feedback
    community_rating: Optional[float] = None
    issues_reported: int = 0


@dataclass
class WardInfrastructure:
    """Infrastructure in a ward."""
    id: str
    name: str
    type: InfrastructureType
    ward: str
    lga: str
    state: str
    address: Optional[str] = None
    status: str = "operational"  # operational, under_repair, closed
    capacity: Optional[str] = None
    contact: Optional[str] = None
    last_verified: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConstituencyBudget:
    """Budget allocation for a constituency."""
    id: str
    year: int
    lga: str
    state: str
    total_allocation: float
    capital_expenditure: float
    recurrent_expenditure: float
    # Breakdown by sector
    education_allocation: float = 0
    health_allocation: float = 0
    infrastructure_allocation: float = 0
    agriculture_allocation: float = 0
    # Execution
    amount_released: float = 0
    amount_spent: float = 0
    source: str = "BudgIT"


# =============================================================================
# Constituency Service
# =============================================================================

class ConstituencyService:
    """
    Service for constituency-level civic data.

    Features:
    - Ward representatives lookup
    - Local project tracking
    - Budget information
    - Infrastructure mapping
    - WhatsApp-formatted responses
    """

    def __init__(self):
        self._representatives: Dict[str, WardRepresentative] = {}
        self._projects: Dict[str, LocalProject] = {}
        self._infrastructure: Dict[str, WardInfrastructure] = {}
        self._budgets: Dict[str, ConstituencyBudget] = {}

        # Initialize with sample data
        self._init_sample_data()

    def _init_sample_data(self):
        """Load sample constituency data."""
        # Sample representatives
        sample_reps = [
            WardRepresentative(
                id="wr_001",
                name="Hon. Adebayo Ogunlesi",
                position="councillor",
                ward="Ward 1",
                lga="Alimosho",
                state="Lagos",
                party="APC",
                term_start=datetime(2023, 5, 29)
            ),
            WardRepresentative(
                id="wr_002",
                name="Chief Musa Ibrahim",
                position="ward_head",
                ward="Sabon Gari",
                lga="Kano Municipal",
                state="Kano",
                term_start=datetime(2022, 1, 1)
            ),
        ]
        for rep in sample_reps:
            key = f"{rep.state}_{rep.lga}_{rep.ward}_{rep.position}".lower()
            self._representatives[key] = rep

        # Sample projects
        sample_projects = [
            LocalProject(
                id="proj_001",
                name="Ikeja-Agege Road Rehabilitation",
                description="Reconstruction of 5km road with drainage",
                category=ProjectCategory.ROADS,
                status=ProjectStatus.IN_PROGRESS,
                location="Ikeja-Agege Road",
                ward="Ward 3",
                lga="Ikeja",
                state="Lagos",
                budget=2500000000,
                percentage_complete=45,
                start_date=datetime(2024, 3, 1),
                expected_completion=datetime(2025, 6, 30),
                funding_source="state"
            ),
            LocalProject(
                id="proj_002",
                name="Primary Health Center Construction",
                description="New 20-bed health center",
                category=ProjectCategory.HEALTHCARE,
                status=ProjectStatus.COMPLETED,
                location="Oshodi",
                ward="Ward 5",
                lga="Oshodi-Isolo",
                state="Lagos",
                budget=150000000,
                percentage_complete=100,
                start_date=datetime(2023, 6, 1),
                actual_completion=datetime(2024, 8, 15),
                funding_source="federal"
            ),
            LocalProject(
                id="proj_003",
                name="Borehole Project",
                description="Construction of 10 solar-powered boreholes",
                category=ProjectCategory.WATER,
                status=ProjectStatus.DELAYED,
                location="Multiple locations",
                ward="All wards",
                lga="Kano Municipal",
                state="Kano",
                budget=50000000,
                percentage_complete=30,
                start_date=datetime(2024, 1, 1),
                expected_completion=datetime(2024, 12, 31),
                funding_source="lga"
            ),
        ]
        for proj in sample_projects:
            self._projects[proj.id] = proj

    # -------------------------------------------------------------------------
    # Representative Lookup
    # -------------------------------------------------------------------------

    def get_ward_representatives(
        self,
        state: str,
        lga: str,
        ward: Optional[str] = None
    ) -> List[WardRepresentative]:
        """Get representatives for a ward or LGA."""
        results = []

        # First try database
        db_results = self._query_representatives_db(state, lga, ward)
        if db_results:
            return db_results

        # Fallback to cached data
        state_lower = state.lower()
        lga_lower = lga.lower()

        for key, rep in self._representatives.items():
            if state_lower in key and lga_lower in key:
                if ward is None or ward.lower() in key:
                    results.append(rep)

        return results

    def _query_representatives_db(
        self,
        state: str,
        lga: str,
        ward: Optional[str]
    ) -> List[WardRepresentative]:
        """Query representatives from database."""
        import os
        from sqlalchemy import create_engine, text

        try:
            engine = create_engine(os.getenv('DATABASE_URL'))

            with engine.connect() as conn:
                query = text("""
                    SELECT id, name, position, ward, lga, state, party,
                           phone, email, term_start, term_end
                    FROM lga_representatives
                    WHERE LOWER(state) = :state
                    AND LOWER(lga) = :lga
                    LIMIT 20
                """)

                params = {"state": state.lower(), "lga": lga.lower()}
                if ward:
                    query = text("""
                        SELECT id, name, position, ward, lga, state, party,
                               phone, email, term_start, term_end
                        FROM lga_representatives
                        WHERE LOWER(state) = :state
                        AND LOWER(lga) = :lga
                        AND LOWER(ward) LIKE :ward
                        LIMIT 20
                    """)
                    params["ward"] = f"%{ward.lower()}%"

                result = conn.execute(query, params)

                reps = []
                for row in result:
                    row_dict = dict(row._mapping)
                    reps.append(WardRepresentative(
                        id=str(row_dict["id"]),
                        name=row_dict["name"],
                        position=row_dict.get("position", "councillor"),
                        ward=row_dict.get("ward", ""),
                        lga=row_dict["lga"],
                        state=row_dict["state"],
                        party=row_dict.get("party"),
                        phone=row_dict.get("phone"),
                        email=row_dict.get("email"),
                        term_start=row_dict.get("term_start"),
                        term_end=row_dict.get("term_end")
                    ))

                return reps

        except Exception as e:
            logger.warning(f"Database query failed: {e}")
            return []

    def format_representatives_whatsapp(
        self,
        reps: List[WardRepresentative],
        location: str
    ) -> str:
        """Format representatives for WhatsApp."""
        if not reps:
            return f"I don't have ward representative data for {location} yet. Try asking about your state or federal representatives."

        lines = [f"📍 *Local Representatives for {location}*\n"]

        # Group by position
        by_position = {}
        for rep in reps:
            pos = rep.position.replace("_", " ").title()
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(rep)

        for position, pos_reps in by_position.items():
            lines.append(f"*{position}:*")
            for rep in pos_reps[:3]:  # Max 3 per position
                party_str = f" ({rep.party})" if rep.party else ""
                ward_str = f" - {rep.ward}" if rep.ward else ""
                lines.append(f"• {rep.name}{party_str}{ward_str}")
            lines.append("")

        lines.append("Reply with a name for more details.")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Project Tracking
    # -------------------------------------------------------------------------

    def get_local_projects(
        self,
        state: str,
        lga: str,
        category: Optional[ProjectCategory] = None,
        status: Optional[ProjectStatus] = None,
        limit: int = 10
    ) -> List[LocalProject]:
        """Get projects in a constituency."""
        results = []

        state_lower = state.lower()
        lga_lower = lga.lower()

        for proj in self._projects.values():
            if proj.state.lower() == state_lower and proj.lga.lower() == lga_lower:
                if category and proj.category != category:
                    continue
                if status and proj.status != status:
                    continue
                results.append(proj)

        # Sort by last_updated
        results.sort(key=lambda p: p.last_updated, reverse=True)
        return results[:limit]

    def get_project_by_id(self, project_id: str) -> Optional[LocalProject]:
        """Get specific project details."""
        return self._projects.get(project_id)

    def format_projects_whatsapp(
        self,
        projects: List[LocalProject],
        location: str
    ) -> str:
        """Format projects for WhatsApp."""
        if not projects:
            return f"No government projects found in {location}. This data is being collected."

        lines = [f"🏗️ *Government Projects in {location}*\n"]

        status_emoji = {
            ProjectStatus.PLANNED: "📋",
            ProjectStatus.IN_PROGRESS: "🚧",
            ProjectStatus.COMPLETED: "✅",
            ProjectStatus.ABANDONED: "❌",
            ProjectStatus.DELAYED: "⚠️"
        }

        for i, proj in enumerate(projects[:5], 1):
            emoji = status_emoji.get(proj.status, "📌")
            status_text = proj.status.value.replace("_", " ").title()

            lines.append(f"{i}. {emoji} *{proj.name}*")
            lines.append(f"   Status: {status_text} ({proj.percentage_complete}%)")

            if proj.budget:
                budget_str = self._format_naira(proj.budget)
                lines.append(f"   Budget: {budget_str}")

            lines.append("")

        lines.append("Reply with number for details.")
        return "\n".join(lines)

    def format_project_detail_whatsapp(self, proj: LocalProject) -> str:
        """Format single project detail for WhatsApp."""
        status_text = proj.status.value.replace("_", " ").title()

        lines = [
            f"🏗️ *{proj.name}*\n",
            f"📍 Location: {proj.location}, {proj.lga}",
            f"📊 Status: {status_text} ({proj.percentage_complete}% complete)",
            f"📁 Category: {proj.category.value.title()}",
        ]

        if proj.budget:
            lines.append(f"💰 Budget: {self._format_naira(proj.budget)}")

        if proj.funding_source:
            lines.append(f"🏛️ Funding: {proj.funding_source.title()} Government")

        if proj.start_date:
            lines.append(f"📅 Started: {proj.start_date.strftime('%B %Y')}")

        if proj.expected_completion and proj.status != ProjectStatus.COMPLETED:
            lines.append(f"⏰ Expected: {proj.expected_completion.strftime('%B %Y')}")

        if proj.actual_completion:
            lines.append(f"✅ Completed: {proj.actual_completion.strftime('%B %Y')}")

        if proj.contractor:
            lines.append(f"🔨 Contractor: {proj.contractor}")

        if proj.issues_reported > 0:
            lines.append(f"\n⚠️ {proj.issues_reported} issues reported by community")

        lines.append("\n— Source: Decide9ja Project Tracker")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Budget Information
    # -------------------------------------------------------------------------

    def get_constituency_budget(
        self,
        state: str,
        lga: str,
        year: int = None
    ) -> Optional[ConstituencyBudget]:
        """Get budget information for a constituency."""
        if year is None:
            year = datetime.now().year

        key = f"{state}_{lga}_{year}".lower()
        return self._budgets.get(key)

    def format_budget_whatsapp(
        self,
        budget: Optional[ConstituencyBudget],
        location: str
    ) -> str:
        """Format budget for WhatsApp."""
        if not budget:
            return f"Budget data for {location} is not yet available. Check budgit.ng for more information."

        execution_rate = (
            budget.amount_spent / budget.amount_released * 100
            if budget.amount_released > 0 else 0
        )

        lines = [
            f"💰 *{location} Budget {budget.year}*\n",
            f"Total: {self._format_naira(budget.total_allocation)}",
            f"• Capital: {self._format_naira(budget.capital_expenditure)}",
            f"• Recurrent: {self._format_naira(budget.recurrent_expenditure)}\n",
            "*Sector Breakdown:*",
        ]

        if budget.education_allocation:
            lines.append(f"📚 Education: {self._format_naira(budget.education_allocation)}")
        if budget.health_allocation:
            lines.append(f"🏥 Health: {self._format_naira(budget.health_allocation)}")
        if budget.infrastructure_allocation:
            lines.append(f"🛣️ Infrastructure: {self._format_naira(budget.infrastructure_allocation)}")

        if budget.amount_released > 0:
            lines.append(f"\n*Execution:*")
            lines.append(f"Released: {self._format_naira(budget.amount_released)}")
            lines.append(f"Spent: {self._format_naira(budget.amount_spent)} ({execution_rate:.0f}%)")

        lines.append(f"\n— Source: {budget.source}")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Infrastructure
    # -------------------------------------------------------------------------

    def get_nearby_infrastructure(
        self,
        state: str,
        lga: str,
        infra_type: Optional[InfrastructureType] = None,
        limit: int = 5
    ) -> List[WardInfrastructure]:
        """Get infrastructure in a location."""
        results = []

        state_lower = state.lower()
        lga_lower = lga.lower()

        for infra in self._infrastructure.values():
            if infra.state.lower() == state_lower and infra.lga.lower() == lga_lower:
                if infra_type and infra.type != infra_type:
                    continue
                results.append(infra)

        return results[:limit]

    def format_infrastructure_whatsapp(
        self,
        infrastructure: List[WardInfrastructure],
        infra_type: str,
        location: str
    ) -> str:
        """Format infrastructure list for WhatsApp."""
        if not infrastructure:
            return f"No {infra_type} data available for {location} yet."

        type_emoji = {
            InfrastructureType.HOSPITAL: "🏥",
            InfrastructureType.SCHOOL: "🏫",
            InfrastructureType.POLICE_STATION: "👮",
            InfrastructureType.MARKET: "🏪",
            InfrastructureType.WATER_FACILITY: "💧"
        }

        lines = [f"📍 *{infra_type.title()} in {location}*\n"]

        for infra in infrastructure:
            emoji = type_emoji.get(infra.type, "📍")
            status_indicator = "✅" if infra.status == "operational" else "⚠️"

            lines.append(f"{emoji} *{infra.name}* {status_indicator}")
            if infra.address:
                lines.append(f"   📍 {infra.address}")
            if infra.contact:
                lines.append(f"   📞 {infra.contact}")
            lines.append("")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _format_naira(self, amount: float) -> str:
        """Format amount in Naira."""
        if amount >= 1_000_000_000:
            return f"₦{amount/1_000_000_000:.1f}B"
        elif amount >= 1_000_000:
            return f"₦{amount/1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"₦{amount/1_000:.0f}K"
        else:
            return f"₦{amount:,.0f}"

    def add_project(self, project: LocalProject) -> str:
        """Add a new project (admin function)."""
        self._projects[project.id] = project
        return project.id

    def update_project_status(
        self,
        project_id: str,
        status: ProjectStatus,
        percentage: int = None
    ) -> bool:
        """Update project status."""
        proj = self._projects.get(project_id)
        if not proj:
            return False

        proj.status = status
        if percentage is not None:
            proj.percentage_complete = percentage
        proj.last_updated = datetime.utcnow()

        if status == ProjectStatus.COMPLETED:
            proj.percentage_complete = 100
            proj.actual_completion = datetime.utcnow()

        return True


# =============================================================================
# Singleton Instance
# =============================================================================

_constituency_service: Optional[ConstituencyService] = None


def get_constituency_service() -> ConstituencyService:
    """Get singleton constituency service instance."""
    global _constituency_service
    if _constituency_service is None:
        _constituency_service = ConstituencyService()
    return _constituency_service
