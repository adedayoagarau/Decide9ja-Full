"""
Enhanced RAG Service v3 - Improved Retrieval-Augmented Generation.
Based on NVIDIA RAG 101 best practices + structured KB integration.

Improvements:
1. Query preprocessing with intent detection
2. Document type boosting (structured cards prioritized)
3. Hybrid search (semantic + keyword BM25)
4. Reranking with document type awareness
5. Structured context formatting by doc type
6. Issue and news integration
"""
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json
import logging
import re

from app.database import Document, Politician, NewsArticle
from app.services.embeddings import get_embedding, cosine_similarity, json_to_embedding

logger = logging.getLogger(__name__)


# Document type priorities (higher = better for canonical answers)
DOC_TYPE_PRIORITY = {
    "politician_card": 1.0,       # Best for "who is" queries
    "jurisdiction_card": 1.0,     # Best for "my representative" queries
    "issue_dossier": 0.95,        # Best for "what's happening" queries
    "procedure_pack": 0.95,       # Best for "how do I" queries
    "governor": 0.85,             # Legacy but useful
    "senator": 0.85,
    "house_member": 0.85,
    "election_result": 0.80,
    "poll": 0.70,
}

# Query intent patterns
INTENT_PATTERNS = {
    "representative": {
        "patterns": ["who is my", "who represents", "my senator", "my rep", "my governor", "representatives in"],
        "boost_types": ["jurisdiction_card", "politician_card", "senator", "house_member", "governor"],
    },
    "politician_info": {
        "patterns": ["who is", "tell me about", "profile of", "what do you know about"],
        "boost_types": ["politician_card", "governor", "senator", "house_member"],
    },
    "issue_tracking": {
        "patterns": ["what is happening", "what's happening", "latest on", "news about", "update on", "status of"],
        "boost_types": ["issue_dossier", "politician_card"],
    },
    "civic_procedure": {
        "patterns": ["how do i", "how to", "steps to", "register to vote", "collect pvc", "find polling"],
        "boost_types": ["procedure_pack"],
    },
    "election": {
        "patterns": ["election result", "who won", "votes for", "2023 election", "election in", "zabe", "ibo"],
        "boost_types": ["election_result", "jurisdiction_card", "politician_card"],
    },
}

# Cross-lingual mappings (Local -> English Concept)
CROSS_LINGUAL_MAPPINGS = {
    # Hausa
    "zabe": "election vote",
    "kudi": "money budget allocation",
    "shugaba": "president leader",
    "gwamna": "governor",
    "majalisar": "assembly parliament house",
    "sanata": "senator",
    
    # Yoruba
    "owo": "money budget allocation",
    "ibo": "election vote",
    "aare": "president",
    "gomina": "governor",
    "ile igbimo": "assembly parliament house",
    
    # Igbo
    "ego": "money budget allocation",
    "ndu": "leader president",
    "onye": "person who",
    "gomenti": "government",
}


