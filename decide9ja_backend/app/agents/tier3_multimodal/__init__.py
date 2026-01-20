"""
Tier 3: Multimodal Agents
=========================
Agents that handle non-text input/output modalities.

Includes:
- Voice transcription (Whisper)
- Voice synthesis (Eleven Labs)
- Image analysis (Claude Vision)
- Location processing (Nominatim)
"""

from app.agents.tier3_multimodal.voice_input import VoiceTranscriptionAgent
from app.agents.tier3_multimodal.image_analysis import ImageAnalysisAgent
from app.agents.tier3_multimodal.location import LocationProcessorAgent

__all__ = [
    "VoiceTranscriptionAgent",
    "ImageAnalysisAgent",
    "LocationProcessorAgent",
]
