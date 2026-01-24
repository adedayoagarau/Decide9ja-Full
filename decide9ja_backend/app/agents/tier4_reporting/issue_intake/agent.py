"""
IssueIntakeAgent
================
Collects citizen reports about local issues (potholes, power, water, etc.)

Multi-step flow:
1. Identify issue type
2. Collect location
3. Collect description
4. Optional: media upload
5. Store and acknowledge

Cost: CHEAP (minimal LLM for classification)

Handles:
- "I want to report a problem"
- "There's a pothole on my street"
- "No water in my area for 3 days"
- "Street lights not working"
"""

from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
import logging
import uuid

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.agents.tier1_entry.classifier import Intent

logger = logging.getLogger(__name__)


class IssueCategory(str, Enum):
    ROAD = "road"
    WATER = "water"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    SECURITY = "security"
    EDUCATION = "education"
    HEALTH = "health"
    CORRUPTION = "corruption"
    OTHER = "other"


class IntakeStep(str, Enum):
    CATEGORY = "category"
    LOCATION = "location"
    DESCRIPTION = "description"
    MEDIA = "media"
    CONFIRM = "confirm"
    COMPLETE = "complete"


@register_agent
class IssueIntakeAgent(BaseAgent):
    name = "issue_intake"
    description = "Collect citizen reports about local issues"
    tier = AgentTier.REPORTING
    cost_level = CostLevel.CHEAP  # Minimal LLM for classification
    handled_intents = [
        Intent.REPORT_ISSUE,
    ]

    # Issue category keywords
    CATEGORY_KEYWORDS = {
        IssueCategory.ROAD: ["road", "pothole", "highway", "street", "bridge", "traffic"],
        IssueCategory.WATER: ["water", "pipe", "tap", "borehole", "well", "flooding"],
        IssueCategory.ELECTRICITY: ["light", "power", "nepa", "phcn", "transformer", "electricity"],
        IssueCategory.SANITATION: ["refuse", "garbage", "waste", "gutter", "drainage", "sewage"],
        IssueCategory.SECURITY: ["crime", "theft", "robbery", "police", "danger", "unsafe"],
        IssueCategory.EDUCATION: ["school", "teacher", "student", "classroom", "education"],
        IssueCategory.HEALTH: ["hospital", "clinic", "doctor", "medicine", "health"],
        IssueCategory.CORRUPTION: ["bribe", "corrupt", "fraud", "misuse", "embezzle"],
    }

    # Priority keywords
    HIGH_PRIORITY_KEYWORDS = [
        "emergency", "urgent", "dangerous", "dying", "fire", "accident",
        "collapsed", "flood", "explosion", "critical"
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent in self.handled_intents

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # Get current step from session
        session_data = input.session_data or {}
        current_step = session_data.get("issue_step", IntakeStep.CATEGORY)
        issue_draft = session_data.get("issue_draft", {})

        # Route to appropriate step handler
        if current_step == IntakeStep.CATEGORY:
            return await self._handle_category_step(input, issue_draft)
        elif current_step == IntakeStep.LOCATION:
            return await self._handle_location_step(input, issue_draft)
        elif current_step == IntakeStep.DESCRIPTION:
            return await self._handle_description_step(input, issue_draft)
        elif current_step == IntakeStep.MEDIA:
            return await self._handle_media_step(input, issue_draft)
        elif current_step == IntakeStep.CONFIRM:
            return await self._handle_confirm_step(input, issue_draft)
        else:
            return self._start_new_report(input)

    def _start_new_report(self, input: AgentInput) -> AgentOutput:
        """Start a new issue report"""
        # Try to auto-detect category from initial message
        category = self._detect_category(input.raw_text)
        priority = self._detect_priority(input.raw_text)

        if category:
            # Category detected, ask for location
            return AgentOutput(
                success=True,
                response_text=f"""📝 *Report an Issue*

I detected you want to report a *{category.value.title()}* issue.

Please provide the *location* of this issue:
• Street name or landmark
• Area/neighborhood
• LGA and State

Example: "Ahmadu Bello Way, near Central Mosque, Kaduna South LGA, Kaduna State\"""",
                session_data={
                    "issue_step": IntakeStep.LOCATION,
                    "issue_draft": {
                        "category": category.value,
                        "priority": priority,
                        "initial_text": input.raw_text,
                        "started_at": datetime.utcnow().isoformat()
                    }
                },
                cost_level=CostLevel.FREE,
                analytics_tags={"step": "category_detected", "category": category.value}
            )

        # No category detected, ask user to select
        return AgentOutput(
            success=True,
            response_text="""📝 *Report an Issue*

What type of issue do you want to report?

1️⃣ Road/Pothole
2️⃣ Water/Pipe
3️⃣ Electricity/Power
4️⃣ Sanitation/Waste
5️⃣ Security
6️⃣ Education
7️⃣ Health
8️⃣ Corruption
9️⃣ Other

Reply with the number or describe your issue.""",
            buttons=[
                {"text": "🛣️ Road", "callback": "issue_cat:road"},
                {"text": "💧 Water", "callback": "issue_cat:water"},
                {"text": "💡 Power", "callback": "issue_cat:electricity"},
                {"text": "🗑️ Sanitation", "callback": "issue_cat:sanitation"},
            ],
            session_data={
                "issue_step": IntakeStep.CATEGORY,
                "issue_draft": {
                    "started_at": datetime.utcnow().isoformat(),
                    "initial_text": input.raw_text
                }
            },
            cost_level=CostLevel.FREE,
            analytics_tags={"step": "category_prompt"}
        )

    async def _handle_category_step(self, input: AgentInput, draft: Dict) -> AgentOutput:
        """Handle category selection"""
        text = input.raw_text.lower().strip()

        # Check for number selection
        category_map = {
            "1": IssueCategory.ROAD, "road": IssueCategory.ROAD,
            "2": IssueCategory.WATER, "water": IssueCategory.WATER,
            "3": IssueCategory.ELECTRICITY, "electricity": IssueCategory.ELECTRICITY, "power": IssueCategory.ELECTRICITY,
            "4": IssueCategory.SANITATION, "sanitation": IssueCategory.SANITATION,
            "5": IssueCategory.SECURITY, "security": IssueCategory.SECURITY,
            "6": IssueCategory.EDUCATION, "education": IssueCategory.EDUCATION,
            "7": IssueCategory.HEALTH, "health": IssueCategory.HEALTH,
            "8": IssueCategory.CORRUPTION, "corruption": IssueCategory.CORRUPTION,
            "9": IssueCategory.OTHER, "other": IssueCategory.OTHER,
        }

        category = category_map.get(text) or self._detect_category(text)

        if not category:
            return AgentOutput(
                success=True,
                response_text="I didn't understand that. Please select a number (1-9) or describe your issue clearly.",
                session_data={
                    "issue_step": IntakeStep.CATEGORY,
                    "issue_draft": draft
                },
                cost_level=CostLevel.FREE
            )

        draft["category"] = category.value
        draft["priority"] = self._detect_priority(text)

        return AgentOutput(
            success=True,
            response_text=f"""✅ Category: *{category.value.title()}*

Now, please provide the *location*:
• Street name or landmark
• Area/neighborhood
• LGA and State

Be as specific as possible to help authorities locate the issue.""",
            session_data={
                "issue_step": IntakeStep.LOCATION,
                "issue_draft": draft
            },
            cost_level=CostLevel.FREE,
            analytics_tags={"step": "location_prompt", "category": category.value}
        )

    async def _handle_location_step(self, input: AgentInput, draft: Dict) -> AgentOutput:
        """Handle location input"""
        location = input.raw_text.strip()

        if len(location) < 10:
            return AgentOutput(
                success=True,
                response_text="Please provide more details about the location (street name, area, LGA).",
                session_data={
                    "issue_step": IntakeStep.LOCATION,
                    "issue_draft": draft
                },
                cost_level=CostLevel.FREE
            )

        # Use user's registered location as context
        if input.user.state and input.user.state.lower() not in location.lower():
            location = f"{location}, {input.user.lga or ''} {input.user.state or ''}".strip()

        draft["location"] = location

        return AgentOutput(
            success=True,
            response_text=f"""✅ Location: *{location}*

Now describe the issue in detail:
• What exactly is the problem?
• How long has it been happening?
• How does it affect the community?

The more details, the better the report.""",
            session_data={
                "issue_step": IntakeStep.DESCRIPTION,
                "issue_draft": draft
            },
            cost_level=CostLevel.FREE,
            analytics_tags={"step": "description_prompt"}
        )

    async def _handle_description_step(self, input: AgentInput, draft: Dict) -> AgentOutput:
        """Handle description input"""
        description = input.raw_text.strip()

        if len(description) < 20:
            return AgentOutput(
                success=True,
                response_text="Please provide more details about the issue (at least a few sentences).",
                session_data={
                    "issue_step": IntakeStep.DESCRIPTION,
                    "issue_draft": draft
                },
                cost_level=CostLevel.FREE
            )

        draft["description"] = description
        draft["priority"] = self._detect_priority(description) or draft.get("priority", "normal")

        return AgentOutput(
            success=True,
            response_text="""✅ Description recorded.

Do you have a *photo or video* of the issue?
• Reply with an image/video
• Or type "skip" to continue without media

Photos help authorities understand and prioritize the issue.""",
            session_data={
                "issue_step": IntakeStep.MEDIA,
                "issue_draft": draft
            },
            buttons=[
                {"text": "📷 Add Photo", "callback": "issue_media:photo"},
                {"text": "⏭️ Skip", "callback": "issue_media:skip"},
            ],
            cost_level=CostLevel.FREE,
            analytics_tags={"step": "media_prompt"}
        )

    async def _handle_media_step(self, input: AgentInput, draft: Dict) -> AgentOutput:
        """Handle media upload or skip"""
        text = input.raw_text.lower().strip()

        # Check for media
        if input.image_urls:
            draft["media_urls"] = input.image_urls
            draft["has_media"] = True
        elif input.video_url:
            draft["media_urls"] = [input.video_url]
            draft["has_media"] = True
        elif text in ["skip", "no", "none", "continue"]:
            draft["has_media"] = False
        else:
            # Assume they sent text instead of media
            draft["has_media"] = False

        # Show confirmation
        return self._show_confirmation(draft)

    def _show_confirmation(self, draft: Dict) -> AgentOutput:
        """Show report summary for confirmation"""
        media_status = "📷 Photo attached" if draft.get("has_media") else "No media"

        summary = f"""📋 *Issue Report Summary*

*Category:* {draft.get('category', 'Other').title()}
*Location:* {draft.get('location', 'Not specified')}
*Priority:* {draft.get('priority', 'normal').title()}

*Description:*
{draft.get('description', 'No description')[:200]}{'...' if len(draft.get('description', '')) > 200 else ''}

*Media:* {media_status}

Is this correct? Reply *Yes* to submit or *No* to start over."""

        return AgentOutput(
            success=True,
            response_text=summary,
            session_data={
                "issue_step": IntakeStep.CONFIRM,
                "issue_draft": draft
            },
            buttons=[
                {"text": "✅ Submit", "callback": "issue_confirm:yes"},
                {"text": "❌ Start Over", "callback": "issue_confirm:no"},
            ],
            cost_level=CostLevel.FREE,
            analytics_tags={"step": "confirm"}
        )

    async def _handle_confirm_step(self, input: AgentInput, draft: Dict) -> AgentOutput:
        """Handle final confirmation"""
        text = input.raw_text.lower().strip()

        if text in ["yes", "y", "submit", "confirm", "ok"]:
            # Submit the report
            return await self._submit_report(input, draft)
        elif text in ["no", "n", "cancel", "start over"]:
            # Start over
            return self._start_new_report(input)
        else:
            return AgentOutput(
                success=True,
                response_text="Please reply *Yes* to submit or *No* to start over.",
                session_data={
                    "issue_step": IntakeStep.CONFIRM,
                    "issue_draft": draft
                },
                cost_level=CostLevel.FREE
            )

    async def _submit_report(self, input: AgentInput, draft: Dict) -> AgentOutput:
        """Submit the issue report to database"""
        # Generate tracking ID
        tracking_id = f"D9J-{uuid.uuid4().hex[:8].upper()}"

        # Build report record
        report = {
            "tracking_id": tracking_id,
            "category": draft.get("category"),
            "location": draft.get("location"),
            "description": draft.get("description"),
            "priority": draft.get("priority", "normal"),
            "media_urls": draft.get("media_urls", []),
            "reporter_phone_hash": input.user.phone_hash,
            "reporter_state": input.user.state,
            "reporter_lga": input.user.lga,
            "status": "submitted",
            "submitted_at": datetime.utcnow().isoformat(),
        }

        # Store in database
        stored = await self._store_report(report)

        if stored:
            response = f"""✅ *Issue Report Submitted!*

*Tracking ID:* {tracking_id}

Save this ID to check your report status later.

Your report has been logged and will be reviewed. We'll notify you of any updates.

Thank you for being an active citizen! 🇳🇬

_Type "track {tracking_id}" to check status anytime._"""
        else:
            response = f"""⚠️ *Report Saved Locally*

*Tracking ID:* {tracking_id}

Your report has been saved. We'll sync it when connection is restored.

Thank you for reporting!"""

        return AgentOutput(
            success=True,
            response_text=response,
            session_data={
                "issue_step": IntakeStep.COMPLETE,
                "last_tracking_id": tracking_id
            },
            data={"report": report, "tracking_id": tracking_id},
            cost_level=CostLevel.FREE,
            analytics_tags={
                "step": "submitted",
                "category": draft.get("category"),
                "priority": draft.get("priority"),
                "has_media": draft.get("has_media", False)
            }
        )

    async def _store_report(self, report: Dict) -> bool:
        """Store report in database using civic_issues service"""
        try:
            from app.services.civic_issues import issue_intake_service

            result = issue_intake_service.report_issue(
                reporter_hash=report.get("reporter_phone_hash", "unknown"),
                title=f"{report.get('category', 'Issue').title()} - {report.get('location', 'Unknown')[:50]}",
                description=report.get("description", ""),
                category=report.get("category", "other"),
                state=report.get("reporter_state", ""),
                lga=report.get("reporter_lga", ""),
                address=report.get("location", ""),
                photo_urls=report.get("media_urls", []),
            )

            if result.get("success"):
                # Update tracking ID with the one from service
                report["db_issue_id"] = result.get("issue_id")
                logger.info(f"Issue report stored: {report['tracking_id']} -> {result.get('issue_id')}")
                return True
            else:
                logger.error(f"Failed to store issue: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Failed to store issue report: {e}")
            return False

    def _detect_category(self, text: str) -> Optional[IssueCategory]:
        """Detect issue category from text"""
        if not text:
            return None

        text_lower = text.lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return category

        return None

    def _detect_priority(self, text: str) -> str:
        """Detect issue priority from text"""
        if not text:
            return "normal"

        text_lower = text.lower()

        if any(kw in text_lower for kw in self.HIGH_PRIORITY_KEYWORDS):
            return "high"

        return "normal"
