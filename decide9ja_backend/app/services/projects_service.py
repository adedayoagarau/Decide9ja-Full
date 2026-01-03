"""
Constituency Projects Service for Decide9ja.

Handles queries about:
- Government projects by state/LGA/constituency
- Project status tracking
- Ministry project performance
- Sponsor (politician) project tracking
"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class Project:
    """Represents a government project."""
    id: int
    title: str
    description: Optional[str]
    project_type: Optional[str]
    sector: Optional[str]
    category: Optional[str]
    state: Optional[str]
    lga: Optional[str]
    constituency: Optional[str]
    budget_amount: Optional[float]
    amount_released: Optional[float]
    amount_utilized: Optional[float]
    budget_year: Optional[int]
    status: str
    completion_percentage: Optional[int]
    sponsor_name: Optional[str]
    sponsor_party: Optional[str]
    ministry_name: Optional[str]
    contractor: Optional[str]
    source: Optional[str]


@dataclass
class ProjectSummary:
    """Summary statistics for projects."""
    total_projects: int
    total_budget: float
    total_released: float
    completed: int
    ongoing: int
    abandoned: int
    not_started: int
    unknown: int


class ProjectsService:
    """Service for querying constituency projects."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy load database engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            import os
            self._engine = create_engine(os.getenv('DATABASE_URL'))
        return self._engine

    def get_projects_by_state(
        self,
        state: str,
        year: int = None,
        status: str = None,
        sector: str = None,
        limit: int = 20
    ) -> List[Project]:
        """Get projects in a state."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT p.id, p.title, p.description, p.project_type, p.sector,
                           p.category, p.state, p.lga, p.constituency,
                           p.budget_amount, p.amount_released, p.amount_utilized,
                           p.budget_year, p.status, p.completion_percentage,
                           pol.name as sponsor_name, pol.party as sponsor_party,
                           m.name as ministry_name, p.contractor, p.source
                    FROM projects p
                    LEFT JOIN politicians pol ON p.sponsor_politician_id = pol.id
                    LEFT JOIN ministries m ON p.ministry_id = m.id
                    WHERE p.state ILIKE :state
                '''
                params = {'state': f'%{state}%', 'limit': limit}

                if year:
                    query += ' AND p.budget_year = :year'
                    params['year'] = year

                if status:
                    query += ' AND p.status ILIKE :status'
                    params['status'] = f'%{status}%'

                if sector:
                    query += ' AND p.sector ILIKE :sector'
                    params['sector'] = f'%{sector}%'

                query += ' ORDER BY p.budget_amount DESC NULLS LAST LIMIT :limit'

                result = conn.execute(text(query), params)

                return [self._row_to_project(row) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get projects by state: {e}")
            return []

    def get_projects_by_lga(
        self,
        lga: str,
        state: str = None,
        year: int = None,
        limit: int = 20
    ) -> List[Project]:
        """Get projects in an LGA."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT p.id, p.title, p.description, p.project_type, p.sector,
                           p.category, p.state, p.lga, p.constituency,
                           p.budget_amount, p.amount_released, p.amount_utilized,
                           p.budget_year, p.status, p.completion_percentage,
                           pol.name as sponsor_name, pol.party as sponsor_party,
                           m.name as ministry_name, p.contractor, p.source
                    FROM projects p
                    LEFT JOIN politicians pol ON p.sponsor_politician_id = pol.id
                    LEFT JOIN ministries m ON p.ministry_id = m.id
                    WHERE p.lga ILIKE :lga
                '''
                params = {'lga': f'%{lga}%', 'limit': limit}

                if state:
                    query += ' AND p.state ILIKE :state'
                    params['state'] = f'%{state}%'

                if year:
                    query += ' AND p.budget_year = :year'
                    params['year'] = year

                query += ' ORDER BY p.budget_amount DESC NULLS LAST LIMIT :limit'

                result = conn.execute(text(query), params)

                return [self._row_to_project(row) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get projects by LGA: {e}")
            return []

    def get_projects_by_constituency(
        self,
        constituency: str,
        year: int = None,
        limit: int = 20
    ) -> List[Project]:
        """Get projects in a constituency."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT p.id, p.title, p.description, p.project_type, p.sector,
                           p.category, p.state, p.lga, p.constituency,
                           p.budget_amount, p.amount_released, p.amount_utilized,
                           p.budget_year, p.status, p.completion_percentage,
                           pol.name as sponsor_name, pol.party as sponsor_party,
                           m.name as ministry_name, p.contractor, p.source
                    FROM projects p
                    LEFT JOIN politicians pol ON p.sponsor_politician_id = pol.id
                    LEFT JOIN ministries m ON p.ministry_id = m.id
                    WHERE p.constituency ILIKE :constituency
                '''
                params = {'constituency': f'%{constituency}%', 'limit': limit}

                if year:
                    query += ' AND p.budget_year = :year'
                    params['year'] = year

                query += ' ORDER BY p.budget_amount DESC NULLS LAST LIMIT :limit'

                result = conn.execute(text(query), params)

                return [self._row_to_project(row) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get projects by constituency: {e}")
            return []

    def get_projects_by_politician(
        self,
        politician_name: str = None,
        politician_id: int = None,
        year: int = None,
        limit: int = 20
    ) -> List[Project]:
        """Get projects sponsored by a politician."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT p.id, p.title, p.description, p.project_type, p.sector,
                           p.category, p.state, p.lga, p.constituency,
                           p.budget_amount, p.amount_released, p.amount_utilized,
                           p.budget_year, p.status, p.completion_percentage,
                           pol.name as sponsor_name, pol.party as sponsor_party,
                           m.name as ministry_name, p.contractor, p.source
                    FROM projects p
                    LEFT JOIN politicians pol ON p.sponsor_politician_id = pol.id
                    LEFT JOIN ministries m ON p.ministry_id = m.id
                    WHERE 1=1
                '''
                params = {'limit': limit}

                if politician_id:
                    query += ' AND p.sponsor_politician_id = :pol_id'
                    params['pol_id'] = politician_id
                elif politician_name:
                    query += ' AND pol.name ILIKE :pol_name'
                    params['pol_name'] = f'%{politician_name}%'

                if year:
                    query += ' AND p.budget_year = :year'
                    params['year'] = year

                query += ' ORDER BY p.budget_amount DESC NULLS LAST LIMIT :limit'

                result = conn.execute(text(query), params)

                return [self._row_to_project(row) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get projects by politician: {e}")
            return []

    def get_projects_by_ministry(
        self,
        ministry_name: str = None,
        ministry_id: int = None,
        year: int = None,
        limit: int = 20
    ) -> List[Project]:
        """Get projects by ministry."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT p.id, p.title, p.description, p.project_type, p.sector,
                           p.category, p.state, p.lga, p.constituency,
                           p.budget_amount, p.amount_released, p.amount_utilized,
                           p.budget_year, p.status, p.completion_percentage,
                           pol.name as sponsor_name, pol.party as sponsor_party,
                           m.name as ministry_name, p.contractor, p.source
                    FROM projects p
                    LEFT JOIN politicians pol ON p.sponsor_politician_id = pol.id
                    LEFT JOIN ministries m ON p.ministry_id = m.id
                    WHERE 1=1
                '''
                params = {'limit': limit}

                if ministry_id:
                    query += ' AND p.ministry_id = :min_id'
                    params['min_id'] = ministry_id
                elif ministry_name:
                    query += ' AND (m.name ILIKE :min_name OR m.short_name ILIKE :min_name)'
                    params['min_name'] = f'%{ministry_name}%'

                if year:
                    query += ' AND p.budget_year = :year'
                    params['year'] = year

                query += ' ORDER BY p.budget_amount DESC NULLS LAST LIMIT :limit'

                result = conn.execute(text(query), params)

                return [self._row_to_project(row) for row in result]

        except Exception as e:
            logger.warning(f"Failed to get projects by ministry: {e}")
            return []

    def get_state_summary(self, state: str, year: int = None) -> Optional[ProjectSummary]:
        """Get project summary for a state."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                query = '''
                    SELECT
                        COUNT(*) as total_projects,
                        COALESCE(SUM(budget_amount), 0) as total_budget,
                        COALESCE(SUM(amount_released), 0) as total_released,
                        COUNT(CASE WHEN status = 'Completed' THEN 1 END) as completed,
                        COUNT(CASE WHEN status = 'Ongoing' THEN 1 END) as ongoing,
                        COUNT(CASE WHEN status = 'Abandoned' THEN 1 END) as abandoned,
                        COUNT(CASE WHEN status = 'Not Started' THEN 1 END) as not_started,
                        COUNT(CASE WHEN status = 'Unknown' THEN 1 END) as unknown
                    FROM projects
                    WHERE state ILIKE :state
                '''
                params = {'state': f'%{state}%'}

                if year:
                    query += ' AND budget_year = :year'
                    params['year'] = year

                result = conn.execute(text(query), params)
                row = result.fetchone()

                if row and row[0] > 0:
                    return ProjectSummary(
                        total_projects=row[0],
                        total_budget=float(row[1]) if row[1] else 0,
                        total_released=float(row[2]) if row[2] else 0,
                        completed=row[3] or 0,
                        ongoing=row[4] or 0,
                        abandoned=row[5] or 0,
                        not_started=row[6] or 0,
                        unknown=row[7] or 0
                    )

        except Exception as e:
            logger.warning(f"Failed to get state summary: {e}")
        return None

    def search_projects(
        self,
        query: str,
        state: str = None,
        sector: str = None,
        year: int = None,
        limit: int = 20
    ) -> List[Project]:
        """Search projects by title/description."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                sql = '''
                    SELECT p.id, p.title, p.description, p.project_type, p.sector,
                           p.category, p.state, p.lga, p.constituency,
                           p.budget_amount, p.amount_released, p.amount_utilized,
                           p.budget_year, p.status, p.completion_percentage,
                           pol.name as sponsor_name, pol.party as sponsor_party,
                           m.name as ministry_name, p.contractor, p.source
                    FROM projects p
                    LEFT JOIN politicians pol ON p.sponsor_politician_id = pol.id
                    LEFT JOIN ministries m ON p.ministry_id = m.id
                    WHERE (p.title ILIKE :query OR p.description ILIKE :query)
                '''
                params = {'query': f'%{query}%', 'limit': limit}

                if state:
                    sql += ' AND p.state ILIKE :state'
                    params['state'] = f'%{state}%'

                if sector:
                    sql += ' AND p.sector ILIKE :sector'
                    params['sector'] = f'%{sector}%'

                if year:
                    sql += ' AND p.budget_year = :year'
                    params['year'] = year

                sql += ' ORDER BY p.budget_amount DESC NULLS LAST LIMIT :limit'

                result = conn.execute(text(sql), params)

                return [self._row_to_project(row) for row in result]

        except Exception as e:
            logger.warning(f"Failed to search projects: {e}")
            return []

    def _row_to_project(self, row) -> Project:
        """Convert a database row to Project object."""
        return Project(
            id=row[0],
            title=row[1],
            description=row[2],
            project_type=row[3],
            sector=row[4],
            category=row[5],
            state=row[6],
            lga=row[7],
            constituency=row[8],
            budget_amount=float(row[9]) if row[9] else None,
            amount_released=float(row[10]) if row[10] else None,
            amount_utilized=float(row[11]) if row[11] else None,
            budget_year=row[12],
            status=row[13] or 'Unknown',
            completion_percentage=row[14],
            sponsor_name=row[15],
            sponsor_party=row[16],
            ministry_name=row[17],
            contractor=row[18],
            source=row[19]
        )

    def format_project(self, project: Project) -> str:
        """Format a single project for display."""
        response = f"🏗️ *{project.title}*\n\n"

        if project.description:
            response += f"{project.description[:200]}{'...' if len(project.description) > 200 else ''}\n\n"

        response += f"📍 *Location:* {project.lga or ''}, {project.state or ''}\n"

        if project.constituency:
            response += f"🗳️ Constituency: {project.constituency}\n"

        if project.sector:
            response += f"📁 Sector: {project.sector}\n"

        if project.budget_amount:
            response += f"💰 Budget: ₦{project.budget_amount:,.0f}\n"

        if project.amount_released:
            response += f"💵 Released: ₦{project.amount_released:,.0f}\n"

        response += f"📊 Status: {project.status}"
        if project.completion_percentage:
            response += f" ({project.completion_percentage}%)"
        response += "\n"

        if project.sponsor_name:
            response += f"👤 Sponsor: {project.sponsor_name} ({project.sponsor_party or 'N/A'})\n"

        if project.ministry_name:
            response += f"🏛️ Ministry: {project.ministry_name}\n"

        if project.source:
            response += f"\n_Source: {project.source}_"

        return response

    def format_projects_list(
        self,
        projects: List[Project],
        title: str = "Projects"
    ) -> str:
        """Format a list of projects for display."""
        if not projects:
            return "No projects found."

        response = f"🏗️ *{title}*\n\n"

        for i, p in enumerate(projects[:10], 1):
            status_emoji = {
                'Completed': '✅',
                'Ongoing': '🔄',
                'Abandoned': '❌',
                'Not Started': '⏳',
                'Unknown': '❓'
            }.get(p.status, '❓')

            response += f"{i}. *{p.title[:50]}{'...' if len(p.title) > 50 else ''}*\n"
            response += f"   {status_emoji} {p.status}"
            if p.budget_amount:
                response += f" | ₦{p.budget_amount:,.0f}"
            response += f"\n   📍 {p.lga or 'N/A'}, {p.state or 'N/A'}\n\n"

        if len(projects) > 10:
            response += f"_...and {len(projects) - 10} more projects_"

        return response

    def format_summary(self, summary: ProjectSummary, title: str) -> str:
        """Format project summary for display."""
        response = f"📊 *{title}*\n\n"
        response += f"Total Projects: {summary.total_projects:,}\n"
        response += f"Total Budget: ₦{summary.total_budget:,.0f}\n"
        response += f"Amount Released: ₦{summary.total_released:,.0f}\n\n"

        response += "*Status Breakdown:*\n"
        response += f"✅ Completed: {summary.completed}\n"
        response += f"🔄 Ongoing: {summary.ongoing}\n"
        response += f"⏳ Not Started: {summary.not_started}\n"
        response += f"❌ Abandoned: {summary.abandoned}\n"

        if summary.unknown:
            response += f"❓ Unknown: {summary.unknown}\n"

        return response


# Singleton instance
projects_service = ProjectsService()


def get_constituency_projects(constituency: str, year: int = None) -> str:
    """Convenience function for message handler."""
    projects = projects_service.get_projects_by_constituency(constituency, year)
    return projects_service.format_projects_list(
        projects,
        f"Projects in {constituency}"
    )


def get_state_projects(state: str, year: int = None, sector: str = None) -> str:
    """Convenience function for state projects."""
    projects = projects_service.get_projects_by_state(state, year, sector=sector)
    return projects_service.format_projects_list(
        projects,
        f"Projects in {state}"
    )


def get_project_summary(state: str, year: int = None) -> str:
    """Convenience function for project summary."""
    summary = projects_service.get_state_summary(state, year)
    if summary:
        title = f"Project Summary for {state}"
        if year:
            title += f" ({year})"
        return projects_service.format_summary(summary, title)
    return f"No project data available for {state}."


def get_politician_projects(name: str, year: int = None) -> str:
    """Convenience function for politician's projects."""
    projects = projects_service.get_projects_by_politician(
        politician_name=name,
        year=year
    )
    return projects_service.format_projects_list(
        projects,
        f"Projects by {name}"
    )
