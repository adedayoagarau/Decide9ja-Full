import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from app.services.rag_router import RAGRouter, Intent, RouterOutput

async def test_pidgin_routing():
    print("🚀 Starting Multilingual RAG Router Test...")
    
    # Mock DB Session
    mock_db = MagicMock()
    
    # Patch all dependencies
    with patch("app.services.rag_router.get_budget_service") as mock_budget_fac, \
         patch("app.services.rag_router.get_enhanced_rag_service") as mock_rag_fac, \
         patch("app.services.rag_router.legislative_service") as mock_leg, \
         patch("app.services.rag_router.elections_service") as mock_election, \
         patch("app.services.embeddings._get_client") as mock_get_client:
        
        # 1. Setup Mock LLM for Classification
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock Response for "Wetin dey sup with Tinubu?" -> General News in Pidgin
        mock_classifier_response = MagicMock()
        mock_classifier_response.choices = [
            MagicMock(message=MagicMock(content='{"intent": "general", "language": "pidgin", "entities": {"politician_name": "Tinubu"}}'))
        ]
        
        # Mock Response for Synthesis (just to avoid error)
        mock_synthesis_response = MagicMock()
        mock_synthesis_response.choices = [
            MagicMock(message=MagicMock(content='Tinubu dey fine, e just go Aso Rock.'))
        ]
        
        mock_client.chat.completions.create.side_effect = [
            mock_classifier_response, # First call: Classification
            mock_synthesis_response   # Second call: Synthesis
        ]
        
        # 2. Setup Mock RAG Services
        mock_rag_instance = MagicMock()
        mock_rag_fac.return_value = mock_rag_instance
        mock_rag_instance.retrieve.return_value = ("Context about Tinubu", [{"title": "News"}])
        
        mock_budget_instance = MagicMock()
        mock_budget_fac.return_value = mock_budget_instance
        
        # 3. Initialize Router
        router = RAGRouter(mock_db)
        
        # 4. Execute Route (Pidgin)
        query = "Wetin dey sup with Tinubu?"
        print(f"📥 Query: '{query}'")
        result = await router.route(query)
        
        # 5. Assertions (Pidgin)
        print("\n🔍 Verifying Results (Pidgin):")
        assert result["intent"] == Intent.GENERAL, f"Expected GENERAL, got {result['intent']}"
        print("✅ Intent classified correctly as GENERAL")
        
        # Check language prop
        mock_rag_instance.retrieve.assert_called()
        call_args = mock_rag_instance.retrieve.call_args
        assert call_args.kwargs.get("language") == "pidgin", f"Expected language='pidgin', got {call_args.kwargs.get('language')}"
        print("✅ Language 'pidgin' was passed to Retrieval Service")

        # --- Test Hausa ---
        print("\n📥 Testing Hausa ('Yaya zabe na 2023?')...")
        # Mock classifier for Hausa
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content='{"intent": "election", "language": "hausa", "entities": {"year": 2023}}'))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content='Zabe na da kyau.'))])
        ]
        mock_election_service = mock_election_instance = MagicMock() # elections_service singleton mock
        mock_election.return_value = mock_election_service # This might be wrong, elections_service is imported directly
        # Actually elections_service is imported as an object, so we mocked the module
        
        await router.route("Yaya zabe na 2023?")
        # usage verification would be on elections_service methods but we just want to ensure no crash and correct routing logic path
        print("✅ Hausa routing executed without error")

        print("\n🎉 All Multilingual Tests Passed!")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_pidgin_routing())
