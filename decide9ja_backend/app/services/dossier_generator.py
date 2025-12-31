import json
import logging
from datetime import datetime
from typing import List, Dict

from app.database import SessionLocal, Issue, IssueEvent, PoliticianIssue, Document, Politician
from app.services.embeddings import get_embedding, embedding_to_json

logger = logging.getLogger(__name__)

def generate_issue_dossiers() -> List[Dict]:
    """
    Fetch all active issues and format them for the RAG system.
    Returns list of dicts with 'content', 'metadata', 'embedding_text'.
    """
    db = SessionLocal()
    dossiers = []
    
    try:
        # Fetch active issues
        issues = db.query(Issue).filter(Issue.status == "active").all()
        logger.info(f"Generating dossiers for {len(issues)} active issues")
        
        for issue in issues:
            dossier = _format_single_dossier(db, issue)
            dossiers.append(dossier)
            
        return dossiers
        
    except Exception as e:
        logger.error(f"Error generating dossiers: {e}")
        return []
    finally:
        db.close()


def _format_single_dossier(db, issue: Issue) -> Dict:
    """Format a single issue into text content."""
    
    # 1. Fetch Events
    events = db.query(IssueEvent).filter(
        IssueEvent.issue_id == issue.issue_id
    ).order_by(IssueEvent.event_date.desc()).all() # Newest first for reading, but Chronological for timeline? 
    # Usually Timeline is Chronological (Old -> New). 
    # But for a "Current Status" summary, Newest is better.
    # I'll do Reverse Chronological (Newest Top) for layout.
    
    # 2. Fetch Politicians
    links = db.query(PoliticianIssue).filter(
        PoliticianIssue.issue_id == issue.issue_id
    ).all()
    
    # 3. Build Markdown
    lines = []
    lines.append(f"# Issue Dossier: {issue.title}")
    lines.append(f"**Domain:** {issue.domain.title()} | **Severity:** {issue.severity.upper()}")
    lines.append(f"**Status:** {issue.status.title()} | **Last Updated:** {datetime.now().strftime('%Y-%m-%d')}")
    if issue.location:
        lines.append(f"**Location:** {issue.location}")
    
    lines.append("")
    lines.append("## Summary")
    lines.append(issue.summary or "No summary available.")
    lines.append("")
    
    # Recent Developments (Events)
    if events:
        lines.append("## Recent Developments (Timeline)")
        for e in events:
            date_str = e.event_date.strftime("%Y-%m-%d") if e.event_date else "Unknown"
            # Highlight verified events
            verified_mark = "✓ " if e.verified else ""
            lines.append(f"- **{date_str}:** {e.title} {verified_mark}")
            if e.description:
                lines.append(f"  * {e.description}")
            if e.source_name:
                lines.append(f"  *(Source: {e.source_name})*")
        lines.append("")
        
    # Key Figures
    if links:
        lines.append("## Key Political Figures")
        for link in links:
            pol = db.query(Politician).filter(Politician.slug == link.politician_slug).first()
            if pol:
                role_desc = link.role.replace("_", " ").title()
                lines.append(f"- **{pol.name}** ({pol.position}) - *{role_desc}*")
                # Could add specific actions if stored
    
    lines.append("")
    lines.append("---")
    lines.append(f"*Decide9ja Intelligence | Confidence Score: {int(issue.confidence * 100)}%*")
    
    content = "\n".join(lines)
    
    # 4. Prepare Metadata
    metadata = {
        "source_type": "issue_dossier",
        "issue_id": issue.issue_id,
        "domain": issue.domain,
        "severity": issue.severity,
        "last_updated": datetime.now().isoformat()
    }
    
    return {
        "doc_id": f"issue_{issue.issue_id}",
        "title": issue.title,
        "content": content,
        "metadata": metadata,
        "embedding_text": f"{issue.title} {issue.domain} {issue.summary} {issue.location}"
    }


def save_dossiers_to_rag(dossiers: List[Dict]):
    """Save formatted dossiers to Document table with embeddings."""
    if not dossiers:
        return
        
    db = SessionLocal()
    try:
        updated_count = 0
        
        for data in dossiers:
            doc_id = data["doc_id"]
            content = data["content"]
            metadata = data["metadata"]
            
            # Generate Embedding
            embedding = get_embedding(content) # Embed full content usually better for RAG context
            
            # Upsert
            existing = db.query(Document).filter(Document.doc_id == doc_id).first()
            
            if existing:
                existing.content = content
                existing.embedding_json = embedding_to_json(embedding)
                existing.metadata_json = json.dumps(metadata)
                existing.title = data["title"]
                existing.last_updated = datetime.now()
            else:
                doc = Document(
                    doc_id=doc_id,
                    title=data["title"],
                    content=content,
                    doc_type="issue_dossier",
                    embedding_json=embedding_to_json(embedding),
                    metadata_json=json.dumps(metadata),
                    state="National" # Broad scope
                )
                db.add(doc)
            
            updated_count += 1
            
        db.commit()
        logger.info(f"Successfully saved {updated_count} issue dossiers to RAG.")
        
    except Exception as e:
        logger.error(f"Failed to save dossiers: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Test run
    dossiers = generate_issue_dossiers()
    print(f"Generated {len(dossiers)} dossiers.")
    save_dossiers_to_rag(dossiers)
