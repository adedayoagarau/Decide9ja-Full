"""VoiceSynthesisAgent - Eleven Labs text-to-speech"""
from app.agents.tier5_output.voice_synthesis.agent import VoiceSynthesisAgent
from app.agents.tier5_output.voice_synthesis.prompt import SYSTEM_PROMPT

__all__ = ["VoiceSynthesisAgent", "SYSTEM_PROMPT"]
