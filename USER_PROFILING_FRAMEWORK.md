# DECIDE9JA USER PROFILING FRAMEWORK
## Building Political Fingerprints for Personalized Civic Engagement

---

# PART 1: THE POLITICAL FINGERPRINT

Every Nigerian citizen has a unique political context defined by five dimensions:

```
┌─────────────────────────────────────────────────────────────┐
│                    POLITICAL FINGERPRINT                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   LOCATION         Who represents them                       │
│   ━━━━━━━━━        (7 levels of government)                  │
│                                                              │
│   LIVELIHOOD       Which policies affect them                │
│   ━━━━━━━━━━       (occupation, income, sector)              │
│                                                              │
│   LIFE STAGE       What they prioritize                      │
│   ━━━━━━━━━━       (age, family, responsibilities)           │
│                                                              │
│   LITERACY         How to communicate with them              │
│   ━━━━━━━━━        (political knowledge, language)           │
│                                                              │
│   ENGAGEMENT       How deep they want to go                  │
│   ━━━━━━━━━━       (passive learner → active advocate)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

# PART 2: DIMENSION 1 — LOCATION STACK

Nigeria has nested political geography. Each layer has different representatives and issues.

## The 7 Layers

```
LAYER 1: ZONE (Geopolitical)
├── North-Central (7 states)
├── North-East (6 states)
├── North-West (7 states)
├── South-East (5 states)
├── South-South (6 states)
└── South-West (6 states)

LAYER 2: STATE (36 + FCT)
└── Each state has: Governor, Deputy Governor, State Assembly

LAYER 3: SENATORIAL DISTRICT (109)
└── 3 per state, each elects 1 Senator

LAYER 4: FEDERAL CONSTITUENCY (360)
└── Each elects 1 House of Reps member

LAYER 5: STATE CONSTITUENCY (~990)
└── Each elects 1 State Assembly member

LAYER 6: LOCAL GOVERNMENT AREA (774)
└── Each has: Chairman, Vice Chairman, Councillors

LAYER 7: WARD (~8,809)
└── Smallest political unit, elects Councillor
└── Contains Polling Units
```

## What Location Unlocks

| If You Know | You Can Tell Them |
|-------------|-------------------|
| State | Governor, Deputy Governor, State issues |
| LGA | Chairman, Local issues, Polling unit area |
| Senatorial District | Their Senator (derived from LGA) |
| Federal Constituency | Their Rep (derived from LGA) |
| State Constituency | Their State Assembly member (derived from LGA) |
| Ward | Their Councillor, Exact polling unit |

## Location Collection Strategy

### Step 1: State (Essential - Ask Directly)
```
Bot: "What state are you in?"
User: "Rivers"
→ SAVED: state = "Rivers"
→ DERIVED: zone = "South-South"
```

### Step 2: LGA (Essential - Ask Directly)
```
Bot: "Which Local Government Area?"
User: "Port Harcourt"
→ SAVED: lga = "Port Harcourt"
→ DERIVED: 
   - senatorial_district = "Rivers South-East" (via lookup table)
   - federal_constituency = "Port Harcourt Federal Constituency 1" or "2"
```

### Step 3: Federal Constituency (Ask if Ambiguous)
Some LGAs span multiple federal constituencies.
```
Bot: "Port Harcourt has two federal constituencies. 
     Are you in the area around:
     A) Old GRA, D/Line, Borokiri
     B) Rumuokwuta, Rumuola, Elelenwo"

User: "A"
→ SAVED: federal_constituency = "Port Harcourt 1"
```

### Step 4: Ward (Optional - Ask When Reporting)
```
Bot: "To find your exact polling unit, what ward are you in?
     Or share your location 📍 and I'll figure it out."

