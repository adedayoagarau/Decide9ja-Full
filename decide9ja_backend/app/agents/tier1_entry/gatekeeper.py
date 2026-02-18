"""
GatekeeperAgent
===============
First agent to process every message.
Handles user recognition, session setup, language detection.
Also preprocesses multimodal inputs (voice, image, location).

Cost: FREE (database lookup only, multimodal agents called separately)

Multimodal Flow:
- Voice note → VoiceTranscriptionAgent → transcribed text
- Image → ImageAnalysisAgent → analysis context
- Location → LocationProcessorAgent → state/LGA context
"""

from typing import Optional, Dict, Any
import logging

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel,
    UserContext
)
from app.agents.registry import register_agent, registry
from app.database import SessionLocal, User

logger = logging.getLogger(__name__)


class InputModality:
    """Input modality types"""
    TEXT = "text"
    VOICE_NOTE = "voice_note"
    IMAGE = "image"
    LOCATION = "location"
    IMAGE_WITH_CAPTION = "image_with_caption"
    VOICE_WITH_LOCATION = "voice_with_location"


@register_agent
class GatekeeperAgent(BaseAgent):
    name = "gatekeeper"
    description = "User recognition and session initialization"
    tier = AgentTier.ENTRY
    cost_level = CostLevel.FREE
    handled_intents = ["__all__"]  # Processes every message first

    # Language detection patterns
    PIDGIN_MARKERS = [
        "wetin", "dey", "una", "abeg", "abi", "wahala",
        "gist", "jare", "sef", "sha", "no be", "na so",
        "how far", "i no", "e no"
    ]
    HAUSA_MARKERS = [
        "yaya", "ina", "sannu", "dan", "kuma", "shin",
        "wani", "wannan", "ya", "kai", "ba", "ne"
    ]
    YORUBA_MARKERS = [
        "bawo", "ṣe", "jọwọ", "ẹ", "pẹlẹ", "kilode",
        "se", "ko", "ni", "mo", "ọjọ", "owo"
    ]
    IGBO_MARKERS = [
        "kedu", "biko", "nwanne", "ọ dị", "gịnị", "nna",
        "daalu", "ndewo", "ọ", "di", "anyi"
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return True  # Always runs first

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # 1. Look up user in database
        user_data = await self._lookup_user(input.user.phone_hash)

        # 2. Detect and preprocess multimodal input
        modality, preprocessed_context = await self._preprocess_multimodal(input)

        # 3. Get effective text (transcribed if voice, or raw_text)
        effective_text = preprocessed_context.get("transcribed_text") or input.raw_text

        # 4. Detect language from effective text
        language = self._detect_language(effective_text)

        # 5. Build enriched user context
        if user_data:
            # Returning user
            user = UserContext(
                phone_hash=input.user.phone_hash,
                name=user_data.get("name"),
                state=user_data.get("state"),
                lga=user_data.get("lga"),
                ward=user_data.get("ward"),
                language=language,
                is_new_user=False,
                is_verified=user_data.get("is_verified", False),
                preferences=user_data.get("preferences", {}),
                followed_politicians=user_data.get("followed_politicians", []),
                reported_issues=user_data.get("reported_issues", []),
            )
        else:
            # New user
            user = UserContext(
                phone_hash=input.user.phone_hash,
                language=language,
                is_new_user=True,
            )

        # 6. If location processing returned user location, update user context
        if preprocessed_context.get("is_nigeria") and preprocessed_context.get("state"):
            user = UserContext(
                phone_hash=user.phone_hash,
                name=user.name,
                state=preprocessed_context.get("state") or user.state,
                lga=preprocessed_context.get("lga") or user.lga,
                ward=user.ward,
                language=user.language,
                is_new_user=user.is_new_user,
                is_verified=user.is_verified,
                preferences=user.preferences,
                followed_politicians=user.followed_politicians,
                reported_issues=user.reported_issues,
            )

        # 7. Check if needs onboarding
        if user.is_new_user or not user.name:
            return AgentOutput(
                success=True,
                handoff_to="onboarding",
                handoff_reason="new_user",
                data={
                    "user": self._user_to_dict(user),
                    "modality": modality,
                    "multimodal_context": preprocessed_context,
                },
                cost_level=CostLevel.FREE
            )

        # 8. Pass to classifier with enriched context
        return AgentOutput(
            success=True,
            handoff_to="classifier",
            handoff_reason="user_recognized",
            data={
                "user": self._user_to_dict(user),
                "modality": modality,
                "multimodal_context": preprocessed_context,
                "effective_text": effective_text,
            },
            cost_level=CostLevel.FREE,
            analytics_tags={
                "user_type": "returning",
                "language": language,
                "input_modality": modality,
            }
        )

    async def _preprocess_multimodal(self, input: AgentInput) -> tuple[str, Dict[str, Any]]:
        """
        Detect input modality and preprocess with appropriate agent.

        Returns:
            Tuple of (modality_type, preprocessed_context)
        """
        preprocessed_context: Dict[str, Any] = {}
        modality = InputModality.TEXT

        context = input.context or {}

        # Voice note - transcribe first
        audio_url = context.get("audio_url") or input.audio_url or input.voice_url
        if audio_url:
            modality = InputModality.VOICE_NOTE

            try:
                transcription_agent = registry.get("voice_transcription")
                if transcription_agent:
                    result = await transcription_agent.handle(AgentInput(
                        message_id=input.message_id,
                        raw_text=input.raw_text,
                        user=input.user,
                        audio_url=audio_url,
                        voice_url=audio_url,
                        context=context,
                        timestamp=input.timestamp,
                    ))

                    if result.success and result.data:
                        preprocessed_context["transcribed_text"] = result.data.get("text", "")
                        preprocessed_context["language_detected"] = result.data.get("language", "")
                        preprocessed_context["transcription_confidence"] = result.data.get("confidence", 0)
                        preprocessed_context["audio_duration_seconds"] = result.data.get("duration_seconds", 0)
                        logger.info("Voice transcribed: %s chars", len(preprocessed_context.get("transcribed_text", "")))
                    else:
                        logger.warning("Voice transcription failed: %s", result.error_message)
                        preprocessed_context["transcription_error"] = result.error_message
            except Exception as e:
                logger.error("Voice preprocessing error: %s", e)
                preprocessed_context["transcription_error"] = str(e)

        # Image - analyze content
        image_url = context.get("image_url") or input.image_url or (input.image_urls[0] if input.image_urls else None)
        if image_url:
            caption = context.get("caption") or input.raw_text

            modality = InputModality.IMAGE_WITH_CAPTION if caption else InputModality.IMAGE

            try:
                image_agent = registry.get("image_analysis")
                if image_agent:
                    result = await image_agent.handle(AgentInput(
                        message_id=input.message_id,
                        raw_text=caption or "",
                        user=input.user,
                        image_url=image_url,
                        context={"caption": caption},
                        timestamp=input.timestamp,
                    ))

                    if result.success and result.data:
                        preprocessed_context["image_type"] = result.data.get("image_type", "unknown")
                        preprocessed_context["is_issue_evidence"] = result.data.get("is_issue_evidence", False)
                        preprocessed_context["issue_category"] = result.data.get("issue_category")
                        preprocessed_context["description"] = result.data.get("description", "")
                        preprocessed_context["detected_text"] = result.data.get("detected_text", "")
                        preprocessed_context["is_sensitive"] = result.data.get("is_sensitive", False)
                        preprocessed_context["politicians_detected"] = result.data.get("politicians_detected", [])
                        logger.info("Image analyzed: type=%s, issue_evidence=%s",
                                  preprocessed_context.get("image_type"),
                                  preprocessed_context.get("is_issue_evidence"))
                    else:
                        logger.warning("Image analysis failed: %s", result.error_message)
                        preprocessed_context["image_error"] = result.error_message
            except Exception as e:
                logger.error("Image preprocessing error: %s", e)
                preprocessed_context["image_error"] = str(e)

        # Location - reverse geocode
        elif context.get("latitude") or input.location:
            modality = InputModality.LOCATION

            lat = context.get("latitude") or (input.location.get("lat") if input.location else None)
            lng = context.get("longitude") or (input.location.get("lng") if input.location else None)

            if lat and lng:
                try:
                    location_agent = registry.get("location_processor")
                    if location_agent:
                        result = await location_agent.handle(AgentInput(
                            message_id=input.message_id,
                            raw_text=input.raw_text,
                            user=input.user,
                            location={"lat": lat, "lng": lng},
                            context=context,
                            timestamp=input.timestamp,
                        ))

                        if result.success and result.data:
                            preprocessed_context["latitude"] = result.data.get("latitude")
                            preprocessed_context["longitude"] = result.data.get("longitude")
                            preprocessed_context["address"] = result.data.get("address", "")
                            preprocessed_context["state"] = result.data.get("state", "")
                            preprocessed_context["lga"] = result.data.get("lga", "")
                            preprocessed_context["locality"] = result.data.get("locality", "")
                            preprocessed_context["is_nigeria"] = result.data.get("is_nigeria", False)
                            logger.info("Location processed: %s, %s (Nigeria=%s)",
                                      preprocessed_context.get("lga"),
                                      preprocessed_context.get("state"),
                                      preprocessed_context.get("is_nigeria"))
                        else:
                            logger.warning("Location processing failed: %s", result.error_message)
                            preprocessed_context["location_error"] = result.error_message
                except Exception as e:
                    logger.error("Location preprocessing error: %s", e)
                    preprocessed_context["location_error"] = str(e)

        return modality, preprocessed_context

    async def _lookup_user(self, phone_hash: str) -> Optional[dict]:
        """Look up user in database by phone_hash."""
        try:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.phone_hash == phone_hash).first()
                if user and user.onboarding_completed:
                    return {
                        "name": user.name,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "state": user.state,
                        "lga": user.lga,
                        "ward": getattr(user, 'ward', None),
                        "is_verified": False,
                        "preferences": {},
                        "followed_politicians": [],
                        "reported_issues": [],
                    }
                return None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"User lookup failed: {e}")
            return None

    def _detect_language(self, text: str) -> str:
        """Detect language from text patterns"""
        text_lower = text.lower()

        # Count markers for each language
        pidgin_count = sum(1 for m in self.PIDGIN_MARKERS if m in text_lower)
        hausa_count = sum(1 for m in self.HAUSA_MARKERS if m in text_lower)
        yoruba_count = sum(1 for m in self.YORUBA_MARKERS if m in text_lower)
        igbo_count = sum(1 for m in self.IGBO_MARKERS if m in text_lower)

        # Return language with most markers (minimum 1)
        max_count = max(pidgin_count, hausa_count, yoruba_count, igbo_count)

        if max_count == 0:
            return "en"  # Default to English

        if pidgin_count == max_count:
            return "pcm"  # Pidgin
        if hausa_count == max_count:
            return "ha"
        if yoruba_count == max_count:
            return "yo"
        if igbo_count == max_count:
            return "ig"

        return "en"

    def _user_to_dict(self, user: UserContext) -> dict:
        """Convert UserContext to dict for handoff"""
        return {
            "phone_hash": user.phone_hash,
            "name": user.name,
            "state": user.state,
            "lga": user.lga,
            "ward": user.ward,
            "language": user.language,
            "is_new_user": user.is_new_user,
            "is_verified": user.is_verified,
            "preferences": user.preferences,
            "followed_politicians": user.followed_politicians,
            "reported_issues": user.reported_issues,
        }
