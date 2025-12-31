# DECIDE9JA WEB DASHBOARD
## Complete Next.js Project Structure & Wireframes

---

# PROJECT STRUCTURE

```
decide9ja-web/
├── app/
│   ├── layout.tsx                    # Root layout with nav
│   ├── page.tsx                      # Landing page
│   ├── globals.css                   # Global styles
│   │
│   ├── (public)/                     # Public pages group
│   │   ├── politicians/
│   │   │   ├── page.tsx              # Politician directory
│   │   │   └── [id]/
│   │   │       └── page.tsx          # Politician profile
│   │   │
│   │   ├── representatives/
│   │   │   └── page.tsx              # Find my reps
│   │   │
│   │   ├── issues/
│   │   │   ├── page.tsx              # Issue explorer
│   │   │   └── [id]/
│   │   │       └── page.tsx          # Single issue
│   │   │
│   │   ├── states/
│   │   │   ├── page.tsx              # State list
│   │   │   └── [state]/
│   │   │       └── page.tsx          # State page
│   │   │
│   │   └── search/
│   │       └── page.tsx              # Search results
│   │
│   ├── admin/                        # Admin dashboard
│   │   ├── layout.tsx                # Admin layout
│   │   ├── page.tsx                  # Admin overview
│   │   ├── users/
│   │   │   └── page.tsx              # User management
│   │   ├── analytics/
│   │   │   └── page.tsx              # Detailed analytics
│   │   ├── issues/
│   │   │   └── page.tsx              # Issue moderation
│   │   └── content/
│   │       └── page.tsx              # Content management
│   │
│   └── api/                          # API routes (proxy to FastAPI)
│       ├── politicians/
│       │   └── route.ts
│       ├── representatives/
│       │   └── route.ts
│       └── stats/
│           └── route.ts
│
├── components/
│   ├── ui/                           # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── badge.tsx
│   │   ├── avatar.tsx
│   │   ├── tabs.tsx
│   │   ├── dialog.tsx
│   │   ├── dropdown-menu.tsx
│   │   └── ...
│   │
│   ├── layout/
│   │   ├── header.tsx                # Main navigation
│   │   ├── footer.tsx                # Site footer
│   │   ├── mobile-nav.tsx            # Mobile menu
│   │   └── admin-sidebar.tsx         # Admin navigation
│   │
│   ├── politicians/
│   │   ├── politician-card.tsx       # Card in directory
│   │   ├── politician-profile.tsx    # Full profile
│   │   ├── promise-tracker.tsx       # Promise list
│   │   ├── politician-timeline.tsx   # Activity timeline
│   │   └── politician-search.tsx     # Search component
│   │
│   ├── representatives/
│   │   ├── location-picker.tsx       # State/LGA selector
│   │   ├── rep-card.tsx              # Representative card
│   │   └── rep-list.tsx              # Grouped rep list
│   │
│   ├── issues/
│   │   ├── issue-card.tsx            # Issue in list
│   │   ├── issue-detail.tsx          # Full issue view
│   │   ├── issue-timeline.tsx        # Event timeline
│   │   ├── issue-map.tsx             # Location on map
│   │   └── report-issue-form.tsx     # Report new issue
│   │
│   ├── maps/
│   │   ├── nigeria-map.tsx           # Interactive Nigeria map
│   │   └── state-map.tsx             # Single state map
│   │
│   ├── charts/
│   │   ├── message-chart.tsx         # Messages over time
│   │   ├── user-chart.tsx            # User growth
│   │   ├── domain-chart.tsx          # Issues by domain
│   │   └── state-chart.tsx           # Activity by state
│   │
│   └── shared/
│       ├── search-bar.tsx            # Global search
│       ├── whatsapp-cta.tsx          # WhatsApp button
│       ├── stats-counter.tsx         # Animated counter
│       ├── loading-skeleton.tsx      # Loading states
│       └── empty-state.tsx           # No results
│
├── lib/
│   ├── api.ts                        # API client
│   ├── utils.ts                      # Utility functions
│   ├── constants.ts                  # App constants
│   └── types.ts                      # TypeScript types
│
├── hooks/
│   ├── use-politicians.ts            # Politician data hooks
│   ├── use-representatives.ts        # Rep lookup hooks
│   ├── use-issues.ts                 # Issue data hooks
│   └── use-analytics.ts              # Admin analytics hooks
│
├── public/
│   ├── images/
│   │   ├── logo.svg
│   │   ├── nigeria-map.svg
│   │   └── placeholder-avatar.png
│   └── fonts/
│
├── styles/
│   └── themes.css                    # Color themes
│
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
├── package.json
└── README.md
```

---

# WIREFRAMES

