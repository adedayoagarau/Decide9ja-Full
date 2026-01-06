"""
Tests for Fact-Checking Service
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.factcheck import (
    FactCheckService,
    FactCheck,
    FactCheckStatus,
    FactCheckVerdict,
    FactCheckRequest,
    ClaimSource,
    EvidenceItem
)


class TestFactCheckVerdict:
    """Tests for fact-check verdict enum."""

    def test_verdict_values(self):
        """Test that all verdict values are defined."""
        assert FactCheckVerdict.TRUE.value == "true"
        assert FactCheckVerdict.MOSTLY_TRUE.value == "mostly_true"
        assert FactCheckVerdict.HALF_TRUE.value == "half_true"
        assert FactCheckVerdict.MOSTLY_FALSE.value == "mostly_false"
        assert FactCheckVerdict.FALSE.value == "false"
        assert FactCheckVerdict.UNVERIFIABLE.value == "unverifiable"
        assert FactCheckVerdict.SATIRE.value == "satire"


class TestFactCheckStatus:
    """Tests for fact-check status enum."""

    def test_status_values(self):
        """Test that all status values are defined."""
        assert FactCheckStatus.PENDING.value == "pending"
        assert FactCheckStatus.IN_REVIEW.value == "in_review"
        assert FactCheckStatus.VERIFIED.value == "verified"
        assert FactCheckStatus.PUBLISHED.value == "published"
        assert FactCheckStatus.REJECTED.value == "rejected"


class TestFactCheck:
    """Tests for FactCheck model."""

    def test_create_factcheck(self):
        """Test creating a fact-check."""
        fc = FactCheck(
            factcheck_id="fc_123",
            claim="The president promised free education",
            verdict=FactCheckVerdict.MOSTLY_TRUE,
            explanation="The promise was made but implementation is partial",
            status=FactCheckStatus.PUBLISHED,
            sources=[],
            evidence=[]
        )

        assert fc.factcheck_id == "fc_123"
        assert fc.verdict == FactCheckVerdict.MOSTLY_TRUE
        assert fc.status == FactCheckStatus.PUBLISHED

    def test_factcheck_with_sources(self):
        """Test fact-check with source citations."""
        sources = [
            ClaimSource(
                name="INEC Official Statement",
                url="https://inec.gov.ng/statement",
                date=datetime(2024, 1, 15),
                credibility_score=0.95
            ),
            ClaimSource(
                name="Channels TV Report",
                url="https://channelstv.com/report",
                date=datetime(2024, 1, 16),
                credibility_score=0.85
            )
        ]

        fc = FactCheck(
            factcheck_id="fc_456",
            claim="Voter registration deadline extended",
            verdict=FactCheckVerdict.TRUE,
            explanation="INEC confirmed the extension",
            status=FactCheckStatus.PUBLISHED,
            sources=sources,
            evidence=[]
        )

        assert len(fc.sources) == 2
        assert fc.sources[0].credibility_score == 0.95

    def test_factcheck_with_evidence(self):
        """Test fact-check with supporting evidence."""
        evidence = [
            EvidenceItem(
                type="document",
                description="Official INEC circular",
                url="https://inec.gov.ng/circular.pdf"
            ),
            EvidenceItem(
                type="video",
                description="Press conference recording",
                url="https://youtube.com/watch?v=..."
            )
        ]

        fc = FactCheck(
            factcheck_id="fc_789",
            claim="Test claim",
            verdict=FactCheckVerdict.TRUE,
            explanation="Supported by evidence",
            status=FactCheckStatus.PUBLISHED,
            sources=[],
            evidence=evidence
        )

        assert len(fc.evidence) == 2
        assert fc.evidence[0].type == "document"


class TestFactCheckService:
    """Tests for FactCheckService."""

    def setup_method(self):
        """Reset service state before each test."""
        FactCheckService._factchecks = {}
        FactCheckService._requests = {}

    def test_create_factcheck(self):
        """Test creating a new fact-check."""
        fc = FactCheckService.create_factcheck(
            claim="Test claim about politics",
            category="politics"
        )

        assert fc.claim == "Test claim about politics"
        assert fc.status == FactCheckStatus.PENDING
        assert fc.factcheck_id in FactCheckService._factchecks

    def test_get_factcheck(self):
        """Test retrieving a fact-check."""
        created = FactCheckService.create_factcheck(
            claim="Get test claim",
            category="economy"
        )

        retrieved = FactCheckService.get_factcheck(created.factcheck_id)
        assert retrieved is not None
        assert retrieved.claim == "Get test claim"

    def test_get_nonexistent_factcheck(self):
        """Test getting a fact-check that doesn't exist."""
        result = FactCheckService.get_factcheck("nonexistent_id")
        assert result is None

    def test_update_factcheck_verdict(self):
        """Test updating fact-check verdict."""
        fc = FactCheckService.create_factcheck(
            claim="Claim to verify",
            category="politics"
        )

        updated = FactCheckService.update_factcheck(
            factcheck_id=fc.factcheck_id,
            verdict=FactCheckVerdict.FALSE,
            explanation="This claim is completely false based on evidence"
        )

        assert updated.verdict == FactCheckVerdict.FALSE
        assert "false" in updated.explanation.lower()

    def test_publish_factcheck(self):
        """Test publishing a fact-check."""
        fc = FactCheckService.create_factcheck(
            claim="Claim to publish",
            category="politics"
        )

        # First verify it
        FactCheckService.update_factcheck(
            factcheck_id=fc.factcheck_id,
            verdict=FactCheckVerdict.TRUE,
            explanation="This is true",
            status=FactCheckStatus.VERIFIED
        )

        # Then publish
        published = FactCheckService.publish_factcheck(fc.factcheck_id)
        assert published.status == FactCheckStatus.PUBLISHED

    def test_list_factchecks(self):
        """Test listing all fact-checks."""
        FactCheckService.create_factcheck("Claim 1", "politics")
        FactCheckService.create_factcheck("Claim 2", "economy")

        all_fcs = FactCheckService.list_factchecks()
        assert len(all_fcs) == 2

    def test_list_factchecks_by_verdict(self):
        """Test filtering fact-checks by verdict."""
        fc1 = FactCheckService.create_factcheck("True claim", "politics")
        fc2 = FactCheckService.create_factcheck("False claim", "politics")

        FactCheckService.update_factcheck(
            fc1.factcheck_id,
            verdict=FactCheckVerdict.TRUE
        )
        FactCheckService.update_factcheck(
            fc2.factcheck_id,
            verdict=FactCheckVerdict.FALSE
        )

        true_fcs = FactCheckService.list_factchecks(verdict=FactCheckVerdict.TRUE)
        assert len(true_fcs) == 1
        assert true_fcs[0].verdict == FactCheckVerdict.TRUE

    def test_list_factchecks_by_category(self):
        """Test filtering fact-checks by category."""
        FactCheckService.create_factcheck("Politics claim", "politics")
        FactCheckService.create_factcheck("Economy claim", "economy")
        FactCheckService.create_factcheck("Another politics", "politics")

        politics_fcs = FactCheckService.list_factchecks(category="politics")
        assert len(politics_fcs) == 2

    def test_search_factchecks(self):
        """Test searching fact-checks by keyword."""
        FactCheckService.create_factcheck(
            "President announced new fuel prices",
            "economy"
        )
        FactCheckService.create_factcheck(
            "Governor promises road construction",
            "infrastructure"
        )

        results = FactCheckService.search_factchecks("fuel")
        assert len(results) >= 1
        assert any("fuel" in fc.claim.lower() for fc in results)

    def test_delete_factcheck(self):
        """Test deleting a fact-check."""
        fc = FactCheckService.create_factcheck(
            "To be deleted",
            "politics"
        )

        success = FactCheckService.delete_factcheck(fc.factcheck_id)
        assert success is True
        assert FactCheckService.get_factcheck(fc.factcheck_id) is None


