# DECIDE9JA MULTIMODAL RAG SYSTEM
# Handles text, voice, images, documents, and location

"""
Architecture:

┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   WhatsApp   │────▶│  Modal Router   │────▶│  Unified Context │
│   Message    │     │                 │     │    Assembler     │
└──────────────┘     └─────────────────┘     └──────────────────┘
                              │                       │
         ┌────────────────────┼────────────────────┐  │
         │          │         │         │          │  │
         ▼          ▼         ▼         ▼          ▼  │
    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
    │  Text  │ │ Voice  │ │ Image  │ │  Doc   │ │Location│
    │Handler │ │Handler │ │Handler │ │Handler │ │Handler │
    └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
         │          │         │         │          │
         │     Whisper   Vision AI   OCR/PDF    Geocode
         │          │         │         │          │
         └──────────┴─────────┴─────────┴──────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │    RAG + LLM     │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │    Response      │
                    │  (Text or Voice) │
                    └──────────────────┘
"""

import os
import base64
import hashlib
import logging
from typing import Optional, Dict, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class ModalityType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    DOCUMENT = "document"
    LOCATION = "location"

@dataclass
class MultimodalInput:
    """Unified input structure for all modalities."""
    modality: ModalityType
    
    # Text content (original or transcribed)
    text: Optional[str] = None
    
    # Media content
    media_url: Optional[str] = None
    media_bytes: Optional[bytes] = None
    media_type: Optional[str] = None  # image/jpeg, audio/ogg, application/pdf
    
    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Metadata
    caption: Optional[str] = None
    duration: Optional[int] = None  # For voice notes (seconds)
    
    # Processing results
    transcription: Optional[str] = None
    image_description: Optional[str] = None
    extracted_text: Optional[str] = None
    detected_entities: Optional[List[str]] = None

@dataclass
class MultimodalContext:
    """Context assembled from multimodal input."""
    original_modality: ModalityType
    processed_query: str  # The query to send to RAG
    additional_context: str  # Extra context from image/voice/doc analysis
    entities_detected: List[str]
    suggested_intent: Optional[str]
    raw_input: MultimodalInput


# =============================================================================
# VOICE HANDLER (Whisper API)
# =============================================================================

