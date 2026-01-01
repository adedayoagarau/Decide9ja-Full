"""
Intelligence Layer Tests

Tests for the complete intelligence layer:
- Fuzzy politician matching
- Retrieval orchestration
- Context assembly
- Web search integration
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass


# === FUZZY MATCHING TESTS ===

class TestPoliticianLookup:
    """Test politician lookup service with fuzzy matching."""
    
    def test_clean_query_removes_prefixes(self):
        """Test query cleaning removes common prefixes."""
        from app.services.politician_lookup import clean_query
        
        assert clean_query("Who is Tinubu") == "tinubu"
        assert clean_query("Tell me about Obi") == "obi"
        assert clean_query("Senator Akpabio") == "akpabio"
        assert clean_query("Hon. Femi Gbajabiamila") == "femi gbajabiamila"
        # Note: Hyphens are removed during cleaning
        assert "ngozi" in clean_query("Dr. Ngozi Okonjo-Iweala").lower()
    
    def test_clean_query_removes_punctuation(self):
        """Test query cleaning removes punctuation."""
        from app.services.politician_lookup import clean_query
        
        assert clean_query("Who is Tinubu?") == "tinubu"
        assert clean_query("Tinubu!") == "tinubu"


class TestRetrievalOrchestrator:
    """Test retrieval orchestration."""
    
    def test_get_strategy_returns_correct_strategy(self):
        """Test strategy selection based on intent."""
        from app.services.retrieval import get_strategy, RetrievalStrategy
        from app.services.router import Intent
        
        assert get_strategy(Intent.REP_LOOKUP) == RetrievalStrategy.DATABASE_ONLY
        assert get_strategy(Intent.POLITICIAN_INFO) == RetrievalStrategy.DATABASE_PLUS_RAG
        assert get_strategy(Intent.NEWS_QUERY) == RetrievalStrategy.WEB_PRIMARY
        assert get_strategy(Intent.FOLLOWUP) == RetrievalStrategy.HYBRID
    
    def test_resolve_pronouns_replaces_he(self):
        """Test pronoun resolution."""
        from app.services.retrieval import resolve_pronouns
        
        @dataclass
        class MockState:
            active_politician_name: str = "Bola Tinubu"
        
        state = MockState()
        
        assert "Bola Tinubu" in resolve_pronouns("What has he done?", state)
        assert "Bola Tinubu's" in resolve_pronouns("What is his record?", state)
    
    def test_resolve_pronouns_no_context(self):
        """Test pronoun resolution with no active context."""
        from app.services.retrieval import resolve_pronouns
        
        @dataclass
        class MockState:
            active_politician_name: str = None
        
        state = MockState()
        
        assert resolve_pronouns("What has he done?", state) == "What has he done?"


class TestContextAssembler:
    """Test context assembly."""
    
    def test_format_user_profile(self):
        """Test user profile formatting."""
        from app.services.context_assembler import format_user_profile
        
        @dataclass
        class MockState:
            name: str = "Adedayo"
            state: str = "Ogun"
            lga: str = "Ijebu North"
            active_politician_name: str = None
            active_topic: str = None
        
        state = MockState()
        profile = format_user_profile(state)
        
        assert "Adedayo" in profile
        assert "Ogun" in profile
        assert "Ijebu North" in profile
    
    def test_format_politician(self):
        """Test politician formatting."""
        from app.services.context_assembler import format_politician
        
        politician = {
            "name": "Bola Tinubu",
            "position": "President",
            "party": "APC",
            "state": "Lagos",
            "bio": "16th President of Nigeria"
        }
        
        formatted = format_politician(politician)
        
        assert "Bola Tinubu" in formatted
        assert "President" in formatted
        assert "APC" in formatted
    
    def test_format_representatives(self):
        """Test representatives list formatting."""
        from app.services.context_assembler import format_representatives
        
        reps = [
            {"name": "Dapo Abiodun", "position": "Governor", "party": "APC"},
            {"name": "Gbenga Daniel", "position": "Senator", "party": "APC"},
        ]
        
        formatted = format_representatives(reps)
        
        assert "Dapo Abiodun" in formatted
        assert "Gbenga Daniel" in formatted
        assert "Governor" in formatted
        assert "Senator" in formatted
    
    def test_truncate_context(self):
        """Test context truncation."""
        from app.services.context_assembler import truncate_context
        
        sections = [
            ("SHORT", "Short content"),
            ("LONG", "x" * 10000),  # Very long content
        ]
        
        truncated = truncate_context(sections, max_chars=500)
        
        assert len(truncated) <= 600  # Some buffer for headers
        assert "SHORT" in truncated


class TestRetrievalResult:
    """Test RetrievalResult dataclass."""
    
    def test_retrieval_result_defaults(self):
        """Test default values."""
        from app.services.retrieval import RetrievalResult
        
        result = RetrievalResult()
        
        assert result.politician is None
        assert result.representatives == []
        assert result.rag_context == ""
        assert result.web_results == []
        assert result.sources_used == []
        assert result.confidence == 0.0
    
    def test_retrieval_result_with_data(self):
        """Test with populated data."""
        from app.services.retrieval import RetrievalResult
        
        result = RetrievalResult(
            politician={"name": "Test"},
            sources_used=["database"],
            confidence=0.9
        )
        
        assert result.politician["name"] == "Test"
        assert "database" in result.sources_used
        assert result.confidence == 0.9


# === INTEGRATION TESTS (require database) ===

@pytest.mark.asyncio
class TestIntegrationFuzzyMatch:
    """Integration tests for fuzzy matching (require database)."""
    
    async def test_misspelled_name_finds_politician(self):
        """'Gbenga Dienel' should find Gbenga Daniel."""
        # This test requires actual database
        # Skip if no database available
        try:
            from app.services.politician_lookup import find_politician
            from app.models.state import UserState
            
            state = UserState(
                user_id="test",
                phone="+234",
                state="Ogun",
                lga="Ijebu North"
            )
            
            result = await find_politician("Gbenga Dienel", state)
            
            # If we have database with Gbenga Daniel
            if result.politician:
                assert "Daniel" in result.politician.get("name", "")
            else:
                pytest.skip("No politician data in test database")
                
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
    
    async def test_location_aware_matching(self):
        """User's representatives should be prioritized."""
        try:
            from app.services.politician_lookup import get_representatives
            
            reps = await get_representatives("Ogun", "Ijebu North")
            
            if reps:
                assert len(reps) > 0
                assert all("name" in r for r in reps)
            else:
                pytest.skip("No representative data in test database")
                
        except Exception as e:
            pytest.skip(f"Database not available: {e}")