User: [Shares WhatsApp location pin]
→ DERIVED: ward = "Ward 5" (via geocoding)
→ DERIVED: polling_unit = "Primary School Diobu, Unit 003"
```

## Location-to-Representative Mapping Table

This is critical infrastructure. You need a lookup table:

```json
{
  "rivers": {
    "port_harcourt": {
      "senatorial_district": "Rivers South-East",
      "federal_constituencies": [
        {
          "name": "Port Harcourt 1",
          "areas": ["Old GRA", "D/Line", "Borokiri", "Nkpolu"]
        },
        {
          "name": "Port Harcourt 2", 
          "areas": ["Rumuokwuta", "Rumuola", "Elelenwo"]
        }
      ],
      "state_constituencies": [
        "Port Harcourt 1",
        "Port Harcourt 2",
        "Port Harcourt 3"
      ],
      "wards": 20
    }
  }
}
```

## Location Intelligence

Beyond just knowing where they are, understand what that means:

```python
class LocationIntelligence:
    """What their location tells us about their likely concerns."""
    
    URBAN_LGAS = ["Lagos Island", "Port Harcourt", "Kano Municipal", ...]
    RURAL_LGAS = ["Gwadabawa", "Ibarapa North", ...]
    CONFLICT_AREAS = ["Borno", "Zamfara", "Kaduna", ...]  # Security priority
    OIL_PRODUCING = ["Rivers", "Delta", "Bayelsa", ...]  # Resource control matters
    BORDER_LGAS = [...]  # Smuggling, customs issues
    
    def get_likely_issues(self, state: str, lga: str) -> List[str]:
        issues = []
        
        if state in self.CONFLICT_AREAS:
            issues.append("security")
        
        if state in self.OIL_PRODUCING:
            issues.append("resource_control")
            issues.append("environmental_degradation")
        
        if lga in self.URBAN_LGAS:
            issues.append("traffic")
            issues.append("housing")
            issues.append("unemployment")
        
        if lga in self.RURAL_LGAS:
            issues.append("agriculture")
            issues.append("roads")
            issues.append("electricity")
        
        return issues
```

---

# PART 3: DIMENSION 2 — LIVELIHOOD STACK

What someone does for a living determines which government policies directly affect them.

## Occupation Categories

```
FORMAL SECTOR
├── Civil Servant (Federal)
│   └── Cares about: Minimum wage, IPPIS, promotions, pension
├── Civil Servant (State)
│   └── Cares about: State salary structure, pension, leave
├── Teacher (Public)
│   └── Cares about: ASUU/ASUP, salary arrears, education funding
├── Teacher (Private)
│   └── Cares about: School regulations, curriculum, tax
├── Healthcare Worker
│   └── Cares about: NHIS, brain drain policy, hazard allowance
├── Banker/Finance
│   └── Cares about: CBN policy, naira value, interest rates
├── Tech Worker
│   └── Cares about: Digital economy policy, tax incentives, data laws
├── Oil & Gas Worker
│   └── Cares about: PIB, local content, NNPC reforms
├── Lawyer
│   └── Cares about: Judicial reforms, NBA policies
└── Journalist/Media
    └── Cares about: Press freedom, NBC regulations

INFORMAL SECTOR
├── Trader/Market Seller
│   └── Cares about: Market levies, import bans, naira value
├── Artisan (Mechanic, Tailor, etc.)
│   └── Cares about: Apprenticeship policy, business registration
├── Farmer
│   └── Cares about: Anchor Borrowers, fertilizer subsidy, land reform
├── Transporter (Driver, Okada, Keke)
│   └── Cares about: Fuel price, vehicle registration, bans
├── Street Vendor
│   └── Cares about: Harassment, permits, market access
└── Domestic Worker
    └── Cares about: Labor laws, minimum wage

BUSINESS OWNER
├── Small Business (SME)
│   └── Cares about: SON regulations, CAC registration, SMEDAN loans
├── Importer/Exporter
│   └── Cares about: Customs, port charges, forex policy
├── Manufacturer
│   └── Cares about: Raw materials, power, tax incentives
├── Contractor
│   └── Cares about: Government contracts, payment delays
└── Tech Startup
    └── Cares about: Startup Act, funding, regulations

NOT EMPLOYED
├── Student
│   └── Cares about: Tuition, student loans, ASUU strikes, NYSC
├── NYSC Member
│   └── Cares about: Allowance, PPA, relocation
├── Job Seeker
│   └── Cares about: Job creation, N-Power, NPOWER
├── Retiree
│   └── Cares about: Pension, gratuity, healthcare
└── Unemployed
    └── Cares about: Social safety net, skills training
```

## Occupation Detection Strategy

### Method 1: Direct Ask (When Relevant)
```
User: "What is the government doing about fuel prices?"

Bot: "Fuel prices affect everyone differently. Are you:
     A) A driver/transporter (fuel is your biggest cost)
     B) A business owner (affects operations)
     C) Regular commuter (transport costs)
     D) Farmer (need fuel for machines/transport)
     
     I'll give you the most relevant breakdown."

User: "A"
→ SAVED: occupation = "transporter"
→ SAVED: occupation_detail = "driver"
```

### Method 2: Infer from Questions
```
User: "When will ASUU call off the strike?"
→ INFERRED: occupation_likely = "student" OR "academic"

User: "Has minimum wage been implemented in Kogi?"
→ INFERRED: occupation_likely = "civil_servant_state"

