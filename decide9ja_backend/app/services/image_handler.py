"""
Image Handler for Decide9ja.
Analyzes images using Claude Vision for:
- Politician identification
- Issue evidence (bad roads, floods)
- Document/form reading
"""
import os
import base64
import logging
import requests
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def is_configured() -> bool:
    """Check if image handler is configured."""
    return bool(ANTHROPIC_API_KEY)


async def download_image(url: str, auth: tuple = None) -> Optional[bytes]:
    """Download image from URL."""
    try:
        headers = {}
        if auth:
            import base64 as b64
            credentials = b64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return None


async def analyze_image(
    image_url: str,
    user_caption: str = "",
    analysis_type: str = "general"
) -> Dict:
    """
    Analyze image using Claude Vision.
    
    Args:
        image_url: URL to image file
        user_caption: Optional caption from user
        analysis_type: "politician", "issue", "document", or "general"
        
    Returns:
        Dict with analysis results, detected items, and suggested actions
    """
    if not ANTHROPIC_API_KEY:
        logger.error("Anthropic API key not configured")
        return {"error": "Image analysis not configured"}
    
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # Download image from Twilio
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        image_data = await download_image(image_url, auth=(twilio_sid, twilio_token))
        
        if not image_data:
            return {"error": "Failed to download image"}
        
        # Encode to base64
        image_b64 = base64.b64encode(image_data).decode("utf-8")
        
        # Determine media type
        media_type = "image/jpeg"  # Default
        if image_url.endswith(".png"):
            media_type = "image/png"
        elif image_url.endswith(".webp"):
            media_type = "image/webp"
        
        # Build analysis prompt based on type
        prompts = {
            "politician": """Analyze this image and:
1. If this shows a Nigerian politician, identify them (name, position, party).
2. If you recognize them, provide key facts.
3. If you don't recognize them or it's not a politician, say so.

Nigerian politicians to recognize: Tinubu, Obi, Atiku, Sanwo-Olu, Wike, El-Rufai, Fayemi, Akpabio, etc.
Party symbols: APC (broom), PDP (umbrella), LP (torch), NNPP (candle).

User caption: {caption}""",
            
            "issue": """Analyze this image for infrastructure or community issues:
1. What type of issue is shown? (road damage, flooding, power outage, waste, etc.)
2. Assess severity: minor, moderate, severe, critical
3. What authority should handle this? (Federal, State, LGA)
4. Describe the issue clearly for a report.

User caption: {caption}""",
            
            "document": """Analyze this document/form image:
1. What type of document is this?
2. Extract key information visible.
3. If it's a ballot or voter document, explain the options.
4. Summarize main content.

User caption: {caption}""",
            
            "general": """Analyze this image in the context of Nigerian politics/civics:
1. What does this image show?
2. Is there anything politically relevant?
3. If it's a person, do you recognize them?
4. If it's an issue (bad road, etc.), describe it.
5. Suggest how I can help the user based on this image.

User caption: {caption}"""
        }
        
        prompt = prompts.get(analysis_type, prompts["general"])
        prompt = prompt.format(caption=user_caption or "No caption provided")
        
        # Call Claude Vision
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )
        
        analysis = response.content[0].text
        
        # Detect what was found
        detected = detect_content_type(analysis)
        
        logger.info(f"Image analyzed: {detected['type']}")
        
        return {
            "analysis": analysis,
            "detected_type": detected["type"],
            "suggested_action": detected["action"],
            "confidence": detected.get("confidence", "medium"),
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return {"error": str(e)}


def detect_content_type(analysis: str) -> Dict:
    """Detect what type of content was found in the image."""
    analysis_lower = analysis.lower()
    
    # Politician detection
    politician_indicators = ["politician", "governor", "senator", "president", "minister", "apc", "pdp", "lp"]
    if any(ind in analysis_lower for ind in politician_indicators):
        return {
            "type": "politician",
            "action": "fetch_profile",
            "confidence": "high" if "recognize" in analysis_lower else "medium"
        }
    
    # Issue detection
    issue_indicators = ["road", "pothole", "flood", "damage", "broken", "issue", "problem", "waste"]
    if any(ind in analysis_lower for ind in issue_indicators):
        return {
            "type": "issue",
            "action": "start_report",
            "confidence": "high"
        }
    
    # Document detection
    doc_indicators = ["document", "form", "ballot", "paper", "official", "letter"]
    if any(ind in analysis_lower for ind in doc_indicators):
        return {
            "type": "document",
            "action": "summarize",
            "confidence": "medium"
        }
    
    return {
        "type": "general",
        "action": "respond",
        "confidence": "low"
    }


def analyze_sync(image_url: str, caption: str = "", analysis_type: str = "general") -> Dict:
    """Synchronous version for simpler use cases."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(analyze_image(image_url, caption, analysis_type))
    finally:
        loop.close()