## Page 1: Landing Page (/)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 🇳🇬 Decide9ja              Politicians  Issues  About    [WhatsApp] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│                                                                             │
│                    Know Your Representatives.                               │
│                    Hold Them Accountable.                                   │
│                                                                             │
│                    Nigeria's civic information platform.                    │
│                    Find your reps, track promises, report issues.           │
│                                                                             │
│                                                                             │
│         ┌───────────────────────────────────────────────────────┐          │
│         │                                                       │          │
│         │   Find Your Representatives                           │          │
│         │                                                       │          │
│         │   ┌─────────────────────┐  ┌─────────────────────┐   │          │
│         │   │ Select State      ▼│  │ Select LGA        ▼│   │          │
│         │   └─────────────────────┘  └─────────────────────┘   │          │
│         │                                                       │          │
│         │              ┌────────────────────┐                   │          │
│         │              │  Find My Reps  →   │                   │          │
│         │              └────────────────────┘                   │          │
│         │                                                       │          │
│         └───────────────────────────────────────────────────────┘          │
│                                                                             │
│                        ─── or use WhatsApp ───                              │
│                                                                             │
│                           ┌──────────┐                                      │
│                           │ QR CODE  │                                      │
│                           │          │                                      │
│                           └──────────┘                                      │
│                        Send "Hi" to start                                   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│                                                                             │
│     ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│     │               │    │               │    │               │           │
│     │     505       │    │      36       │    │    1,247      │           │
│     │  Politicians  │    │    States     │    │    Issues     │           │
│     │   Tracked     │    │   Covered     │    │   Reported    │           │
│     │               │    │               │    │               │           │
│     └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     TRENDING ISSUES                                          [View All →]   │
│                                                                             │
│     ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐│
│     │ 🔴 Power            │ │ 🟡 Infrastructure   │ │ 🟡 Security         ││
│     │                     │ │                     │ │                     ││
│     │ National Grid       │ │ Lagos-Ibadan        │ │ Kaduna Rail         ││
│     │ Collapse #7         │ │ Expressway          │ │ Safety              ││
│     │                     │ │                     │ │                     ││
│     │ 📍 Nationwide       │ │ 📍 Lagos, Ogun      │ │ 📍 Kaduna, FCT      ││
│     │ Updated 2h ago      │ │ Updated 1d ago      │ │ Updated 3d ago      ││
│     │                     │ │                     │ │                     ││
│     │ [View Issue →]      │ │ [View Issue →]      │ │ [View Issue →]      ││
│     └─────────────────────┘ └─────────────────────┘ └─────────────────────┘│
│                                                                             │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     HOW IT WORKS                                                            │
│                                                                             │
│     ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐      │
│     │       1         │    │       2         │    │       3         │      │
│     │                 │    │                 │    │                 │      │
│     │  📍 Enter your  │    │  👥 See your    │    │  📝 Track &     │      │
│     │    location     │    │ representatives │    │    report       │      │
│     │                 │    │                 │    │                 │      │
│     └─────────────────┘    └─────────────────┘    └─────────────────┘      │
│                                                                             │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     FEATURED POLITICIANS                                     [View All →]   │
│                                                                             │
│     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│     │ ┌────┐       │ │ ┌────┐       │ │ ┌────┐       │ │ ┌────┐       │    │
│     │ │IMG │       │ │ │IMG │       │ │ │IMG │       │ │ │IMG │       │    │
│     │ └────┘       │ │ └────┘       │ │ └────┘       │ │ └────┘       │    │
│     │ Bola Tinubu  │ │ Sanwo-Olu   │ │ Peter Obi    │ │ Atiku        │    │
│     │ President    │ │ Gov Lagos   │ │ LP Leader    │ │ PDP Leader   │    │
│     │ APC          │ │ APC         │ │ LP           │ │ PDP          │    │
│     └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘    │
│                                                                             │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  🇳🇬 Decide9ja                                                      │   │
│  │                                                                     │   │
│  │  About   Contact   Privacy   Terms                                  │   │
│  │                                                                     │   │
│  │  © 2024 Decide9ja. Built for Nigerians.                            │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 2: Find My Representatives (/representatives)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 🇳🇬 Decide9ja              Politicians  Issues  About    [WhatsApp] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     Find Your Representatives                                               │
│     Enter your location to see who represents you at every level           │
│                                                                             │
│     ┌────────────────────────────────────────────────────────────────┐     │
│     │                                                                │     │
│     │   ┌─────────────────────┐    ┌─────────────────────┐          │     │
│     │   │ Lagos             ▼│    │ Alimosho          ▼│          │     │
│     │   │ State              │    │ LGA                │          │     │
│     │   └─────────────────────┘    └─────────────────────┘          │     │
│     │                                                                │     │
│     │   ┌──────────────────────────────────────────┐                │     │
│     │   │  📍 Or use my current location           │                │     │
│     │   └──────────────────────────────────────────┘                │     │
│     │                                                                │     │
│     └────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     📍 SHOWING REPRESENTATIVES FOR: Alimosho, Lagos                        │
│        Senatorial District: Lagos West                                      │
│        Federal Constituency: Alimosho Federal Constituency                  │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     🇳🇬 FEDERAL LEVEL                                                       │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  PRESIDENT                                                      │    │
│     │  ┌────────┐                                                     │    │
│     │  │  IMG   │  Bola Ahmed Tinubu                                  │    │
│     │  │        │  All Progressives Congress (APC)                    │    │
│     │  └────────┘  In office since: May 29, 2023                      │    │
│     │                                                                 │    │
│     │              Promise Score: ████████░░░░░░░░ 23%               │    │
│     │                                                                 │    │
│     │              [View Full Profile →]                              │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                                                                 │    │
│     │  SENATOR (Lagos West)                                           │    │
│     │  ┌────────┐                                                     │    │
│     │  │  IMG   │  Solomon Olamilekan Adeola                          │    │
│     │  │        │  All Progressives Congress (APC)                    │    │
│     │  └────────┘  In office since: June 2023                         │    │
│     │                                                                 │    │
│     │              Attendance: 78%  •  Bills Sponsored: 3             │    │
│     │                                                                 │    │
│     │              [View Full Profile →]                              │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                                                                 │    │
│     │  HOUSE OF REPRESENTATIVES (Alimosho Federal)                    │    │
│     │  ┌────────┐                                                     │    │
│     │  │  IMG   │  Kehinde Joseph Odeneye                             │    │
│     │  │        │  All Progressives Congress (APC)                    │    │
│     │  └────────┘  In office since: June 2023                         │    │
│     │                                                                 │    │
│     │              Attendance: 82%  •  Bills Sponsored: 1             │    │
│     │                                                                 │    │
│     │              [View Full Profile →]                              │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│                                                                             │
│     🏛️ STATE LEVEL                                                         │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  GOVERNOR                                                       │    │
│     │  ┌────────┐                                                     │    │
│     │  │  IMG   │  Babajide Olusola Sanwo-Olu                         │    │
│     │  │        │  All Progressives Congress (APC)                    │    │
│     │  └────────┘  In office since: May 2019 (2nd term)               │    │
│     │                                                                 │    │
│     │              Promise Score: ████████████░░░░ 31%               │    │
│     │                                                                 │    │
│     │              [View Full Profile →]                              │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                                                                 │    │
│     │  STATE HOUSE OF ASSEMBLY (Alimosho I)                           │    │
│     │  ┌────────┐                                                     │    │
│     │  │  IMG   │  Bisi Yusuff                                        │    │
│     │  │        │  All Progressives Congress (APC)                    │    │
│     │  └────────┘                                                     │    │
│     │                                                                 │    │
│     │              [View Full Profile →]                              │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│                                                                             │
│     🏘️ LOCAL LEVEL                                                         │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  LGA CHAIRMAN                                                   │    │
│     │  ┌────────┐                                                     │    │
│     │  │  IMG   │  Jelili Sulaimon                                    │    │
│     │  │        │  All Progressives Congress (APC)                    │    │
│     │  └────────┘                                                     │    │
│     │                                                                 │    │
│     │              [View Full Profile →]                              │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  📝 Report an Issue in Alimosho                                │    │
│     │                                                                 │    │
│     │  See a problem? Let us know. We'll track it and connect it    │    │
│     │  to the responsible representatives.                           │    │
│     │                                                                 │    │
│     │                   [ Report Issue → ]                            │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│                                                                             │
│     💬 PREFER WHATSAPP?                                                    │
│                                                                             │
│     Ask about your representatives on WhatsApp.                             │
│     Just send "Who is my senator?" to get started.                         │
│                                                                             │
│                      [ Open WhatsApp → ]                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 3: Politician Directory (/politicians)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 🇳🇬 Decide9ja              Politicians  Issues  About    [WhatsApp] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     Politicians                                                             │
│     505 politicians tracked across Nigeria                                  │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     ┌────────────────────────────────────────────────────────────────┐     │
│     │ 🔍 Search politicians...                                       │     │
│     └────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│     ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│     │ Position ▼│ │ Party    ▼│ │ State    ▼│ │ Sort by  ▼│           │
│     │ All        │ │ All        │ │ All        │ │ Name A-Z   │           │
│     └────────────┘ └────────────┘ └────────────┘ └────────────┘           │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     Showing 505 politicians                                 [Grid] [List]   │
│                                                                             │
│     ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐         │
│     │                  │ │                  │ │                  │         │
│     │    ┌────────┐    │ │    ┌────────┐    │ │    ┌────────┐    │         │
│     │    │  IMG   │    │ │    │  IMG   │    │ │    │  IMG   │    │         │
│     │    │        │    │ │    │        │    │ │    │        │    │         │
│     │    └────────┘    │ │    └────────┘    │ │    └────────┘    │         │
│     │                  │ │                  │ │                  │         │
│     │  Bola Tinubu     │ │  Babajide        │ │  Peter Obi       │         │
│     │                  │ │  Sanwo-Olu       │ │                  │         │
│     │  ┌─────┐         │ │  ┌─────┐         │ │  ┌─────┐         │         │
│     │  │ APC │         │ │  │ APC │         │ │  │ LP  │         │         │
│     │  └─────┘         │ │  └─────┘         │ │  └─────┘         │         │
│     │                  │ │                  │ │                  │         │
│     │  President       │ │  Governor        │ │  Former Governor │         │
│     │  Federal         │ │  Lagos           │ │  Anambra         │         │
│     │                  │ │                  │ │                  │         │
│     │  Promise: 23%    │ │  Promise: 31%    │ │  Promise: --     │         │
│     │                  │ │                  │ │                  │         │
│     │  [View Profile]  │ │  [View Profile]  │ │  [View Profile]  │         │
│     │                  │ │                  │ │                  │         │
│     └──────────────────┘ └──────────────────┘ └──────────────────┘         │
│                                                                             │
│     ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐         │
│     │                  │ │                  │ │                  │         │
│     │    ┌────────┐    │ │    ┌────────┐    │ │    ┌────────┐    │         │
│     │    │  IMG   │    │ │    │  IMG   │    │ │    │  IMG   │    │         │
│     │    │        │    │ │    │        │    │ │    │        │    │         │
│     │    └────────┘    │ │    └────────┘    │ │    └────────┘    │         │
│     │                  │ │                  │ │                  │         │
│     │  Atiku           │ │  Nyesom Wike     │ │  Godswill        │         │
│     │  Abubakar        │ │                  │ │  Akpabio         │         │
│     │  ┌─────┐         │ │  ┌─────┐         │ │  ┌─────┐         │         │
│     │  │ PDP │         │ │  │ PDP │         │ │  │ APC │         │         │
│     │  └─────┘         │ │  └─────┘         │ │  └─────┘         │         │
│     │                  │ │                  │ │                  │         │
│     │  Former VP       │ │  FCT Minister    │ │  Senate Pres.    │         │
│     │  Federal         │ │  Federal         │ │  Akwa Ibom       │         │
│     │                  │ │                  │ │                  │         │
│     │  [View Profile]  │ │  [View Profile]  │ │  [View Profile]  │         │
│     │                  │ │                  │ │                  │         │
│     └──────────────────┘ └──────────────────┘ └──────────────────┘         │
│                                                                             │
│     ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐         │
│     │        ...       │ │        ...       │ │        ...       │         │
│     └──────────────────┘ └──────────────────┘ └──────────────────┘         │
│                                                                             │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │         ◀ Previous    1  2  3  4  5  ...  51    Next ▶         │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 4: Politician Profile (/politicians/[id])

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 🇳🇬 Decide9ja              Politicians  Issues  About    [WhatsApp] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ← Back to Politicians                                                      │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │    ┌──────────────┐                                             │    │
│     │    │              │    Babajide Olusola Sanwo-Olu               │    │
│     │    │              │                                             │    │
│     │    │     IMG      │    Governor of Lagos State                  │    │
│     │    │              │                                             │    │
│     │    │              │    ┌─────┐                                  │    │
│     │    └──────────────┘    │ APC │  All Progressives Congress       │    │
│     │                        └─────┘                                  │    │
│     │                                                                 │    │
│     │    📅 In office since May 29, 2019 (2nd term)                  │    │
│     │    📍 Represents Lagos State (14+ million people)              │    │
│     │                                                                 │    │
│     │    ┌──────────────────────────────────────────┐                │    │
│     │    │ 💬 Ask about this politician on WhatsApp │                │    │
│     │    └──────────────────────────────────────────┘                │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ Overview │ Promises │ Timeline │ Related Issues │ Contact       │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     OVERVIEW                                                                │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  BIOGRAPHY                                                      │    │
│     │  ─────────                                                      │    │
│     │                                                                 │    │
│     │  Babajide Olusola Sanwo-Olu (born June 25, 1965) is a          │    │
│     │  Nigerian politician serving as the Governor of Lagos State    │    │
│     │  since May 2019. He is currently serving his second term.      │    │
│     │                                                                 │    │
│     │  Before becoming governor, he served as Commissioner for       │    │
│     │  Commerce and Industry, Commissioner for Establishments,       │    │
│     │  Training and Pensions, and Managing Director of First         │    │
│     │  Atlantic Bank.                                                 │    │
│     │                                                                 │    │
│     │  EDUCATION                                                      │    │
│     │  ─────────                                                      │    │
│     │  • University of Lagos (B.Sc. Surveying)                       │    │
│     │  • London Business School (MBA)                                │    │
│     │  • Harvard Kennedy School (Public Administration)              │    │
│     │                                                                 │    │
│     │  PREVIOUS POSITIONS                                             │    │
│     │  ──────────────────                                             │    │
│     │  • MD/CEO, First Atlantic Bank                                 │    │
│     │  • Commissioner, Lagos Ministry of Commerce                    │    │
│     │  • Commissioner, Establishments & Training                     │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  QUICK STATS                                                    │    │
│     │                                                                 │    │
│     │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │    │
│     │  │     31%       │  │      12       │  │      8        │       │    │
│     │  │   Promise     │  │   Promises    │  │   Related     │       │    │
│     │  │    Score      │  │     Kept      │  │    Issues     │       │    │
│     │  └───────────────┘  └───────────────┘  └───────────────┘       │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│                                                                             │
│     PROMISE TRACKER                                                         │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  Promise Score: 31%                                             │    │
│     │                                                                 │    │
│     │  ███████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░    │    │
│     │                                                                 │    │
│     │  ✅ Kept: 12    ⏳ In Progress: 8    ❌ Broken: 3    ❓ TBD: 15 │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ ✅ KEPT                                                         │    │
│     │                                                                 │    │
│     │ Lagos Rail Mass Transit (Blue Line)                            │    │
│     │ Promised: 2019 Campaign • Delivered: September 2023            │    │
│     │                                                                 │    │
│     │ The Blue Line is a 13km rail line from Marina to Mile 2.       │    │
│     │ Commercial operations began September 2023.                    │    │
│     │                                                                 │    │
│     │ Evidence: [Official Commissioning ↗] [News Coverage ↗]         │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │ ✅ KEPT                                                         │    │
│     │                                                                 │    │
│     │ Oshodi Transport Interchange                                   │    │
│     │ Promised: 2019 • Delivered: April 2019                         │    │
│     │                                                                 │    │
│     │ Multi-modal transport hub at Oshodi serving buses, BRT.        │    │
│     │                                                                 │    │
│     │ Evidence: [Project Completion ↗]                               │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │ ⏳ IN PROGRESS                                                  │    │
│     │                                                                 │    │
│     │ Fourth Mainland Bridge                                         │    │
│     │ Promised: 2019 • Status: Feasibility/Planning Phase            │    │
│     │                                                                 │    │
│     │ 37km bridge from Lekki to Ikorodu. PPP model announced.        │    │
│     │ Construction not yet started as of December 2024.              │    │
│     │                                                                 │    │
│     │ Evidence: [Feasibility Report ↗] [News Update Dec 2024 ↗]      │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │ ❌ BROKEN                                                       │    │
│     │                                                                 │    │
│     │ End Lagos Traffic in First Term                                │    │
│     │ Promised: 2019 • Outcome: Traffic remains severe               │    │
│     │                                                                 │    │
│     │ Campaign promise to solve Lagos traffic. Traffic remains       │    │
│     │ a major issue despite some infrastructure improvements.        │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│     [View All 38 Promises →]                                                │
│                                                                             │
│                                                                             │
│     RELATED ISSUES IN LAGOS                                                 │
│                                                                             │
│     ┌─────────────────────┐ ┌─────────────────────┐                        │
│     │ 🟡 Infrastructure   │ │ 🟡 Flooding         │                        │
│     │                     │ │                     │                        │
│     │ Lekki-Epe Road      │ │ Victoria Island     │                        │
│     │ Expansion           │ │ Flooding            │                        │
│     │                     │ │                     │                        │
│     │ [View →]            │ │ [View →]            │                        │
│     └─────────────────────┘ └─────────────────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 5: Issue Explorer (/issues)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 🇳🇬 Decide9ja              Politicians  Issues  About    [WhatsApp] │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     Issues Tracker                                                          │
│     Tracking 127 active issues across Nigeria                               │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     ┌────────────────────────────────────────────────────────────────┐     │
│     │ 🔍 Search issues...                                            │     │
│     └────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│     ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│     │ Domain   ▼│ │ State    ▼│ │ Severity ▼│ │ Status   ▼│           │
│     │ All        │ │ All        │ │ All        │ │ Active     │           │
│     └────────────┘ └────────────┘ └────────────┘ └────────────┘           │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │                    ┌─────────────────────┐                      │    │
│     │                    │                     │                      │    │
│     │                    │                     │                      │    │
│     │                    │   NIGERIA MAP       │                      │    │
│     │                    │                     │                      │    │
│     │                    │   (Interactive)     │                      │    │
│     │                    │                     │                      │    │
│     │                    │   Showing issue     │                      │    │
│     │                    │   density by state  │                      │    │
│     │                    │                     │                      │    │
│     │                    │   🔴 High           │                      │    │
│     │                    │   🟡 Medium         │                      │    │
│     │                    │   🟢 Low            │                      │    │
│     │                    │                     │                      │    │
│     │                    └─────────────────────┘                      │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│                                                                             │
│     DOMAIN BREAKDOWN                                                        │
│                                                                             │
│     ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │
│     │ 🔌     │ │ 🛣️     │ │ 🔒     │ │ 💧     │ │ 🏥     │ │ 📚     │     │
│     │ Power  │ │ Roads  │ │Security│ │ Water  │ │ Health │ │ Edu    │     │
│     │  23    │ │  31    │ │  18    │ │  12    │ │   9    │ │   8    │     │
│     └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘     │
│                                                                             │
│                                                                             │
│     ACTIVE ISSUES                                                           │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  🔴 SEVERE                                        Power         │    │
│     │                                                                 │    │
│     │  National Grid Collapse #7 (2024)                              │    │
│     │                                                                 │    │
│     │  The national power grid collapsed for the 7th time in 2024    │    │
│     │  on [date], plunging most of Nigeria into darkness.            │    │
│     │                                                                 │    │
│     │  📍 Nationwide                                                  │    │
│     │  📅 Last updated: 2 hours ago                                  │    │
│     │  📊 Confidence: High (verified by 3 sources)                   │    │
│     │  👥 Accountable: NERC, TCN, Ministry of Power                  │    │
│     │                                                                 │    │
│     │  Timeline: 12 events  •  Evidence: 8 artifacts                 │    │
│     │                                                                 │    │
│     │  [View Full Issue →]                                           │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                                                                 │    │
│     │  🟡 MODERATE                                    Infrastructure  │    │
│     │                                                                 │    │
│     │  Lagos-Ibadan Expressway Reconstruction Delays                 │    │
│     │                                                                 │    │
│     │  The Lagos-Ibadan expressway reconstruction project has        │    │
│     │  faced repeated delays since 2013.                             │    │
│     │                                                                 │    │
│     │  📍 Lagos, Ogun                                                │    │
│     │  📅 Last updated: 1 day ago                                    │    │
│     │  📊 Confidence: High (verified by 5 sources)                   │    │
│     │  👥 Accountable: Federal Ministry of Works, Julius Berger      │    │
│     │                                                                 │    │
│     │  Timeline: 24 events  •  Evidence: 15 artifacts                │    │
│     │                                                                 │    │
│     │  [View Full Issue →]                                           │    │
│     │                                                                 │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                                                                 │    │
│     │  🟡 MODERATE                                        Security    │    │
│     │                                                                 │    │
│     │  Kaduna-Abuja Rail Safety Concerns                             │    │
│     │                                                                 │    │
│     │  Security concerns persist on the Kaduna-Abuja rail line       │    │
│     │  following the 2022 attack.                                    │    │
│     │                                                                 │    │
│     │  📍 Kaduna, FCT                                                │    │
│     │  📅 Last updated: 3 days ago                                   │    │
│     │  📊 Confidence: Medium                                         │    │
│     │  👥 Accountable: NRC, Ministry of Transportation               │    │
│     │                                                                 │    │
│     │  [View Full Issue →]                                           │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│     [Load More Issues]                                                      │
│                                                                             │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                                                                 │    │
│     │  📝 Report a New Issue                                         │    │
│     │                                                                 │    │
│     │  See something that needs tracking? Report it.                 │    │
│     │                                                                 │    │
│     │  [Report Issue via WhatsApp →]   [Report on Web →]             │    │
│     │                                                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Page 6: Admin Dashboard (/admin)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 🇳🇬 Decide9ja Admin                               Ade ▼   [Logout]  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌────────────┬────────────────────────────────────────────────────────┐   │
│  │            │                                                        │   │
│  │  SIDEBAR   │                                                        │   │
│  │            │   OVERVIEW                                             │   │
│  │  ─────────│   Last updated: Just now                               │   │
│  │            │                                                        │   │
│  │  📊        │   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ │
│  │  Overview  │   │   247     │ │  1,842    │ │   68%     │ │   4.2     │ │
│  │            │   │  Users    │ │ Messages  │ │ Retention │ │ Avg Turns │ │
│  │  👥        │   │   ↑23%    │ │   ↑45%    │ │   ↑5%     │ │   ↓0.3    │ │
│  │  Users     │   └───────────┘ └───────────┘ └───────────┘ └───────────┘ │
│  │            │                                                        │   │
│  │  📈        │                                                        │   │
│  │  Analytics │   MESSAGE VOLUME (Last 7 Days)                         │   │
│  │            │   ┌────────────────────────────────────────────────┐   │   │
│  │  📝        │   │                                                │   │   │
│  │  Issues    │   │  300 ┤                                         │   │   │
│  │            │   │      │                         ╭───╮           │   │   │
│  │  📰        │   │  200 ┤              ╭───╮     │   │  ╭───╮    │   │   │
│  │  Content   │   │      │    ╭───╮    │   │╭───╮│   │ │   │    │   │   │
│  │            │   │  100 ┤   │   │╭───╮│   ││   ││   │╭│   │    │   │   │
│  │  ⚙️        │   │      │───│   ││   ││   ││   ││   ││   ││    │   │   │
│  │  Settings  │   │    0 ┼───┴───┴┴───┴┴───┴┴───┴┴───┴┴───┴─────   │   │
│  │            │   │       Mon  Tue  Wed  Thu  Fri  Sat  Sun        │   │   │
│  │            │   └────────────────────────────────────────────────┘   │   │
│  │            │                                                        │   │
│  │            │                                                        │   │
│  │            │   ┌─────────────────────────┐ ┌─────────────────────────┐ │
│  │            │   │ TOP QUERIES             │ │ TOP STATES              │ │
│  │            │   │ ─────────────           │ │ ──────────              │ │
│  │            │   │                         │ │                         │ │
│  │            │   │ 1. Who is my senator    │ │ 1. Lagos        89      │ │
│  │            │   │    156 queries          │ │    ████████████████     │ │
│  │            │   │                         │ │                         │ │
│  │            │   │ 2. Tell me about Tinubu│ │ 2. Ogun         34      │ │
│  │            │   │    98 queries           │ │    ████████             │ │
│  │            │   │                         │ │                         │ │
│  │            │   │ 3. Report bad road      │ │ 3. Rivers       28      │ │
│  │            │   │    67 queries           │ │    ███████              │ │
│  │            │   │                         │ │                         │ │
│  │            │   │ 4. My governor          │ │ 4. Kano         21      │ │
│  │            │   │    54 queries           │ │    █████                │ │
│  │            │   │                         │ │                         │ │
│  │            │   │ 5. Fuel price news      │ │ 5. FCT          19      │ │
│  │            │   │    43 queries           │ │    █████                │ │
│  │            │   │                         │ │                         │ │
│  │            │   └─────────────────────────┘ └─────────────────────────┘ │
│  │            │                                                        │   │
│  │            │                                                        │   │
│  │            │   RECENT ACTIVITY                                      │   │
│  │            │   ┌────────────────────────────────────────────────┐   │   │
│  │            │   │                                                │   │   │
│  │            │   │  🟢 New user from Lagos                       │   │   │
│  │            │   │     2 minutes ago                              │   │   │
│  │            │   │                                                │   │   │
│  │            │   │  📝 Issue reported: Bad road in Agege         │   │   │
│  │            │   │     15 minutes ago  [Review]                   │   │   │
│  │            │   │                                                │   │   │
│  │            │   │  💬 High engagement session (12 turns)        │   │   │
│  │            │   │     32 minutes ago                             │   │   │
│  │            │   │                                                │   │   │
│  │            │   │  🟢 New user from Kano                        │   │   │
│  │            │   │     1 hour ago                                 │   │   │
│  │            │   │                                                │   │   │
│  │            │   │  ⚠️ Webhook error - retry succeeded           │   │   │
│  │            │   │     2 hours ago                                │   │   │
│  │            │   │                                                │   │   │
│  │            │   └────────────────────────────────────────────────┘   │   │
│  │            │                                                        │   │
│  │            │                                                        │   │
│  │            │   ISSUES PENDING REVIEW                                │   │
│  │            │   ┌────────────────────────────────────────────────┐   │   │
│  │            │   │                                                │   │   │
│  │            │   │  🟡 Bad road in Agege, Lagos                  │   │   │
│  │            │   │     Reported 2 hours ago                       │   │   │
│  │            │   │     [Review] [Approve] [Reject]                │   │   │
│  │            │   │                                                │   │   │
│  │            │   │  🟡 No water in Kubwa, FCT                    │   │   │
│  │            │   │     Reported 5 hours ago                       │   │   │
│  │            │   │     [Review] [Approve] [Reject]                │   │   │
│  │            │   │                                                │   │   │
│  │            │   │  🟢 Flooding in Yaba, Lagos [Verified]        │   │   │
│  │            │   │     Approved 1 day ago                         │   │   │
│  │            │   │                                                │   │   │
│  │            │   └────────────────────────────────────────────────┘   │   │
│  │            │                                                        │   │
│  └────────────┴────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# COMPONENT SPECIFICATIONS

