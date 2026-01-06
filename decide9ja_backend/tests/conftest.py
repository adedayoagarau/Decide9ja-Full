"""
Pytest Configuration and Shared Fixtures
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =====================
# Database Fixtures
# =====================

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.all.return_value = []
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_get_db(mock_db_session):
    """Mock the get_db dependency."""
    with patch('app.database.get_db') as mock:
        mock.return_value = mock_db_session
        yield mock_db_session


# =====================
# API Client Fixtures
# =====================

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def authenticated_client(test_client):
    """Create an authenticated test client with API key."""
    # Set up test API key
    from app.auth.api_keys import APIKeyAuth

    raw_key, api_key = APIKeyAuth.create_key(
        name="Test Client Key",
        role="admin",
        scopes=["*"],
        created_by="pytest"
    )

    # Add API key header to client
    test_client.headers["X-API-Key"] = raw_key
    yield test_client

    # Cleanup
    APIKeyAuth.revoke_key(api_key.key_id)


# =====================
# Service Fixtures
# =====================

@pytest.fixture
def reset_auth_state():
    """Reset authentication state before and after tests."""
    from app.auth.api_keys import APIKeyAuth
    from app.auth.audit import AuditLogger

    # Store original state
    original_keys = APIKeyAuth._keys.copy()
    original_usage = APIKeyAuth._usage.copy()
    original_logs = AuditLogger._logs.copy()

    # Clear state
    APIKeyAuth._keys = {}
    APIKeyAuth._usage = {}
    AuditLogger._logs = []

    yield

    # Restore state
    APIKeyAuth._keys = original_keys
    APIKeyAuth._usage = original_usage
    AuditLogger._logs = original_logs


@pytest.fixture
def reset_broadcast_state():
    """Reset broadcast service state."""
    from app.services.broadcast import BroadcastService

    original_campaigns = BroadcastService._campaigns.copy()
    BroadcastService._campaigns = {}

    yield

    BroadcastService._campaigns = original_campaigns


@pytest.fixture
def reset_factcheck_state():
    """Reset fact-check service state."""
    from app.services.factcheck import FactCheckService

    original_factchecks = FactCheckService._factchecks.copy()
    original_requests = FactCheckService._requests.copy()

    FactCheckService._factchecks = {}
    FactCheckService._requests = {}

    yield

    FactCheckService._factchecks = original_factchecks
    FactCheckService._requests = original_requests


@pytest.fixture
def reset_constituency_state():
    """Reset constituency service state."""
    from app.services.constituency import ConstituencyService

    original_constituencies = ConstituencyService._constituencies.copy()
    original_issues = ConstituencyService._issues.copy()

    ConstituencyService._constituencies = {}
    ConstituencyService._issues = {}

    yield

    ConstituencyService._constituencies = original_constituencies
    ConstituencyService._issues = original_issues


# =====================
# Mock External Services
# =====================

@pytest.fixture
def mock_twilio():
    """Mock Twilio WhatsApp client."""
    with patch('app.services.twilio_whatsapp.TwilioClient') as mock:
        mock_instance = MagicMock()
        mock_instance.messages.create = MagicMock(
            return_value=MagicMock(sid="SM_test_message_id")
        )
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic Claude API."""
    with patch('app.services.llm.anthropic') as mock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="This is a test response from Claude.")
        ]
        mock_client.messages.create.return_value = mock_response
        mock.Anthropic.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_s3():
    """Mock AWS S3 client."""
    with patch('boto3.client') as mock:
        mock_client = MagicMock()
        mock_client.upload_fileobj = MagicMock()
        mock_client.generate_presigned_url = MagicMock(
            return_value="https://s3.example.com/test-file"
        )
        mock.return_value = mock_client
        yield mock_client


# =====================
# Sample Data Fixtures
# =====================

@pytest.fixture
def sample_politician():
    """Create a sample politician for testing."""
    return {
        "id": "pol_test_123",
        "name": "Test Politician",
        "position": "Senator",
        "state": "Lagos",
        "party": "APC",
        "biography": "A test politician for unit testing.",
        "contact": {
            "email": "test@senate.gov.ng",
            "phone": "08012345678"
        }
    }


@pytest.fixture
def sample_election():
    """Create a sample election for testing."""
    return {
        "id": "elec_test_456",
        "name": "Test Election 2027",
        "type": "Presidential",
        "date": "2027-02-25",
        "candidates": [
            {"name": "Candidate A", "party": "APC"},
            {"name": "Candidate B", "party": "PDP"}
        ]
    }


@pytest.fixture
def sample_factcheck():
    """Create a sample fact-check for testing."""
    return {
        "factcheck_id": "fc_test_789",
        "claim": "Test claim about politics",
        "verdict": "false",
        "explanation": "This claim is false because...",
        "sources": [
            {
                "name": "Official Source",
                "url": "https://example.gov.ng"
            }
        ]
    }


@pytest.fixture
def sample_issue():
    """Create a sample community issue for testing."""
    return {
        "issue_id": "issue_test_101",
        "title": "Test Issue",
        "description": "A test community issue",
        "category": "infrastructure",
        "status": "open",
        "location": "Test Location, Lagos",
        "reporter_id": "user_test"
    }


# =====================
# Utility Functions
# =====================

def assert_response_ok(response):
    """Assert that a response is successful (2xx)."""
    assert 200 <= response.status_code < 300, f"Expected 2xx, got {response.status_code}: {response.text}"


def assert_response_error(response, expected_status=None):
    """Assert that a response is an error."""
    if expected_status:
        assert response.status_code == expected_status
    else:
        assert response.status_code >= 400


# =====================
# Async Test Support
# =====================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =====================
# Environment Setup
# =====================

@pytest.fixture(autouse=True)
def set_test_environment():
    """Set test environment variables."""
    original_env = os.environ.copy()

    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["TWILIO_ACCOUNT_SID"] = "test_sid"
    os.environ["TWILIO_AUTH_TOKEN"] = "test_token"
    os.environ["TWILIO_WHATSAPP_NUMBER"] = "whatsapp:+1234567890"

    yield

    os.environ.clear()
    os.environ.update(original_env)
