"""
Financial Intelligence Service
Gap 7: Advanced Financial Intelligence
Migrated to SQLAlchemy & PostgreSQL
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import or_, and_, func, String

# Use absolute import from app.database since backend is in path
from app.database import SessionLocal, Finding, Budget, Transaction

# Setup logging
logger = logging.getLogger(__name__)

class FinancialIntelligenceService:
    def __init__(self):
        pass

    def _prepare_fts_query(self, query: str) -> Optional[List[str]]:
        import re
        """
        Prepare a natural language query for basic ILIKE search keywords.
        """
        if not query or not query.strip():
            return None

        # Clean dangerous characters
        cleaned = re.sub(r'[^\w\s]', ' ', query)
        
        # Split into words, filter short/stop words
        stop_words = {
            'the', 'is', 'at', 'on', 'in', 'a', 'an', 'of', 'to', 'for',
            'and', 'or', 'but', 'not', 'with', 'by', 'from', 'as', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'what', 'who', 'when', 'where', 'how', 'which', 'that', 'this',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'me', 'him',
            'about', 'tell', 'can', 'you', 'i', 'it', 'they', 'we', 'he', 'she',
        }
        
        words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in stop_words]
        
        if not words:
            words = [w for w in cleaned.split() if len(w) > 1]
        
        if not words:
            return None

        return words

    def search_financials(self, query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Unified search across Findings, Transactions, and Budgets using SQLAlchemy.
        Uses OR logic (match ANY keyword) with relevance ranking (more matches = higher rank).
        """
        words = self._prepare_fts_query(query)
        if not words:
            return {"metadata": {"query": query, "total_returned": 0}, "results": []}

        session = SessionLocal()
        results = []

        # 1. Search Findings — OR logic: match ANY keyword in ANY field
        try:
            or_conditions = []
            for w in words:
                term = f"%{w}%"
                or_conditions.append(Finding.title.ilike(term))
                or_conditions.append(Finding.description.ilike(term))
                or_conditions.append(Finding.project_name.ilike(term))
                or_conditions.append(Finding.jurisdiction.ilike(term))
                or_conditions.append(Finding.mda.ilike(term))
                or_conditions.append(func.cast(Finding.year, String).ilike(term))

            finding_records = session.query(Finding).filter(or_(*or_conditions)).limit(limit).offset(offset).all()
            for f in finding_records:
                # Use description or project_name as main text, NOT title
                # (title is often a flag like 'VAGUE_DESCRIPTION' or 'CONTRACT_SPLITTING')
                display_text = f.description or f.project_name or f.title
                flag_type = f.title if f.title not in (display_text, None) else None
                results.append({
                    'id': f.id,
                    'source_type': 'finding',
                    'main_text': display_text,
                    'sub_text': f.mda or f.project_name or '',
                    'flag_type': flag_type,
                    'amount': f.amount,
                    'year': f.year,
                    'jurisdiction': f.jurisdiction,
                    'risk_score': f.risk_score,
                    'enriched_analysis': f.enriched_analysis
                })
        except Exception as e:
            logger.error(f"Error searching findings: {e}")

        # 2. Search Budgets — OR logic
        try:
            or_conditions = []
            for w in words:
                term = f"%{w}%"
                or_conditions.append(Budget.project.ilike(term))
                or_conditions.append(Budget.mda.ilike(term))
                or_conditions.append(Budget.jurisdiction.ilike(term))
                or_conditions.append(func.cast(Budget.year, String).ilike(term))

            budget_records = session.query(Budget).filter(or_(*or_conditions)).limit(limit).offset(offset).all()
            for b in budget_records:
                results.append({
                    'id': b.id,
                    'source_type': 'budget',
                    'main_text': b.project,
                    'sub_text': b.mda,
                    'amount': b.amount,
                    'year': b.year,
                    'jurisdiction': b.jurisdiction,
                    'risk_score': 0,
                    'enriched_analysis': None
                })
        except Exception as e:
            logger.error(f"Error searching budgets: {e}")

        # 3. Search Transactions — OR logic
        try:
            or_conditions = []
            for w in words:
                term = f"%{w}%"
                or_conditions.append(Transaction.description.ilike(term))
                or_conditions.append(Transaction.payer.ilike(term))
                or_conditions.append(Transaction.receiver.ilike(term))
                or_conditions.append(Transaction.state.ilike(term))
                or_conditions.append(Transaction.payment_date.ilike(term))

            txn_records = session.query(Transaction).filter(or_(*or_conditions)).limit(limit).offset(offset).all()
            for t in txn_records:
                try:
                    year = int(t.payment_date[:4]) if t.payment_date and len(t.payment_date) >= 4 else None
                except:
                    year = None

                results.append({
                    'id': t.id,
                    'source_type': 'transaction',
                    'main_text': t.description or 'No description',
                    'sub_text': f"{t.payer or '?'} → {t.receiver or '?'}",
                    'payment_date': t.payment_date,
                    'payer': t.payer,
                    'receiver': t.receiver,
                    'amount': t.amount,
                    'year': year,
                    'jurisdiction': t.state,
                    'risk_score': 0,
                    'enriched_analysis': None
                })
        except Exception as e:
            logger.error(f"Error searching transactions: {e}")

        session.close()

        for item in results:
            if item.get('year'):
                try: item['year'] = int(item['year'])
                except: item['year'] = 0

        # Relevance ranking: count how many query keywords each result matches
        for item in results:
            searchable = ' '.join(str(v) for v in [
                item.get('main_text', ''), item.get('sub_text', ''),
                item.get('jurisdiction', ''), item.get('year', '')
            ]).lower()
            item['relevance_score'] = sum(1 for w in words if w.lower() in searchable)

        # Sort by relevance first, then year DESC, then amount DESC
        results.sort(key=lambda x: (x.get('relevance_score', 0), x.get('year') or 0, x.get('amount') or 0), reverse=True)
        
        # Add automated insights
        processed_results = [self._process_row(r) for r in results[:limit]]
        
        return {
            "metadata": {
                "query": query,
                "total_returned": len(processed_results),
                "generated_at": datetime.now().isoformat()
            },
            "results": processed_results
        }

    def _process_row(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Add computed insights to dict."""
        
        # Neutral Insight Generation
        insights = []
        
        # Insight 1: Magnitude Context
        amount = item.get('amount')
        if amount:
            if amount > 1_000_000_000:
                insights.append(f"This is a major entry: ₦{amount/1_000_000_000:.2f} Billion")
            elif amount > 1_000_000:
                insights.append(f"Significant entry: ₦{amount/1_000_000:.2f} Million")
        
        # Insight 2: Contextual Flags with meaningful labels
        if item.get('source_type') == 'finding' and item.get('risk_score', 0) > 0:
            flag = item.get('flag_type', '')
            if flag == 'CONTRACT_SPLITTING':
                insights.append("Flagged for suspected contract splitting")
            elif flag == 'DUPLICATE_ALLOCATION':
                insights.append("Flagged as possible duplicate allocation")
            elif flag == 'VAGUE_DESCRIPTION':
                insights.append("Budget line has vague/generic description — warrants scrutiny")
            elif flag:
                insights.append(f"Audit flag: {flag.replace('_', ' ').title()}")
            else:
                insights.append(f"Risk score: {item['risk_score']}/100")
             
        # Parse enriched analysis if available
        if item.get('enriched_analysis'):
            try:
                analysis = json.loads(item['enriched_analysis'])
                if isinstance(analysis, dict):
                    # extract simplified summary
                    summary = analysis.get('analysis') or analysis.get('summary')
                    if summary:
                        insights.append(f"Analysis: {summary[:100]}...")
            except:
                pass

        item['automated_insights'] = insights
        return item
    
    def get_state_summary(self, state: str, year: int = 2026) -> Dict[str, Any]:
        """Get summary stats for a state/year using SQLAlchemy."""
        session = SessionLocal()
        summary = {"state": state, "year": year}
        
        # Total Budget
        try:
            total = session.query(func.sum(Budget.amount)).filter(Budget.jurisdiction == state, Budget.year == year).scalar()
            count = session.query(func.count(Budget.id)).filter(Budget.jurisdiction == state, Budget.year == year).scalar()
            summary['total_budget'] = float(total) if total else 0
            summary['line_items'] = float(count) if count else 0
        except Exception as e:
            logger.error(f"Error getting budget summary: {e}")
            summary['total_budget'] = 0
            summary['line_items'] = 0
            
        # Top 3 MDAs
        try:
            top_mdas = session.query(
                Budget.mda, 
                func.sum(Budget.amount).label('total')
            ).filter(
                Budget.jurisdiction == state, 
                Budget.year == year
            ).group_by(Budget.mda).order_by(func.sum(Budget.amount).desc()).limit(3).all()
            
            summary['top_mdas'] = [{"mda": str(mda), "total": float(total)} for mda, total in top_mdas]
        except Exception as e:
            logger.error(f"Error getting top mdas: {e}")
            summary['top_mdas'] = []
            
        session.close()
        return summary

    def get_context_for_rag(self, query: str, limit: int = 10) -> str:
        """
        Format financial intelligence for LLM context.
        Includes rich metadata: dates, payer/receiver, flag types.
        """
        data = self.search_financials(query, limit=limit)
        results = data.get("results", [])

        if not results:
            return ""

        context_lines = []
        for item in results:
            src = item['source_type'].upper()
            jurisdiction = item.get('jurisdiction', 'Federal')
            year = item.get('year', '?')

            if src == 'TRANSACTION':
                date = item.get('payment_date', '?')
                payer = item.get('payer', '?')
                receiver = item.get('receiver', '?')
                line = f"- [PAYMENT {date}] {item['main_text']}"
                line += f"\n  Paid by: {payer} → To: {receiver}"
                if item.get('amount'):
                    line += f" | Amount: ₦{item['amount']:,.2f}"
            elif src == 'FINDING':
                flag = item.get('flag_type', '')
                flag_label = f" [{flag}]" if flag and flag != 'VAGUE_DESCRIPTION' else ""
                line = f"- [AUDIT FINDING{flag_label}] {jurisdiction} ({year}): {item['main_text']}"
                if item.get('sub_text'):
                    line += f"\n  MDA: {item['sub_text']}"
                if item.get('amount'):
                    line += f" | Amount: ₦{item['amount']:,.2f}"
                if item.get('risk_score', 0) > 0:
                    line += f" | Risk: {item['risk_score']}/100"
            else:
                line = f"- [BUDGET] {jurisdiction} ({year}): {item['main_text']}"
                if item.get('sub_text'):
                    line += f" | MDA: {item['sub_text']}"
                if item.get('amount'):
                    line += f" | Amount: ₦{item['amount']:,.2f}"

            context_lines.append(line)

        return "\n".join(context_lines)

# Singleton accessor
_service = None
def get_financial_intelligence(db=None): # db arg for compatibility with RAG call signature
    global _service
    if _service is None:
        _service = FinancialIntelligenceService()
    return _service