## 1. Header Component

```tsx
// components/layout/header.tsx

interface HeaderProps {
  showSearch?: boolean;
  variant?: 'default' | 'transparent';
}

/*
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🇳🇬 Decide9ja        [Search...]       Politicians  Issues  About  [WhatsApp]│
└─────────────────────────────────────────────────────────────────────────────┘

Mobile:
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🇳🇬 Decide9ja                                                    [☰ Menu]   │
└─────────────────────────────────────────────────────────────────────────────┘
*/
```

## 2. Politician Card Component

```tsx
// components/politicians/politician-card.tsx

interface PoliticianCardProps {
  id: string;
  name: string;
  position: string;
  party: string;
  state: string;
  imageUrl?: string;
  promiseScore?: number;
}

/*
┌──────────────────────────────┐
│       ┌──────────┐           │
│       │   IMG    │           │
│       └──────────┘           │
│                              │
│    Babajide Sanwo-Olu        │
│                              │
│    ┌─────┐                   │
│    │ APC │                   │
│    └─────┘                   │
│                              │
│    Governor                  │
│    Lagos State               │
│                              │
│    Promise: ████░░░ 31%      │
│                              │
│    [View Profile →]          │
│                              │
└──────────────────────────────┘
*/
```

## 3. Location Picker Component

