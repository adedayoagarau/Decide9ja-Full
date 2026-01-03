"""
Governance Knowledge Base for Decide9ja.

Contains explanatory content about:
- How Nigerian government works
- Voter registration process
- Constitutional rights
- How laws are made
- Current major policies

This content is used to answer "how does X work?" questions.
"""
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GovContent:
    """A piece of governance knowledge."""
    title: str
    content: str
    category: str
    keywords: List[str]
    simplified: Optional[str] = None  # Pidgin/simplified version


# ============================================
# GOVERNANCE KNOWLEDGE BASE
# ============================================

GOVERNANCE_KNOWLEDGE: Dict[str, GovContent] = {
    # === GOVERNMENT STRUCTURE ===
    "government_structure": GovContent(
        title="How Nigerian Government Is Structured",
        category="structure",
        keywords=["government", "structure", "how", "work", "federal", "state", "local"],
        content="""Nigeria operates a federal system with three tiers of government:

*1. Federal Government (Abuja)*
- Led by the President (currently Bola Tinubu)
- National Assembly: Senate (109 members) + House of Reps (360 members)
- Handles: Defence, foreign affairs, currency, immigration, police

*2. State Government (36 States + FCT)*
- Led by Governors (elected every 4 years)
- State House of Assembly makes state laws
- Handles: Education, health, roads, land, local security

*3. Local Government (774 LGAs)*
- Led by LGA Chairmen
- Handles: Primary education, basic health, local roads, waste management

The Constitution defines which tier handles what. Federal laws override state laws when they conflict.""",
        simplified="Na so Nigeria government take work: Federal government dey Abuja with President; State government dey your state with Governor; Local government dey your LGA with Chairman. Each one get their own work wey Constitution give them."
    ),

    "three_arms": GovContent(
        title="The Three Arms of Government",
        category="structure",
        keywords=["arms", "executive", "legislature", "judiciary", "separation", "powers"],
        content="""Nigeria has three separate arms of government:

*1. Executive (President/Governors)*
- Implements laws
- Manages day-to-day government
- Controls security forces
- Appoints ministers/commissioners

*2. Legislature (National Assembly/State Assembly)*
- Makes laws
- Approves budgets
- Confirms appointments
- Oversees the executive

*3. Judiciary (Courts)*
- Interprets laws
- Settles disputes
- Checks the other arms
- Headed by Chief Justice

This "separation of powers" prevents any one arm from becoming too powerful."""
    ),

    # === VOTING & ELECTIONS ===
    "voter_registration": GovContent(
        title="How to Register to Vote",
        category="voting",
        keywords=["register", "vote", "pvc", "inec", "card", "how", "registration"],
        content="""To vote in Nigeria, you need to register with INEC:

*Step 1: CVR (Continuous Voter Registration)*
- Visit INEC office in your LGA or use INEC CVR portal online
- Bring: Valid ID (NIN, passport, driver's license)
- They'll take your photo and fingerprints

*Step 2: Wait for Verification*
- INEC verifies your details
- You can check status on INEC website

*Step 3: Collect Your PVC*
- PVC = Permanent Voter Card
- Collect from your INEC LGA office
- Bring original ID used for registration

*Requirements:*
- Must be 18 years or older
- Must be Nigerian citizen
- Must not be of unsound mind

*Tip:* Your PVC is tied to your registered address. If you move, you can transfer your registration.""",
        simplified="To register for vote: Go INEC office for your LGA, carry your NIN or passport. Dem go snap your picture take your fingerprint. After some weeks, go back collect your PVC. You must don reach 18 years."
    ),

    "how_to_vote": GovContent(
        title="How to Vote on Election Day",
        category="voting",
        keywords=["vote", "election", "day", "polling", "unit", "bvas", "how"],
        content="""On election day:

*1. Find Your Polling Unit*
- Check INEC website or SMS
- Go early (voting starts 8:30am)

*2. Get Accredited*
- Show your PVC
- INEC official verifies with BVAS (biometric machine)
- Your fingerprint must match

*3. Collect Ballot Paper*
- You'll get paper for each election (President, Senate, House)
- Go to voting cubicle for privacy

*4. Mark Your Choice*
- Use the stamp provided
- Stamp ONLY in the box of your chosen candidate's party
- Don't write anything else

*5. Cast Your Vote*
- Fold the paper
- Put in the correct ballot box
- Your finger will be marked with ink

*Important:*
- Don't take photos of your ballot
- Don't show anyone how you voted
- Results are counted at your polling unit"""
    ),

    # === LAWMAKING ===
    "how_bill_becomes_law": GovContent(
        title="How a Bill Becomes Law in Nigeria",
        category="lawmaking",
        keywords=["bill", "law", "pass", "national", "assembly", "president", "sign"],
        content="""For a bill to become law in Nigeria:

*1. First Reading*
- Bill is introduced in Senate or House
- Title is read, no debate yet
- Referred to relevant committee

*2. Committee Stage*
- Committee studies the bill
- May hold public hearings
- Makes recommendations

*3. Second Reading*
- Full debate on the bill's principles
- Members speak for/against
- Vote to proceed or reject

*4. Committee of the Whole*
- Detailed clause-by-clause review
- Amendments can be made

*5. Third Reading*
- Final vote in that chamber
- If passed, goes to other chamber

*6. Concurrence*
- Other chamber repeats the process
- If different versions, conference committee harmonizes

*7. Presidential Assent*
- President has 30 days to sign or veto
- If vetoed, 2/3 majority can override
- If no action in 30 days, it becomes law

A typical bill takes 6-18 months to become law."""
    ),

    # === RIGHTS ===
    "constitutional_rights": GovContent(
        title="Your Constitutional Rights",
        category="rights",
        keywords=["rights", "constitution", "freedom", "citizen", "fundamental"],
        content="""Chapter IV of the 1999 Constitution guarantees these rights:

*1. Right to Life (Section 33)*
- No one can take your life arbitrarily

*2. Right to Dignity (Section 34)*
- No torture, inhuman treatment, or slavery

*3. Right to Personal Liberty (Section 35)*
- You can't be arrested without cause
- Must be told why you're arrested
- Must be brought to court within 24-48 hours

*4. Right to Fair Hearing (Section 36)*
- Right to a fair trial
- Innocent until proven guilty
- Right to legal representation

*5. Right to Privacy (Section 37)*
- Your home, correspondence, communications are protected

*6. Freedom of Thought & Religion (Section 38)*
- Worship as you choose
- Change religion if you want

*7. Freedom of Expression (Section 39)*
- Speak, publish, receive information
- Press freedom (with limits)

*8. Freedom of Movement (Section 41)*
- Live and move freely in Nigeria
- Enter/leave Nigeria freely

*9. Freedom from Discrimination (Section 42)*
- Cannot be discriminated against based on tribe, religion, sex, etc.

*Note:* These rights can be limited during emergencies or for public safety."""
    ),

    # === CURRENT POLICIES ===
    "tax_reform_2024": GovContent(
        title="2024/2025 Tax Reform Laws Explained",
        category="policy",
        keywords=["tax", "reform", "vat", "2024", "2025", "tinubu", "new"],
        content="""The Tax Reform Laws that took effect January 1, 2026:

*Key Changes:*

*1. VAT Redistribution*
- Before: States shared VAT equally
- Now: States get VAT based on what they generate (derivation)
- Lagos, Rivers benefit more; some northern states get less

*2. VAT Rate*
- Remains 7.5% (no increase yet)
- Plan to increase gradually to 15% by 2030

*3. VAT Exemptions*
- Basic food items (rice, beans, yam) still exempt
- Education and healthcare still exempt
- Small businesses under ₦25M turnover exempt

*4. Personal Income Tax*
- Lower earners pay less
- Higher earners pay more
- First ₦800,000 annual income: 0%

*5. Nigeria Revenue Service (NRS)*
- Replaces FIRS
- Single agency for federal taxes

*Why It Matters:*
- States that generate more revenue keep more
- May affect federal allocations to some states
- Designed to encourage states to grow their economies

*Controversy:*
- Northern states worry about losing revenue
- Some see it as favoring Lagos and the South
- Constitutional concerns about derivation principle""",
        simplified="New tax law don start. VAT money wey your state generate, your state go keep more. Before, dem share am equally. Small business wey no reach ₦25 million no need pay VAT. Basic food like rice and beans still no get VAT."
    ),

    "fuel_subsidy": GovContent(
        title="Fuel Subsidy Removal Explained",
        category="policy",
        keywords=["fuel", "subsidy", "removal", "petrol", "price", "tinubu"],
        content="""President Tinubu removed fuel subsidy on May 29, 2023:

*What Was the Subsidy?*
- Government paid part of fuel cost so Nigerians pay less
- Cost ₦4-10 trillion per year
- Critics said it benefited the rich more (who own cars)
- Also benefited smugglers who sold cheap Nigerian fuel abroad

*What Happened After Removal:*
- Petrol price jumped from ~₦195 to ₦600+
- Transportation costs increased
- Cost of goods increased
- Protests in some areas

*Government's Response:*
- CNG (Compressed Natural Gas) conversion program
- Cash transfers to poor households
- Wage increase for workers
- Promise to invest savings in infrastructure

*Current Status (2026):*
- Prices have stabilized around ₦900-1200/litre
- Danfo buses now cost more
- CNG adoption growing slowly
- Palliatives still being distributed

*Arguments For Removal:*
- Savings can fund roads, schools, hospitals
- Subsidy was being stolen
- Encourages alternative energy

*Arguments Against:*
- Hurt poor Nigerians most
- Increased cost of living
- Should have phased out gradually"""
    ),

    "student_loan": GovContent(
        title="Student Loan Scheme Explained",
        category="policy",
        keywords=["student", "loan", "education", "university", "nelfund"],
        content="""The Nigerian Education Loan Fund (NELFUND):

*Who Can Apply?*
- Nigerian students in accredited institutions
- Federal and state universities/polytechnics
- Must have JAMB registration
- Need guarantor (not required to be civil servant anymore)

*What It Covers:*
- Tuition fees
- Upkeep/living expenses
- Books and materials

*How Much?*
- Up to ₦500,000 per session
- Interest-free while studying
- 2% interest after graduation

*How to Repay:*
- Start repaying 2 years after graduation
- Maximum 10 years to repay
- Can pay through salary deduction

*How to Apply:*
1. Visit nelfund.gov.ng
2. Create account with NIN
3. Fill application form
4. Submit required documents
5. Wait for verification

*Requirements:*
- Valid NIN
- JAMB profile
- Admission letter
- Bank account

*Note:* The scheme is still rolling out. Not all institutions are covered yet."""
    ),
}


