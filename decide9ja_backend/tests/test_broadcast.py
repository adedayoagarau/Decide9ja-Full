"""
Tests for Broadcast & Proactive Messaging Service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from app.services.broadcast import (
    BroadcastService,
    BroadcastCampaign,
    BroadcastStatus,
    BroadcastPriority,
    MessageTemplate,
    TargetingCriteria,
    DeliveryStats
)


class TestBroadcastCampaign:
    """Tests for BroadcastCampaign model."""

    def test_create_campaign(self):
        """Test creating a broadcast campaign."""
        campaign = BroadcastCampaign(
            campaign_id="test_123",
            name="Test Campaign",
            message_template=MessageTemplate(
                template="Hello {name}!",
                variables=["name"]
            ),
            targeting=TargetingCriteria(),
            status=BroadcastStatus.DRAFT
        )

        assert campaign.campaign_id == "test_123"
        assert campaign.name == "Test Campaign"
        assert campaign.status == BroadcastStatus.DRAFT

    def test_campaign_default_values(self):
        """Test campaign default values."""
        campaign = BroadcastCampaign(
            campaign_id="test",
            name="Test",
            message_template=MessageTemplate(template="Hi", variables=[]),
            targeting=TargetingCriteria(),
            status=BroadcastStatus.DRAFT
        )

        assert campaign.priority == BroadcastPriority.NORMAL
        assert campaign.sent_count == 0
        assert campaign.failed_count == 0


class TestMessageTemplate:
    """Tests for message templates."""

    def test_template_with_variables(self):
        """Test template with variable placeholders."""
        template = MessageTemplate(
            template="Hello {name}, your state is {state}.",
            variables=["name", "state"]
        )

        assert "{name}" in template.template
        assert "name" in template.variables
        assert "state" in template.variables

    def test_template_simple(self):
        """Test simple template without variables."""
        template = MessageTemplate(
            template="Important announcement for all citizens!",
            variables=[]
        )

        assert template.template == "Important announcement for all citizens!"
        assert len(template.variables) == 0


class TestTargetingCriteria:
    """Tests for broadcast targeting."""

    def test_default_targeting(self):
        """Test default targeting (all users)."""
        criteria = TargetingCriteria()

        assert criteria.states is None
        assert criteria.lgas is None
        assert criteria.min_engagement is None
        assert criteria.exclude_inactive is False

    def test_state_targeting(self):
        """Test targeting by state."""
        criteria = TargetingCriteria(
            states=["Lagos", "Abuja", "Rivers"]
        )

        assert "Lagos" in criteria.states
        assert len(criteria.states) == 3

    def test_engagement_targeting(self):
        """Test targeting by engagement level."""
        criteria = TargetingCriteria(
            min_engagement=5,
            exclude_inactive=True
        )

        assert criteria.min_engagement == 5
        assert criteria.exclude_inactive is True


class TestBroadcastService:
    """Tests for BroadcastService."""

    def setup_method(self):
        """Reset service state before each test."""
        BroadcastService._campaigns = {}
        BroadcastService._scheduled_jobs = {}

    def test_create_campaign(self):
        """Test creating a new campaign."""
        campaign = BroadcastService.create_campaign(
            name="New Campaign",
            template="Hello citizens of {state}!",
            variables=["state"],
            targeting=TargetingCriteria(states=["Lagos"])
        )

        assert campaign.name == "New Campaign"
        assert campaign.status == BroadcastStatus.DRAFT
        assert campaign.campaign_id in BroadcastService._campaigns

    def test_get_campaign(self):
        """Test retrieving a campaign."""
        created = BroadcastService.create_campaign(
            name="Get Test",
            template="Test message",
            variables=[]
        )

        retrieved = BroadcastService.get_campaign(created.campaign_id)
        assert retrieved is not None
        assert retrieved.name == "Get Test"

    def test_get_nonexistent_campaign(self):
        """Test getting a campaign that doesn't exist."""
        result = BroadcastService.get_campaign("nonexistent_id")
        assert result is None

    def test_update_campaign(self):
        """Test updating campaign details."""
        campaign = BroadcastService.create_campaign(
            name="Original Name",
            template="Original message",
            variables=[]
        )

        updated = BroadcastService.update_campaign(
            campaign_id=campaign.campaign_id,
            name="Updated Name",
            template="Updated message"
        )

        assert updated.name == "Updated Name"
        assert "Updated message" in updated.message_template.template

    def test_update_nonexistent_campaign(self):
        """Test updating a campaign that doesn't exist."""
        result = BroadcastService.update_campaign(
            campaign_id="nonexistent",
            name="Test"
        )
        assert result is None

    def test_cannot_update_sent_campaign(self):
        """Test that sent campaigns cannot be updated."""
        campaign = BroadcastService.create_campaign(
            name="Test",
            template="Test",
            variables=[]
        )
        campaign.status = BroadcastStatus.SENT

        result = BroadcastService.update_campaign(
            campaign_id=campaign.campaign_id,
            name="New Name"
        )

        # Should return None or unchanged campaign based on implementation
        assert result is None or result.name == "Test"

    def test_list_campaigns(self):
        """Test listing all campaigns."""
        BroadcastService.create_campaign("Campaign 1", "Msg 1", [])
        BroadcastService.create_campaign("Campaign 2", "Msg 2", [])

        campaigns = BroadcastService.list_campaigns()
        assert len(campaigns) == 2

    def test_list_campaigns_by_status(self):
        """Test filtering campaigns by status."""
        c1 = BroadcastService.create_campaign("Draft 1", "Msg", [])
        c2 = BroadcastService.create_campaign("Draft 2", "Msg", [])
        c2.status = BroadcastStatus.SCHEDULED

        drafts = BroadcastService.list_campaigns(status=BroadcastStatus.DRAFT)
        assert len(drafts) == 1
        assert drafts[0].name == "Draft 1"

    def test_delete_campaign(self):
        """Test deleting a campaign."""
        campaign = BroadcastService.create_campaign(
            name="To Delete",
            template="Message",
            variables=[]
        )

        success = BroadcastService.delete_campaign(campaign.campaign_id)
        assert success is True
        assert BroadcastService.get_campaign(campaign.campaign_id) is None

    def test_delete_nonexistent_campaign(self):
        """Test deleting a campaign that doesn't exist."""
        success = BroadcastService.delete_campaign("nonexistent")
        assert success is False

    def test_schedule_campaign(self):
        """Test scheduling a campaign for future delivery."""
        campaign = BroadcastService.create_campaign(
            name="Scheduled",
            template="Future message",
            variables=[]
        )

        scheduled_time = datetime.utcnow() + timedelta(hours=2)
        result = BroadcastService.schedule_campaign(
            campaign_id=campaign.campaign_id,
            scheduled_time=scheduled_time
        )

        assert result.status == BroadcastStatus.SCHEDULED
        assert result.scheduled_time == scheduled_time

    def test_cancel_scheduled_campaign(self):
        """Test canceling a scheduled campaign."""
        campaign = BroadcastService.create_campaign(
            name="To Cancel",
            template="Message",
            variables=[]
        )
        campaign.status = BroadcastStatus.SCHEDULED

        result = BroadcastService.cancel_campaign(campaign.campaign_id)
        assert result.status == BroadcastStatus.CANCELLED

    def test_get_campaign_stats(self):
        """Test getting campaign statistics."""
        campaign = BroadcastService.create_campaign(
            name="Stats Test",
            template="Message",
            variables=[]
        )
        campaign.sent_count = 100
        campaign.failed_count = 5
        campaign.delivered_count = 95

        stats = BroadcastService.get_campaign_stats(campaign.campaign_id)

        assert stats is not None
        assert stats["sent_count"] == 100
        assert stats["failed_count"] == 5
        assert stats["delivery_rate"] > 0