```tsx
// components/representatives/location-picker.tsx

interface LocationPickerProps {
  onLocationSelect: (state: string, lga: string) => void;
  showGeolocate?: boolean;
}

/*
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ┌─────────────────────────┐  ┌─────────────────────────┐     │
│   │ Select State          ▼│  │ Select LGA            ▼│     │
│   └─────────────────────────┘  └─────────────────────────┘     │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  📍 Use my current location                              │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
*/
```

## 4. Issue Card Component

```tsx
// components/issues/issue-card.tsx

interface IssueCardProps {
  id: string;
  title: string;
  domain: string;
  severity: 'low' | 'moderate' | 'severe';
  location: string;
  updatedAt: string;
  eventCount: number;
  evidenceCount: number;
  confidence: 'low' | 'medium' | 'high';
}

/*
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  🔴 SEVERE                                          Power       │
│                                                                 │
│  National Grid Collapse #7 (2024)                               │
│                                                                 │
│  The national power grid collapsed for the 7th time...          │
│                                                                 │
│  📍 Nationwide                                                  │
│  📅 Updated 2 hours ago                                         │
│  📊 Confidence: High                                            │
│                                                                 │
│  Timeline: 12 events  •  Evidence: 8 artifacts                  │
│                                                                 │
│  [View Full Issue →]                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
*/
```