User: "What's the new CAC registration process?"
→ INFERRED: occupation_likely = "business_owner"

User: "Where can I get fertilizer subsidy?"
→ INFERRED: occupation_likely = "farmer"
```

### Method 3: Explicit Mention
```
User: "As a nurse, I want to know about hazard allowance"
→ EXTRACTED: occupation = "healthcare_worker"
→ EXTRACTED: occupation_detail = "nurse"
```

## Occupation-Based Response Personalization

```python
OCCUPATION_POLICY_MAP = {
    "farmer": {
        "economy": [
            "Anchor Borrowers Programme status",
            "Fertilizer subsidy distribution",
            "Agricultural commodity prices",
            "Land reform policies"
        ],
        "relevant_agencies": ["CBN", "Ministry of Agriculture", "NIRSAL"],
        "tone": "practical, focus on access and prices"
    },
    "transporter": {
        "economy": [
            "Fuel subsidy removal impact",
            "CNG conversion program",
            "Vehicle financing schemes",
            "Road conditions"
        ],
        "relevant_agencies": ["NNPC", "FRSC", "State transport ministries"],
        "tone": "direct, focus on costs and alternatives"
    },
    "civil_servant_federal": {
        "economy": [
            "Minimum wage implementation",
            "IPPIS issues",
            "Promotion policies",
            "Pension reforms"
        ],
        "relevant_agencies": ["OHCSF", "PenCom", "Ministry of Finance"],
        "tone": "formal, policy-focused"
    },
    "student": {
        "education": [
            "ASUU status",
            "Student loan application",
            "JAMB/POST-UTME updates",
            "Scholarship opportunities"
        ],
        "economy": [
            "Youth employment programs",
            "N-Power registration",
            "NYSC updates"
        ],
        "relevant_agencies": ["TETFUND", "NELFUND", "Ministry of Education"],
        "tone": "accessible, step-by-step guidance"
    }
}
```

---

# PART 4: DIMENSION 3 — LIFE STAGE STACK

Where someone is in life determines their priorities.

## Life Stages

```
YOUTH (18-25)
├── Priorities: Education, first job, opportunity, future
├── Issues: ASUU, unemployment, skills, NYSC
├── Communication: Informal, use Pidgin if appropriate, quick
└── Engagement: Social media savvy, share-ready content

YOUNG ADULT (26-35)
├── Priorities: Career growth, starting family, housing
├── Issues: Jobs, rent, healthcare, childcare costs
├── Communication: Direct, practical, solution-focused
└── Engagement: Time-poor, wants concise answers

ESTABLISHED ADULT (36-50)
├── Priorities: Children's education, security, wealth building
├── Issues: School fees, security, economy, property
├── Communication: Detailed when needed, respects expertise
└── Engagement: Serious about civic participation

ELDER (50+)
├── Priorities: Health, pension, legacy, stability
├── Issues: Healthcare, pension delays, security
├── Communication: Respectful, patient, thorough
└── Engagement: May need tech guidance, but highly committed
```

## Life Stage Detection

### Method 1: Infer from Topics
```python
def infer_life_stage(message_history: List[str]) -> str:
    topics = extract_topics(message_history)
    
    youth_signals = ["JAMB", "WAEC", "NYSC", "student loan", "first job", "school fees"]
    young_adult_signals = ["rent", "wedding", "baby", "apartment", "career"]
    established_signals = ["children school", "secondary school", "property", "investment"]
    elder_signals = ["pension", "retirement", "grandchildren", "health insurance"]
    
    # Score each life stage based on topic matches
    scores = calculate_scores(topics, [youth_signals, young_adult_signals, ...])
    return highest_score_stage(scores)
```

### Method 2: Direct Ask (Natural Context)
```
User: [Asks about education policy]

Bot: "Education is a big topic! Quick question - are you:
     A) A student yourself
     B) Parent of school-age children
     C) Working in education
     D) Just generally interested
     
     I'll focus on what's most relevant."
```

### Method 3: Explicit Signals
```
User: "My children's school increased fees again"
→ INFERRED: life_stage = "established_adult"
→ INFERRED: has_children = True
→ INFERRED: children_school_age = True

User: "I just finished NYSC, looking for job"
→ INFERRED: life_stage = "youth"
→ INFERRED: employment_status = "job_seeker"
→ INFERRED: education = "graduate"
```

## Life Stage Response Adaptation

Same question, different answers:

### "What is the government doing about the economy?"

**Youth (18-25):**
```
"Here's what affects young people directly:

