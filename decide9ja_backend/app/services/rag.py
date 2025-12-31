"""
RAG Service - Retrieval-Augmented Generation.
Retrieves relevant documents for a query using semantic search.
"""
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
import json

from app.database import Document, Politician
from app.services.embeddings import get_embedding, cosine_similarity, json_to_embedding


class RAGService:
    """
    Retrieves relevant context from the knowledge base.
    CRITICAL: The LLM only sees what this service returns.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.max_context_tokens = 3000  # Approximate limit for Claude context
        self.web_search_enabled = True  # Enable web search fallback
        self.min_confidence_threshold = 0.5  # Trigger web search below this
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
        include_web_search: bool = True
    ) -> Tuple[str, List[Dict]]:
        """
        Main retrieval function.
        
        Args:
            query: User's question
            top_k: Number of documents to retrieve
            filters: Optional dict with state, party, position filters
            
        Returns:
            Tuple of (formatted_context_string, list_of_source_documents)
        """
        # Generate query embedding
        query_embedding = get_embedding(query)
        
        # Get all documents (in production, use vector DB with index)
        docs_query = self.db.query(Document)
        
        # Apply filters if provided
        if filters:
            if filters.get("state"):
                docs_query = docs_query.filter(Document.state.ilike(f"%{filters['state']}%"))
            if filters.get("party"):
                docs_query = docs_query.filter(Document.party == filters["party"])
            if filters.get("position"):
                docs_query = docs_query.filter(Document.position.ilike(f"%{filters['position']}%"))
            if filters.get("doc_type"):
                docs_query = docs_query.filter(Document.doc_type == filters["doc_type"])
        
        documents = docs_query.all()
        
        if not documents:
            return "NO DATA FOUND: The database is empty.", []
        
        # Calculate similarities
        scored_docs = []
        for doc in documents:
            if doc.embedding_json:
                doc_embedding = json_to_embedding(doc.embedding_json)
                similarity = cosine_similarity(query_embedding, doc_embedding)
                scored_docs.append((similarity, doc))
        
        # Sort by similarity (descending)
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Take top_k
        top_docs = scored_docs[:top_k]
        
        if not top_docs:
            return "NO RELEVANT DATA FOUND for your query.", []
        
        # Format context
        context_parts = []
        sources = []
        
        for similarity, doc in top_docs:
            if similarity < 0.3:  # Threshold for relevance
                continue
                
            context_parts.append(f"=== [{doc.doc_type.upper()}] {doc.title} ===")
            context_parts.append(doc.content)
            
            # Add metadata if available
            if doc.metadata_json:
                try:
                    meta = json.loads(doc.metadata_json)
                    if meta.get("party"):
                        context_parts.append(f"Party: {meta['party']}")
                    if meta.get("state"):
                        context_parts.append(f"State: {meta['state']}")
                except:
                    pass
            
            context_parts.append(f"[Relevance: {similarity:.2f}]\n")
            
            sources.append({
                "doc_id": doc.doc_id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "similarity": similarity
            })
        
        if not context_parts:
            return "NO RELEVANT DATA FOUND with sufficient confidence.", []
        
        context = "\n".join(context_parts)
        
        # Add recent news if available
        try:
            from app.services.news_pipeline import get_news_context_for_rag
            news_context = get_news_context_for_rag(query, self.db, limit=3)
            if news_context:
                context = f"{context}\n\n{news_context}"
        except Exception as e:
            # News module not available or error, continue without news
            pass
        
        return context, sources
    
    def find_politician(
        self,
        name: Optional[str] = None,
        state: Optional[str] = None,
        position: Optional[str] = None,
        constituency: Optional[str] = None
    ) -> List[Politician]:
        """
        Direct lookup of politicians by attributes.
        """
        query = self.db.query(Politician)
        
        if name:
            query = query.filter(Politician.name.ilike(f"%{name}%"))
        if state:
            query = query.filter(Politician.state.ilike(f"%{state}%"))
        if position:
            query = query.filter(Politician.position.ilike(f"%{position}%"))
        if constituency:
            query = query.filter(Politician.constituency.ilike(f"%{constituency}%"))
        
        return query.limit(10).all()
    
    def get_senator_by_district(self, state: str, district: str = None) -> Optional[str]:
        """
        Get senator for a specific state/district.
        E.g., "Lagos Central" -> Senator for Lagos Central
        """
        # Combine state and district for search
        search_term = f"{state} {district}".strip() if district else state
        
        politicians = self.find_politician(
            state=state,
            position="senator"
        )
        
        if not politicians:
            # Try searching in constituency
            politicians = self.db.query(Politician).filter(
                Politician.position.ilike("%senator%"),
                Politician.constituency.ilike(f"%{search_term}%")
            ).all()
        
        if not politicians:
            return None
        
        # Format response
        result = []
        for p in politicians:
            result.append(f"- {p.name} ({p.party}) - {p.constituency or p.state}")
        
        return "\n".join(result)


def get_rag_service(db: Session) -> RAGService:
    """Factory function for RAG service."""
    return RAGService(db)


async def retrieve_with_web_fallback(
    db: Session,
    query: str,
    top_k: int = 5,
    filters: Optional[Dict] = None
) -> Tuple[str, List[Dict], bool]:
    """
    Hybrid retrieval: DB first, then web search if confidence is low.
    
    Returns:
        Tuple of (context, sources, used_web_search)
    """
    import asyncio
    from app.services.web_search import search_web
    
    rag = RAGService(db)
    
    # First try database
    db_context, db_sources = rag.retrieve(query, top_k, filters)
    
    # Check if we got good results
    max_similarity = max([s.get("similarity", 0) for s in db_sources]) if db_sources else 0
    
    if max_similarity >= rag.min_confidence_threshold:
        # Good DB results, no need for web
        return db_context, db_sources, False
    
    # Low confidence or no results - try web search
    try:
        web_context, web_sources = await search_web(query)
        
        if web_context:
            # Combine DB and web results
            combined_context = db_context
            if combined_context and not combined_context.startswith("NO"):
                combined_context += "\n\n" + web_context
            else:
                combined_context = web_context
            
            # Merge sources
            for ws in web_sources:
                db_sources.append({
                    "doc_id": ws.get("url", ""),
                    "title": ws.get("title", ""),
                    "doc_type": "web_search",
                    "similarity": 0.0,
                    "source": ws.get("source", "")
                })
            
            return combined_context, db_sources, True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Web search failed: {e}")
    
    # Web search failed, return DB results anyway
    return db_context, db_sources, False
