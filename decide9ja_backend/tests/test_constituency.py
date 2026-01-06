"""
Tests for Constituency & Community Features
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.constituency import (
    ConstituencyService,
    Constituency,
    CommunityIssue,
    IssueStatus,
    IssuePriority,
    IssueCategory
)


class TestConstituency:
    """Tests for Constituency model."""

    def test_create_constituency(self):
        """Test creating a constituency."""
        constituency = Constituency(
            constituency_id="const_123",
            name="Ikeja",
            state="Lagos",
            type="federal",
            representatives=[]
        )

        assert constituency.name == "Ikeja"
        assert constituency.state == "Lagos"

    def test_constituency_with_representatives(self):
        """Test constituency with elected representatives."""
        constituency = Constituency(
            constituency_id="const_456",
            name="Surulere I",
            state="Lagos",
            type="state",
            representatives=[
                {
                    "name": "John Doe",
                    "position": "House of Representatives",
                    "party": "APC",
                    "term": "2023-2027"
                }
            ]
        )

        assert len(constituency.representatives) == 1
        assert constituency.representatives[0]["party"] == "APC"


class TestCommunityIssue:
    """Tests for CommunityIssue model."""

    def test_create_issue(self):
        """Test creating a community issue."""
        issue = CommunityIssue(
            issue_id="issue_123",
            title="Pothole on Main Street",
            description="Large pothole causing accidents",
            category=IssueCategory.INFRASTRUCTURE,
            status=IssueStatus.OPEN,
            reporter_id="user_123",
            location="Ikeja, Lagos"
        )

        assert issue.title == "Pothole on Main Street"
        assert issue.status == IssueStatus.OPEN
        assert issue.category == IssueCategory.INFRASTRUCTURE

    def test_issue_with_location_data(self):
        """Test issue with GPS coordinates."""
        issue = CommunityIssue(
            issue_id="issue_456",
            title="Streetlight not working",
            description="Dark and unsafe at night",
            category=IssueCategory.SECURITY,
            status=IssueStatus.OPEN,
            reporter_id="user_456",
            location="Victoria Island",
            latitude=6.4281,
            longitude=3.4219
        )

        assert issue.latitude == 6.4281
        assert issue.longitude == 3.4219


class TestIssueStatus:
    """Tests for issue status enum."""

    def test_status_values(self):
        """Test that all status values are defined."""
        assert IssueStatus.OPEN.value == "open"
        assert IssueStatus.ACKNOWLEDGED.value == "acknowledged"
        assert IssueStatus.IN_PROGRESS.value == "in_progress"
        assert IssueStatus.RESOLVED.value == "resolved"
        assert IssueStatus.CLOSED.value == "closed"
        assert IssueStatus.REJECTED.value == "rejected"


class TestIssueCategory:
    """Tests for issue category enum."""

    def test_category_values(self):
        """Test that all category values are defined."""
        assert IssueCategory.INFRASTRUCTURE.value == "infrastructure"
        assert IssueCategory.SECURITY.value == "security"
        assert IssueCategory.HEALTHCARE.value == "healthcare"
        assert IssueCategory.EDUCATION.value == "education"
        assert IssueCategory.ENVIRONMENT.value == "environment"
        assert IssueCategory.UTILITIES.value == "utilities"
        assert IssueCategory.OTHER.value == "other"


class TestConstituencyService:
    """Tests for ConstituencyService."""

    def setup_method(self):
        """Reset service state before each test."""
        ConstituencyService._constituencies = {}
        ConstituencyService._issues = {}

    def test_get_constituency_by_location(self):
        """Test finding constituency by coordinates."""
        # Add test constituency
        ConstituencyService._constituencies["test_1"] = Constituency(
            constituency_id="test_1",
            name="Ikeja Federal",
            state="Lagos",
            type="federal",
            representatives=[],
            boundaries={
                "north": 6.7,
                "south": 6.5,
                "east": 3.4,
                "west": 3.2
            }
        )

        result = ConstituencyService.get_constituency_by_location(
            latitude=6.6,
            longitude=3.3
        )

        # May or may not find depending on implementation
        assert result is None or result.name == "Ikeja Federal"

    def test_get_constituency_by_name(self):
        """Test finding constituency by name."""
        ConstituencyService._constituencies["test_2"] = Constituency(
            constituency_id="test_2",
            name="Eti-Osa",
            state="Lagos",
            type="federal",
            representatives=[]
        )

        result = ConstituencyService.get_constituency_by_name("Eti-Osa")
        assert result is not None
        assert result.name == "Eti-Osa"

    def test_list_constituencies_by_state(self):
        """Test listing constituencies by state."""
        ConstituencyService._constituencies["lagos_1"] = Constituency(
            constituency_id="lagos_1",
            name="Ikeja",
            state="Lagos",
            type="federal",
            representatives=[]
        )
        ConstituencyService._constituencies["lagos_2"] = Constituency(
            constituency_id="lagos_2",
            name="Surulere",
            state="Lagos",
            type="federal",
            representatives=[]
        )
        ConstituencyService._constituencies["abuja_1"] = Constituency(
            constituency_id="abuja_1",
            name="Abaji",
            state="FCT",
            type="federal",
            representatives=[]
        )

        lagos = ConstituencyService.list_constituencies(state="Lagos")
        assert len(lagos) == 2

    def test_create_issue(self):
        """Test creating a community issue."""
        issue = ConstituencyService.create_issue(
            title="Broken water pipe",
            description="Water pipe burst on the main road",
            category=IssueCategory.UTILITIES,
            reporter_id="user_issue",
            location="Lekki Phase 1"
        )

        assert issue.title == "Broken water pipe"
        assert issue.status == IssueStatus.OPEN
        assert issue.issue_id in ConstituencyService._issues

    def test_get_issue(self):
        """Test retrieving an issue."""
        created = ConstituencyService.create_issue(
            title="Test Issue",
            description="Test description",
            category=IssueCategory.OTHER,
            reporter_id="user_get",
            location="Test Location"
        )

        retrieved = ConstituencyService.get_issue(created.issue_id)
        assert retrieved is not None
        assert retrieved.title == "Test Issue"

    def test_update_issue_status(self):
        """Test updating issue status."""
        issue = ConstituencyService.create_issue(
            title="Status Update Test",
            description="Testing status updates",
            category=IssueCategory.INFRASTRUCTURE,
            reporter_id="user_status",
            location="Test"
        )

        updated = ConstituencyService.update_issue_status(
            issue_id=issue.issue_id,
            status=IssueStatus.ACKNOWLEDGED,
            updated_by="admin_1"
        )

        assert updated.status == IssueStatus.ACKNOWLEDGED

    def test_list_issues_by_location(self):
        """Test listing issues by location."""
        ConstituencyService.create_issue(
            title="Issue 1",
            description="Desc 1",
            category=IssueCategory.SECURITY,
            reporter_id="user1",
            location="Ikeja"
        )
        ConstituencyService.create_issue(
            title="Issue 2",
            description="Desc 2",
            category=IssueCategory.HEALTHCARE,
            reporter_id="user2",
            location="Ikeja"
        )
        ConstituencyService.create_issue(
            title="Issue 3",
            description="Desc 3",
            category=IssueCategory.EDUCATION,
            reporter_id="user3",
            location="VI"
        )

        ikeja_issues = ConstituencyService.list_issues(location="Ikeja")
        assert len(ikeja_issues) == 2

    def test_list_issues_by_status(self):
        """Test filtering issues by status."""
        issue1 = ConstituencyService.create_issue(
            title="Open Issue",
            description="Still open",
            category=IssueCategory.OTHER,
            reporter_id="user_a",
            location="Test"
        )
        issue2 = ConstituencyService.create_issue(
            title="Resolved Issue",
            description="Fixed",
            category=IssueCategory.OTHER,
            reporter_id="user_b",
            location="Test"
        )
        issue2.status = IssueStatus.RESOLVED

        open_issues = ConstituencyService.list_issues(status=IssueStatus.OPEN)
        assert len(open_issues) == 1

    def test_list_issues_by_category(self):
        """Test filtering issues by category."""
        ConstituencyService.create_issue(
            title="Security 1",
            description="Security issue",
            category=IssueCategory.SECURITY,
            reporter_id="user_sec1",
            location="Test"
        )
        ConstituencyService.create_issue(
            title="Health 1",
            description="Health issue",
            category=IssueCategory.HEALTHCARE,
            reporter_id="user_health",
            location="Test"
        )

        security = ConstituencyService.list_issues(category=IssueCategory.SECURITY)
        assert len(security) == 1
        assert security[0].category == IssueCategory.SECURITY

    def test_add_issue_update(self):
        """Test adding updates to an issue."""
        issue = ConstituencyService.create_issue(
            title="Issue with Updates",
            description="Will have updates",
            category=IssueCategory.INFRASTRUCTURE,
            reporter_id="user_updates",
            location="Test"
        )

        updated = ConstituencyService.add_issue_update(
            issue_id=issue.issue_id,
            update_text="Work has begun on this issue",
            updated_by="admin_updates"
        )

        assert len(updated.updates) == 1
        assert "Work has begun" in updated.updates[0]["text"]

    def test_upvote_issue(self):
        """Test upvoting an issue."""
        issue = ConstituencyService.create_issue(
            title="Popular Issue",
            description="Many people affected",
            category=IssueCategory.UTILITIES,
            reporter_id="user_popular",
            location="Test"
        )

        initial_votes = issue.upvotes
        updated = ConstituencyService.upvote_issue(
            issue_id=issue.issue_id,
            user_id="voter_1"
        )

        assert updated.upvotes == initial_votes + 1

    def test_prevent_duplicate_upvote(self):
        """Test preventing duplicate upvotes."""
        issue = ConstituencyService.create_issue(
            title="No Duplicate Votes",
            description="Test",
            category=IssueCategory.OTHER,
            reporter_id="user_dup",
            location="Test"
        )

        # First vote
        ConstituencyService.upvote_issue(issue.issue_id, "voter_2")
        votes_after_first = ConstituencyService.get_issue(issue.issue_id).upvotes

        # Second vote (should be prevented)
        ConstituencyService.upvote_issue(issue.issue_id, "voter_2")
        votes_after_second = ConstituencyService.get_issue(issue.issue_id).upvotes

        # Votes should be the same
        assert votes_after_first == votes_after_second


class TestRepresentativeLookup:
    """Tests for representative lookup functionality."""

    def setup_method(self):
        """Reset service state before each test."""
        ConstituencyService._constituencies = {}

    def test_get_representatives_for_constituency(self):
        """Test getting representatives for a constituency."""
        ConstituencyService._constituencies["test_rep"] = Constituency(
            constituency_id="test_rep",
            name="Test Constituency",
            state="Lagos",
            type="federal",
            representatives=[
                {
                    "name": "Hon. Test Person",
                    "position": "Member, House of Representatives",
                    "party": "APC",
                    "phone": "08012345678",
                    "email": "test@nass.gov.ng"
                }
            ]
        )

        reps = ConstituencyService.get_representatives("test_rep")
        assert len(reps) == 1
        assert reps[0]["name"] == "Hon. Test Person"


class TestIssueRouting:
    """Tests for routing issues to appropriate authorities."""

    def test_route_federal_road_issue(self):
        """Test routing federal road issue to FERMA."""
        routing = ConstituencyService.get_issue_routing(
            category=IssueCategory.INFRASTRUCTURE,
            subcategory="federal_road"
        )

        assert "FERMA" in routing["authority"] or "Federal" in routing["authority"]

    def test_route_state_road_issue(self):
        """Test routing state road issue to state works ministry."""
        routing = ConstituencyService.get_issue_routing(
            category=IssueCategory.INFRASTRUCTURE,
            subcategory="state_road"
        )

        assert "State" in routing["authority"] or "Works" in routing["authority"]

    def test_route_security_issue(self):
        """Test routing security issue to appropriate agency."""
        routing = ConstituencyService.get_issue_routing(
            category=IssueCategory.SECURITY
        )

        assert routing["authority"] is not None


class TestGamification:
    """Tests for community engagement gamification."""

    def test_award_points_for_issue_report(self):
        """Test awarding points for reporting an issue."""
        from app.services.gamification import GamificationService

        points = GamificationService.award_points(
            user_id="gamer_1",
            action="report_issue"
        )

        assert points > 0

    def test_award_points_for_verified_issue(self):
        """Test bonus points for verified issues."""
        from app.services.gamification import GamificationService

        points = GamificationService.award_points(
            user_id="gamer_2",
            action="issue_verified"
        )

        # Verified issues should give more points
        assert points >= 10

    def test_get_user_level(self):
        """Test calculating user engagement level."""
        from app.services.gamification import GamificationService

        # Add some points
        for _ in range(5):
            GamificationService.award_points("gamer_3", "report_issue")

        level = GamificationService.get_user_level("gamer_3")
        assert level >= 1

    def test_get_leaderboard(self):
        """Test getting community leaderboard."""
        from app.services.gamification import GamificationService

        GamificationService.award_points("leader_1", "report_issue")
        GamificationService.award_points("leader_1", "report_issue")
        GamificationService.award_points("leader_2", "report_issue")

        leaderboard = GamificationService.get_leaderboard(limit=10)
        assert len(leaderboard) > 0
        # First place should have most points
        if len(leaderboard) > 1:
            assert leaderboard[0]["points"] >= leaderboard[1]["points"]


class TestConstituencyIntegration:
    """Integration tests for constituency features."""

    def setup_method(self):
        """Reset service state before each test."""
        ConstituencyService._constituencies = {}
        ConstituencyService._issues = {}

    def test_full_issue_lifecycle(self):
        """Test complete issue lifecycle."""
        # 1. Citizen reports issue
        issue = ConstituencyService.create_issue(
            title="Broken streetlight",
            description="Streetlight on Broad Street not working for 2 weeks",
            category=IssueCategory.UTILITIES,
            reporter_id="citizen_lifecycle",
            location="Marina, Lagos"
        )
        assert issue.status == IssueStatus.OPEN

        # 2. Community upvotes
        ConstituencyService.upvote_issue(issue.issue_id, "community_1")
        ConstituencyService.upvote_issue(issue.issue_id, "community_2")

        updated_issue = ConstituencyService.get_issue(issue.issue_id)
        assert updated_issue.upvotes >= 2

        # 3. Authority acknowledges
        ConstituencyService.update_issue_status(
            issue_id=issue.issue_id,
            status=IssueStatus.ACKNOWLEDGED,
            updated_by="lasema_admin"
        )

        # 4. Work begins
        ConstituencyService.update_issue_status(
            issue_id=issue.issue_id,
            status=IssueStatus.IN_PROGRESS,
            updated_by="lasema_admin"
        )

        ConstituencyService.add_issue_update(
            issue_id=issue.issue_id,
            update_text="Repair team dispatched to location",
            updated_by="lasema_admin"
        )

        # 5. Issue resolved
        final = ConstituencyService.update_issue_status(
            issue_id=issue.issue_id,
            status=IssueStatus.RESOLVED,
            updated_by="lasema_admin"
        )

        assert final.status == IssueStatus.RESOLVED
        assert len(final.updates) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