📚 Student Loans: NELFUND now disbursing. Have you applied?
💼 Jobs: N-Power batch applications open. 3MTT training free.
💰 Cost of living: Transport & food up 40%. Here's how some are coping...

Want details on any of these?"
```

**Established Adult (36-50):**
```
"Key economic policies affecting families:

📈 Inflation: Now at 34%. Food basket up significantly.
🏫 School fees: Private schools raised 20-40%. Public school funding status.
🏠 Interest rates: Mortgage rates at 28%. Property market outlook.
⛽ Fuel: ₦617/litre official. CNG conversion incentives available.

Which area should I expand on?"
```

**Elder (50+):**
```
"Economic policies affecting retirees:

👴 Pension: FG pension increase announced but not implemented in some states.
🏥 Health: NHIS expansion covers some new conditions.
💵 Naira: Savings affected by inflation. Here's what some are doing.

I can explain any of these in more detail."
```

---

# PART 5: DIMENSION 4 — POLITICAL LITERACY STACK

How much does the user already know? Tailor complexity accordingly.

## Literacy Levels

```
NOVICE
├── Doesn't know their representatives
├── Unfamiliar with government structure
├── Needs basics explained
├── Questions: "Who is my governor?", "What is a senator?"
└── Response style: Simple, educational, no jargon

INFORMED
├── Knows basic structure
├── Follows news casually
├── Wants specific information
├── Questions: "What is Tinubu's education policy?"
└── Response style: Direct answers with context

ENGAGED
├── Follows politics actively
├── Knows representatives by name
├── Wants depth and nuance
├── Questions: "How did my senator vote on the finance bill?"
└── Response style: Detailed, include voting records, positions

EXPERT
├── Works in policy/politics/civil society
├── Wants data and sources
├── May challenge information
├── Questions: "What's the constitutional basis for..."
└── Response style: Technical, cite sources, acknowledge complexity
```

## Literacy Detection

### Method 1: Analyze Question Sophistication
```python
def assess_political_literacy(question: str) -> str:
    novice_patterns = [
        "who is", "what is a", "how do I vote", "what does .* mean"
    ]
    informed_patterns = [
        "what is .* policy on", "position on", "compare"
    ]
    engaged_patterns = [
        "how did .* vote", "track record", "promises vs delivery"
    ]
    expert_patterns = [
        "constitutional", "legislative process", "appropriation", "MTEF"
    ]
    
    # Match and score
    ...
```

### Method 2: Track Over Time
```python
class LiteracyTracker:
    def update_literacy_score(self, user_id: str, interaction: dict):
        """
        Over multiple conversations, build literacy profile.
        """
        current_score = self.get_score(user_id)
        
        # Questions about basic structure = lower literacy signal
        # Questions about voting records = higher literacy signal
        # Correct use of political terms = higher literacy signal
        # Confusion about structure = lower literacy signal
        
        # Adjust score based on interaction
        new_score = calculate_new_score(current_score, interaction)
        self.save_score(user_id, new_score)
```

## Literacy-Adapted Responses

### Question: "Tell me about the Senate"

**Novice:**
```
"The Senate is the upper house of Nigeria's National Assembly (like our parliament).

Key facts:
👥 109 Senators total (3 from each state + 1 from FCT)
📋 They make laws, approve budgets, confirm appointments
⏰ Elected every 4 years

Your state (Lagos) has 3 senators:
• Lagos Central: Wasiu Eshilokun (APC)
• Lagos East: Tokunbo Abiru (APC)  
• Lagos West: Oluranti Adebule (APC)

Want to know more about what your senator has done?"
```

**Engaged:**
```
"Lagos has 3 senators in the 10th Senate:

Lagos Central - Wasiu Eshilokun (APC)
• Committees: Judiciary, Ethics
• Bills sponsored: 2
• Attendance: No public record yet

Lagos East - Tokunbo Abiru (APC)
• Committees: Banking, Finance
• Notable: Led financial inclusion debates

Lagos West - Oluranti Adebule (APC)
• First female senator from Lagos
• Committees: Women Affairs, Health

Want their voting records on specific bills?"
```

---

# PART 6: DIMENSION 5 — ENGAGEMENT STACK

How does this user want to participate?

## Engagement Levels

```
PASSIVE LEARNER
├── Occasional questions
├── Just wants information
├── Won't share or report
├── May not return often
└── Goal: Answer their question well

ACTIVE USER
├── Regular conversations
├── Tracks specific officials
├── May report issues
├── Returns frequently
└── Goal: Provide depth, remember preferences

REPORTER
├── Submits community reports
├── Takes photos of issues
├── Wants to see impact
├── Shares reports with neighbors
└── Goal: Make reporting easy, show aggregated impact