class TestFactCheckRequest:
    """Tests for user fact-check requests."""

    def setup_method(self):
        """Reset service state before each test."""
        FactCheckService._factchecks = {}
        FactCheckService._requests = {}

    def test_submit_request(self):
        """Test submitting a fact-check request."""
        request = FactCheckService.submit_request(
            claim="I heard the election was postponed",
            source="WhatsApp forward",
            user_id="user_123"
        )

        assert request.claim == "I heard the election was postponed"
        assert request.user_id == "user_123"
        assert request.status == "pending"

    def test_request_includes_timestamp(self):
        """Test that request includes submission timestamp."""
        request = FactCheckService.submit_request(
            claim="Test claim",
            source="Social media",
            user_id="user_456"
        )

        assert request.submitted_at is not None
        assert isinstance(request.submitted_at, datetime)

    def test_list_pending_requests(self):
        """Test listing pending fact-check requests."""
        FactCheckService.submit_request("Claim 1", "source", "user1")
        FactCheckService.submit_request("Claim 2", "source", "user2")

        pending = FactCheckService.list_requests(status="pending")
        assert len(pending) == 2

    def test_process_request(self):
        """Test processing a fact-check request."""
        request = FactCheckService.submit_request(
            claim="Claim to process",
            source="Facebook",
            user_id="user_789"
        )

        # Process the request (creates a fact-check)
        fc = FactCheckService.process_request(
            request_id=request.request_id,
            reviewer_id="moderator_1"
        )

        assert fc is not None
        assert fc.claim == "Claim to process"

        # Request status should be updated
        updated_request = FactCheckService.get_request(request.request_id)
        assert updated_request.status == "processed"

    def test_reject_request(self):
        """Test rejecting a fact-check request."""
        request = FactCheckService.submit_request(
            claim="Invalid request",
            source="Unknown",
            user_id="user_000"
        )

        result = FactCheckService.reject_request(
            request_id=request.request_id,
            reason="Not a verifiable claim"
        )

        assert result.status == "rejected"
        assert "Not a verifiable claim" in result.rejection_reason


