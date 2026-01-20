"""
ImageAnalysisAgent
==================
Analyzes images using Claude Vision API.

Cost: MEDIUM (Claude Sonnet vision call)

Features:
- Issue evidence detection (roads, water, electricity)
- OCR for documents/signs
- Entity extraction (politicians, locations)
- Nigerian context awareness

Usage:
    agent = ImageAnalysisAgent()
    output = await agent.handle(AgentInput(
        image_urls=["https://..."],
        raw_text="Caption if any"
    ))
    # output.data contains analysis results
"""

import os
import base64
import json
import time
import logging
import httpx
from typing import Optional, Dict, List
from datetime import datetime

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class ImageAnalysisAgent(BaseAgent):
    """Analyzes images using Claude Vision API"""

    name = "image_analysis"
    description = "Analyze images using Claude Vision"
    tier = AgentTier.MULTIMODAL
    cost_level = CostLevel.MEDIUM  # Vision API call

    # Image types we can detect
    IMAGE_TYPES = {
        "issue_evidence": "Photo showing infrastructure problem",
        "document": "Document, form, or official paper",
        "politician": "Photo of a politician or political event",
        "news": "Screenshot of news article",
        "general": "General photo",
    }

    # Issue categories for evidence detection
    ISSUE_CATEGORIES = [
        "road",           # Potholes, damaged roads
        "water",          # Water shortage, flooding, sewage
        "electricity",    # Power outage, damaged lines
        "waste",          # Garbage, sanitation
        "flooding",       # Flood damage
        "security",       # Security concerns
        "education",      # School infrastructure
        "health",         # Hospital/clinic issues
        "other",
    ]

    # Configuration
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 1024
    TIMEOUT_SECONDS = 60
    MAX_IMAGE_SIZE_MB = 10

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS)
        return self._http_client

    async def can_handle(self, input: AgentInput) -> bool:
        """Check if we have image content to analyze"""
        return bool(input.image_urls)

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Analyze image and return structured results"""
        self._call_count += 1
        start_time = time.time()

        if not input.image_urls:
            return self.fail("No image URL provided")

        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY not configured")
            return self.fail("Image analysis service not configured")

        try:
            # Use first image (WhatsApp typically sends one at a time)
            image_url = input.image_urls[0]
            caption = input.raw_text  # User's caption if any

            # Download image
            image_bytes, media_type = await self._download_image(image_url)

            if not image_bytes:
                return self.fail("Failed to download image")

            # Check size
            size_mb = len(image_bytes) / (1024 * 1024)
            if size_mb > self.MAX_IMAGE_SIZE_MB:
                return self.fail(f"Image too large ({size_mb:.1f}MB > {self.MAX_IMAGE_SIZE_MB}MB)")

            # Encode to base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # Analyze with Claude Vision
            analysis = await self._analyze_image(image_base64, media_type, caption)

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Analyzed image in %.0fms: type=%s, is_issue=%s",
                processing_time,
                analysis.get("type"),
                analysis.get("is_issue_evidence")
            )

            # Build response based on analysis type
            response_text = self._build_response_text(analysis, caption)

            return AgentOutput(
                success=True,
                response_text=response_text,
                data={
                    "image_type": analysis.get("type", "general"),
                    "description": analysis.get("description", ""),
                    "extracted_text": analysis.get("extracted_text"),
                    "entities": analysis.get("entities", []),
                    "is_issue_evidence": analysis.get("is_issue_evidence", False),
                    "issue_category": analysis.get("issue_category"),
                    "issue_severity": analysis.get("issue_severity"),
                    "location_hints": analysis.get("location_hints", []),
                    "processing_time_ms": processing_time,
                    "original_image_url": image_url,
                },
                cost_level=CostLevel.MEDIUM,
                analytics_tags={
                    "modality": "image_input",
                    "image_type": analysis.get("type", "general"),
                    "is_issue": analysis.get("is_issue_evidence", False),
                }
            )

        except httpx.TimeoutException:
            logger.error("Image analysis timeout")
            return self.fail("Image analysis timed out. Please try again.")

        except Exception as e:
            logger.exception("Image analysis failed: %s", e)
            return self.fail(f"Image analysis failed: {str(e)}")

    async def _download_image(self, url: str) -> tuple:
        """Download image from URL"""
        client = await self._get_client()

        try:
            # Handle WhatsApp media URLs
            headers = {}
            if "graph.facebook.com" in url or "whatsapp" in url.lower():
                whatsapp_token = os.getenv("WHATSAPP_TOKEN")
                if whatsapp_token:
                    headers["Authorization"] = f"Bearer {whatsapp_token}"

            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "image/jpeg")

            # Map content type to media type
            media_type_map = {
                "image/jpeg": "image/jpeg",
                "image/jpg": "image/jpeg",
                "image/png": "image/png",
                "image/gif": "image/gif",
                "image/webp": "image/webp",
            }
            media_type = media_type_map.get(content_type, "image/jpeg")

            return response.content, media_type

        except Exception as e:
            logger.error("Failed to download image from %s: %s", url, e)
            return None, ""

    async def _analyze_image(
        self,
        image_base64: str,
        media_type: str,
        caption: Optional[str]
    ) -> Dict:
        """Analyze image using Claude Vision API"""
        client = await self._get_client()

        # Build analysis prompt
        prompt = self._build_analysis_prompt(caption)

        # Build message with image
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_base64
                }
            },
            {
                "type": "text",
                "text": prompt
            }
        ]

        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": self.MODEL,
                "max_tokens": self.MAX_TOKENS,
                "messages": [{"role": "user", "content": content}]
            }
        )

        if response.status_code != 200:
            logger.error("Claude Vision API error: %s %s", response.status_code, response.text[:200])
            raise Exception(f"Vision API error: {response.status_code}")

        result = response.json()
        response_text = result["content"][0]["text"]

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            return json.loads(json_str.strip())
        except json.JSONDecodeError:
            # Fallback: return basic analysis
            logger.warning("Failed to parse vision response as JSON")
            return {
                "type": "general",
                "description": response_text[:200],
                "is_issue_evidence": False,
            }

    def _build_analysis_prompt(self, caption: Optional[str]) -> str:
        """Build the analysis prompt for Claude Vision"""
        prompt = """Analyze this image in the context of Nigerian civic engagement. Return a JSON object with:

{
    "type": "issue_evidence|document|politician|news|general",
    "description": "Brief description of what's in the image (1-2 sentences)",
    "extracted_text": "Any text visible in the image (OCR). Null if none.",
    "entities": [
        {"type": "person|place|organization|politician", "name": "..."}
    ],
    "is_issue_evidence": true/false,
    "issue_category": "road|water|electricity|waste|flooding|security|education|health|other",
    "issue_severity": "low|medium|high|critical",
    "location_hints": ["Any location indicators visible in the image"]
}

Rules:
- is_issue_evidence = true if this shows infrastructure problems (bad roads, flooding, power lines down, etc.)
- For politicians, try to identify if recognizable
- Extract Nigerian location hints (street signs, landmarks, state names)
- issue_severity: critical=life-threatening, high=major disruption, medium=moderate, low=minor inconvenience

Return ONLY the JSON object, no other text."""

        if caption:
            prompt += f"\n\nUser's caption: \"{caption}\""

        return prompt

    def _build_response_text(self, analysis: Dict, caption: Optional[str]) -> str:
        """Build human-readable response text from analysis"""
        image_type = analysis.get("type", "general")
        description = analysis.get("description", "image")

        if analysis.get("is_issue_evidence"):
            category = analysis.get("issue_category", "issue")
            severity = analysis.get("issue_severity", "unknown")

            return (
                f"I can see this appears to be evidence of a {category} issue "
                f"(severity: {severity}). {description}\n\n"
                "Would you like to file an issue report? I can help document this."
            )

        elif image_type == "document":
            extracted = analysis.get("extracted_text", "")
            if extracted:
                return f"I see a document. Here's what I can read:\n\n{extracted[:500]}"
            return f"I see a document: {description}"

        elif image_type == "politician":
            entities = analysis.get("entities", [])
            politicians = [e["name"] for e in entities if e.get("type") == "politician"]
            if politicians:
                return f"I recognize this shows: {', '.join(politicians)}. {description}"
            return f"This appears to be a political photo. {description}"

        else:
            return f"Thanks for sharing this image. {description}"

    async def cleanup(self):
        """Cleanup HTTP client"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