ADVOCATE
├── Shares Decide9ja with others
├── Wants to organize community
├── Interested in civic action
├── May want accountability tools
└── Goal: Provide tools for mobilization
```

## Engagement Tracking

```python
class EngagementProfile:
    user_id: str
    
    # Activity metrics
    total_messages: int
    total_sessions: int
    days_active: int
    last_active: datetime
    
    # Behavioral signals
    reports_submitted: int
    reports_endorsed: int  # "I've seen this too"
    questions_asked: int
    follow_up_questions: int  # Depth of inquiry
    
    # Calculated level
    @property
    def engagement_level(self) -> str:
        if self.reports_submitted > 3:
            return "reporter"
        elif self.days_active > 14 and self.total_sessions > 10:
            return "active"
        else:
            return "passive"
    
    @property
    def is_potential_advocate(self) -> bool:
        # High engagement + multiple reports + consistent return
        return (
            self.engagement_level in ["active", "reporter"] and
            self.reports_endorsed > 2 and
            self.days_active > 30
        )
```

## Engagement-Based Features

| Level | Features Offered |
|-------|-----------------|
| Passive | Basic Q&A, no follow-up |
| Active | "Would you like updates when this changes?" |
| Reporter | "Submit a report", "Track your report status" |
| Advocate | "Share with your community", "Download report summary" |

---

# PART 7: THE COMPLETE PROFILE SCHEMA

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class EngagementLevel(Enum):
    PASSIVE = "passive"
    ACTIVE = "active"
    REPORTER = "reporter"
    ADVOCATE = "advocate"

class PoliticalLiteracy(Enum):
    NOVICE = "novice"
    INFORMED = "informed"
    ENGAGED = "engaged"
    EXPERT = "expert"

class LifeStage(Enum):
    YOUTH = "18-25"
    YOUNG_ADULT = "26-35"
    ESTABLISHED = "36-50"
    ELDER = "50+"

@dataclass
class LocationProfile:
    """The 7-layer location stack."""
    zone: Optional[str] = None                    # Derived from state
    state: Optional[str] = None                   # Asked directly
    senatorial_district: Optional[str] = None     # Derived from LGA
    federal_constituency: Optional[str] = None    # Derived or asked
    state_constituency: Optional[str] = None      # Derived
    lga: Optional[str] = None                     # Asked directly
    ward: Optional[str] = None                    # Asked when reporting
    polling_unit: Optional[str] = None            # Derived from ward
    
    # Location intelligence
    is_urban: Optional[bool] = None
    is_conflict_area: Optional[bool] = None
    is_oil_producing: Optional[bool] = None
    
    # Completeness
    @property
    def completeness(self) -> float:
        fields = [self.state, self.lga, self.senatorial_district]
        filled = sum(1 for f in fields if f is not None)
        return filled / len(fields)

@dataclass
class LivelihoodProfile:
    """Occupation and economic context."""
    occupation_category: Optional[str] = None     # "formal", "informal", "business", "not_employed"
    occupation: Optional[str] = None              # "teacher", "farmer", "trader"
    occupation_detail: Optional[str] = None       # "secondary school teacher", "rice farmer"
    sector: Optional[str] = None                  # "public", "private", "self_employed"
    income_bracket: Optional[str] = None          # Inferred, never asked
    
    # Confidence scores (0-1)
    occupation_confidence: float = 0.0
    
    # Relevant policy areas (derived)
    @property
    def policy_interests(self) -> List[str]:
        # Return relevant policy areas based on occupation
        return OCCUPATION_POLICY_MAP.get(self.occupation, {}).get("economy", [])

@dataclass  
class DemographicProfile:
    """Life stage and personal context."""
    life_stage: Optional[LifeStage] = None
    age_bracket: Optional[str] = None             # Inferred from life stage signals
    has_children: Optional[bool] = None           # Inferred from topics
    children_school_age: Optional[bool] = None
    education_level: Optional[str] = None         # Inferred from vocabulary, topics
    gender: Optional[str] = None                  # Only if volunteered
    
    # Confidence
    life_stage_confidence: float = 0.0

@dataclass
class PoliticalProfile:
    """Political knowledge and preferences."""
    literacy_level: PoliticalLiteracy = PoliticalLiteracy.NOVICE
    
    # Voting status
    has_pvc: Optional[bool] = None
    knows_polling_unit: Optional[bool] = None
    registered_voter: Optional[bool] = None
    
    # Issues (extracted from conversations)
    issues_mentioned: List[str] = field(default_factory=list)        # Raw mentions
    issues_care_about: List[str] = field(default_factory=list)       # Aggregated
    
    # Candidates/officials they ask about
    candidates_queried: List[str] = field(default_factory=list)
    officials_following: List[str] = field(default_factory=list)     # Repeated queries
    
    # IMPORTANT: We do NOT store political party preference
    # That would be sensitive data we shouldn't hold

@dataclass
class EngagementProfile:
    """How they interact with the platform."""
    level: EngagementLevel = EngagementLevel.PASSIVE
    
    # Activity
    first_seen: Optional[datetime] = None
    last_active: Optional[datetime] = None
    total_sessions: int = 0
    total_messages: int = 0
    days_active: int = 0
    
    # Behavior
    reports_submitted: int = 0
    reports_endorsed: int = 0
    questions_asked: int = 0
    
    # Preferences
    preferred_language: str = "en"  # en, pcm, ha, yo, ig
    response_length_preference: str = "medium"  # short, medium, detailed
    
    # Sentiment trend
    sentiment_scores: List[float] = field(default_factory=list)
    
    @property
    def average_sentiment(self) -> float:
        if not self.sentiment_scores:
            return 0.0
        return sum(self.sentiment_scores) / len(self.sentiment_scores)

@dataclass
class UserProfile:
    """The complete political fingerprint."""
    # Identity (hashed, never raw)
    user_id: str                                  # UUID
    phone_hash: str                               # SHA256 of phone number
    
    # The five dimensions
    location: LocationProfile = field(default_factory=LocationProfile)
    livelihood: LivelihoodProfile = field(default_factory=LivelihoodProfile)
    demographic: DemographicProfile = field(default_factory=DemographicProfile)
    political: PoliticalProfile = field(default_factory=PoliticalProfile)
    engagement: EngagementProfile = field(default_factory=EngagementProfile)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Profile completeness
    @property
    def completeness_score(self) -> float:
        scores = [
            self.location.completeness * 0.4,     # Location is most important
            (1.0 if self.livelihood.occupation else 0.0) * 0.2,
            (1.0 if self.demographic.life_stage else 0.0) * 0.15,
            (1.0 if self.political.has_pvc is not None else 0.0) * 0.15,
            min(self.engagement.total_messages / 10, 1.0) * 0.1
        ]
        return sum(scores)
    
    # Representatives (derived from location)
    def get_representatives(self) -> Dict[str, str]:
        """Return all representatives based on location."""
        return {
            "president": "Bola Tinubu",
            "governor": lookup_governor(self.location.state),
            "senator": lookup_senator(self.location.senatorial_district),
            "representative": lookup_rep(self.location.federal_constituency),
            "lga_chairman": lookup_chairman(self.location.state, self.location.lga)
        }
```