class VoiceHandler:
    """
    Handles voice notes using OpenAI Whisper API.
    
    Nigerian considerations:
    - Support Nigerian English accent
    - Handle Pidgin transcription
    - Handle code-switching (English + Yoruba/Igbo/Hausa)
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_url = "https://api.openai.com/v1/audio/transcriptions"
    
    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> Dict:
        """
        Transcribe voice note to text.
        
        Args:
            audio_bytes: Audio file bytes (ogg, mp3, wav, etc.)
            language: Language hint (en, pcm for Pidgin, ha, yo, ig)
        
        Returns:
            {
                "text": "transcribed text",
                "language": "detected language",
                "confidence": 0.95
            }
        """
        if not self.api_key:
            return {"error": "OpenAI API key not configured"}
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            files = {
                "file": ("audio.ogg", BytesIO(audio_bytes), "audio/ogg"),
                "model": (None, "whisper-1"),
                "language": (None, language if language != "pcm" else "en"),
                "prompt": (None, self._get_nigerian_prompt())
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                files=files
            )
            response.raise_for_status()
            
            result = response.json()
            transcribed_text = result.get("text", "")
            
            # Detect if Pidgin
            detected_lang = self._detect_pidgin(transcribed_text)
            
            return {
                "text": transcribed_text,
                "language": detected_lang,
                "confidence": 0.9  # Whisper doesn't return confidence
            }
            
        except Exception as e:
            logger.error(f"Voice transcription error: {e}")
            return {"error": str(e)}
    
    def _get_nigerian_prompt(self) -> str:
        """Prompt to help Whisper with Nigerian context."""
        return """
        Nigerian English transcription. Common terms:
        INEC, PVC, APC, PDP, LP, NNPP, Naira, LGA, 
        Tinubu, Obi, Atiku, Sanwo-Olu, governor, senator,
        wahala, no wahala, wetin, abeg, oya, na so
        """
    
    def _detect_pidgin(self, text: str) -> str:
        """Detect if transcribed text is Pidgin."""
        pidgin_markers = [
            "wetin", "dey", "no be", "wahala", "abeg", 
            "oya", "na", "e don", "shey", "dem"
        ]
        text_lower = text.lower()
        pidgin_count = sum(1 for marker in pidgin_markers if marker in text_lower)
        
        if pidgin_count >= 2:
            return "pcm"  # Pidgin
        return "en"


# =============================================================================
# IMAGE HANDLER (Vision AI)
# =============================================================================

class ImageHandler:
    """
    Handles image analysis using vision models.
    
    Capabilities:
    1. Politician recognition
    2. Document/form analysis
    3. Issue evidence analysis (bad roads, etc.)
    4. General image description
    """
    
    def __init__(self):
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Nigerian politician image database (for recognition)
        self.politician_embeddings = {}  # Would be loaded from file
    
    async def analyze(
        self, 
        image_bytes: bytes, 
        context: str = "",
        analysis_type: str = "auto"
    ) -> Dict:
        """
        Analyze an image.
        
        Args:
            image_bytes: Image file bytes
            context: Any caption or context provided
            analysis_type: "politician", "document", "issue", "auto"
        
        Returns:
            {
                "description": "detailed description",
                "type": "politician|document|issue|general",
                "entities": ["Tinubu", "APC"],
                "extracted_text": "any text in image",
                "issue_category": "road|water|electricity|etc",
                "confidence": 0.85
            }
        """
        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Use Claude Vision (preferred) or GPT-4V
        if self.anthropic_api_key:
            return await self._analyze_with_claude(image_base64, context, analysis_type)
        elif self.openai_api_key:
            return await self._analyze_with_gpt4v(image_base64, context, analysis_type)
        else:
            return {"error": "No vision API configured"}
    
    async def _analyze_with_claude(
        self, 
        image_base64: str, 
        context: str,
        analysis_type: str
    ) -> Dict:
        """Analyze image using Claude Vision."""
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        
        # Build prompt based on analysis type
        prompt = self._build_vision_prompt(analysis_type, context)
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            result_text = response.content[0].text
            return self._parse_vision_response(result_text, analysis_type)
            
        except Exception as e:
            logger.error(f"Claude Vision error: {e}")
            return {"error": str(e)}
    
    async def _analyze_with_gpt4v(
        self, 
        image_base64: str, 
        context: str,
        analysis_type: str
    ) -> Dict:
        """Analyze image using GPT-4 Vision."""
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = self._build_vision_prompt(analysis_type, context)
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1024
        }
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result_text = response.json()["choices"][0]["message"]["content"]
            return self._parse_vision_response(result_text, analysis_type)
            
        except Exception as e:
            logger.error(f"GPT-4V error: {e}")
            return {"error": str(e)}
    
    def _build_vision_prompt(self, analysis_type: str, context: str) -> str:
        """Build prompt for vision analysis."""
        
        base_prompt = """You are analyzing an image for Decide9ja, a Nigerian civic information assistant.

Context from user: {context}

Analyze this image and respond in JSON format:
{{
    "type": "politician|document|issue|general",
    "description": "brief description of what you see",
    "entities": ["list", "of", "named", "entities"],
    "extracted_text": "any text visible in the image",
    "confidence": 0.0-1.0
}}
"""
        
        if analysis_type == "politician":
            base_prompt += """
Focus on identifying Nigerian politicians. Look for:
- Face recognition (if known politician)
- Party symbols (APC broom, PDP umbrella, LP logo)
- Campaign materials
- Official settings (National Assembly, Government House)

Add to JSON:
"politician_name": "name if recognized",
"party": "party if identifiable",
"position": "any official position visible"
"""
        
        elif analysis_type == "document":
            base_prompt += """