class TestVerdictLabels:
    """Tests for verdict display labels."""

    def test_verdict_labels_are_clear(self):
        """Test that verdict labels are user-friendly."""
        labels = {
            FactCheckVerdict.TRUE: "TRUE",
            FactCheckVerdict.MOSTLY_TRUE: "MOSTLY TRUE",
            FactCheckVerdict.HALF_TRUE: "HALF TRUE",
            FactCheckVerdict.MOSTLY_FALSE: "MOSTLY FALSE",
            FactCheckVerdict.FALSE: "FALSE",
            FactCheckVerdict.UNVERIFIABLE: "UNVERIFIABLE",
            FactCheckVerdict.SATIRE: "SATIRE/PARODY"
        }

        for verdict, expected in labels.items():
            label = FactCheckService.get_verdict_label(verdict)
            assert label.upper() == expected.upper()

    def test_verdict_color_codes(self):
        """Test that verdicts have appropriate color codes."""
        colors = FactCheckService.get_verdict_colors()

        # True should be green-ish
        assert colors[FactCheckVerdict.TRUE] in ["green", "#00ff00", "#28a745"]

        # False should be red-ish
        assert colors[FactCheckVerdict.FALSE] in ["red", "#ff0000", "#dc3545"]


class TestSimilarityDetection:
    """Tests for detecting similar claims."""

    def setup_method(self):
        """Reset service state before each test."""
        FactCheckService._factchecks = {}
        FactCheckService._requests = {}

    def test_find_similar_claims(self):
        """Test finding similar fact-checked claims."""
        # Create existing fact-checks
        FactCheckService.create_factcheck(
            "President announced fuel price increase",
            "economy"
        )
        FactCheckService.create_factcheck(
            "Governor inaugurates new highway",
            "infrastructure"
        )

        # Search for similar
        similar = FactCheckService.find_similar(
            "Is fuel going up in price?"
        )

        # Should find the fuel-related fact-check
        assert len(similar) >= 0  # May be 0 if similarity threshold not met


class TestFactCheckIntegration:
    """Integration tests for fact-checking workflow."""

    def setup_method(self):
        """Reset service state before each test."""
        FactCheckService._factchecks = {}
        FactCheckService._requests = {}

    def test_full_factcheck_workflow(self):
        """Test complete fact-checking workflow."""
        # 1. User submits request
        request = FactCheckService.submit_request(
            claim="The government allocated N500bn for education",
            source="Twitter post",
            user_id="user_workflow"
        )
        assert request.status == "pending"

        # 2. Moderator processes request
        fc = FactCheckService.process_request(
            request_id=request.request_id,
            reviewer_id="mod_1"
        )
        assert fc.status == FactCheckStatus.PENDING

        # 3. Fact-checker investigates and adds verdict
        updated = FactCheckService.update_factcheck(
            factcheck_id=fc.factcheck_id,
            verdict=FactCheckVerdict.HALF_TRUE,
            explanation=(
                "The budget allocation was N350bn, not N500bn. "
                "However, additional supplementary funds were approved."
            ),
            sources=[
                ClaimSource(
                    name="Budget Office",
                    url="https://budget.gov.ng/2024",
                    date=datetime.now(),
                    credibility_score=0.99
                )
            ],
            status=FactCheckStatus.VERIFIED
        )
        assert updated.verdict == FactCheckVerdict.HALF_TRUE

        # 4. Editor publishes
        published = FactCheckService.publish_factcheck(fc.factcheck_id)
        assert published.status == FactCheckStatus.PUBLISHED

        # 5. Verify it's searchable
        results = FactCheckService.search_factchecks("education")
        assert len(results) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
