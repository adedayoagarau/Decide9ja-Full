# Decide9ja

## The AI-Powered Political Intelligence Platform for Nigeria

---

# The Problem

**220 million Nigerians lack reliable access to political information.**

- **Information Asymmetry**: Voters don't know their representatives, their voting records, or budget allocations to their communities
- **Fragmented Data**: Political information is scattered across INEC, BudgIT, news outlets, and government portals with no unified access
- **Misinformation Epidemic**: WhatsApp forwards and social media spread false political claims with no verification tools
- **Language Barriers**: Most civic tech serves English speakers only, excluding millions who communicate in Pidgin, Hausa, Yoruba, or Igbo
- **Rural Exclusion**: Web-first platforms miss the 70%+ of Nigerians whose primary internet is WhatsApp

**The 2027 election cycle is approaching. Nigerians need a trusted source of political truth.**

---

# The Solution

**Decide9ja is the "everything app" for Nigerian politics.**

We combine the largest political knowledge base in Nigeria with agentic AI to deliver instant, accurate, sourced political intelligence—via WhatsApp, web, and voice.

### What Users Can Do

| Ask About | Example Query |
|-----------|---------------|
| **Representatives** | "Who is my senator for Lagos Central?" |
| **Politicians** | "What has Tinubu done about fuel subsidy?" |
| **Elections** | "2023 presidential results in Kano" |
| **Budget** | "How much was allocated to education in 2024?" |
| **History** | "What coups happened in Nigeria?" |
| **Fact-Checking** | "Did Atiku really say this?" |
| **Issues** | "Report bad roads in my LGA" |

**Every answer includes sources: INEC, BudgIT, verified news, Wikipedia.**

---

# Platform Features

## Core Intelligence

- **Representative Finder**: Instant lookup across 774 LGAs, 360 federal constituencies, 109 senatorial districts
- **Politician Profiles**: 4,789+ profiles with voting records, promises, controversies, net worth
- **Election Results**: Complete data from 2007-2023 (presidential, gubernatorial, legislative)
- **Budget Tracker**: 74,000+ records from BudgIT—federal allocations, FAAC, constituency projects
- **Fact Checker**: Verify claims against our verified database
- **News Intelligence**: Real-time aggregation from 5 major outlets, updated every 2 hours

## Community & Engagement

- **Issue Reporting**: Citizens report local problems (power, roads, water, security)
- **Daily Briefings**: Personalized civic digest based on location and interests
- **Civic Quizzes**: Gamified learning about Nigerian politics and history
- **Achievement System**: Badges and leaderboards for civic engagement

## Multi-Channel Access

| Channel | Status | Reach |
|---------|--------|-------|
| **WhatsApp Bot** | Live | 49M Nigerian users |
| **Web App** | Live | Urban, professional |
| **Voice Calls** | Beta | Feature phone users |
| **SMS Fallback** | Ready | Rural areas |

---

# Data Assets

## The Largest Nigerian Political Knowledge Base

| Source | Records | Content |
|--------|---------|---------|
| **Wikidata** | 8,392 | Politicians, parties, states, events |
| **Wikipedia** | 1,646 | Historical articles, coups, transitions |
| **BudgIT** | 74,000+ | Budget data, FAAC allocations, MDA projects |
| **INEC** | 774 LGAs | Electoral geography, polling units, results |
| **News Crawlers** | Live | 5 major Nigerian outlets |
| **Academic Archives** | 110MB | Nigerian governance research |

**Total: 189MB of structured, sourced, verified political intelligence.**

## Data Quality

- **Dual Search**: Vector embeddings + keyword search for accuracy
- **Source Weighting**: INEC official > Premium Times > social media
- **Neutrality Checking**: Flags partisan language automatically
- **Citation Requirement**: Every response includes sources

---

# Technical Architecture

## Stack Overview

```
FRONTEND                    BACKEND                     DATA
─────────────────────────   ─────────────────────────   ─────────────────────
Next.js 16 + React 19       FastAPI + Python            PostgreSQL
TypeScript 5                Claude API (LLM)            Vector Embeddings
Tailwind CSS 4              OpenAI (Embeddings)         Knowledge Graph
Radix UI                    Twilio (WhatsApp/Voice)     Redis Cache
                            NetworkX (Graph)
```

## AI System

**Multi-Agent Architecture**:
- Understanding Agent: Classifies intent
- Retrieval Agent: Routes to optimal data source
- Verifier Agent: Fact-checks claims
- Memory Agent: Maintains conversation context

**Nigerian-Optimized NLP**:
- 5 languages (English, Pidgin, Hausa, Yoruba, Igbo)
- Fuzzy matching for name variations ("Tinubu" = "BAT" = "Jagaban")
- Entity extraction for all 37 states, 774 LGAs

## Production Deployment

- **Hosting**: Railway (auto-deploy on git push)
- **Database**: PostgreSQL with pgvector
- **Background Jobs**: APScheduler for news crawling, alerts
- **News Crawler**: Azure Functions (free tier)

---

# Market Opportunity

## The Numbers