Focus on extracting text from the document. This could be:
- Ballot paper
- Government form
- Political manifesto
- Official letter
- Budget document

Add to JSON:
"document_type": "type of document",
"key_information": ["important", "extracted", "points"]
"""
        
        elif analysis_type == "issue":
            base_prompt += """
This is likely a civic issue being reported. Analyze for:
- Type of issue (bad road, flooding, waste, broken infrastructure)
- Severity (minor, moderate, severe)
- Location clues (street signs, landmarks)
- Evidence quality (clear photo, usable for report)

Add to JSON:
"issue_type": "road|flooding|waste|electricity|water|other",
"severity": "minor|moderate|severe",
"location_clues": ["any", "visible", "location", "hints"],
"evidence_quality": "poor|fair|good|excellent"
"""
        
        return base_prompt.format(context=context or "None provided")
    
    def _parse_vision_response(self, response_text: str, analysis_type: str) -> Dict:
        """Parse vision model response into structured data."""
        import json
        
        try:
            # Try to extract JSON from response
            # Sometimes models wrap JSON in markdown code blocks
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text
            
            result = json.loads(json_str.strip())
            return result
            
        except json.JSONDecodeError:
            # Fallback: return raw description
            return {
                "type": analysis_type if analysis_type != "auto" else "general",
                "description": response_text,
                "entities": [],
                "extracted_text": "",
                "confidence": 0.5
            }


# =============================================================================
# DOCUMENT HANDLER (PDF/OCR)
# =============================================================================

class DocumentHandler:
    """
    Handles document analysis (PDFs, images of documents).
    
    Use cases:
    - Party manifestos
    - Budget documents
    - Bills and legislation
    - Official forms
    """
    
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    async def extract_and_analyze(
        self, 
        doc_bytes: bytes, 
        doc_type: str = "application/pdf",
        query: Optional[str] = None
    ) -> Dict:
        """
        Extract text from document and optionally answer questions about it.
        
        Args:
            doc_bytes: Document file bytes
            doc_type: MIME type
            query: Optional question to answer about the document
        
        Returns:
            {
                "extracted_text": "full text",
                "summary": "brief summary",
                "key_points": ["point 1", "point 2"],
                "answer": "answer to query if provided",
                "document_type": "manifesto|budget|bill|form|other"
            }
        """
        
        # For PDFs, use a PDF extraction library
        if doc_type == "application/pdf":
            extracted_text = await self._extract_pdf_text(doc_bytes)
        else:
            # For images, use OCR via vision model
            image_handler = ImageHandler()
            result = await image_handler.analyze(doc_bytes, analysis_type="document")
            extracted_text = result.get("extracted_text", "")
        
        if not extracted_text:
            return {"error": "Could not extract text from document"}
        
        # Analyze the extracted text
        return await self._analyze_document_text(extracted_text, query)
    
    async def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF."""
        try:
            import pypdf
            
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            text_parts = []
            
            for page in reader.pages:
                text_parts.append(page.extract_text())
            
            return "\n\n".join(text_parts)
            
        except ImportError:
            logger.warning("pypdf not installed, using fallback")
            return ""
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""
    
    async def _analyze_document_text(self, text: str, query: Optional[str]) -> Dict:
        """Analyze extracted document text using LLM."""
        import anthropic
        
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        prompt = f"""Analyze this Nigerian political/civic document:

DOCUMENT TEXT:
{text[:10000]}  # Limit to ~10k chars

Provide analysis in JSON format:
{{
    "document_type": "manifesto|budget|bill|policy|form|letter|other",
    "summary": "2-3 sentence summary",
    "key_points": ["up to 5 key points"],
    "entities_mentioned": ["politicians", "parties", "places mentioned"],
    "relevance": "why this matters to Nigerian citizens"
}}
"""
        
        if query:
            prompt += f"""

Also answer this specific question about the document:
Question: {query}

Add to JSON:
"answer": "direct answer to the question"
"""
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text
            
            # Parse JSON response
            import json
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0]
            else:
                json_str = result_text
            
            result = json.loads(json_str.strip())
            result["extracted_text"] = text[:2000] + "..." if len(text) > 2000 else text
            return result
            
        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            return {
                "extracted_text": text[:2000],
                "summary": "Could not generate summary",
                "error": str(e)
            }


