"""Tier 2: Core Specialists - Database-first agents for Nigerian politics"""
from app.agents.tier2_core.rep_lookup import RepLookupAgent
from app.agents.tier2_core.politician_profile import PoliticianProfileAgent
from app.agents.tier2_core.election_info import ElectionInfoAgent
from app.agents.tier2_core.news_query import NewsQueryAgent
from app.agents.tier2_core.promise_lookup import PromiseLookupAgent
from app.agents.tier2_core.candidate_compare import CandidateCompareAgent
from app.agents.tier2_core.manifesto import ManifestoAgent
from app.agents.tier2_core.voting_record import VotingRecordAgent
from app.agents.tier2_core.engagement import EngagementAgent

__all__ = [
    "RepLookupAgent",
    "PoliticianProfileAgent",
    "ElectionInfoAgent",
    "NewsQueryAgent",
    "PromiseLookupAgent",
    "CandidateCompareAgent",
    "ManifestoAgent",
    "VotingRecordAgent",
    "EngagementAgent",
]