class EnhancedRAGService:
    """
    Enhanced RAG with structured KB integration.
    Prioritizes structured cards for canonical answers.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.max_context_tokens = 4000
        self.min_confidence_threshold = 0.25
        self.rerank_candidates = 15  # Get more, rerank to top 5
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
        language: str = "en",
    ) -> Tuple[str, List[Dict]]:
        """
        Enhanced retrieval with intent detection and document type boosting.
        
        Args:
            query: User's question
            top_k: Number of documents to return
            filters: Optional dict with state, party, position filters
            
        Returns:
            Tuple of (formatted_context_string, list_of_source_documents)
        """
        # Step 1: Detect query intent
        intent = self._detect_intent(query)
        
        # Step 2: Expand query based on intent
        expanded_query = self._preprocess_query(query, intent)
        
        # Step 3: Get candidates using hybrid search with type boosting
        candidates = self._hybrid_search(expanded_query, self.rerank_candidates, filters, intent, language)
        
        if not candidates:
            return "NO DATA FOUND for your query.", []
        
        # Step 4: Rerank with intent awareness
        reranked = self._rerank_results(candidates, query, intent, top_k, language)
        
        # Step 5: Format context by document type
        context, sources = self._format_context(reranked, intent)
        
        # Step 6: Add issue context if relevant
        if intent in ["issue_tracking", "politician_info"]:
            context = self._add_issue_context(query, context)
        
        # Step 7: Add news if relevant
        context = self._add_news_context(query, context)
        
        return context, sources
    
    def _detect_intent(self, query: str) -> str:
        """Detect user's query intent."""
        query_lower = query.lower()
        
        for intent, config in INTENT_PATTERNS.items():
            for pattern in config["patterns"]:
                if pattern in query_lower:
                    logger.debug(f"Detected intent: {intent}")
                    return intent
        
        return "general"
    
    def _preprocess_query(self, query: str, intent: str) -> str:
        """Preprocess and expand the query based on intent."""
        # Nigerian political terms expansion
        expansions = {
            "senator": "senator senatorial NASS national assembly senate",
            "representative": "representative house rep member NASS federal constituency",
            "governor": "governor state executive gubernatorial",
            "president": "president presidency aso rock federal tinubu",
            "power": "power electricity NEPA PHCN light grid outage blackout",
            "security": "security kidnapping bandits terrorism insecurity violence",
            "fuel": "fuel petrol PMS scarcity subsidy price",
            "vote": "vote voter registration PVC election INEC",
            "budget": "budget allocation spending fiscal appropriation",
        }
        
        query_lower = query.lower()
        entities = []
        
        for term, expansion in expansions.items():
            if term in query_lower:
                entities.append(expansion)
        
        # Add intent-specific terms
        if intent == "representative":
            entities.append("constituency senatorial district representative")
        elif intent == "civic_procedure":
            entities.append("INEC registration steps guide how to")
        elif intent == "issue_tracking":
            entities.append("latest update news development crisis")
            
        # Cross-lingual expansion
        for term, expansion in CROSS_LINGUAL_MAPPINGS.items():
            if term in query_lower:
                entities.append(expansion)
        
        if entities:
            return f"{query} {' '.join(entities)}"
        return query
    
    def _hybrid_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict],
        intent: str,
        language: str = "en"
    ) -> List[Tuple[float, Document]]:
        """Hybrid search with document type boosting."""
        query_embedding = get_embedding(query)
        
        docs_query = self.db.query(Document)
        
        # Apply filters
        if filters:
            if filters.get("state"):
                docs_query = docs_query.filter(Document.state.ilike(f"%{filters['state']}%"))
            if filters.get("party"):
                docs_query = docs_query.filter(Document.party == filters["party"])
            if filters.get("doc_type"):
                docs_query = docs_query.filter(Document.doc_type == filters["doc_type"])
        
        documents = docs_query.all()
        
        if not documents:
            return []
        
        # Calculate semantic scores
        semantic_scores = {}
        for doc in documents:
            if doc.embedding_json:
                doc_embedding = json_to_embedding(doc.embedding_json)
                semantic_scores[doc.doc_id] = cosine_similarity(query_embedding, doc_embedding)
            else:
                semantic_scores[doc.doc_id] = 0.0
        
        # Calculate keyword scores
        keyword_scores = self._keyword_score(query, documents)
        
        # Get intent-boosted types
        boost_types = INTENT_PATTERNS.get(intent, {}).get("boost_types", [])
        
        # Combine scores with type boost
        combined = []
        for doc in documents:
            semantic = semantic_scores.get(doc.doc_id, 0)
            keyword = keyword_scores.get(doc.doc_id, 0)
            
            # Base score: 70% semantic, 30% keyword
            base_score = (0.7 * semantic) + (0.3 * keyword)
            
            # Apply document type priority boost
            type_priority = DOC_TYPE_PRIORITY.get(doc.doc_type, 0.5)
            
            # Apply intent-specific boost
            intent_boost = 0.15 if doc.doc_type in boost_types else 0
            
            # Apply language boost (if available in doc)
            # Assuming Document model has 'language' attribute now
            lang_boost = 0.2 if getattr(doc, 'language', 'en') == language else 0
            
            final_score = base_score * type_priority + intent_boost + lang_boost
            combined.append((final_score, doc))
        
        # Sort and return top candidates
        combined.sort(key=lambda x: x[0], reverse=True)
        return combined[:limit]
    
    def _keyword_score(self, query: str, documents: List[Document]) -> Dict[str, float]:
        """Simple BM25-like keyword scoring."""
        query_terms = set(re.findall(r'\w+', query.lower()))
        scores = {}
        
        for doc in documents:
            text = f"{doc.title} {doc.content}".lower()
            doc_terms = set(re.findall(r'\w+', text))
            
            # Calculate term overlap
            overlap = len(query_terms & doc_terms)
            total_terms = len(query_terms)
            
            scores[doc.doc_id] = overlap / max(total_terms, 1)
        
        return scores
    
    def _rerank_results(
        self,
        candidates: List[Tuple[float, Document]],
        original_query: str,
        intent: str,
        top_k: int,
        language: str = "en"
    ) -> List[Tuple[float, Document]]:
        """Rerank candidates with intent awareness."""
        query_terms = set(re.findall(r'\w+', original_query.lower()))
        boost_types = INTENT_PATTERNS.get(intent, {}).get("boost_types", [])
        
        reranked = []
        for score, doc in candidates:
            # Title match boost
            title_terms = set(re.findall(r'\w+', doc.title.lower()))
            title_overlap = len(query_terms & title_terms) / max(len(query_terms), 1)
            title_boost = title_overlap * 0.15
            
            # Content freshness boost for cards
            freshness_boost = 0.05 if doc.doc_type in ["politician_card", "jurisdiction_card", "issue_dossier"] else 0
            
            # Intent alignment boost
            intent_alignment = 0.1 if doc.doc_type in boost_types else 0
            
            # Language match boost (reinforce during rerank)
            lang_match = 0.1 if getattr(doc, 'language', 'en') == language else 0
            
            boosted_score = score + title_boost + freshness_boost + intent_alignment + lang_match
            reranked.append((boosted_score, doc))
        
        reranked.sort(key=lambda x: x[0], reverse=True)
        return reranked[:top_k]
    
    def _format_context(
        self,
        results: List[Tuple[float, Document]],
        intent: str
    ) -> Tuple[str, List[Dict]]:
        """Format results with document type awareness."""
        context_parts = []
        sources = []
        
        # Group by document type for cleaner output
        type_labels = {
            "politician_card": "👤 POLITICIAN",
            "jurisdiction_card": "🏛️ JURISDICTION",
            "issue_dossier": "⚠️ ISSUE",
            "procedure_pack": "📋 GUIDE",
            "governor": "👤 GOVERNOR",
            "senator": "👤 SENATOR",
            "house_member": "👤 HOUSE REP",
            "election_result": "🗳️ ELECTION",
            "poll": "📊 POLL",
        }
        
        for score, doc in results:
            if score < self.min_confidence_threshold:
                continue
            
            # Get formatted type label
            type_label = type_labels.get(doc.doc_type, "📄 DOCUMENT")
            
            # Add header
            context_parts.append(f"─── {type_label}: {doc.title} ───")
            
            # Content limit based on type
            if doc.doc_type in ["politician_card", "jurisdiction_card"]:
                # Cards are concise, show full content
                context_parts.append(doc.content[:1200])
            elif doc.doc_type == "procedure_pack":
                # Show more for procedures
                context_parts.append(doc.content[:1500])
            elif doc.doc_type == "issue_dossier":
                # Issues need detail
                context_parts.append(doc.content[:1000])
            else:
                context_parts.append(doc.content[:600])
            
            # Add metadata line
            meta = {}
            if doc.metadata_json:
                try:
                    meta = json.loads(doc.metadata_json)
                except:
                    pass
            
            meta_parts = []
            if meta.get("party"):
                meta_parts.append(f"Party: {meta['party']}")
            if meta.get("state"):
                meta_parts.append(f"State: {meta['state']}")
            if meta.get("severity"):
                meta_parts.append(f"Severity: {meta['severity']}")
            if meta.get("source_type"):
                meta_parts.append(f"Type: {meta['source_type']}")
            
            if meta_parts:
                context_parts.append(f"[{' | '.join(meta_parts)}]")
            
            context_parts.append(f"[Relevance: {score:.2f}]\n")
            
            sources.append({
                "doc_id": doc.doc_id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "similarity": score,
                "metadata": meta
            })
        
        if not context_parts:
            return "NO RELEVANT DATA FOUND.", []
        
        return "\n".join(context_parts), sources
    
    def _add_issue_context(self, query: str, context: str) -> str:
        """Add active issues if relevant to query."""
        try:
            from app.database import Issue
            
            # Check for issue-related keywords
            issue_keywords = ["power", "security", "fuel", "economy", "governance", "health", "education"]
            query_lower = query.lower()
            
            for keyword in issue_keywords:
                if keyword in query_lower:
                    # Find related issues
                    issues = self.db.query(Issue).filter(
                        Issue.domain == keyword,
                        Issue.status == "active"
                    ).limit(2).all()
                    
                    if issues:
                        issue_context = "\n─── ACTIVE ISSUES ───\n"
                        for issue in issues:
                            issue_context += f"• {issue.title} ({issue.severity})\n"
                            if issue.summary:
                                issue_context += f"  {issue.summary[:150]}...\n"
                        return f"{context}\n{issue_context}"
        except Exception as e:
            logger.debug(f"Could not add issue context: {e}")
        
        return context
    
    def _add_news_context(self, query: str, context: str) -> str:
        """Add recent news if relevant."""
        try:
            from app.services.news_pipeline import get_news_context_for_rag
            news = get_news_context_for_rag(query, self.db, limit=3)
            if news:
                return f"{context}\n\n─── RECENT NEWS ───\n{news}"
        except Exception as e:
            logger.debug(f"Could not add news context: {e}")
        return context


def get_enhanced_rag_service(db: Session) -> EnhancedRAGService:
    """Factory function for enhanced RAG service."""
    return EnhancedRAGService(db)

