"""
Tier 3: Multimodal Agents
=========================
Agents that handle non-text input/output modalities.

Includes:
- Voice transcription (Whisper)
- Image analysis
- Document processing
"""

from app.agents.tier3_multimodal.voice_input import VoiceTranscriptionAgent

__all__ = [
    "VoiceTranscriptionAgent",
]
