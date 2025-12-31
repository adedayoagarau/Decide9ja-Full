"""
Setup Tax Reform Bills 2024/2025 - Current Legislation
Bootstrap script to ingest the controversial Tax Reform Bills into the RAG system.
"""
import os
import sys
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal, Document
from app.services.embeddings import get_embedding, embedding_to_json

TAX_REFORM_CONTENT = [
    {
        "title": "Tax Reform Bills 2024: Overview",
        "doc_type": "POLICY_EXPLAINER",
        "content": """# Nigeria Tax Reform Bills 2024/2025

**Status:** Controversial bills currently before the National Assembly

## The Four Bills

President Tinubu sent 4 tax reform bills to the National Assembly in October 2024:

1. **Nigeria Tax Bill 2024** - Consolidates income tax, VAT, and other taxes
2. **Tax Administration Bill** - Streamlines tax collection and compliance
3. **Nigeria Revenue Service Bill** - Replaces FIRS with new structure
4. **Joint Revenue Board Bill** - Coordinates federal/state tax efforts

## Key Changes Proposed

- **VAT Rate**: Increase from 7.5% to 10% by 2025, then 15% by 2030
- **VAT Distribution**: Derivation-based (where goods are consumed, not where companies register)
- **Zero VAT on essentials**: Food, education, healthcare, rent exempt
- **Higher income tax threshold**: First ₦800,000 tax-free (up from ₦200,000)

## Why It's Controversial

The VAT derivation model would shift revenue from Northern states to Southern commercial hubs like Lagos and Rivers. Northern governors say this is unfair to less industrialized states."""
    },
    {
        "title": "Tax Reform Bills 2024: The VAT Controversy",
        "doc_type": "POLICY_EXPLAINER", 
        "content": """# The VAT Derivation Controversy

**The Core Issue:** How should VAT revenue be shared among states?

## Current System (2024)
- 15% to Federal Government
- 50% to States (shared based on population, equality, terrain)
- 35% to Local Governments

## Proposed New System
- VAT goes to the state where goods are **consumed**, not where companies are registered
- This is called "derivation-based" distribution

## Who Wins and Loses?

**Winners (Support the Bill):**
- Lagos State (most consumption happens there)
- Rivers State (high commercial activity)
- Southern governors generally

**Losers (Oppose the Bill):**
- Northern states with lower commercial activity
- States with smaller populations
- 19 Northern governors released statement opposing the bill

## The Northern Governors' Position

On December 2024, Northern governors met and demanded:
- Withdrawal of the bills
- More consultation before any changes
- Rejection of derivation-based VAT sharing

They argue it would impoverish their states and widen the North-South economic gap."""
    },
    {
        "title": "Tax Reform Bills 2024: Timeline and Status",
        "doc_type": "POLICY_EXPLAINER",
        "content": """# Tax Reform Bills 2024: Timeline

## Key Events

**September 2024:**
- Presidential Committee on Fiscal Policy releases recommendations
- Led by Taiwo Oyedele

**October 2024:**
- President Tinubu sends 4 tax bills to National Assembly
- Bills generate immediate controversy

**November 2024:**
- Public hearings begin
- Northern governors start mobilizing opposition
- Business groups express mixed reactions

**December 2024:**
- 19 Northern governors meet, demand withdrawal
- National Assembly postpones second reading
- Consultations ongoing

## Current Status (Late December 2024)

- Bills are still in committee
- Second reading postponed due to controversy
- Government says it's open to amendments
- Northern governors remain opposed

## What to Watch

- Whether the VAT derivation model survives
- Possible compromise on revenue sharing formula
- Impact on 2025 budget if delayed"""
    },
    {
        "title": "Tax Reform Bills 2024: Impact on Nigerians",
        "doc_type": "POLICY_EXPLAINER",
        "content": """# How the Tax Reform Bills Affect You

## If You're a Salaried Worker

**Good News:**
- First ₦800,000 of annual income would be TAX-FREE
- Currently only ₦200,000 is exempt
- If you earn under ₦800,000/year, you pay ZERO income tax

**Example:**
- ₦100,000/month salary = ₦1.2M/year
- You'd only be taxed on ₦400,000 (₦1.2M - ₦800,000)
- Current: Taxed on ₦1M

## If You Buy Goods

**What Gets More Expensive:**
- VAT rises from 7.5% to 10% in 2025
- Eventually 15% by 2030
- Luxury items will cost more

**What Stays Cheap (Zero VAT):**
- Basic food items (rice, beans, garri, bread)
- Education and school fees
- Healthcare and medicines
- Rent and accommodation

## For Business Owners

- Small businesses under ₦25M turnover exempt from income tax
- Simplified filing process
- Single tax authority (Nigeria Revenue Service) instead of multiple agencies"""
    },
    {
        "title": "Tax Reform Bills 2024: Who Said What",
        "doc_type": "POLICY_EXPLAINER",
        "content": """# Voices on the Tax Reform Bills

## In Favor

**Taiwo Oyedele (Presidential Tax Committee Chair):**
"These bills will make Nigeria's tax system fairer. The poor will pay less, the rich will pay more."

**Wale Edun (Finance Minister):**
"We need to increase tax revenue to fund development. Currently only 10% of Nigerians pay tax."

**Lagos State:**
Supports the bills as Lagos would receive more VAT revenue under derivation model.

## Against

**Northern Governors Forum (19 governors):**
"The VAT derivation model is designed to impoverish the North. We demand withdrawal."

**Nasir El-Rufai (Former Kaduna Governor):**
"This will widen inequality between states. The North will suffer."

**Some Northern Senators:**
Threatened to vote against the bills if VAT derivation is not removed.

## Neutral/Concerned

**NACCIMA (Business Group):**
"We support tax reform but need more time to study the implications."

**Labour Unions:**
"We welcome higher exemption thresholds but worry about VAT increases on goods."

**Civil Society:**
"More public consultation needed before passing such major reforms." """
    }
]


def setup_tax_policy():
    """Ingest Tax Reform Bills 2024 content into RAG system."""
    db = SessionLocal()
    
    try:
        # Remove old tax policy entries
        old_docs = db.query(Document).filter(
            Document.doc_type == "POLICY_EXPLAINER"
        ).all()
        
        removed = 0
        for doc in old_docs:
            if "tax" in doc.title.lower() or "finance act" in doc.title.lower():
                db.delete(doc)
                removed += 1
        
        db.commit()
        print(f"Removed {removed} old tax policy documents")
        
        # Add new content
        added = 0
        for item in TAX_REFORM_CONTENT:
            # Check if already exists
            existing = db.query(Document).filter(
                Document.title == item["title"]
            ).first()
            
            if existing:
                print(f"Updating: {item['title']}")
                existing.content = item["content"]
                existing.embedding_json = embedding_to_json(get_embedding(item["content"]))
            else:
                print(f"Adding: {item['title']}")
                doc = Document(
                    doc_type=item["doc_type"],
                    doc_id=item["title"].lower().replace(" ", "_").replace(":", "")[:100],
                    title=item["title"],
                    content=item["content"],
                    embedding_json=embedding_to_json(get_embedding(item["content"])),
                    state="Nigeria",
                )
                db.add(doc)
                added += 1
        
        db.commit()
        print(f"\n✅ Tax Reform Bills 2024 content loaded: {added} new documents")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    setup_tax_policy()