# =============================================================================
# LOCATION HANDLER
# =============================================================================

class LocationHandler:
    """
    Handles location data - reverse geocoding and representative lookup.
    (Already exists in your codebase, this is an enhanced version)
    """
    
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    
    async def process_location(self, lat: float, lng: float) -> Dict:
        """
        Process a location pin.
        
        Returns:
            {
                "state": "Lagos",
                "lga": "Alimosho",
                "address": "123 Somewhere Street, Ikeja",
                "senatorial_district": "Lagos West",
                "federal_constituency": "Alimosho Federal",
                "representatives": {
                    "senator": "...",
                    "house_rep": "...",
                    "governor": "..."
                }
            }
        """
        # Reverse geocode
        location_data = await self._reverse_geocode(lat, lng)
        
        if location_data.get("error"):
            return location_data
        
        # Lookup representatives based on location
        representatives = await self._lookup_representatives(
            location_data.get("state"),
            location_data.get("lga")
        )
        
        location_data["representatives"] = representatives
        return location_data
    
    async def _reverse_geocode(self, lat: float, lng: float) -> Dict:
        """Convert coordinates to address using Google Maps API."""
        if not self.google_api_key:
            return {"error": "Google Maps API not configured"}
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "latlng": f"{lat},{lng}",
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data["status"] != "OK":
                return {"error": f"Geocoding failed: {data['status']}"}
            
            # Parse Nigerian address components
            result = {
                "latitude": lat,
                "longitude": lng,
                "formatted_address": data["results"][0]["formatted_address"]
            }
            
            for component in data["results"][0]["address_components"]:
                types = component["types"]
                
                if "administrative_area_level_1" in types:
                    result["state"] = component["long_name"].replace(" State", "")
                elif "administrative_area_level_2" in types:
                    result["lga"] = component["long_name"]
                elif "locality" in types:
                    result["city"] = component["long_name"]
                elif "route" in types:
                    result["street"] = component["long_name"]
            
            return result
            
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return {"error": str(e)}
    
    async def _lookup_representatives(self, state: str, lga: str) -> Dict:
        """Look up representatives for a location."""
        # This would query your database
        # Placeholder implementation
        return {
            "governor": f"Governor of {state}",
            "senator": f"Senator for {state}",
            "house_rep": f"Rep for {lga} constituency"
        }


# =============================================================================
# MULTIMODAL ROUTER
# =============================================================================