---

# PART 8: PROGRESSIVE PROFILING FLOWS

## First Contact Flow

```
┌─────────────────────────────────────────────────────────────┐
│ USER: "Hi"                                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ BOT: "Welcome to Decide9ja! 🗳️                              │
│                                                              │
│ I help you get info about your elected officials and        │
│ report issues in your community.                            │
│                                                              │
│ What state are you in?"                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ USER: "Kano"                                                 │
│                                                              │
│ → SAVED: state = "Kano"                                      │
│ → DERIVED: zone = "North-West"                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ BOT: "Great! Which Local Government Area?"                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ USER: "Fagge"                                                │
│                                                              │
│ → SAVED: lga = "Fagge"                                       │
│ → DERIVED: senatorial = "Kano Central"                       │
│ → DERIVED: federal_constituency = "Kano Municipal"           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ BOT: "Perfect! You're in Kano Central senatorial district.  │
│                                                              │
│ Quick question - do you have your PVC (voter's card)?       │
│ 1️⃣ Yes, I have it                                           │
│ 2️⃣ No, not yet                                              │
│ 3️⃣ Applied, haven't collected"                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ USER: "1"                                                    │
│                                                              │
│ → SAVED: has_pvc = True                                      │
│ → SAVED: registered_voter = True                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ BOT: "You're all set! 🎉                                     │
│                                                              │
│ Your representatives:                                        │
│ 🏛️ Governor: Abba Yusuf (NNPP)                              │
│ 🏛️ Senator: Rufai Sani Hanga (NNPP)                         │
│ 🏛️ LGA Chairman: [Name]                                     │
│                                                              │
│ What would you like to know?"                                │
└─────────────────────────────────────────────────────────────┘

PROFILE AFTER FIRST CONTACT:
├── location.state = "Kano"
├── location.lga = "Fagge"  
├── location.senatorial_district = "Kano Central"
├── political.has_pvc = True
└── completeness = 65%
```