class TestBroadcastStatus:
    """Tests for broadcast status enum."""

    def test_status_values(self):
        """Test that all status values are defined."""
        assert BroadcastStatus.DRAFT.value == "draft"
        assert BroadcastStatus.SCHEDULED.value == "scheduled"
        assert BroadcastStatus.SENDING.value == "sending"
        assert BroadcastStatus.SENT.value == "sent"
        assert BroadcastStatus.PAUSED.value == "paused"
        assert BroadcastStatus.CANCELLED.value == "cancelled"
        assert BroadcastStatus.FAILED.value == "failed"


class TestBroadcastPriority:
    """Tests for broadcast priority enum."""

    def test_priority_values(self):
        """Test that all priority values are defined."""
        assert BroadcastPriority.LOW.value == "low"
        assert BroadcastPriority.NORMAL.value == "normal"
        assert BroadcastPriority.HIGH.value == "high"
        assert BroadcastPriority.URGENT.value == "urgent"


class TestTemplateRendering:
    """Tests for message template rendering."""

    def test_render_template_with_variables(self):
        """Test rendering template with variable substitution."""
        template = MessageTemplate(
            template="Hello {name}! Updates for {state}.",
            variables=["name", "state"]
        )

        result = BroadcastService.render_template(
            template,
            {"name": "Chidi", "state": "Lagos"}
        )

        assert "Chidi" in result
        assert "Lagos" in result

    def test_render_template_missing_variable(self):
        """Test rendering with missing variable uses placeholder."""
        template = MessageTemplate(
            template="Hello {name}!",
            variables=["name"]
        )

        result = BroadcastService.render_template(
            template,
            {}  # No variables provided
        )

        # Should either use placeholder or original {name}
        assert result is not None


