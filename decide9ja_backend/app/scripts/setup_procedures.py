import json
import logging
import uuid
from datetime import datetime
from app.database import SessionLocal, Document, init_db
from app.services.embeddings import get_embedding, embedding_to_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Core Procedures Data
PROCEDURES = [
    {
        "procedure_id": "voter-registration-guide",
        "title": "How to Register to Vote (CVR)",
        "category": "voter_registration",
        "summary": "Step-by-step guide on the Continuous Voter Registration (CVR) process in Nigeria.",
        "steps": [
            {
                "num": 1,
                "action": "Check Eligibility",
                "details": "You must be a Nigerian citizen, at least 18 years old, and live in or originate from the LGA where you want to register."
            },
            {
                "num": 2,
                "action": "Pre-Register Online (Optional)",
                "details": "Visit the INEC CVR portal (cvr.inecnigeria.org) to start your registration and schedule an appointment."
            },
            {
                "num": 3,
                "action": "Biometric Capture",
                "details": "Visit the designated INEC registration center for fingerprint and facial capture.",
                "docs": ["Birth Certificate or Declaration of Age", "Proof of Residence"]
            },
            {
                "num": 4,
                "action": "Collect TVC",
                "details": "You will be issued a Temporary Voter Card (TVC) as proof of registration."
            }
        ],
        "official_links": [
            {"title": "INEC CVR Portal", "url": "https://cvr.inecnigeria.org"}
        ]
    },
    {
        "procedure_id": "pvc-collection-guide",
        "title": "How to Collect Your Permanent Voter Card (PVC)",
        "category": "pvc",
        "summary": "Guide on checking PVC status and collecting your card from INEC.",
        "steps": [
            {
                "num": 1,
                "action": "Check PVC Status",
                "details": "Visit voters.inecnigeria.org and enter your details to confirm your PVC is ready and where it is located."
            },
            {
                "num": 2,
                "action": "Visit Pickup Location",
                "details": "Go to the INEC LGA office or designated collection center where you registered.",
                "docs": ["Temporary Voter Card (TVC)"]
            },
            {
                "num": 3,
                "action": "Verify and Sign",
                "details": "Verify the details on the PVC are correct before signing the collection register."
            }
        ],
        "official_links": [
            {"title": "Check Voter Status", "url": "https://voters.inecnigeria.org"}
        ]
    },
    {
        "procedure_id": "recall-process-guide",
        "title": "How to Recall a Senator or Rep Member",
        "category": "accountability",
        "summary": "Constitutional process for recalling an underperforming legislator (INEC Guidelines).",
        "steps": [
            {
                "num": 1,
                "action": "Petition Signing",
                "details": "A petition must be signed by more than 50% of registered voters in the member's constituency."
            },
            {
                "num": 2,
                "action": "Submit to INEC",
                "details": "Submit the petition to the INEC Chairman with signatures and voters card numbers."
            },
            {
                "num": 3,
                "action": "Verification",
                "details": "INEC verifies the signatures. If valid, a referendum is scheduled within 90 days."
            },
            {
                "num": 4,
                "action": "Referendum Vote",
                "details": "A simple majority (Yes vote) is needed to recall the member."
            }
        ],
        "official_links": [
            {"title": "INEC Recall Procedure", "url": "https://inecnigeria.org"}
        ]
    },
    {
        "procedure_id": "report-election-issue",
        "title": "How to Report Election Irregularities",
        "category": "reporting",
        "summary": "Steps to safely and effectively report issues like violence, rigging, or logistical failures.",
        "steps": [
            {
                "num": 1,
                "action": "Document Evidence",
                "details": "Take photos or videos if safe to do so. Note the Polling Unit Code and time."
            },
            {
                "num": 2,
                "action": "Use INEC IReV",
                "details": "Check if results uploaded to IReV match what you see."
            },
            {
                "num": 3,
                "action": "Contact Authorities",
                "details": "Call the INEC Situation Room or Police hotline.",
                "docs": ["Photo/Video Evidence", "PU Location"]
            },
            {
                "num": 4,
                "action": "Report to Decide9ja",
                "details": "Send a message to our WhatsApp bot describing the issue and location."
            }
        ],
        "official_links": []
    }
]

def generate_procedure_card(procedure):
    """Generate Markdown content for a procedure."""
    lines = []
    lines.append(f"# Procedure: {procedure['title']}")
    lines.append(f"**Category:** {procedure['category'].replace('_', ' ').title()}")
    lines.append(f"**Summary:** {procedure['summary']}")
    lines.append("")
    lines.append("## Steps")
    
    for step in procedure['steps']:
        lines.append(f"### Step {step['num']}: {step['action']}")
        lines.append(step['details'])
        if "docs" in step:
            docs_str = ", ".join(step["docs"])
            lines.append(f"- *Required Documents: {docs_str}*")
        lines.append("")
        
    if procedure.get("official_links"):
        lines.append("## Official Resources")
        for link in procedure["official_links"]:
            lines.append(f"- [{link['title']}]({link['url']})")
    
    lines.append("")
    lines.append("---")
    lines.append(f"*Source: Decide9ja Civic Guide | Verified: {datetime.now().strftime('%Y-%m-%d')}*")
    
    return "\n".join(lines)

def bootstrap_procedures():
    db = SessionLocal()
    try:
        logger.info("Bootstrapping Procedure Packs...")
        count = 0
        
        for data in PROCEDURES:
            content = generate_procedure_card(data)
            
            # Metadata
            metadata = {
                "source_type": "procedure_pack",
                "procedure_id": data["procedure_id"],
                "category": data["category"],
                "valid_from": datetime.now().year
            }
            
            # Embedding
            embedding = get_embedding(content)
            
            # Upsert
            doc_id = f"proc_{data['procedure_id']}"
            existing = db.query(Document).filter(Document.doc_id == doc_id).first()
            
            if existing:
                existing.content = content
                existing.embedding_json = embedding_to_json(embedding)
                existing.metadata_json = json.dumps(metadata)
                existing.title = data["title"]
            else:
                doc = Document(
                    doc_id=doc_id,
                    title=data["title"],
                    content=content,
                    doc_type="procedure_pack",
                    embedding_json=embedding_to_json(embedding),
                    metadata_json=json.dumps(metadata),
                    state="National"
                )
                db.add(doc)
            count += 1
            
        db.commit()
        logger.info(f"Successfully created {count} Procedure Packs.")
        
    except Exception as e:
        logger.error(f"Failed to create procedures: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    bootstrap_procedures()
