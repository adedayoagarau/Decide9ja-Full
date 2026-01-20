"""
LocationProcessorAgent Prompt
=============================
No LLM prompt needed - uses Nominatim API for geocoding.
"""

SYSTEM_PROMPT = """
Location Processor Agent - No LLM Required

This agent uses OpenStreetMap Nominatim API for reverse geocoding.
No system prompt is used for location processing.

Nigerian Administrative Structure:
- 36 States + FCT (Federal Capital Territory)
- 774 Local Government Areas (LGAs)
- Each LGA has multiple wards
"""

# Nigerian states for reference
NIGERIAN_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "Federal Capital Territory", "Gombe", "Imo", "Jigawa", "Kaduna",
    "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger",
    "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba",
    "Yobe", "Zamfara"
]

# No LLM configuration needed
MAX_TOKENS = 0
TEMPERATURE = 0.0