class GovernanceKnowledgeService:
    """Service for retrieving governance knowledge."""

    def __init__(self):
        self.knowledge = GOVERNANCE_KNOWLEDGE

    def search(self, query: str) -> Optional[GovContent]:
        """Search for relevant governance content."""
        query_lower = query.lower()

        # Score each content by keyword matches
        scores = {}
        for key, content in self.knowledge.items():
            score = 0
            for keyword in content.keywords:
                if keyword in query_lower:
                    score += 1
            if score > 0:
                scores[key] = score

        if scores:
            best_match = max(scores, key=scores.get)
            return self.knowledge[best_match]

        return None

    def get_by_category(self, category: str) -> List[GovContent]:
        """Get all content in a category."""
        return [c for c in self.knowledge.values() if c.category == category]

    def get_all_titles(self) -> List[str]:
        """Get all available topics."""
        return [c.title for c in self.knowledge.values()]

    def format_content(self, content: GovContent, use_simplified: bool = False) -> str:
        """Format content for display."""
        if use_simplified and content.simplified:
            return f"📚 *{content.title}*\n\n{content.simplified}"
        return f"📚 *{content.title}*\n\n{content.content}"


# Singleton instance
governance_knowledge = GovernanceKnowledgeService()


def explain_governance(query: str, pidgin: bool = False) -> str:
    """Convenience function for message handler."""
    content = governance_knowledge.search(query)
    if content:
        return governance_knowledge.format_content(content, use_simplified=pidgin)
    return "I don't have a detailed explainer for that topic yet. Try asking about: government structure, voting, how laws are made, your rights, or current policies like tax reform."


def get_governance_topics() -> str:
    """List available governance topics."""
    titles = governance_knowledge.get_all_titles()
    response = "📚 *Governance Topics I Can Explain:*\n\n"
    for title in titles:
        response += f"• {title}\n"
    response += "\nAsk about any of these topics!"
    return response
