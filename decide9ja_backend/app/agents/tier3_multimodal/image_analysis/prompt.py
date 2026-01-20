"""
ImageAnalysisAgent Prompt
=========================
Vision prompt for analyzing images in Nigerian civic context.
"""

SYSTEM_PROMPT = """
You are analyzing images for Decide9ja, a Nigerian civic engagement platform.

Focus on:
1. Infrastructure issues (roads, water, electricity, waste)
2. Political content (politicians, events, campaigns)
3. Documents (official papers, IDs, forms)
4. Location identification (Nigerian states, LGAs, landmarks)

Be concise and factual. For issue evidence, assess severity accurately.
"""

# Analysis categories
IMAGE_TYPES = ["issue_evidence", "document", "politician", "news", "general"]
ISSUE_CATEGORIES = ["road", "water", "electricity", "waste", "flooding", "security", "education", "health", "other"]
SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

MAX_TOKENS = 1024
TEMPERATURE = 0.3  # Low temperature for consistent analysis