## Ongoing Profiling (From Conversations)

```
SESSION 2:
┌─────────────────────────────────────────────────────────────┐
│ USER: "What is Tinubu doing about fuel? I'm spending too    │
│       much on diesel for my generator."                     │
└─────────────────────────────────────────────────────────────┘

EXTRACTION:
├── issues_mentioned.append("fuel_prices")
├── issues_mentioned.append("electricity") 
├── occupation_signal = "business_owner" (has generator)
├── sentiment = "frustrated"

→ Occupation confidence: 0.4 (weak signal)

┌─────────────────────────────────────────────────────────────┐
│ USER: "My shop is not making profit anymore"                │
└─────────────────────────────────────────────────────────────┘

EXTRACTION:
├── occupation_signal = "trader" OR "business_owner"
├── issues_care_about.append("economy")

→ Occupation confidence: 0.6 (stronger signal)

BOT RESPONSE (adapted to likely trader/business):
"Fuel prices are affecting businesses hard. Here's what's relevant for you:

⛽ Diesel now ₦1,200/litre (up from ₦800)
🏭 Govt CNG conversion program for businesses - up to 50% cheaper
💡 Kano specifically: Generator ban rumors - FALSE

Would you like info on the CNG conversion program?"
```

## Strategic Questions (Ask When Natural)

```python
STRATEGIC_QUESTIONS = {
    "occupation": {
        "trigger": "asks about economy/jobs/policy",
        "question": "This affects people differently. What kind of work do you do?",
        "options": ["Business/Trading", "Government work", "Farming", "Driving/Transport", "Student", "Other"]
    },
    "age_bracket": {
        "trigger": "asks about youth programs OR pension OR education",
        "question": "I can show you the most relevant programs. Are you in the 18-35 or 35+ age range?",
        "options": ["18-35", "35+"]
    },
    "ward": {
        "trigger": "wants to report issue OR find polling unit",
        "question": "To pinpoint the right location, what area/ward are you in? Or share your location 📍",
        "options": None  # Free text or location share
    },
    "language": {
        "trigger": "after 5+ messages",
        "question": "By the way, would you prefer I respond in Pidgin? Or we're good with English?",
        "options": ["English fine", "Pidgin better", "Hausa", "Yoruba", "Igbo"]
    }
}
```

---

# PART 9: PRIVACY & ETHICS FRAMEWORK

This is a political platform. Trust is everything.

## What We NEVER Do

```
❌ Store raw phone numbers (always hash)
❌ Store political party preference
❌ Store who they plan to vote for
❌ Sell individual user data
❌ Share user data with political parties
❌ Use data to target political advertising
❌ Allow campaigns to message users directly
```

## What We DO (With Consent)

```
✅ Store location (state, LGA) for personalization
✅ Store occupation for relevance
✅ Store issues they care about
✅ Store engagement patterns
✅ Aggregate anonymized insights
✅ Share aggregate trends (not individuals)
```

## Transparency Features

```python
# User can ask "What do you know about me?"

def get_user_summary(user_id: str) -> str:
    profile = get_profile(user_id)
    
    return f"""
Here's what I know about you (from our conversations):

📍 Location: {profile.location.state}, {profile.location.lga}
💼 Occupation: {profile.livelihood.occupation or "Not sure yet"}
🗳️ Voter status: {"Registered" if profile.political.has_pvc else "Not confirmed"}
💬 We've chatted: {profile.engagement.total_messages} times

Issues you've asked about:
{format_list(profile.political.issues_care_about)}

I use this to give you relevant info. I never share your personal data.

Want me to delete anything? Just say "forget my [location/occupation/etc]"
"""
```

## Data Deletion

```
User: "Forget my occupation"

Bot: "Done! I've removed your occupation from my memory. 
     I'll ask again if it becomes relevant.
     
     Anything else you'd like me to forget?"
```

---

# PART 10: USING THE PROFILE FOR PERSONALIZATION

## In the RAG Pipeline

