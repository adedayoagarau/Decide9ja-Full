"""
Tests for Fuzzy Matching Service

Verifies that misspelled politician names are correctly matched.
"""
import pytest
from app.services.fuzzy_match import (
    fuzzy_find_politician,
    extract_politician_name_from_text,
    find_closest_match
)


class TestFuzzyFindPolitician:
    """Test fuzzy politician name matching."""
    
    def test_exact_match(self):
        """Exact matches should return 100% similarity."""
        candidates = [
            {"name": "Gbenga Daniel", "party": "APC"},
            {"name": "Bola Tinubu", "party": "APC"},
        ]
        
        result = fuzzy_find_politician("Gbenga Daniel", candidates)
        
        assert result is not None
        politician, similarity, suggestion = result
        assert politician["name"] == "Gbenga Daniel"
        assert similarity == 100
        assert suggestion is None
    
    def test_misspelled_dienel_to_daniel(self):
        """'Gbenga Dienel' should match 'Gbenga Daniel'."""
        candidates = [
            {"name": "Gbenga Daniel", "party": "APC", "position": "Senator"},
            {"name": "Bola Tinubu", "party": "APC", "position": "President"},
            {"name": "Peter Obi", "party": "LP", "position": "Former Governor"},
        ]
        
        result = fuzzy_find_politician("Gbenga Dienel", candidates)
        
        assert result is not None
        politician, similarity, suggestion = result
        assert politician["name"] == "Gbenga Daniel"
        assert similarity >= 75  # Should be high enough to match
        assert suggestion is not None  # Should suggest correction
        assert "Did you mean" in suggestion
    
    def test_misspelled_tinbu_to_tinubu(self):
        """'Tinbu' should match 'Bola Tinubu' with lower threshold."""
        candidates = [
            {"name": "Gbenga Daniel", "party": "APC"},
            {"name": "Bola Tinubu", "party": "APC"},
            {"name": "Peter Obi", "party": "LP"},
        ]
        
        # Short queries need lower threshold
        result = fuzzy_find_politician("Tinbu", candidates, threshold=60)
        
        assert result is not None
        politician, similarity, suggestion = result
        assert politician["name"] == "Bola Tinubu"
    
    def test_partial_name_match(self):
        """First or last name only should still match."""
        candidates = [
            {"name": "Gbenga Daniel", "party": "APC"},
            {"name": "Atiku Abubakar", "party": "PDP"},
            {"name": "Peter Obi", "party": "LP"},
        ]
        
        result = fuzzy_find_politician("Atiku", candidates)
        
        assert result is not None
        politician, similarity, suggestion = result
        assert politician["name"] == "Atiku Abubakar"
    
    def test_abubaker_to_abubakar(self):
        """'Abubaker' should match 'Abubakar' (common misspelling)."""
        candidates = [
            {"name": "Atiku Abubakar", "party": "PDP"},
            {"name": "Bola Tinubu", "party": "APC"},
        ]
        
        result = fuzzy_find_politician("Atiku Abubaker", candidates)
        
        assert result is not None
        politician, similarity, suggestion = result
        assert politician["name"] == "Atiku Abubakar"
    
    def test_no_match_below_threshold(self):
        """Completely different names should not match."""
        candidates = [
            {"name": "Gbenga Daniel", "party": "APC"},
            {"name": "Atiku Abubakar", "party": "PDP"},
        ]
        
        result = fuzzy_find_politician("John Smith", candidates, threshold=80)
        
        assert result is None
    
    def test_empty_candidates(self):
        """Empty candidates list should return None."""
        result = fuzzy_find_politician("Tinubu", [])
        assert result is None
    
    def test_empty_query(self):
        """Empty query should return None."""
        candidates = [{"name": "Gbenga Daniel"}]
        result = fuzzy_find_politician("", candidates)
        assert result is None


class TestExtractPoliticianName:
    """Test politician name extraction from queries."""
    
    def test_who_is_pattern(self):
        """'Who is X?' pattern."""
        name = extract_politician_name_from_text("Who is Gbenga Daniel?")
        # Now normalized to lowercase
        assert "gbenga" in name.lower() or "daniel" in name.lower()
    
    def test_about_pattern(self):
        """'Tell me about X' pattern."""
        name = extract_politician_name_from_text("Tell me about Tinubu")
        assert "tinubu" in name.lower()
    
    def test_info_on_pattern(self):
        """'Info on X' pattern."""
        name = extract_politician_name_from_text("Info on Atiku Abubakar")
        assert "atiku" in name.lower() or "abubakar" in name.lower()
    
    def test_just_name(self):
        """Just a name should be preserved (normalized lowercase)."""
        name = extract_politician_name_from_text("Gbenga Daniel")
        assert "gbenga" in name.lower() and "daniel" in name.lower()


class TestFindClosestMatch:
    """Test generic fuzzy string matching."""
    
    def test_state_matching(self):
        """Test matching Nigerian states with typos."""
        states = ["Lagos", "Kano", "Ogun", "Oyo", "Rivers"]
        
        # Common typos
        assert find_closest_match("Lago", states) == "Lagos"
        assert find_closest_match("Kanu", states) == "Kano"
        assert find_closest_match("Ribers", states, threshold=70) is not None
    
    def test_no_match(self):
        """Test when no match is found."""
        options = ["Lagos", "Kano"]
        result = find_closest_match("Completely Different", options, threshold=80)
        assert result is None


# Integration test placeholder (requires database)
class TestFuzzyMatchingIntegration:
    """Integration tests - run with database."""
    
    @pytest.mark.asyncio
    async def test_misspelled_query_finds_senator(self):
        """
        Integration test: 'Gbenga Dienel' should find Gbenga Daniel.
        
        This test requires:
        1. Database with Gbenga Daniel as Ogun East Senator
        2. User state set to Ogun
        """
        # This is a placeholder - actual test would use database
        pass