## 5. Nigeria Map Component

```tsx
// components/maps/nigeria-map.tsx

interface NigeriaMapProps {
  data: StateData[];
  onStateClick: (state: string) => void;
  colorScale: 'issues' | 'users' | 'custom';
}

/*
Interactive SVG map of Nigeria with:
- 36 states + FCT
- Hover states showing name + value
- Click to drill down
- Color scale legend
- Zoom controls
*/
```

## 6. Promise Tracker Component

```tsx
// components/politicians/promise-tracker.tsx

interface PromiseTrackerProps {
  promises: Promise[];
  summary: {
    kept: number;
    inProgress: number;
    broken: number;
    unknown: number;
  };
}

/*
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Promise Score: 31%                                             │
│                                                                 │
│  ███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │
│                                                                 │
│  ✅ Kept: 12    ⏳ In Progress: 8    ❌ Broken: 3    ❓ TBD: 15 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ✅ KEPT                                                         │
│                                                                 │
│ Lagos Rail Mass Transit (Blue Line)                             │
│ Promised: 2019  •  Delivered: September 2023                    │
│                                                                 │
│ [Evidence ↗]                                                    │
└─────────────────────────────────────────────────────────────────┘
*/
```

---

# COLOR SCHEME

```css
/* Nigerian-inspired palette */

:root {
  /* Primary - Nigerian Green */
  --primary-50: #f0fdf4;
  --primary-100: #dcfce7;
  --primary-500: #22c55e;
  --primary-600: #16a34a;
  --primary-700: #15803d;
  --primary-800: #166534;
  --primary-900: #14532d;
  
  /* Accent - Nigerian Flag colors */
  --green: #008751;
  --white: #ffffff;
  
  /* Severity colors */
  --severe: #ef4444;    /* Red */
  --moderate: #f59e0b;  /* Yellow/Orange */
  --low: #22c55e;       /* Green */
  
  /* Party colors */
  --apc: #1e3a8a;       /* Blue */
  --pdp: #dc2626;       /* Red */
  --lp: #16a34a;        /* Green */
  --nnpp: #7c3aed;      /* Purple */
  
  /* Neutrals */
  --gray-50: #f9fafb;
  --gray-100: #f3f4f6;
  --gray-200: #e5e7eb;
  --gray-300: #d1d5db;
  --gray-400: #9ca3af;
  --gray-500: #6b7280;
  --gray-600: #4b5563;
  --gray-700: #374151;
  --gray-800: #1f2937;
  --gray-900: #111827;
}
```