class MultimodalRouter:
    """
    Routes incoming messages to appropriate handlers and assembles unified context.
    """
    
    def __init__(self):
        self.voice_handler = VoiceHandler()
        self.image_handler = ImageHandler()
        self.document_handler = DocumentHandler()
        self.location_handler = LocationHandler()
    
    async def process(self, message: Dict) -> MultimodalContext:
        """
        Process any type of WhatsApp message into unified context.
        
        Args:
            message: Parsed WhatsApp message with type, content, etc.
        
        Returns:
            MultimodalContext ready for RAG + LLM
        """
        msg_type = message.get("type", "text")
        
        # Build MultimodalInput
        mm_input = MultimodalInput(
            modality=ModalityType(msg_type) if msg_type in [e.value for e in ModalityType] else ModalityType.TEXT
        )
        
        # Route to appropriate handler
        if msg_type == "text":
            return await self._process_text(message, mm_input)
        
        elif msg_type == "voice" or msg_type == "audio":
            return await self._process_voice(message, mm_input)
        
        elif msg_type == "image":
            return await self._process_image(message, mm_input)
        
        elif msg_type == "document":
            return await self._process_document(message, mm_input)
        
        elif msg_type == "location":
            return await self._process_location(message, mm_input)
        
        else:
            # Fallback to text
            return await self._process_text(message, mm_input)
    
    async def _process_text(self, message: Dict, mm_input: MultimodalInput) -> MultimodalContext:
        """Process text message."""
        text = message.get("text", "")
        mm_input.text = text
        
        return MultimodalContext(
            original_modality=ModalityType.TEXT,
            processed_query=text,
            additional_context="",
            entities_detected=self._extract_entities(text),
            suggested_intent=self._detect_intent(text),
            raw_input=mm_input
        )
    
    async def _process_voice(self, message: Dict, mm_input: MultimodalInput) -> MultimodalContext:
        """Process voice message."""
        # Download audio from WhatsApp
        audio_url = message.get("audio_url") or message.get("voice", {}).get("url")
        audio_bytes = await self._download_media(audio_url)
        
        if not audio_bytes:
            return self._error_context("Could not download voice message", mm_input)
        
        mm_input.media_bytes = audio_bytes
        mm_input.duration = message.get("voice", {}).get("duration")
        
        # Transcribe
        transcription_result = await self.voice_handler.transcribe(audio_bytes)
        
        if transcription_result.get("error"):
            return self._error_context(f"Could not transcribe: {transcription_result['error']}", mm_input)
        
        transcribed_text = transcription_result["text"]
        mm_input.transcription = transcribed_text
        mm_input.text = transcribed_text
        
        return MultimodalContext(
            original_modality=ModalityType.VOICE,
            processed_query=transcribed_text,
            additional_context=f"[Transcribed from voice note, {mm_input.duration}s, detected language: {transcription_result.get('language', 'en')}]",
            entities_detected=self._extract_entities(transcribed_text),
            suggested_intent=self._detect_intent(transcribed_text),
            raw_input=mm_input
        )
    
    async def _process_image(self, message: Dict, mm_input: MultimodalInput) -> MultimodalContext:
        """Process image message."""
        # Download image
        image_url = message.get("image_url") or message.get("image", {}).get("url")
        image_bytes = await self._download_media(image_url)
        
        if not image_bytes:
            return self._error_context("Could not download image", mm_input)
        
        mm_input.media_bytes = image_bytes
        mm_input.caption = message.get("caption", "")
        
        # Analyze image
        analysis_result = await self.image_handler.analyze(
            image_bytes,
            context=mm_input.caption,
            analysis_type="auto"
        )
        
        if analysis_result.get("error"):
            return self._error_context(f"Could not analyze image: {analysis_result['error']}", mm_input)
        
        mm_input.image_description = analysis_result.get("description", "")
        mm_input.extracted_text = analysis_result.get("extracted_text", "")
        mm_input.detected_entities = analysis_result.get("entities", [])
        
        # Build query from caption + image analysis
        query_parts = []
        if mm_input.caption:
            query_parts.append(mm_input.caption)
        if analysis_result.get("type") == "politician":
            query_parts.append(f"Tell me about {analysis_result.get('politician_name', 'this politician')}")
        elif analysis_result.get("type") == "issue":
            query_parts.append(f"Help me report this {analysis_result.get('issue_type', 'issue')}")
        else:
            query_parts.append(mm_input.image_description)
        
        processed_query = " ".join(query_parts) if query_parts else "What is this image about?"
        
        return MultimodalContext(
            original_modality=ModalityType.IMAGE,
            processed_query=processed_query,
            additional_context=f"""[Image Analysis]
Type: {analysis_result.get('type', 'unknown')}
Description: {analysis_result.get('description', 'N/A')}
Text in image: {analysis_result.get('extracted_text', 'None')}
Entities: {', '.join(analysis_result.get('entities', []))}""",
            entities_detected=analysis_result.get("entities", []),
            suggested_intent=self._intent_from_image_type(analysis_result.get("type")),
            raw_input=mm_input
        )
    
    async def _process_document(self, message: Dict, mm_input: MultimodalInput) -> MultimodalContext:
        """Process document message."""
        doc_url = message.get("document_url") or message.get("document", {}).get("url")
        doc_bytes = await self._download_media(doc_url)
        
        if not doc_bytes:
            return self._error_context("Could not download document", mm_input)
        
        mm_input.media_bytes = doc_bytes
        mm_input.media_type = message.get("document", {}).get("mime_type", "application/pdf")
        mm_input.caption = message.get("caption", "")
        
        # Extract and analyze document
        analysis_result = await self.document_handler.extract_and_analyze(
            doc_bytes,
            doc_type=mm_input.media_type,
            query=mm_input.caption if mm_input.caption else None
        )
        
        if analysis_result.get("error"):
            return self._error_context(f"Could not analyze document: {analysis_result['error']}", mm_input)
        
        mm_input.extracted_text = analysis_result.get("extracted_text", "")
        
        processed_query = mm_input.caption or f"Summarize this {analysis_result.get('document_type', 'document')}"
        
        return MultimodalContext(
            original_modality=ModalityType.DOCUMENT,
            processed_query=processed_query,
            additional_context=f"""[Document Analysis]
Type: {analysis_result.get('document_type', 'unknown')}
Summary: {analysis_result.get('summary', 'N/A')}
Key Points:
{chr(10).join('• ' + p for p in analysis_result.get('key_points', []))}""",
            entities_detected=analysis_result.get("entities_mentioned", []),
            suggested_intent="document_analysis",
            raw_input=mm_input
        )
    
    async def _process_location(self, message: Dict, mm_input: MultimodalInput) -> MultimodalContext:
        """Process location message."""
        location = message.get("location", {})
        lat = location.get("latitude") or location.get("lat")
        lng = location.get("longitude") or location.get("lng")
        
        if not lat or not lng:
            return self._error_context("Invalid location data", mm_input)
        
        mm_input.latitude = lat
        mm_input.longitude = lng
        
        # Process location
        location_result = await self.location_handler.process_location(lat, lng)
        
        if location_result.get("error"):
            return self._error_context(f"Could not process location: {location_result['error']}", mm_input)
        
        processed_query = f"Show me my representatives in {location_result.get('lga', 'my area')}, {location_result.get('state', 'my state')}"
        
        return MultimodalContext(
            original_modality=ModalityType.LOCATION,
            processed_query=processed_query,
            additional_context=f"""[Location Data]
State: {location_result.get('state', 'Unknown')}
LGA: {location_result.get('lga', 'Unknown')}
Address: {location_result.get('formatted_address', 'Unknown')}
Representatives: {location_result.get('representatives', {})}""",
            entities_detected=[location_result.get('state'), location_result.get('lga')],
            suggested_intent="representative_lookup",
            raw_input=mm_input
        )
    
    async def _download_media(self, url: str) -> Optional[bytes]:
        """Download media from URL."""
        if not url:
            return None
        
        try:
            # For Twilio, media URLs require authentication
            twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
            twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if twilio_sid and twilio_token and "twilio.com" in url:
                response = requests.get(url, auth=(twilio_sid, twilio_token))
            else:
                response = requests.get(url)
            
            response.raise_for_status()
            return response.content
            
        except Exception as e:
            logger.error(f"Media download error: {e}")
            return None
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text."""
        # Simple keyword-based extraction
        # Would be enhanced with NER model
        entities = []
        
        # Nigerian politicians
        politicians = [
            "Tinubu", "Obi", "Atiku", "Sanwo-Olu", "Buhari",
            "Osinbajo", "Shettima", "Wike", "Fayemi"
        ]
        for p in politicians:
            if p.lower() in text.lower():
                entities.append(p)
        
        # Parties
        parties = ["APC", "PDP", "LP", "Labour Party", "NNPP"]
        for party in parties:
            if party.lower() in text.lower():
                entities.append(party)
        
        return entities
    
    def _detect_intent(self, text: str) -> Optional[str]:
        """Detect intent from text."""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ["who is my", "my senator", "my governor", "my rep"]):
            return "representative_lookup"
        if any(kw in text_lower for kw in ["report", "bad road", "problem", "issue", "complain"]):
            return "issue_reporting"
        if any(kw in text_lower for kw in ["vote", "election", "polling", "pvc"]):
            return "election_info"
        if any(kw in text_lower for kw in ["promise", "track", "did he", "has she"]):
            return "promise_tracking"
        
        return "general_inquiry"
    
    def _intent_from_image_type(self, image_type: str) -> Optional[str]:
        """Map image type to intent."""
        mapping = {
            "politician": "politician_info",
            "document": "document_analysis",
            "issue": "issue_reporting",
            "general": "general_inquiry"
        }
        return mapping.get(image_type, "general_inquiry")
    
    def _error_context(self, error_message: str, mm_input: MultimodalInput) -> MultimodalContext:
        """Create error context."""
        return MultimodalContext(
            original_modality=mm_input.modality,
            processed_query=error_message,
            additional_context=f"[ERROR: {error_message}]",
            entities_detected=[],
            suggested_intent=None,
            raw_input=mm_input
        )


# =============================================================================
# INTEGRATION WITH MESSAGE HANDLER
# =============================================================================

async def process_multimodal_message(message: Dict) -> str:
    """
    Main entry point for processing any WhatsApp message.
    
    This replaces the single-modality handler.
    """
    router = MultimodalRouter()
    
    # 1. Process through multimodal router
    context = await router.process(message)
    
    # 2. Get RAG results using processed query
    from app.services.rag import RAGService
    from app.database import SessionLocal
    
    db = SessionLocal()
    rag = RAGService(db)
    rag_results, sources = rag.retrieve(context.processed_query, top_k=5)
    db.close()
    
    # 3. Check if web search needed
    web_results = ""
    if _needs_web_search(context.processed_query):
        from app.services.web_search import search
        web_results = search(context.processed_query)
    
    # 4. Build combined context for LLM
    full_context = f"""
