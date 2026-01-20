"""
VoiceTranscriptionAgent Prompt
==============================
This agent doesn't use LLM - it uses Whisper API directly.
This file exists for consistency with the agent structure.
"""

SYSTEM_PROMPT = """
Voice Transcription Agent - No LLM Required

This agent uses OpenAI Whisper API for speech-to-text conversion.
No system prompt is used for transcription.

Supported languages:
- English (en)
- Nigerian Pidgin (pcm)
- Yoruba (yo)
- Hausa (ha)
- Igbo (ig)
"""

# No LLM configuration needed
MAX_TOKENS = 0
TEMPERATURE = 0.0