---

# API INTEGRATION

```typescript
// lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = {
  // Politicians
  politicians: {
    list: (params?: PoliticianFilters) => 
      fetch(`${API_BASE}/api/politicians?${new URLSearchParams(params)}`),
    get: (id: string) => 
      fetch(`${API_BASE}/api/politicians/${id}`),
    search: (query: string) => 
      fetch(`${API_BASE}/api/politicians/search?q=${query}`),
  },
  
  // Representatives
  representatives: {
    byLocation: (state: string, lga: string) =>
      fetch(`${API_BASE}/api/representatives?state=${state}&lga=${lga}`),
  },
  
  // Issues
  issues: {
    list: (params?: IssueFilters) =>
      fetch(`${API_BASE}/api/issues?${new URLSearchParams(params)}`),
    get: (id: string) =>
      fetch(`${API_BASE}/api/issues/${id}`),
  },
  
  // Stats
  stats: {
    overview: () =>
      fetch(`${API_BASE}/api/stats`),
  },
  
  // Admin
  admin: {
    analytics: () =>
      fetch(`${API_BASE}/api/admin/analytics/overview`),
    users: () =>
      fetch(`${API_BASE}/api/admin/users`),
    pendingIssues: () =>
      fetch(`${API_BASE}/api/admin/issues/pending`),
  },
};
```

---

# RESPONSIVE BREAKPOINTS

```css
/* Tailwind defaults */
sm: 640px   /* Mobile landscape */
md: 768px   /* Tablet */
lg: 1024px  /* Desktop */
xl: 1280px  /* Large desktop */
2xl: 1536px /* Extra large */
```

---

# DEPLOYMENT

```bash
# Vercel (recommended)
vercel

# Or build and export
npm run build
npm run start
```

---

# NEXT STEPS

1. Initialize Next.js project with shadcn/ui
2. Create layout and header components
3. Build landing page
4. Build representatives lookup (core feature)
5. Build politician directory and profile
6. Add admin dashboard
7. Connect to FastAPI backend
8. Deploy to Vercel

---

# ANTIGRAVITY PROMPT

See separate file: DECIDE9JA_FRONTEND_PROMPT.md
