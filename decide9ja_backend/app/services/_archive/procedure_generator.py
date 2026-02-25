"""
Procedure Pack Generator for RAG Knowledge Base.
Creates step-by-step guides for civic actions.

Pack Types:
1. Voter Registration
2. PVC Collection
3. Polling Unit Verification
4. Issue Reporting
5. FOIA Requests
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from app.database import SessionLocal, Document
from app.services.embeddings import get_embedding, embedding_to_json

logger = logging.getLogger(__name__)


@dataclass
class ProcedureStep:
    """A single step in a procedure."""
    step_number: int
    action: str
    details: str
    documents_required: List[str] = field(default_factory=list)
    expected_duration: str = ""
    tips: str = ""


@dataclass
class ProcedurePack:
    """A complete procedure guide."""
    procedure_id: str
    title: str
    category: str
    description: str
    
    # Applicability
    nationwide: bool = True
    states: List[str] = field(default_factory=list)
    
    # Validity
    valid_from: str = "2024-01-01"
    valid_to: Optional[str] = None
    
    # Steps
    steps: List[ProcedureStep] = field(default_factory=list)
    
    # Requirements
    eligibility: List[str] = field(default_factory=list)
    documents_required: List[str] = field(default_factory=list)
    
    # Links
    official_links: List[Dict] = field(default_factory=list)
    
    # FAQ
    common_issues: List[Dict] = field(default_factory=list)
    
    # Metadata
    last_verified: str = ""
    source: str = "INEC"
    
    def to_rag_document(self) -> str:
        """Convert to RAG-optimized document."""
        lines = []
        
        # Header
        lines.append(f"# {self.title}")
        lines.append(f"*Category: {self.category.replace('_', ' ').title()}*")
        lines.append("")
        
        # Description
        lines.append(self.description)
        lines.append("")
        
        # Eligibility
        if self.eligibility:
            lines.append("## Who Can Apply")
            for req in self.eligibility:
                lines.append(f"- {req}")
            lines.append("")
        
        # Documents Required
        if self.documents_required:
            lines.append("## Documents Required")
            for doc in self.documents_required:
                lines.append(f"- {doc}")
            lines.append("")
        
        # Steps
        if self.steps:
            lines.append("## Steps to Follow")
            for step in self.steps:
                lines.append(f"### Step {step.step_number}: {step.action}")
                lines.append(step.details)
                if step.documents_required:
                    lines.append(f"*Required: {', '.join(step.documents_required)}*")
                if step.expected_duration:
                    lines.append(f"*Duration: {step.expected_duration}*")
                if step.tips:
                    lines.append(f"💡 **Tip:** {step.tips}")
                lines.append("")
        
        # Official Links
        if self.official_links:
            lines.append("## Official Resources")
            for link in self.official_links:
                lines.append(f"- [{link.get('title', 'Link')}]({link.get('url', '')})")
            lines.append("")
        
        # Common Issues
        if self.common_issues:
            lines.append("## Common Issues & Solutions")
            for issue in self.common_issues:
                lines.append(f"**Q: {issue.get('issue', '')}**")
                lines.append(f"A: {issue.get('solution', '')}")
                lines.append("")
        
        # Applicability
        if not self.nationwide and self.states:
            lines.append(f"*This procedure applies to: {', '.join(self.states)}*")
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Source: {self.source} | Valid from: {self.valid_from} | Last verified: {self.last_verified}*")
        
        return "\n".join(lines)
    
    def get_search_text(self) -> str:
        """Get text optimized for embedding."""
        terms = [
            self.title,
            self.category.replace("_", " "),
            self.description[:100],
            f"how to {self.title.lower()}",
            f"steps for {self.category.replace('_', ' ')}",
        ]
        
        # Add step actions as search terms
        for step in self.steps:
            terms.append(step.action)
        
        return " | ".join([t for t in terms if t])


def create_procedure_packs() -> List[ProcedurePack]:
    """Create all procedure packs."""
    packs = []
    now = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Voter Registration
    voter_reg = ProcedurePack(
        procedure_id="voter_registration",
        title="How to Register to Vote in Nigeria",
        category="voter_registration",
        description="This guide explains how to register as a voter in Nigeria with the Independent National Electoral Commission (INEC). Registration is free and gives you the right to vote in elections.",
        nationwide=True,
        valid_from="2024-01-01",
        eligibility=[
            "Nigerian citizen by birth or naturalization",
            "At least 18 years old",
            "Not mentally incapacitated",
            "Not previously registered",
        ],
        documents_required=[
            "Valid means of identification (NIN, Driver's License, or International Passport)",
            "Proof of address (utility bill or letter from employer/community leader)",
        ],
        steps=[
            ProcedureStep(
                step_number=1,
                action="Visit INEC CVR Portal or Office",
                details="Go to cvr.inecnigeria.org to pre-register online, or visit your nearest INEC local government office during working hours (8am-4pm, Monday-Friday).",
                expected_duration="Online: 10-15 minutes",
                tips="Pre-registering online saves time at the INEC office."
            ),
            ProcedureStep(
                step_number=2,
                action="Complete Registration Form",
                details="Fill out the Voter Registration Form (EC-01) with your personal details including full name, date of birth, address, and National Identification Number (NIN).",
                documents_required=["NIN", "Proof of address"],
                tips="Double-check all spellings and dates before submitting."
            ),
            ProcedureStep(
                step_number=3,
                action="Biometric Capture",
                details="At the INEC office, officials will capture your photograph and fingerprints. This is mandatory and cannot be done online.",
                expected_duration="15-30 minutes",
                tips="Wear plain clothes without caps or sunglasses."
            ),
            ProcedureStep(
                step_number=4,
                action="Claim Your PVC",
                details="After about 2-4 weeks, check the INEC website or visit your registration center to confirm your PVC is ready, then collect it.",
                expected_duration="2-4 weeks processing",
                tips="Keep your registration slip safe as you'll need it to collect your PVC."
            ),
        ],
        official_links=[
            {"title": "INEC CVR Portal", "url": "https://cvr.inecnigeria.org"},
            {"title": "INEC Official Website", "url": "https://www.inecnigeria.org"},
            {"title": "Find INEC Office Near You", "url": "https://www.inecnigeria.org/contact-us"},
        ],
        common_issues=[
            {
                "issue": "I don't have a NIN. Can I still register?",
                "solution": "No, NIN is now mandatory for voter registration. Visit NIMC to enroll for NIN first at nimc.gov.ng."
            },
            {
                "issue": "The INEC website is not working.",
                "solution": "You can still register by visiting your local INEC office directly. Pre-registration online is optional."
            },
            {
                "issue": "I've moved to a new state. What do I do?",
                "solution": "You need to apply for voter transfer at an INEC office in your new location. Bring your PVC and proof of new address."
            },
        ],
        last_verified=now,
        source="INEC Official Guidelines",
    )
    packs.append(voter_reg)
    
    # 2. PVC Collection
    pvc_collection = ProcedurePack(
        procedure_id="pvc_collection",
        title="How to Collect Your Permanent Voter's Card (PVC)",
        category="pvc",
        description="After registering to vote, you need to collect your Permanent Voter's Card (PVC) to be able to vote on election day. This guide explains how to check and collect your PVC.",
        nationwide=True,
        valid_from="2024-01-01",
        eligibility=[
            "Completed voter registration with INEC",
            "Biometric capture completed",
        ],
        documents_required=[
            "Voter registration slip",
            "Valid ID (NIN, Driver's License, or Passport)",
        ],
        steps=[
            ProcedureStep(
                step_number=1,
                action="Check PVC Status Online",
                details="Visit verify.inecnigeria.org and enter your VIN (Voter Identification Number) to check if your PVC is ready for collection.",
                expected_duration="2 minutes",
                tips="Your VIN is on your registration slip."
            ),
            ProcedureStep(
                step_number=2,
                action="Locate Collection Center",
                details="INEC will announce collection centers, usually at your local government INEC office or designated distribution points.",
                tips="Follow INEC announcements on social media or radio for specific dates."
            ),
            ProcedureStep(
                step_number=3,
                action="Visit During Distribution Period",
                details="Bring your registration slip and valid ID. INEC will verify your identity using the biometric system and hand over your PVC.",
                expected_duration="15-45 minutes (depending on queue)",
                documents_required=["Registration slip", "Valid ID"],
            ),
            ProcedureStep(
                step_number=4,
                action="Verify Your PVC Details",
                details="Check that your name, photo, and polling unit are correct on the PVC before leaving. Report any errors immediately.",
                tips="Do not laminate your PVC as this may damage the chip."
            ),
        ],
        official_links=[
            {"title": "Check PVC Status", "url": "https://verify.inecnigeria.org"},
            {"title": "INEC Official Website", "url": "https://www.inecnigeria.org"},
        ],
        common_issues=[
            {
                "issue": "My PVC shows 'Not Ready'.",
                "solution": "Wait a few more weeks and check again. Processing can take 4-8 weeks. If issue persists, visit your INEC office."
            },
            {
                "issue": "I lost my registration slip.",
                "solution": "You can still collect your PVC with valid ID. INEC can verify you through biometrics."
            },
            {
                "issue": "My name is misspelled on my PVC.",
                "solution": "Visit your INEC office to request correction. Bring supporting documents showing correct spelling."
            },
        ],
        last_verified=now,
        source="INEC Official Guidelines",
    )
    packs.append(pvc_collection)
    
    # 3. Find Your Polling Unit
    polling_unit = ProcedurePack(
        procedure_id="find_polling_unit",
        title="How to Find Your Polling Unit",
        category="voting",
        description="Your polling unit is where you go to vote on election day. This guide helps you find and verify your assigned polling unit.",
        nationwide=True,
        valid_from="2024-01-01",
        eligibility=[
            "Registered voter with PVC",
        ],
        documents_required=[
            "Your PVC (shows polling unit code)",
            "Voter Identification Number (VIN)",
        ],
        steps=[
            ProcedureStep(
                step_number=1,
                action="Check Your PVC",
                details="Your PVC has a Polling Unit (PU) code printed on it. This is your assigned voting location.",
                tips="The format is typically: State/LGA/Registration Area/Polling Unit."
            ),
            ProcedureStep(
                step_number=2,
                action="Use INEC Polling Unit Finder",
                details="Visit votersvalidation.inecnigeria.org and enter your VIN to see your polling unit details including the address.",
                expected_duration="2 minutes",
            ),
            ProcedureStep(
                step_number=3,
                action="Visit Before Election Day",
                details="If possible, visit your polling unit before election day to know the exact location and how to get there.",
                tips="Polling opens at 8:30am. Arrive early on election day."
            ),
        ],
        official_links=[
            {"title": "INEC Voter Validation", "url": "https://votersvalidation.inecnigeria.org"},
            {"title": "INEC Official Website", "url": "https://www.inecnigeria.org"},
        ],
        common_issues=[
            {
                "issue": "I can't find my polling unit location.",
                "solution": "Ask locals in the area or contact INEC's helpline. Most polling units are at schools, churches, or community halls."
            },
            {
                "issue": "I've moved but my polling unit is in my old area.",
                "solution": "You must vote at your registered polling unit or apply for voter transfer before the next election."
            },
        ],
        last_verified=now,
        source="INEC Official Guidelines",
    )
    packs.append(polling_unit)
    
    # 4. Report Election Issues
    election_reporting = ProcedurePack(
        procedure_id="election_reporting",
        title="How to Report Election Irregularities",
        category="reporting",
        description="If you witness election malpractice, violence, or irregularities on election day, you can report to official bodies. This guide explains how.",
        nationwide=True,
        valid_from="2024-01-01",
        steps=[
            ProcedureStep(
                step_number=1,
                action="Document the Incident",
                details="If safe to do so, note the time, location, description of incident, and people involved. Take photos or videos if possible.",
                tips="Your safety comes first. Only record if it won't put you at risk."
            ),
            ProcedureStep(
                step_number=2,
                action="Report to INEC",
                details="Call INEC's election day hotline or visit their social media. Provide details of the incident and your polling unit.",
                tips="INEC: @inaborenig on X (Twitter)"
            ),
            ProcedureStep(
                step_number=3,
                action="Report to Civil Society",
                details="Report to election observer organizations like YIAGA Africa, TMG, or NDI who monitor elections and can amplify reports.",
                tips="YIAGA: @ABORENIYELECTION"
            ),
            ProcedureStep(
                step_number=4,
                action="Report to Security Agencies",
                details="For violence or threats, contact the police (112) or other security agencies.",
                tips="Keep yourself safe first."
            ),
        ],
        official_links=[
            {"title": "INEC Nigeria", "url": "https://twitter.com/inaborenig"},
            {"title": "YIAGA Africa", "url": "https://yiaga.org/report"},
            {"title": "Nigeria Police Emergency", "url": "tel:112"},
        ],
        common_issues=[
            {
                "issue": "I'm afraid to report because I might be targeted.",
                "solution": "Report anonymously through YIAGA or TMG platforms. You don't have to give your name."
            },
            {
                "issue": "The polling officials are the ones committing the offense.",
                "solution": "Report to INEC headquarters or civil society organizations, not to the officials at the same location."
            },
        ],
        last_verified=now,
        source="INEC, YIAGA Africa Guidelines",
    )
    packs.append(election_reporting)
    
    return packs


def save_procedure_packs_to_rag(packs: List[ProcedurePack], db_session=None) -> int:
    """Save procedure packs to RAG document store."""
    if db_session is None:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        count = 0
        
        for pack in packs:
            doc_id = f"procedure_pack_{pack.procedure_id}"
            content = pack.to_rag_document()
            search_text = pack.get_search_text()
            
            embedding = get_embedding(f"{search_text}\n\n{content}")
            embedding_json = embedding_to_json(embedding)
            
            metadata = {
                "source_type": "procedure_pack",
                "procedure_id": pack.procedure_id,
                "category": pack.category,
                "nationwide": pack.nationwide,
                "valid_from": pack.valid_from,
                "step_count": len(pack.steps),
            }
            
            existing = db_session.query(Document).filter(Document.doc_id == doc_id).first()
            if existing:
                existing.title = f"Guide: {pack.title}"
                existing.content = content
                existing.doc_type = "procedure_pack"
                existing.embedding_json = embedding_json
                existing.metadata_json = json.dumps(metadata)
            else:
                doc = Document(
                    doc_id=doc_id,
                    title=f"Guide: {pack.title}",
                    content=content,
                    doc_type="procedure_pack",
                    embedding_json=embedding_json,
                    metadata_json=json.dumps(metadata),
                )
                db_session.add(doc)
            count += 1
        
        db_session.commit()
        logger.info(f"Saved {count} procedure packs to RAG")
        return count
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to save procedure packs: {e}")
        raise
        
    finally:
        if should_close:
            db_session.close()


def run_procedure_generation():
    """Run procedure pack generation."""
    print("=== PROCEDURE PACK GENERATION ===")
    print()
    
    print("Step 1: Creating procedure packs...")
    packs = create_procedure_packs()
    print(f"  Created {len(packs)} packs")
    for pack in packs:
        print(f"    - {pack.title} ({len(pack.steps)} steps)")
    
    print()
    print("Step 2: Sample pack:")
    print("-" * 50)
    print(packs[0].to_rag_document()[:1500])
    print("...")
    print("-" * 50)
    
    print()
    print("Step 3: Saving to RAG document store...")
    count = save_procedure_packs_to_rag(packs)
    print(f"  Saved {count} packs")
    
    print()
    print("=== COMPLETE ===")
    return count


if __name__ == "__main__":
    run_procedure_generation()
