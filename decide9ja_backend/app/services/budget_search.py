"""
Budget Search Service

Connects the Decide9ja backend to the budget database (budgets table in catalog.db).
Enables searching across Federal and State budget line items.
"""

import os
import sqlite3
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Catalog database paths (reuse existing logic or import)
_env_catalog = os.getenv("CATALOG_DB_PATH", "")
CATALOG_DB_PATHS = [
    *([] if not _env_catalog else [Path(_env_catalog)]),
    Path("/Volumes/Crucial X10/Decide9ja/data/catalog.db"),
    Path("/app/data/catalog.db"),
    Path(os.path.expanduser("~/Decide9ja/data/catalog.db")),
]

@dataclass
class BudgetLineItem:
    """A single budget line item."""
    id: int
    year: int
    jurisdiction: str
    mda: str
    project: str
    amount: float
    source_file: str
    page: int
    relevance_rank: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "year": self.year,
            "jurisdiction": self.jurisdiction,
            "mda": self.mda,
            "project": self.project,
            "amount": self.amount,
            "formatted_amount": f"₦{self.amount:,.2f}",
            "source": self.source_file
        }

@dataclass
class BudgetSearchResult:
    """Results from a budget search."""
    query: str
    items: List[BudgetLineItem] = field(default_factory=list)
    total_matches: int = 0
    search_time_ms: float = 0
    source: str = "budget_fts5"

    @property
    def has_results(self) -> bool:
        return len(self.items) > 0

    def to_context_string(self, max_items: int = 10) -> str:
        """Format results as context string for LLM."""
        if not self.items:
            return ""

        parts = [f"=== BUDGET DATA ({self.total_matches} matches) ==="]
        for i, item in enumerate(self.items[:max_items]):
            parts.append(f"\n--- [{i+1}] {item.jurisdiction} {item.year} Budget ---")
            parts.append(f"MDA: {item.mda}")
            parts.append(f"Project: {item.project}")
            parts.append(f"Amount: ₦{item.amount:,.2f}")
        return "\n".join(parts)

class BudgetSearchService:
    """
    Service for searching Federal and State budgets.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = self._resolve_db_path(db_path)
        self._available = self._db_path is not None
        if self._available:
            logger.info(f"💰 Budget search initialized: {self._db_path}")
        else:
            logger.warning("💰 Budget database not found — search disabled")

    def _resolve_db_path(self, explicit_path: Optional[str] = None) -> Optional[Path]:
        if explicit_path:
            p = Path(explicit_path)
            if p.exists():
                return p
        for path in CATALOG_DB_PATHS:
            if path and path.exists():
                return path
        return None

    @property
    def is_available(self) -> bool:
        return self._available

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        if not self._available:
            return None
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=5)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Budget DB connection error: {e}")
            return None

    def search(
        self,
        query: str,
        limit: int = 20,
        year: Optional[int] = None,
        jurisdiction: Optional[str] = None,
        mda_filter: Optional[str] = None,
        min_amount: Optional[float] = None
    ) -> BudgetSearchResult:
        """
        Search budget line items.
        """
        start = datetime.now()
        result = BudgetSearchResult(query=query)

        if not self._available:
            return result

        conn = self._get_connection()
        if not conn:
            return result

        try:
            fts_query = self._prepare_fts_query(query)
            
            # Base query joins FTS table for ranking
            # Note: We use LEFT JOIN or just query raw table if no FTS query?
            # If FTS query exists, we use FTS. If not, normal filter.
            
            params = []
            where_clauses = []
            
            if fts_query:
                # FTS search
                table = "budgets_fts f JOIN budgets b ON f.rowid = b.id"
                where_clauses.append("budgets_fts MATCH ?")
                params.append(fts_query)
                order_by = "rank"
            else:
                # Regular filter search
                table = "budgets b"
                order_by = "amount DESC"  # Default sort by amount if no text match
            
            # Apply filters
            if year:
                where_clauses.append("b.year = ?")
                params.append(year)
            
            if jurisdiction:
                where_clauses.append("b.jurisdiction LIKE ?")
                params.append(f"%{jurisdiction}%")
                
            if mda_filter:
                where_clauses.append("b.mda LIKE ?")
                params.append(f"%{mda_filter}%")
                
            if min_amount:
                where_clauses.append("b.amount >= ?")
                params.append(min_amount)

            where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            sql = f"""
                SELECT b.id, b.year, b.jurisdiction, b.mda, b.project, b.amount, b.source_file, b.page
                FROM {table}
                {where_str}
                ORDER BY {order_by}
                LIMIT ?
            """
            params.append(limit)
            
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            for row in rows:
                item = BudgetLineItem(
                    id=row["id"],
                    year=row["year"],
                    jurisdiction=row["jurisdiction"],
                    mda=row["mda"] or "Unknown",
                    project=row["project"],
                    amount=row["amount"] or 0.0,
                    source_file=row["source_file"] or "",
                    page=row["page"] or 0
                )
                result.items.append(item)
            
            result.total_matches = len(rows) # Approximation suitable for now
            
        except Exception as e:
            logger.error(f"Budget search error: {e}")
        finally:
            conn.close()

        elapsed = (datetime.now() - start).total_seconds() * 1000
        result.search_time_ms = elapsed
        
        return result

    def _prepare_fts_query(self, query: str) -> Optional[str]:
        """Simple FTS query preparation."""
        if not query or not query.strip():
            return None
        # Naive: OR all terms
        cleaned = re.sub(r'[^\w\s]', '', query)
        words = cleaned.split()
        if not words: return None
        return " OR ".join(words)

# Singleton
_budget_service: Optional[BudgetSearchService] = None

def get_budget_service() -> BudgetSearchService:
    global _budget_service
    if _budget_service is None:
        _budget_service = BudgetSearchService()
    return _budget_service
