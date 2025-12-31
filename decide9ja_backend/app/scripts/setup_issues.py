import json
import logging
import uuid
from datetime import datetime
from app.database import SessionLocal, Issue, IssueEvent, PoliticianIssue, Document, init_db, Politician
from app.services.embeddings import get_embedding, embedding_to_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Core Issues Data (Seed)
CORE_ISSUES = [
    {
        "issue_id": "fuel-subsidy-removal",
        "title": "Fuel Subsidy Removal",
        "domain": "economy",
        "severity": "critical",
        "status": "active",
        "location": "Nationwide",
        "summary": "The removal of the Premium Motor Spirit (PMS) subsidy by the Federal Government in May 2023, leading to a triping of petrol prices and increased cost of living.",
        "states": [],
        "events": [
            {
                "title": "President Announces Subsidy Removal",
                "date": "2023-05-29",
                "description": "In his inaugural address, President Bola Tinubu declared 'Subsidy is gone', citing budget sustainability.",
                "type": "statement"
            },
            {
                "title": "NLC Threatens Strike",
                "date": "2023-06-02",
                "description": "Nigeria Labour Congress (NLC) issued ultimatum over fuel price hike.",
                "type": "action"
            }
        ],
        "linked_politicians": [
            {"slug": "bola-tinubu", "role": "responsible"}
        ]
    },
    {
        "issue_id": "naira-forex-crisis",
        "title": "Naira Devaluation and Forex Crisis",
        "domain": "economy",
        "severity": "critical",
        "status": "active",
        "location": "Nationwide",
        "summary": "The floating of the Naira by the CBN has led to a significant devaluation against the Dollar, driving inflation and gathering economic instability.",
        "states": [],
        "events": [
            {
                "title": "CBN Unifies Exchange Rates",
                "date": "2023-06-14",
                "description": "The Central Bank of Nigeria abolished segmentation, allowing the Naira to float.",
                "type": "policy"
            }
        ],
        "linked_politicians": [
             {"slug": "bola-tinubu", "role": "responsible"}
             # Yemi Cardoso (CBN gov) might not be in our politician DB of elected officials
        ]
    },
    {
        "issue_id": "insecurity-north-west",
        "title": "Banditry in North West",
        "domain": "security",
        "severity": "severe",
        "status": "active",
        "location": "North West Zone",
        "summary": "Persistent attacks by armed bandits in Zamfara, Kaduna, Katsina, and Sokoto involving kidnapping for ransom and cattle rustling.",
        "states": ["Zamfara", "Kaduna", "Katsina", "Sokoto", "Kebbi"],
        "events": [],
        "linked_politicians": [
             # Governors would be linked dynamically if slugs match
        ]
    },
    {
        "issue_id": "national-grid-collapse",
        "title": "Frequent National Grid Collapse",
        "domain": "power",
        "severity": "severe",
        "status": "active",
        "location": "Nationwide",
        "summary": "Repeated total and partial collapses of the national electricity grid causing blackouts across the country.",
        "states": [],
        "events": [
            {
                "title": "Grid Collapses Again",
                "date": "2024-02-04",
                "description": "Power generation dropped to 0MW forcing a nationwide blackout.",
                "type": "news"
            }
        ],
        "linked_politicians": []
    },
    {
        "issue_id": "japa-syndrome",
        "title": "Japa (Brain Drain)",
        "domain": "social",
        "severity": "moderate",
        "status": "active",
        "location": "Nationwide",
        "summary": "Mass emigration of skilled professionals, particularly doctors and tech workers, seeking better opportunities abroad.",
        "states": [],
        "events": [],
        "linked_politicians": []
    }
]

