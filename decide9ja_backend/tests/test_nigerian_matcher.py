"""
Test fixtures for Nigerian Fuzzy Matching
Based on positive and negative pairs from the handbook
"""

import pytest
from app.utils.nigerian_matcher import (
    normalize_text, normalize_name, strip_honorifics,
    match_state, match_party, match_politician_name,
    NigerianMatcher
)

# ==========================================
# POSITIVE PAIRS - Should Match
# ==========================================

POSITIVE_PARTY_PAIRS = [
    ("Accord Nigeria", "Accord"),
    # ("A.", "Accord"),  # Too ambiguous - single letters shouldn't match
    ("AA party", "Action Alliance"),
    ("AAC.", "African Action Congress"),
    ("A.A.C.", "African Action Congress"),
    ("ADC.", "African Democratic Congress"),
    ("ADC", "African Democratic Congress"),
    ("ADP", "Action Democratic Party"),
    ("A.P.C.", "All Progressives Congress"),
    ("Progressives Congress", "All Progressives Congress"),
    ("APGA", "All Progressives Grand Alliance"),
    ("APGA.", "All Progressives Grand Alliance"),
    ("Allied People Movement", "Allied Peoples Movement"),
    ("PDP", "Peoples Democratic Party"),
    ("P.D.P.", "Peoples Democratic Party"),
    ("Labour Party", "Labour Party"),
    ("LP", "Labour Party"),
    ("NNPP", "New Nigeria Peoples Party"),
]

POSITIVE_STATE_PAIRS = [
    ("Abia", "Abia"),
    ("AB", "Abia"),
    ("Lagos", "Lagos"),
    ("Lagos state", "Lagos"),
    ("lagos st", "Lagos"),
    ("FCT", "FCT"),
    ("Abuja", "FCT"),
    ("federal capital territory", "FCT"),
    ("Akwa Ibom", "Akwa Ibom"),
    ("Akwa-Ibom", "Akwa Ibom"),
    ("akwaibom", "Akwa Ibom"),
    ("crossriver", "Cross River"),
    ("Cross River", "Cross River"),
]

# ==========================================
# NEGATIVE PAIRS - Should NOT Match
# ==========================================

NEGATIVE_PAIRS = [
    # Acronym collisions
    ("NIS", "NIMC"),  # NIS is Immigration, not NIMC
    ("NIMC", "NIS"),  # NIMC is Identity, not Immigration
    ("Niger", "Nigeria"),  # State vs Country
    ("GTB", "Globus Bank"),  # GTB is GTBank
    ("Etisalat", "Airtel"),  # Etisalat is 9mobile
    # Party confusions
    ("APC", "APGA"),  # Different parties
    ("PDP", "PRP"),  # Different parties
    ("LP", "ZLP"),  # Different parties
]


class TestNormalization:
    """Test normalization functions."""
    
    def test_normalize_text_basic(self):
        assert normalize_text("  Hello World  ") == "hello world"
        assert normalize_text("Hello, World!") == "hello world"
        assert normalize_text("A.P.C.") == "apc"
    
    def test_strip_honorifics(self):
        assert strip_honorifics("Dr. Ahmed Bola") == "ahmed bola"
        assert strip_honorifics("Sen. Orji Uzor Kalu") == "orji uzor kalu"
        assert strip_honorifics("Alhaji Chief Bola Tinubu") == "bola tinubu"
        assert strip_honorifics("Hon. James Faleke") == "james faleke"
        assert strip_honorifics("Prof. Wole Soyinka") == "wole soyinka"
    
    def test_normalize_name(self):
        assert normalize_name("Dr. Bola Ahmed Tinubu") == "bola ahmed tinubu"
        assert normalize_name("HIS EXCELLENCY BABAJIDE SANWO-OLU") == "babajide sanwo-olu"


class TestStateMatching:
    """Test state matching."""
    
    @pytest.mark.parametrize("input_text,expected", POSITIVE_STATE_PAIRS)
    def test_positive_state_matches(self, input_text, expected):
        result = match_state(input_text)
        assert result is not None, f"Failed to match '{input_text}'"
        assert result[0] == expected, f"Expected '{expected}', got '{result[0]}'"
        assert result[1] >= 0.7, f"Confidence too low: {result[1]}"
    
    def test_niger_is_not_nigeria(self):
        result = match_state("Niger")
        assert result is not None
        assert result[0] == "Niger"  # Should match Niger STATE, not Nigeria
        
    def test_fuzzy_state_match(self):
        result = match_state("Lagoss")  # Typo
        assert result is not None
        assert result[0] == "Lagos"


class TestPartyMatching:
    """Test political party matching."""
    
    @pytest.mark.parametrize("input_text,expected", POSITIVE_PARTY_PAIRS)
    def test_positive_party_matches(self, input_text, expected):
        result = match_party(input_text)
        assert result is not None, f"Failed to match '{input_text}'"
        assert result[1] == expected, f"Expected '{expected}', got '{result[1]}'"
    
    def test_apc_not_apga(self):
        result = match_party("APC")
        assert result is not None
        assert result[0] == "APC"
        assert "Grand Alliance" not in result[1]
    
    def test_pdp_not_prp(self):
        result = match_party("PDP")
        assert result is not None
        assert result[0] == "PDP"
        assert "Redemption" not in result[1]


class TestPoliticianMatching:
    """Test politician name matching."""
    
    def test_match_with_honorific_stripped(self):
        candidates = [
            {"name": "Bola Ahmed Tinubu", "id": 1},
            {"name": "Atiku Abubakar", "id": 2},
            {"name": "Peter Obi", "id": 3},
        ]
        
        results = match_politician_name("President Tinubu", candidates)
        assert len(results) > 0
        assert results[0][0]["name"] == "Bola Ahmed Tinubu"
    
    def test_match_partial_name(self):
        candidates = [
            {"name": "Babajide Sanwo-Olu", "id": 1},
            {"name": "Nyesom Wike", "id": 2},
        ]
        
        results = match_politician_name("Sanwo-Olu", candidates)
        assert len(results) > 0
        assert results[0][0]["name"] == "Babajide Sanwo-Olu"
    
    def test_match_full_name(self):
        candidates = [
            {"name": "Alex Otti", "id": 1},
            {"name": "Otti Alex", "id": 2},
            {"name": "Charles Otti", "id": 3},
        ]
        
        results = match_politician_name("Alex Otti", candidates)
        assert len(results) > 0
        assert results[0][0]["name"] == "Alex Otti"
        assert results[0][1] > 0.9


class TestNigerianMatcher:
    """Test the high-level NigerianMatcher API."""
    
    def test_match_state(self):
        matcher = NigerianMatcher()
        result = matcher.match_any("Lagos", entity_type="state")
        
        assert result["matched"] is True
        assert result["result"] == "Lagos"
        assert result["confidence"] == 1.0
    
    def test_match_party(self):
        matcher = NigerianMatcher()
        result = matcher.match_any("APC", entity_type="party")
        
        assert result["matched"] is True
        assert result["result"]["acronym"] == "APC"
        assert result["result"]["name"] == "All Progressives Congress"
    
    def test_disambiguation_needed(self):
        matcher = NigerianMatcher()
        result = matcher.match_any("Lagoos", entity_type="state")  # Typo
        
        assert result["matched"] is True
        assert result["result"] == "Lagos"
        assert result["confidence"] < 1.0
        # Should flag for disambiguation due to lower confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
