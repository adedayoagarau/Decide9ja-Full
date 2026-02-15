"""
Budget & Financial Intelligence API
Gap 9: Frontend Integration
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.services.financial_intelligence import get_financial_intelligence, FinancialIntelligenceService
from app.services.budget_search import get_budget_service

router = APIRouter(prefix="/api/budget", tags=["budget"])

@router.get("/search")
async def search_financials(
    q: str, 
    limit: int = 20, 
    offset: int = 0,
    service: FinancialIntelligenceService = Depends(get_financial_intelligence)
):
    """
    Unified search for financial data (Findings, Budgets, Transactions).
    Returns neutral results with automated insights.
    """
    return service.search_financials(query=q, limit=limit, offset=offset)

@router.get("/state/{state_name}")
async def get_state_summary(
    state_name: str,
    year: int = 2026,
    service: FinancialIntelligenceService = Depends(get_financial_intelligence)
):
    """
    Get high-level budget summary for a state.
    """
    try:
        data = service.get_state_summary(state=state_name, year=year)
        if not data:
            raise HTTPException(status_code=404, detail="State data not found")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/findings")
async def get_all_findings(
    limit: int = 50,
    offset: int = 0,
    service: FinancialIntelligenceService = Depends(get_financial_intelligence)
):
    """
    Get raw findings (pagination support).
    """
    # determining how to expose raw findings via search service or direct DB
    # Re-using search with empty query might work if supported, or custom SQL
    # For now, let's use a specific query on the service if implementation allows
    # The service search logic uses MATCH which needs a term, or we can add a method.
    # We'll rely on the client using search for now, or add a 'list_findings' later.
    return service.search_financials(query="risk", limit=limit, offset=offset)

@router.get("/red-flags")
async def get_red_flags(
    jurisdiction: Optional[str] = None,
    limit: int = 50,
    service: FinancialIntelligenceService = Depends(get_financial_intelligence)
):
    """
    Get high-risk 'Red Flag' findings (e.g. suspicious payments, budget anomalies).
    """
    return service.get_red_flags(jurisdiction=jurisdiction, limit=limit)