=== MULTIMODAL INPUT ===
Original format: {context.original_modality.value}
Processed query: {context.processed_query}

{context.additional_context}

=== DATABASE RESULTS ===
{rag_results}

=== WEB SEARCH ===
{web_results if web_results else "Not performed"}
"""
    
    # 5. Generate response
    from app.services.llm import generate_response_sync
    
    response = generate_response_sync(
        user_message=context.processed_query,
        context=full_context
    )
    
    # 6. Format for WhatsApp
    from app.services.whatsapp import format_for_whatsapp
    return format_for_whatsapp(response)


def _needs_web_search(query: str) -> bool:
    """Check if query needs real-time web search."""
    keywords = ["today", "latest", "recent", "news", "current", "2024", "2025", "now", "just"]
    return any(kw in query.lower() for kw in keywords)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

"""
# In your webhook handler:

@router.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    # Parse Twilio message (includes type detection)
    message = parse_twilio_message(await request.form())
    
    # Process through multimodal system
    response = await process_multimodal_message(message)
    
    # Send response
    send_whatsapp_message(message["from"], response)
    
    return {"status": "ok"}


# The system automatically handles:

# TEXT:
# User: "Who is my senator?"
# → Direct to RAG + LLM

# VOICE:
# User: [30-second voice note asking about Tinubu]
# → Transcribe → RAG + LLM

# IMAGE (Politician):
# User: [Photo of Sanwo-Olu]
# → Vision AI identifies → Returns profile

# IMAGE (Issue):
# User: [Photo of pothole] + "See this road"
# → Vision AI analyzes → Starts issue reporting flow

# DOCUMENT:
# User: [PDF of APC manifesto]
# → Extracts text → Summarizes key promises

# LOCATION:
# User: [Drops location pin]
# → Reverse geocode → Shows representatives for that area
"""
