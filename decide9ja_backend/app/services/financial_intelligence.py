"""
Financial Intelligence Service
Gap 7: Advanced Financial Intelligence
"""
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

class FinancialIntelligenceService:
    def __init__(self, db_path: str = "/Volumes/Crucial X10/Decide9ja/data/catalog.db"):
        self.db_path = db_path

    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _prepare_fts_query(self, query: str) -> Optional[str]:
        import re
        """
        Prepare a natural language query for FTS5 MATCH syntax.
        """
        if not query or not query.strip():
            return None

        # If user already quoted, pass through
        if '"' in query:
            # Clean dangerous characters but preserve quotes
            cleaned = re.sub(r'[^\w\s"*]', ' ', query)
            return cleaned.strip() or None

        # Remove FTS special characters
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

        # Use OR for broader matching
        return " OR ".join(words)

    def search_financials(self, query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Unified search across Findings, Transactions, and Budgets.
        Principles: Neutrality (show all matches), Insight (calculate facts).
        """
        conn = self.get_db()
        cursor = conn.cursor()
        
        fts_query = self._prepare_fts_query(query)
        if not fts_query:
            return {"metadata": {"query": query, "total_returned": 0}, "results": []}

        # 1. Search Findings (FTS5) - Pre-computed risks/anomalies
        # We search primarily by text match
        findings_query = """
            SELECT 
                f.id, 
                'finding' as source_type,
                f.title as main_text,
                f.description as sub_text,
                f.amount,
                f.year,
                f.jurisdiction,
                f.risk_score,
                f.enriched_analysis
            FROM findings_fts fts
            JOIN findings f ON f.rowid = fts.rowid
            WHERE findings_fts MATCH ? 
            ORDER BY fts.rank 
            LIMIT ? OFFSET ?
        """
        
        # 2. Search Budgets (FTS5) - Planned allocations
        budgets_query = """
            SELECT 
                b.id, 
                'budget' as source_type,
                b.project as main_text,
                b.mda as sub_text,
                b.amount,
                b.year,
                b.jurisdiction,
                0 as risk_score,
                NULL as enriched_analysis
            FROM budgets_fts fts
            JOIN budgets b ON b.rowid = fts.rowid
            WHERE budgets_fts MATCH ? 
            ORDER BY fts.rank 
            LIMIT ? OFFSET ?
        """
        
        # 3. Search Transactions (Regular LIKE for now, pending FTS) - Actual payments
        # Optimization: Use FTS if table grows large. For now, LIKE on payer/receiver/desc
        transactions_query = """
            SELECT 
                id, 
                'transaction' as source_type,
                description as main_text,
                payer || ' -> ' || receiver as sub_text,
                amount,
                strftime('%Y', payment_date) as year,
                state as jurisdiction,
                0 as risk_score,
                NULL as enriched_analysis
            FROM transactions 
            WHERE description LIKE ? OR payer LIKE ? OR receiver LIKE ?
            ORDER BY payment_date DESC 
            LIMIT ? OFFSET ?
        """

        results = []
        
        # Execute Findings Search
        try:
            cursor.execute(findings_query, (fts_query, limit, offset))
            for row in cursor.fetchall():
                results.append(self._process_row(row))
        except Exception as e:
            logger.error(f"Error searching findings: {e}")

        # Execute Budgets Search (if we need more results or want mix)
        # Note: Ideally we'd UNION ALL and order by relevance, but FTS rank is table-specific.
        # For this iteration, we fetch separately and mix.
        try:
            cursor.execute(budgets_query, (fts_query, limit, offset))
            for row in cursor.fetchall():
                results.append(self._process_row(row))
        except Exception as e:
            logger.error(f"Error searching budgets: {e}")
            
        # Execute Transactions Search
        try:
            like_query = f"%{query}%"
            cursor.execute(transactions_query, (like_query, like_query, like_query, limit, offset))
            for row in cursor.fetchall():
                results.append(self._process_row(row))
        except Exception as e:
             logger.error(f"Error searching transactions: {e}")

        conn.close()
        
        # Sort combined results by 'relevance' approximation (findings first, then amount?)
        # For neutral search, maybe just sort by date (year) desc?
        # Let's sort by year DESC, then Amount DESC
        results.sort(key=lambda x: (x['year'] or 0, x['amount'] or 0), reverse=True)
        
        return {
            "metadata": {
                "query": query,
                "total_returned": len(results),
                "generated_at": datetime.now().isoformat()
            },
            "results": results[:limit] # Re-slice after sort
        }

    def _process_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert row to dict and add computed insights."""
        item = dict(row)
        
        # Neutral Insight Generation
        insights = []
        
        # Insight 1: Magnitude Context
        amount = item.get('amount')
        if amount:
            if amount > 1_000_000_000:
                insights.append(f"This is a major entry: ₦{amount/1_000_000_000:.2f} Billion")
            elif amount > 1_000_000:
                insights.append(f"Significant entry: ₦{amount/1_000_000:.2f} Million")
        
        # Insight 2: Contextual Flags (Neutral)
        if item['source_type'] == 'finding' and item['risk_score'] > 0:
             insights.append(f"Flagged in audit with risk score {item['risk_score']}/100")
             
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
        """Get summary stats for a state/year."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        summary = {"state": state, "year": year}
        
        # Total Budget
        try:
            cursor.execute("SELECT SUM(amount), COUNT(*) FROM budgets WHERE jurisdiction = ? AND year = ?", (state, year))
            total, count = cursor.fetchone()
            summary['total_budget'] = total or 0
            summary['line_items'] = count or 0
        except:
            summary['total_budget'] = 0
            
        # Top 3 MDAs
        try:
            cursor.execute("""
                SELECT mda, SUM(amount) as total 
                FROM budgets 
                WHERE jurisdiction = ? AND year = ? 
                GROUP BY mda 
                ORDER BY total DESC 
                LIMIT 3
            """, (state, year))
            summary['top_mdas'] = [dict(row) for row in cursor.fetchall()]
        except:
            summary['top_mdas'] = []
            
        conn.close()
        return summary

    def get_context_for_rag(self, query: str, limit: int = 5) -> str:
        """
        Format financial intelligence for LLM context.
        """
        data = self.search_financials(query, limit=limit)
        results = data.get("results", [])
        
        if not results:
            return ""
            
        context_lines = []
        for item in results:
            line = f"- [{item['source_type'].upper()}] {item['jurisdiction']} ({item['year']}): {item['main_text']}"
            if item.get('amount'):
                line += f" | Amount: ₦{item['amount']:,.2f}"
            if item.get('automated_insights'):
                line += f" | Insights: {'; '.join(item['automated_insights'])}"
            context_lines.append(line)
            
        return "\n".join(context_lines)

# Singleton accessor
_service = None
def get_financial_intelligence(db=None): # db arg for compatibility with RAG call signature
    global _service
    if _service is None:
        _service = FinancialIntelligenceService()
    return _service
