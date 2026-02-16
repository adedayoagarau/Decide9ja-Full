"""
Decide9ja Multi-Agent System
============================

Architecture: Database First, LLM Last
- Gatekeeper → Classifier → Router → Specialist → Response

Cost Target: 80% of queries at $0 (database + cache + rules)
"""

from app.agents.base import (
    # Enums
    AgentTier,
    CostLevel,
    # Data classes
    UserContext,
    AgentInput,
    AgentOutput,
    # Base classes
    BaseAgent,
    DatabaseAgent,
    LLMAgent,
)

from app.agents.registry import (
    registry,
    register_agent,
    get_agent,
    get_agent_for_intent,
    AgentRegistry,
)

# Import tier modules to register all agents
# Tier 1: Entry Layer
from app.agents.tier1_entry import (
    GatekeeperAgent,
    ClassifierAgent,
    RouterAgent,
)

from app.agents.onboarding import OnboardingAgent

# Tier 2: Core Specialists
from app.agents.tier2_core import (
    RepLookupAgent,
    PoliticianProfileAgent,
    ElectionInfoAgent,
    NewsQueryAgent,
    PromiseLookupAgent,
    CandidateCompareAgent,
    ManifestoAgent,
    ManifestoAgent,
    VotingRecordAgent,
    FactCheckAgent,
)

# Tier 3: Multimodal
from app.agents.tier3_multimodal import (
    VoiceTranscriptionAgent,
    ImageAnalysisAgent,
    LocationProcessorAgent,
)

# Tier 4: Reporting
from app.agents.tier4_reporting import (
    IssueIntakeAgent,
)

# Tier 5: Output Layer
from app.agents.tier5_output import (
    FallbackAgent,
    VoiceSynthesisAgent,
    ResponseComposerAgent,
)

# Tier 6: Analytics & Research
from app.agents.tier6_analytics import (
    DataCollectorAgent,
    ResearchOrchestratorAgent,
    SourceCrawlerAgent,
    DataExtractorAgent,
    KnowledgeCacheAgent,
)

__all__ = [
    # Enums
    "AgentTier",
    "CostLevel",
    # Data classes
    "UserContext",
    "AgentInput",
    "AgentOutput",
    # Base classes
    "BaseAgent",
    "DatabaseAgent",
    "LLMAgent",
    # Registry
    "registry",
    "register_agent",
    "get_agent",
    "get_agent_for_intent",
    "AgentRegistry",
    # Tier 1 Agents
    "GatekeeperAgent",
    "ClassifierAgent",
    "RouterAgent",
    "OnboardingAgent",
    # Tier 2 Agents
    "RepLookupAgent",
    "PoliticianProfileAgent",
    "ElectionInfoAgent",
    "NewsQueryAgent",
    "PromiseLookupAgent",
    "CandidateCompareAgent",
    "ManifestoAgent",
    "ManifestoAgent",
    "VotingRecordAgent",
    "FactCheckAgent",
    # Tier 3 Agents
    "VoiceTranscriptionAgent",
    "ImageAnalysisAgent",
    "LocationProcessorAgent",
    # Tier 4 Agents
    "IssueIntakeAgent",
    # Tier 5 Agents
    "FallbackAgent",
    "VoiceSynthesisAgent",
    "ResponseComposerAgent",
    # Tier 6 Agents
    "DataCollectorAgent",
    "ResearchOrchestratorAgent",
    "SourceCrawlerAgent",
    "DataExtractorAgent",
    "KnowledgeCacheAgent",
]
