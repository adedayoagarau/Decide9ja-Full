"""
VoiceSynthesisAgent Prompt
==========================
This agent doesn't use LLM - it uses Eleven Labs API directly.
This file exists for consistency with the agent structure.
"""

SYSTEM_PROMPT = """
Voice Synthesis Agent - No LLM Required

This agent uses Eleven Labs API for text-to-speech conversion.
No system prompt is used for synthesis.

Voice characteristics:
- Clear, professional Nigerian English accent
- Natural pacing with appropriate pauses
- Warm, helpful tone suitable for civic engagement
"""

# No LLM configuration needed
MAX_TOKENS = 0
TEMPERATURE = 0.0