def bootstrap_issues():
    db = SessionLocal()
    try:
        logger.info("Bootstrapping Core Issues...")
        
        for data in CORE_ISSUES:
            # 1. Upsert Issue
            issue = db.query(Issue).filter(Issue.issue_id == data["issue_id"]).first()
            if not issue:
                issue = Issue(
                    issue_id=data["issue_id"],
                    title=data["title"],
                    domain=data["domain"],
                    severity=data["severity"],
                    status=data["status"],
                    location=data["location"],
                    states_json=json.dumps(data.get("states", [])),
                    summary=data["summary"],
                    first_reported=datetime.now(),
                    confidence=1.0,
                    verified=True
                )
                db.add(issue)
                db.flush() # Get ID
            
            # 2. Upsert Events
            for evt in data.get("events", []):
                evt_id = f"evt_{uuid.uuid4().hex[:8]}"
                # Simple check duplication by title for seed data
                exists = db.query(IssueEvent).filter(IssueEvent.issue_id==issue.issue_id, IssueEvent.title==evt["title"]).first()
                if not exists:
                    new_evt = IssueEvent(
                        event_id=evt_id,
                        issue_id=issue.issue_id,
                        title=evt["title"],
                        description=evt["description"],
                        event_date=datetime.strptime(evt["date"], "%Y-%m-%d"),
                        event_type=evt["type"],
                        source_name="Decide9ja History",
                        verified=True
                    )
                    db.add(new_evt)
            
            # 3. Link Politicians
            for link in data.get("linked_politicians", []):
                # Verify politician exists
                pol = db.query(Politician).filter(Politician.slug == link["slug"]).first()
                if pol:
                    p_link = db.query(PoliticianIssue).filter(
                        PoliticianIssue.politician_slug == link["slug"],
                        PoliticianIssue.issue_id == issue.issue_id
                    ).first()
                    if not p_link:
                        new_p = PoliticianIssue(
                            politician_slug=link["slug"],
                            issue_id=issue.issue_id,
                            role=link["role"]
                        )
                        db.add(new_p)
            
            # 4. Generate RAG Card
            generate_rag_card(db, issue)
            
        db.commit()
        logger.info("Issues Bootstrapped Successfully.")
        
    except Exception as e:
        logger.error(f"Bootstrap failed: {e}")
        db.rollback()
    finally:
        db.close()

def generate_rag_card(db, issue):
    """Generate Markdown Dossier and save to Document store."""
    
    # Fetch related data
    events = db.query(IssueEvent).filter(IssueEvent.issue_id == issue.issue_id).order_by(IssueEvent.event_date).all()
    pol_links = db.query(PoliticianIssue).filter(PoliticianIssue.issue_id == issue.issue_id).all()
    
    lines = []
    lines.append(f"# Issue Dossier: {issue.title}")
    lines.append(f"**Domain:** {issue.domain.title()} | **Severity:** {issue.severity.upper()} | **Status:** {issue.status.title()}")
    lines.append(f"**Location:** {issue.location}")
    lines.append("")
    lines.append(f"## Summary")
    lines.append(issue.summary)
    lines.append("")
    
    if events:
        lines.append("## Timeline")
        for e in events:
            date_str = e.event_date.strftime("%Y-%m-%d") if e.event_date else "Unknown Date"
            lines.append(f"- **{date_str}:** {e.title} - {e.description}")
        lines.append("")
        
    if pol_links:
        lines.append("## Key Associated Figures")
        for link in pol_links:
            pol = db.query(Politician).filter(Politician.slug == link.politician_slug).first()
            if pol:
                lines.append(f"- **{pol.name}** ({pol.position}): {link.role.title()}")
    
    lines.append("")
    lines.append("---")
    lines.append(f"*Source: Decide9ja Issue Tracker | Confidence: {issue.confidence*100:.0f}%*")
    
    content = "\n".join(lines)
    
    # Metadata
    metadata = {
        "source_type": "issue_dossier",
        "issue_id": issue.issue_id,
        "domain": issue.domain,
        "severity": issue.severity,
        "year": datetime.now().year
    }
    
    # Embedding
    embedding = get_embedding(content)
    
    # Upsert Document
    doc_id = f"issue_{issue.issue_id}"
    existing = db.query(Document).filter(Document.doc_id == doc_id).first()
    
    if existing:
        existing.content = content
        existing.embedding_json = embedding_to_json(embedding)
        existing.metadata_json = json.dumps(metadata)
        existing.title = issue.title
    else:
        doc = Document(
            doc_id=doc_id,
            title=issue.title,
            content=content,
            doc_type="issue_dossier",
            embedding_json=embedding_to_json(embedding),
            metadata_json=json.dumps(metadata),
            state="National" # Or specific
        )
        db.add(doc)

if __name__ == "__main__":
    init_db()
    bootstrap_issues()