| Metric | Value |
|--------|-------|
| Nigeria Population | 220M+ |
| WhatsApp Users | 49M |
| Internet Users | 122M |
| Eligible Voters | 93M registered |
| Politically Engaged (Target) | 15M+ |

## Why Now

1. **2027 Election Cycle**: Peak demand for political information
2. **WhatsApp Penetration**: Primary internet for most Nigerians
3. **Civic Tech Momentum**: Growing NGO investment in voter education
4. **AI Maturity**: LLMs now capable of nuanced political Q&A
5. **Data Availability**: Open government data finally accessible

## Revenue Opportunities

| Model | Target Customer |
|-------|-----------------|
| **B2B API** | NGOs, media houses, research firms |
| **Premium Tier** | Power users, journalists, analysts |
| **Civic Partnerships** | BudgIT, SERAP, election observers |
| **Government Contracts** | INEC, state election bodies |
| **Embedded Widgets** | Media sites, civic organizations |

---

# Competitive Advantage

## Why Decide9ja Wins

| Aspect | Decide9ja | Competitors |
|--------|-----------|-------------|
| **Politicians Covered** | 4,789+ | 50-200 |
| **Geographic Depth** | 774 LGAs, 7-layer hierarchy | State-level only |
| **Data Sources** | 6+ authoritative | 1-2 sources |
| **Languages** | 5 Nigerian languages | English only |
| **User Channels** | WhatsApp + Web + Voice | Single channel |
| **AI System** | Multi-agent, agentic | Single LLM or none |
| **Real-Time News** | Auto-updated 2-hourly | Manual or none |
| **Community Features** | Issue reporting + gamification | Lookup only |

## Technical Moat

1. **Nigerian NLP**: Fuzzy matching for Nigerian names is hard to replicate
2. **Data Relationships**: Knowledge graph connects politicians, parties, events
3. **Multi-Source Retrieval**: Combines database, knowledge graph, news, web
4. **Production Hardening**: Security, rate limiting, prompt injection guards

---

# Current State

## What's Built

- **42,000+ lines** of production Python backend
- **60+ services** covering all platform features
- **21 API routes** for web and mobile clients
- **Full Next.js frontend** with politician search, issues, dashboard
- **WhatsApp bot** with guided onboarding and conversational AI
- **Comprehensive test suite** for critical paths

## What's Working

- Production deployment on Railway
- WhatsApp webhook receiving messages
- Knowledge graph queries returning results
- News crawler updating every 2 hours
- Full CRUD for issues, politicians, users

## What's Needed

| Priority | Need | Why |
|----------|------|-----|
| **Critical** | User acquisition | Platform ready, needs users |
| **High** | B2B sales | Revenue from API customers |
| **High** | Partnerships | BudgIT, INEC, NGOs for data + distribution |
| **Medium** | Mobile app | Native experience for power users |
| **Medium** | Fine-tuned models | Nigerian political domain expertise |

---

# Roadmap

## Phase 1: Growth (0-6 months)
- Launch marketing campaign for 2027 election interest
- Onboard first 10 B2B API customers
- Secure partnerships with 3 civic organizations
- Target: 50,000 active WhatsApp users

## Phase 2: Scale (6-12 months)
- 2027 election prediction engine
- Constituency-level sentiment analysis
- Civic education certification program
- Target: 500,000 users, $100K ARR

## Phase 3: Expand (12-24 months)
- Multi-country expansion (Ghana, Kenya, South Africa)
- Real-time parliament session tracking
- Enterprise platform for media companies
- Target: $1M ARR, regional presence

---

# The Ask

## Looking For: Co-Founder(s)

The engineering foundation is solid. What's needed:

### Ideal Co-Founder Profile

**Option A: Growth/Product**
- Experience scaling consumer products in Africa
- Marketing expertise (viral campaigns, community building)
- Product intuition for emerging market users

**Option B: Business Development**
- B2B/B2G sales experience in Nigeria
- NGO, government, or media industry connections
- Fundraising experience for African startups

### What You'd Own

- Go-to-market strategy and execution
- Revenue generation (B2B API, partnerships)
- Fundraising and investor relations
- Team building (sales, marketing, operations)

### What's Already Built

- Full technical platform (no CTO needed immediately)
- Production infrastructure (Railway, PostgreSQL, Redis)
- Complete data pipeline (scrapers, knowledge graph, RAG)
- Multi-channel delivery (WhatsApp, web, voice)

---

# Why This Matters

Nigeria is Africa's largest democracy. 93 million registered voters deserve:

- **Truth** over WhatsApp misinformation
- **Access** to their representatives' records
- **Transparency** in how their money is spent
- **Voice** to report issues in their communities

**Decide9ja makes informed citizenship possible.**

The platform is built. The data is ready. The 2027 election is coming.

**Let's empower Nigerian voters together.**

---

## Contact

[Add your contact information here]

---

*Built with data from INEC, BudgIT, Wikipedia, Wikidata, and verified Nigerian news sources.*
*All political information is presented neutrally without endorsement of any candidate or party.*