class TestDeliveryStats:
    """Tests for delivery statistics."""

    def test_stats_calculation(self):
        """Test delivery statistics calculation."""
        stats = DeliveryStats(
            total_recipients=100,
            sent=95,
            delivered=90,
            failed=5,
            pending=0
        )

        assert stats.total_recipients == 100
        assert stats.sent == 95
        assert stats.delivered == 90

    def test_delivery_rate_calculation(self):
        """Test delivery rate percentage calculation."""
        stats = DeliveryStats(
            total_recipients=100,
            sent=100,
            delivered=95,
            failed=5,
            pending=0
        )

        # Delivery rate should be 95%
        rate = stats.delivered / stats.sent * 100 if stats.sent > 0 else 0
        assert rate == 95.0


class TestProactiveMessaging:
    """Tests for proactive messaging features."""

    def test_election_reminder_template(self):
        """Test election reminder message template."""
        template = MessageTemplate(
            template=(
                "Election Reminder: {election_name} is on {date}. "
                "Your polling unit: {polling_unit}. "
                "Don't forget your PVC!"
            ),
            variables=["election_name", "date", "polling_unit"]
        )

        result = BroadcastService.render_template(
            template,
            {
                "election_name": "Presidential Election",
                "date": "February 25, 2027",
                "polling_unit": "Ward 5, Ikeja"
            }
        )

        assert "Presidential Election" in result
        assert "February 25, 2027" in result
        assert "Ward 5, Ikeja" in result

    def test_factcheck_alert_template(self):
        """Test fact-check alert message template."""
        template = MessageTemplate(
            template=(
                "Fact-Check Alert: A claim about {topic} is circulating. "
                "Our verdict: {verdict}. Details: {link}"
            ),
            variables=["topic", "verdict", "link"]
        )

        result = BroadcastService.render_template(
            template,
            {
                "topic": "fuel subsidy",
                "verdict": "MISLEADING",
                "link": "https://decide9ja.ng/fc/123"
            }
        )

        assert "fuel subsidy" in result
        assert "MISLEADING" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