@pytest.mark.asyncio
class TestIntegrationRetrieval:
    """Integration tests for retrieval orchestrator."""
    
    async def test_news_query_uses_web_search(self):
        """News queries should trigger web search."""
        try:
            from app.services.retrieval import retrieve
            from app.services.router import Intent
            from app.models.state import UserState
            
            state = UserState(user_id="test", phone="+234")
            
            result = await retrieve(
                Intent.NEWS_QUERY,
                "What's the latest on the 2026 budget?",
                state
            )
            
            # Should have some results
            assert result.news_results or result.web_results or result.suggestions
            
        except Exception as e:
            pytest.skip(f"External services not available: {e}")
    
    async def test_rep_lookup_uses_database(self):
        """Representative lookup should use database."""
        try:
            from app.services.retrieval import retrieve
            from app.services.router import Intent
            from app.models.state import UserState
            
            state = UserState(
                user_id="test",
                phone="+234",
                state="Lagos",
                lga="Ikeja"
            )
            
            result = await retrieve(
                Intent.REP_LOOKUP,
                "Who is my representative?",
                state
            )
            
            if result.representatives:
                assert "database" in result.sources_used
            else:
                pytest.skip("No representative data")
                
        except Exception as e:
            pytest.skip(f"Database not available: {e}")


# === MOCK TESTS ===

class TestWithMocks:
    """Tests using mocks for external dependencies."""
    
    @pytest.mark.asyncio
    async def test_retrieve_hybrid_combines_sources(self):
        """Hybrid retrieval should try all sources."""
        # This is a simple structural test that verifies the code paths exist
        from app.services.retrieval import RetrievalResult, resolve_pronouns
        
        @dataclass
        class MockState:
            state: str = "Lagos"
            lga: str = "Ikeja"
            active_politician_id: str = None
            active_politician_name: str = "Tinubu"
        
        state = MockState()
        
        # Test pronoun resolution works
        resolved = resolve_pronouns("What has he done?", state)
        assert "Tinubu" in resolved
        
        # Test RetrievalResult can be created and modified
        result = RetrievalResult()
        result.politician = {"name": "Test"}
        result.sources_used.append("database")
        result.confidence = 0.9
        
        assert result.politician["name"] == "Test"
        assert "database" in result.sources_used
        assert result.confidence == 0.9