```python
async def generate_response(
    user_message: str,
    user_profile: UserProfile,
    retrieved_context: str
) -> str:
    
    # Build personalization layer
    personalization = build_personalization_prompt(user_profile)
    
    system_prompt = f"""
{BASE_SYSTEM_PROMPT}

{personalization}

CONTEXT FROM DATABASE:
{retrieved_context}
"""
    
    response = await claude.generate(
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    
    return response


def build_personalization_prompt(profile: UserProfile) -> str:
    """Build the personalization section of the system prompt."""
    
    parts = ["USER CONTEXT:"]
    
    # Location
    if profile.location.state:
        reps = profile.get_representatives()
        parts.append(f"""
LOCATION: {profile.location.state}, {profile.location.lga or 'LGA unknown'}
THEIR REPRESENTATIVES:
- Governor: {reps.get('governor', 'Unknown')}
- Senator: {reps.get('senator', 'Unknown')} ({profile.location.senatorial_district})
- LGA Chairman: {reps.get('lga_chairman', 'Unknown')}
""")
    
    # Occupation
    if profile.livelihood.occupation:
        parts.append(f"""
OCCUPATION: {profile.livelihood.occupation}
RELEVANT POLICIES: {', '.join(profile.livelihood.policy_interests[:3])}
""")
    
    # Life stage
    if profile.demographic.life_stage:
        parts.append(f"""
LIFE STAGE: {profile.demographic.life_stage.value}
LIKELY PRIORITIES: {get_life_stage_priorities(profile.demographic.life_stage)}
""")
    
    # Political literacy
    parts.append(f"""
POLITICAL LITERACY: {profile.political.literacy_level.value}
COMMUNICATION STYLE: {get_communication_style(profile.political.literacy_level)}
""")
    
    # Issues they care about
    if profile.political.issues_care_about:
        parts.append(f"""
ISSUES THEY CARE ABOUT: {', '.join(profile.political.issues_care_about[:5])}
""")
    
    # Language
    parts.append(f"""
LANGUAGE PREFERENCE: {profile.engagement.preferred_language}
""")
    
    # Instructions
    parts.append("""
PERSONALIZATION RULES:
- Reference their specific location and representatives when relevant
- Relate policies to their occupation if known
- Match complexity to their political literacy level
- Prioritize issues they've shown interest in
- Use their preferred language/tone
- Remember: they are from {state} - local context matters
""".format(state=profile.location.state or "Nigeria"))
    
    return "\n".join(parts)
```

## Example: Same Question, Different Profiles

### Question: "What is the government doing about security?"

**Profile A: Farmer in Zamfara, Novice**
```
Security in Zamfara is critical right now. Here's the simple breakdown:

🛡️ Military deployed to your state - Operation Hadarin Daji
📍 Your LGA ({lga}) - check local vigilante coordination
📱 Report suspicious activity: NPF hotline 0800-CALL-NPF

Your governor (Dauda Lawal) recently met with security chiefs.
He promised more local vigilantes for farming areas.

Are you facing specific security challenges on your farm?
```

**Profile B: Business Owner in Lagos, Engaged**
```
Security situation by level:

FEDERAL:
- Defence budget: ₦2.56T (2024) - 8.9% of total
- NSA restructuring ongoing
- Police reform: 50,000 new recruits promised, 15,000 delivered

LAGOS SPECIFIC:
- Sanwo-Olu's THEMES security pillar: ₦45B allocated
- Neighborhood watch expansion
- CCTV coverage: From 2,000 to planned 13,000

For your business:
- CAC now requires security compliance certificate
- Private security registration changes

What aspect affects your business most?
```

---

# PART 11: PROFILE COMPLETION PROMPTS

Nudge users to complete their profile naturally.

```python
def get_profile_completion_nudge(profile: UserProfile) -> Optional[str]:
    """Return a natural nudge to complete profile, or None if not appropriate."""
    
    # Only nudge occasionally (every 5th session)
    if profile.engagement.total_sessions % 5 != 0:
        return None
    
    if profile.location.state and not profile.location.lga:
        return "By the way, if you tell me your LGA, I can show you your local chairman and report local issues."
    
    if not profile.political.has_pvc:
        return "Quick one - do you have your voter's card (PVC)? I can help with registration if needed."
    
    if not profile.livelihood.occupation and profile.engagement.total_messages > 10:
        return "I notice you ask about economic policies. What kind of work do you do? I can tailor my answers better."
    
    return None
```

---

# SUMMARY

The political fingerprint is built from:

1. **LOCATION** - Where they are (7 layers)
2. **LIVELIHOOD** - What they do (occupation, sector)
3. **LIFE STAGE** - What they prioritize (age, family)
4. **LITERACY** - How to communicate (knowledge level)
5. **ENGAGEMENT** - How deep they want to go (passive → advocate)

Collection happens:
- **Explicitly** - State, LGA, Voter status (ask at start)
- **Strategically** - Occupation, Age (ask when relevant)
- **Implicitly** - Issues, Sentiment, Life stage (extract from every message)

The result: Every response feels personally relevant without being creepy.
