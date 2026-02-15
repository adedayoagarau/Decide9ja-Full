"""
Knowledge Base Ingestion Script.
Ingests the nigeria_politics_knowledge_base.xlsx into RAG documents.

Creates source reference documents by category for:
1. News Sources - For verifying news provenance
2. Government Agencies - For official data sources
3. Civil Society - For watchdog/monitoring sources
4. Electoral Bodies - For election-related queries
5. Research Institutes - For policy/analysis sources
"""
import pandas as pd
import json
import logging
from typing import Dict, List
from datetime import datetime

import sys
sys.path.insert(0, '/Users/Admin/Decide9ja/decide9ja_backend')

from app.database import SessionLocal, Document
from app.services.embeddings import get_embedding, embedding_to_json

logger = logging.getLogger(__name__)


# Categories to ingest (most relevant for RAG)
RELEVANT_CATEGORIES = {
    "news_sources": {
        "doc_types": ["News Outlet"],
        "title": "Nigerian News Sources Reference",
        "description": "Authoritative news sources for Nigerian political information.",
    },
    "government_agencies": {
        "doc_types": ["Government Agency", "Government Portal", "Judiciary", "Legislature"],
        "title": "Nigerian Government Agencies Reference",
        "description": "Official government sources for data and policy information.",
    },
    "electoral_bodies": {
        "doc_types": ["Electoral Body"],
        "title": "Nigerian Electoral Bodies Reference",
        "description": "INEC and election-related sources for voting and election information.",
    },
    "civil_society": {
        "doc_types": ["Civil Society", "Research Institute"],
        "title": "Nigerian Civil Society and Research Organizations",
        "description": "NGOs, think tanks, and research organizations monitoring governance.",
    },
    "political_parties": {
        "doc_types": ["Political Party"],
        "title": "Nigerian Political Parties Reference",
        "description": "Official political party sources and information.",
    },
}


def load_excel_data(filepath: str) -> pd.DataFrame:
    """Load the knowledge base Excel file."""
    return pd.read_excel(filepath)


def create_category_document(category_key: str, config: Dict, df: pd.DataFrame) -> Dict:
    """Create a RAG document for a category of sources."""
    # Filter data
    category_df = df[df["Document Type"].isin(config["doc_types"])]
    
    if len(category_df) == 0:
        return None
    
    # Build document content
    lines = []
    lines.append(f"# {config['title']}")
    lines.append("")
    lines.append(config['description'])
    lines.append("")
    
    # Group by reliability tier
    for tier in ["Tier 1", "Tier 2"]:
        tier_df = category_df[category_df["Reliability Tier"] == tier]
        if len(tier_df) == 0:
            continue
        
        tier_label = "High Reliability (Tier 1)" if tier == "Tier 1" else "Standard Reliability (Tier 2)"
        lines.append(f"## {tier_label}")
        lines.append("")
        
        for _, row in tier_df.iterrows():
            name = row["Source Name"]
            entity = row["Entity"]
            link = row.get("Source Link", "")
            
            if pd.notna(link) and link:
                lines.append(f"- **{name}** ({entity}): {link}")
            else:
                lines.append(f"- **{name}** ({entity})")
        
        lines.append("")
    
    # Footer
    lines.append("---")
    lines.append(f"*Source: Nigeria Politics Knowledge Base | {len(category_df)} sources | Generated: {datetime.now().strftime('%Y-%m-%d')}*")
    
    content = "\n".join(lines)
    
    return {
        "doc_id": f"source_reference_{category_key}",
        "title": config["title"],
        "content": content,
        "doc_type": "source_reference",
        "source_count": len(category_df),
        "category": category_key,
    }


def save_documents_to_rag(documents: List[Dict], db_session=None) -> int:
    """Save source reference documents to RAG."""
    if db_session is None:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        saved = 0
        
        for doc in documents:
            if doc is None:
                continue
            
            # Generate embedding
            search_text = f"{doc['title']} {doc['category']} Nigerian sources reference"
            embedding = get_embedding(f"{search_text}\n\n{doc['content'][:2000]}")
            embedding_json = embedding_to_json(embedding)
            
            # Auto-detect language
            try:
                from langdetect import detect
                language = detect(doc["content"][:1000])
                if language not in ['en', 'ha', 'yo', 'ig', 'pidgin']:
                    language = 'en'
            except:
                language = 'en'
            
            metadata = {
                "source_type": "source_reference",
                "category": doc["category"],
                "source_count": doc["source_count"],
            }
            
            # Check if exists
            existing = db_session.query(Document).filter(Document.doc_id == doc["doc_id"]).first()
            
            if existing:
                existing.title = doc["title"]
                existing.content = doc["content"]
                existing.doc_type = "source_reference"
                existing.embedding_json = embedding_json
                existing.metadata_json = json.dumps(metadata)
                existing.language = language
            else:
                new_doc = Document(
                    doc_id=doc["doc_id"],
                    title=doc["title"],
                    content=doc["content"],
                    doc_type="source_reference",
                    embedding_json=embedding_json,
                    metadata_json=json.dumps(metadata),
                    language=language
                )
                db_session.add(new_doc)
            
            saved += 1
        
        db_session.commit()
        return saved
        
    except Exception as e:
        db_session.rollback()
        raise
        
    finally:
        if should_close:
            db_session.close()


def run_ingestion():
    """Run the full ingestion pipeline."""
    print("=== KNOWLEDGE BASE INGESTION ===")
    print()
    
    # Load data
    print("Step 1: Loading Excel file...")
    df = load_excel_data("/Users/Admin/Decide9ja/nigeria_politics_knowledge_base.xlsx")
    print(f"  Loaded {len(df)} sources")
    
    # Create documents
    print("\nStep 2: Creating category documents...")
    documents = []
    for cat_key, config in RELEVANT_CATEGORIES.items():
        doc = create_category_document(cat_key, config, df)
        if doc:
            print(f"  {cat_key}: {doc['source_count']} sources")
            documents.append(doc)
    
    # Show sample
    print("\nStep 3: Sample document:")
    if documents:
        print("-" * 50)
        print(documents[0]["content"][:800])
        print("...")
        print("-" * 50)
    
    # Save to RAG
    print("\nStep 4: Saving to RAG...")
    saved = save_documents_to_rag(documents)
    print(f"  Saved {saved} documents")
    
    print("\n=== COMPLETE ===")
    return saved


if __name__ == "__main__":
    run_ingestion()
