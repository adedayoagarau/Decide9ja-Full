#!/usr/bin/env python3
"""
Seed Politicians Database
=========================
Populates the politicians table with Nigerian political figures from:
1. Wikidata JSON file (4,789 politicians)
2. Manual enrichment data for key figures

Run with: python scripts/seed_politicians.py

Options:
  --list     List politicians without seeding
  --count    Show count only
  --wikidata Import from wikidata JSON only (skip manual data)
  --manual   Use manual data only (skip wikidata)
"""

import os
import sys
import json
from datetime import datetime
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Path to wikidata politicians JSON
WIKIDATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "nigeria_knowledge_data", "wikidata", "nigerian_politicians.json"
)

def slugify(name: str) -> str:
    """Convert name to URL-safe slug."""
    return name.lower().replace(" ", "-").replace(".", "").replace("'", "")


# =============================================================================
# POLITICIAN DATA - Comprehensive list of key Nigerian politicians
# =============================================================================

POLITICIANS = [
    # ===========================================
    # FEDERAL EXECUTIVE
    # ===========================================
    {
        "name": "Bola Ahmed Tinubu",
        "party": "APC",
        "position": "President",
        "state": "Lagos",
        "bio": "16th President of Nigeria since May 29, 2023. Former Governor of Lagos State (1999-2007). Leader of the All Progressives Congress. Known as 'Jagaban' and credited with building the political structure that led to APC's victories."
    },
    {
        "name": "Kashim Shettima",
        "party": "APC",
        "position": "Vice President",
        "state": "Borno",
        "bio": "17th Vice President of Nigeria since May 29, 2023. Former Governor of Borno State (2011-2019). Served during the peak of Boko Haram insurgency. Former banker and Commissioner in Borno State."
    },

    # ===========================================
    # 2023 PRESIDENTIAL CANDIDATES
    # ===========================================
    {
        "name": "Atiku Abubakar",
        "party": "PDP",
        "position": "Former Vice President",
        "state": "Adamawa",
        "bio": "Vice President of Nigeria (1999-2007) under Obasanjo. PDP Presidential candidate in 2023, 2019, and 2007. Successful businessman. Founded the American University of Nigeria, Yola."
    },
    {
        "name": "Peter Obi",
        "party": "LP",
        "position": "Former Governor",
        "state": "Anambra",
        "bio": "Labour Party Presidential candidate in 2023. Former Governor of Anambra State (2006-2014). Known for his frugal governance style. Led the 'Obidient' movement that mobilized youth voters."
    },
    {
        "name": "Rabiu Musa Kwankwaso",
        "party": "NNPP",
        "position": "Former Governor",
        "state": "Kano",
        "bio": "NNPP Presidential candidate in 2023. Two-time Governor of Kano State. Former Minister of Defence. Leader of the 'Kwankwasiyya' political movement."
    },

    # ===========================================
    # NATIONAL ASSEMBLY LEADERSHIP
    # ===========================================
    {
        "name": "Godswill Akpabio",
        "party": "APC",
        "position": "Senate President",
        "state": "Akwa Ibom",
        "bio": "10th Senate President since June 2023. Former Governor of Akwa Ibom State (2007-2015). Former Minister of Niger Delta Affairs. Known for infrastructure development during his governorship."
    },
    {
        "name": "Jibrin Barau",
        "party": "APC",
        "position": "Deputy Senate President",
        "state": "Kano",
        "bio": "Deputy Senate President since June 2023. Senator representing Kano North. Former member of House of Representatives. Experienced legislator with multiple terms."
    },
    {
        "name": "Tajudeen Abbas",
        "party": "APC",
        "position": "Speaker of the House",
        "state": "Kaduna",
        "bio": "Speaker of the 10th House of Representatives since June 2023. Representing Zaria Federal Constituency. Fourth-term member of the House."
    },
    {
        "name": "Benjamin Kalu",
        "party": "APC",
        "position": "Deputy Speaker",
        "state": "Abia",
        "bio": "Deputy Speaker of the 10th House of Representatives. Representing Bende Federal Constituency, Abia State. Former spokesperson for the 9th House."
    },
    {
        "name": "Ali Ndume",
        "party": "APC",
        "position": "Senator",
        "state": "Borno",
        "bio": "Senator representing Borno South. Known for his vocal criticism of government policies on security. Former Senate Leader. Multiple-term senator."
    },

    # ===========================================
    # FORMER PRESIDENTS
    # ===========================================
    {
        "name": "Muhammadu Buhari",
        "party": "APC",
        "position": "Former President",
        "state": "Katsina",
        "bio": "15th President of Nigeria (2015-2023). Military Head of State (1983-1985). Led anti-corruption campaigns. Oversaw COVID-19 pandemic response and economic challenges."
    },
    {
        "name": "Goodluck Ebele Jonathan",
        "party": "PDP",
        "position": "Former President",
        "state": "Bayelsa",
        "bio": "14th President of Nigeria (2010-2015). First president from the Niger Delta. Conceded the 2015 election peacefully. Former Vice President and Deputy Governor."
    },
    {
        "name": "Olusegun Obasanjo",
        "party": "PDP",
        "position": "Former President",
        "state": "Ogun",
        "bio": "12th President (1999-2007) and former Military Head of State (1976-1979). Oversaw transition from military rule. Implemented debt relief and GSM revolution."
    },
    {
        "name": "Ibrahim Babangida",
        "party": "None",
        "position": "Former Military President",
        "state": "Niger",
        "bio": "Military President (1985-1993). Known as 'IBB' or 'Maradona'. Annulled June 12, 1993 election. Credited with establishing NYSC, NDE, and SAP reforms."
    },
    {
        "name": "Abdulsalami Abubakar",
        "party": "None",
        "position": "Former Head of State",
        "state": "Niger",
        "bio": "Military Head of State (1998-1999). Oversaw transition to democracy and handed power to Obasanjo. Retired General. Peace mediator in Africa."
    },

    # ===========================================
    # KEY MINISTERS (CURRENT CABINET)
    # ===========================================
    {
        "name": "Wale Edun",
        "party": "APC",
        "position": "Minister of Finance",
        "state": "Lagos",
        "bio": "Minister of Finance and Coordinating Minister of the Economy. Former Commissioner for Finance in Lagos State. Investment banker and economist."
    },
    {
        "name": "Nyesom Wike",
        "party": "PDP",
        "position": "Minister of FCT",
        "state": "Rivers",
        "bio": "Minister of the Federal Capital Territory since 2023. Former Governor of Rivers State (2015-2023). Known for infrastructure projects and political influence."
    },
    {
        "name": "Festus Keyamo",
        "party": "APC",
        "position": "Minister of Aviation",
        "state": "Delta",
        "bio": "Minister of Aviation and Aerospace Development. Human rights lawyer. Former spokesman for Tinubu 2023 campaign. Senior Advocate of Nigeria (SAN)."
    },
    {
        "name": "Abubakar Atiku Bagudu",
        "party": "APC",
        "position": "Minister of Budget",
        "state": "Kebbi",
        "bio": "Minister of Budget and Economic Planning. Former Governor of Kebbi State (2015-2023). Former Chairman of Nigerian Governors Forum."
    },

    # ===========================================
    # GOVERNORS - SOUTH WEST
    # ===========================================
    {
        "name": "Babajide Sanwo-Olu",
        "party": "APC",
        "position": "Governor",
        "state": "Lagos",
        "bio": "Governor of Lagos State since 2019. Former Commissioner for various ministries. Oversaw COVID-19 response and End SARS protests. Infrastructure focus."
    },
    {
        "name": "Dapo Abiodun",
        "party": "APC",
        "position": "Governor",
        "state": "Ogun",
        "bio": "Governor of Ogun State since 2019. Businessman and oil industry executive. Focus on industrialization and agricultural development."
    },
    {
        "name": "Seyi Makinde",
        "party": "PDP",
        "position": "Governor",
        "state": "Oyo",
        "bio": "Governor of Oyo State since 2019. Engineer and businessman. Focus on education, healthcare, and road infrastructure."
    },
    {
        "name": "Ademola Adeleke",
        "party": "PDP",
        "position": "Governor",
        "state": "Osun",
        "bio": "Governor of Osun State since 2022. Known as 'the dancing Senator'. Brother of late Isiaka Adeleke. Won after Supreme Court victory."
    },
    {
        "name": "Biodun Oyebanji",
        "party": "APC",
        "position": "Governor",
        "state": "Ekiti",
        "bio": "Governor of Ekiti State since 2022. Former Secretary to Ekiti State Government. Succeeded Kayode Fayemi."
    },
    {
        "name": "Lucky Aiyedatiwa",
        "party": "APC",
        "position": "Governor",
        "state": "Ondo",
        "bio": "Governor of Ondo State since 2024. Became governor after death of Rotimi Akeredolu. Former Deputy Governor."
    },

    # ===========================================
    # GOVERNORS - SOUTH EAST
    # ===========================================
    {
        "name": "Charles Soludo",
        "party": "APGA",
        "position": "Governor",
        "state": "Anambra",
        "bio": "Governor of Anambra State since 2022. Former CBN Governor (2004-2009). Renowned economist. Implemented banking consolidation reforms."
    },
    {
        "name": "Hope Uzodinma",
        "party": "APC",
        "position": "Governor",
        "state": "Imo",
        "bio": "Governor of Imo State since 2020. Supreme Court declared him winner after initial results. Former Senator. Businessman."
    },
    {
        "name": "Alex Otti",
        "party": "LP",
        "position": "Governor",
        "state": "Abia",
        "bio": "Governor of Abia State since 2023. Former Diamond Bank MD/CEO. Labour Party's highest elected official. Focus on debt clearance and civil service reform."
    },
    {
        "name": "Peter Mbah",
        "party": "PDP",
        "position": "Governor",
        "state": "Enugu",
        "bio": "Governor of Enugu State since 2023. Former Commissioner for Finance. Businessman with focus on economic growth target of $30B GDP."
    },
    {
        "name": "Francis Nwifuru",
        "party": "APC",
        "position": "Governor",
        "state": "Ebonyi",
        "bio": "Governor of Ebonyi State since 2023. Former Speaker of Ebonyi House of Assembly. Succeeded David Umahi."
    },

    # ===========================================
    # GOVERNORS - SOUTH SOUTH
    # ===========================================
    {
        "name": "Siminalayi Fubara",
        "party": "PDP",
        "position": "Governor",
        "state": "Rivers",
        "bio": "Governor of Rivers State since 2023. Former Accountant General of Rivers State. Succeeded Nyesom Wike amid political tensions."
    },
    {
        "name": "Umo Eno",
        "party": "PDP",
        "position": "Governor",
        "state": "Akwa Ibom",
        "bio": "Governor of Akwa Ibom State since 2023. Former Commissioner for Lands. Pastor and businessman. Succeeded Udom Emmanuel."
    },
    {
        "name": "Sheriff Oborevwori",
        "party": "PDP",
        "position": "Governor",
        "state": "Delta",
        "bio": "Governor of Delta State since 2023. Former Speaker of Delta House of Assembly. Succeeded Ifeanyi Okowa."
    },
    {
        "name": "Douye Diri",
        "party": "PDP",
        "position": "Governor",
        "state": "Bayelsa",
        "bio": "Governor of Bayelsa State since 2020. Supreme Court ruling. Former Senator. Focus on infrastructure and education."
    },
    {
        "name": "Bassey Otu",
        "party": "APC",
        "position": "Governor",
        "state": "Cross River",
        "bio": "Governor of Cross River State since 2023. Former Senator representing Cross River South. Succeeded Ben Ayade."
    },
    {
        "name": "Monday Okpebholo",
        "party": "APC",
        "position": "Governor",
        "state": "Edo",
        "bio": "Governor of Edo State since 2024. Won September 2024 governorship election. Former Senator. Succeeded Godwin Obaseki."
    },

    # ===========================================
    # GOVERNORS - NORTH CENTRAL
    # ===========================================
    {
        "name": "AbdulRahman AbdulRazaq",
        "party": "APC",
        "position": "Governor",
        "state": "Kwara",
        "bio": "Governor of Kwara State since 2019. Part of 'O to ge' (Enough is Enough) movement that ended Saraki dynasty. Businessman."
    },
    {
        "name": "Bala Mohammed",
        "party": "PDP",
        "position": "Governor",
        "state": "Bauchi",
        "bio": "Governor of Bauchi State since 2019. Former FCT Minister. Former Senator. Focus on education and agriculture."
    },
    {
        "name": "Caleb Mutfwang",
        "party": "PDP",
        "position": "Governor",
        "state": "Plateau",
        "bio": "Governor of Plateau State since 2023. Medical doctor and pastor. Won after tribunal battles. Focus on peace and unity."
    },
    {
        "name": "Hyacinth Alia",
        "party": "APC",
        "position": "Governor",
        "state": "Benue",
        "bio": "Governor of Benue State since 2023. Catholic priest. First clergy to become governor. Succeeded Samuel Ortom."
    },
    {
        "name": "Abdullahi Sule",
        "party": "APC",
        "position": "Governor",
        "state": "Nasarawa",
        "bio": "Governor of Nasarawa State since 2019. Former MD of Dangote Sugar Refinery. Engineer and businessman."
    },
    {
        "name": "Mohammed Umar Bago",
        "party": "APC",
        "position": "Governor",
        "state": "Niger",
        "bio": "Governor of Niger State since 2023. Former member of House of Representatives. Young governor with entrepreneurship focus."
    },
    {
        "name": "Ahmed Usman Ododo",
        "party": "APC",
        "position": "Governor",
        "state": "Kogi",
        "bio": "Governor of Kogi State since 2024. Former Auditor General. Handpicked successor of Yahaya Bello."
    },

    # ===========================================
    # GOVERNORS - NORTH EAST
    # ===========================================
    {
        "name": "Babagana Umara Zulum",
        "party": "APC",
        "position": "Governor",
        "state": "Borno",
        "bio": "Governor of Borno State since 2019. Professor and former Commissioner. Known for hands-on approach to insurgency and IDPs."
    },
    {
        "name": "Ahmadu Umaru Fintiri",
        "party": "PDP",
        "position": "Governor",
        "state": "Adamawa",
        "bio": "Governor of Adamawa State since 2019. Former Acting Governor. Accountant and politician. Focus on education."
    },
    {
        "name": "Muhammad Inuwa Yahaya",
        "party": "APC",
        "position": "Governor",
        "state": "Gombe",
        "bio": "Governor of Gombe State since 2019. Former Commissioner and accountant. Focus on infrastructure development."
    },
    {
        "name": "Mai Mala Buni",
        "party": "APC",
        "position": "Governor",
        "state": "Yobe",
        "bio": "Governor of Yobe State since 2019. Former APC National Caretaker Chairman. Oversaw party's restructuring 2020-2022."
    },
    {
        "name": "Umar Namadi",
        "party": "APC",
        "position": "Governor",
        "state": "Jigawa",
        "bio": "Governor of Jigawa State since 2023. Former Deputy Governor. Succeeded Muhammad Badaru Abubakar."
    },
    {
        "name": "Agbu Kefas",
        "party": "PDP",
        "position": "Governor",
        "state": "Taraba",
        "bio": "Governor of Taraba State since 2023. Former military officer. Businessman. Youngest governor in Nigeria."
    },

    # ===========================================
    # GOVERNORS - NORTH WEST
    # ===========================================
    {
        "name": "Uba Sani",
        "party": "APC",
        "position": "Governor",
        "state": "Kaduna",
        "bio": "Governor of Kaduna State since 2023. Former Senator. Focus on dialogue with bandits (different from El-Rufai's approach)."
    },
    {
        "name": "Abba Kabir Yusuf",
        "party": "NNPP",
        "position": "Governor",
        "state": "Kano",
        "bio": "Governor of Kano State since 2023. NNPP candidate backed by Kwankwaso. Former Commissioner. Emirate restoration controversy."
    },
    {
        "name": "Ahmad Aliyu",
        "party": "APC",
        "position": "Governor",
        "state": "Sokoto",
        "bio": "Governor of Sokoto State since 2023. Former Deputy Governor. Won after tribunal and appeal court battles."
    },
    {
        "name": "Dauda Lawal",
        "party": "PDP",
        "position": "Governor",
        "state": "Zamfara",
        "bio": "Governor of Zamfara State since 2023. Former bank executive. Focus on security challenges and banditry."
    },
    {
        "name": "Dikko Umaru Radda",
        "party": "APC",
        "position": "Governor",
        "state": "Katsina",
        "bio": "Governor of Katsina State since 2023. Former SMEDAN DG. Focus on small business and entrepreneurship."
    },
    {
        "name": "Nasir Idris",
        "party": "APC",
        "position": "Governor",
        "state": "Kebbi",
        "bio": "Governor of Kebbi State since 2023. Former Senator. Focus on agriculture and education."
    },

    # ===========================================
    # FORMER GOVERNORS (INFLUENTIAL)
    # ===========================================
    {
        "name": "Nasir Ahmad El-Rufai",
        "party": "APC",
        "position": "Former Governor",
        "state": "Kaduna",
        "bio": "Former Governor of Kaduna State (2015-2023). Former FCT Minister. Known for controversial reforms and tough stance on security."
    },
    {
        "name": "Rotimi Amaechi",
        "party": "APC",
        "position": "Former Minister",
        "state": "Rivers",
        "bio": "Former Minister of Transportation (2015-2023). Former Governor of Rivers State. Oversaw railway modernization projects."
    },
    {
        "name": "Kayode Fayemi",
        "party": "APC",
        "position": "Former Governor",
        "state": "Ekiti",
        "bio": "Former Governor of Ekiti State (2010-2014, 2018-2022). Former Nigeria Governors Forum Chair. Academic and politician."
    },
    {
        "name": "Babatunde Fashola",
        "party": "APC",
        "position": "Former Minister",
        "state": "Lagos",
        "bio": "Former Minister of Works and Housing (2015-2023). Former Governor of Lagos State (2007-2015). Lawyer and administrator."
    },
    {
        "name": "Adams Oshiomhole",
        "party": "APC",
        "position": "Senator",
        "state": "Edo",
        "bio": "Senator representing Edo North. Former APC National Chairman. Former Governor of Edo State. Labour leader turned politician."
    },
    {
        "name": "Bukola Saraki",
        "party": "PDP",
        "position": "Former Senate President",
        "state": "Kwara",
        "bio": "8th Senate President (2015-2019). Former Governor of Kwara State (2003-2011). Doctor and banker. Political dynasty."
    },
    {
        "name": "Yakubu Dogara",
        "party": "PDP",
        "position": "Former Speaker",
        "state": "Bauchi",
        "bio": "Former Speaker of House of Representatives (2015-2019). Lawyer and politician. Represents Bogoro/Dass/Tafawa Balewa constituency."
    },
    {
        "name": "Femi Gbajabiamila",
        "party": "APC",
        "position": "Chief of Staff",
        "state": "Lagos",
        "bio": "Chief of Staff to President Tinubu since 2023. Former Speaker of House of Representatives (2019-2023). Lawyer."
    },

    # ===========================================
    # PARTY LEADERS
    # ===========================================
    {
        "name": "Abdullahi Ganduje",
        "party": "APC",
        "position": "APC National Chairman",
        "state": "Kano",
        "bio": "APC National Chairman since 2023. Former Governor of Kano State (2015-2023). Embroiled in corruption allegations during tenure."
    },
    {
        "name": "Umar Damagum",
        "party": "PDP",
        "position": "PDP Acting Chairman",
        "state": "Yobe",
        "bio": "Acting PDP National Chairman. Former Deputy National Chairman. Overseeing party amid internal crises."
    },
    {
        "name": "Julius Abure",
        "party": "LP",
        "position": "LP National Chairman",
        "state": "Edo",
        "bio": "Labour Party National Chairman. Oversaw party's rise in 2023 elections. Facing factional challenges."
    },

    # ===========================================
    # OTHER KEY POLITICIANS
    # ===========================================
    {
        "name": "Yemi Osinbajo",
        "party": "APC",
        "position": "Former Vice President",
        "state": "Ogun",
        "bio": "13th Vice President of Nigeria (2015-2023). Professor of Law. Pastor. Lost APC presidential primary to Tinubu in 2022."
    },
    {
        "name": "Orji Uzor Kalu",
        "party": "APC",
        "position": "Senator",
        "state": "Abia",
        "bio": "Senator representing Abia North. Chief Whip of the Senate. Former Governor of Abia State (1999-2007). Businessman."
    },
    {
        "name": "Rochas Okorocha",
        "party": "APC",
        "position": "Senator",
        "state": "Imo",
        "bio": "Senator representing Imo West. Former Governor of Imo State (2011-2019). Known for free education policy and statues."
    },
    {
        "name": "Dino Melaye",
        "party": "PDP",
        "position": "Former Senator",
        "state": "Kogi",
        "bio": "Former Senator representing Kogi West. Known for activism and social media presence. Vocal critic of APC government."
    },
    {
        "name": "Shehu Sani",
        "party": "PDP",
        "position": "Former Senator",
        "state": "Kaduna",
        "bio": "Former Senator representing Kaduna Central. Human rights activist. Known for witty social commentary on Nigerian politics."
    },
]

# Create lookup dict for manual enrichment by name
MANUAL_ENRICHMENT = {slugify(p["name"]): p for p in POLITICIANS}


def load_wikidata_politicians() -> list:
    """Load and deduplicate politicians from wikidata JSON."""
    if not os.path.exists(WIKIDATA_PATH):
        print(f"Warning: Wikidata file not found at {WIKIDATA_PATH}")
        return []

    with open(WIKIDATA_PATH, 'r') as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"Loaded {len(results)} raw records from wikidata")

    # Deduplicate by person entity - same person may have multiple positions
    by_person = defaultdict(lambda: {
        "positions": set(),
        "parties": set(),
        "name": None,
        "description": None,
        "birth_date": None,
        "death_date": None,
        "gender": None,
        "image": None,
        "wikidata_id": None
    })

    for r in results:
        person_url = r.get("person", "")
        wikidata_id = person_url.split("/")[-1] if person_url else None

        if not wikidata_id:
            continue

        entry = by_person[wikidata_id]
        entry["wikidata_id"] = wikidata_id
        entry["name"] = r.get("personLabel")
        entry["description"] = r.get("personDescription")
        entry["birth_date"] = r.get("birthDate")
        entry["death_date"] = r.get("deathDate")
        entry["gender"] = r.get("genderLabel")
        entry["image"] = r.get("image")

        if r.get("positionLabel"):
            entry["positions"].add(r["positionLabel"])
        if r.get("partyLabel"):
            entry["parties"].add(r["partyLabel"])

    # Convert to list with consolidated data
    politicians = []
    for wikidata_id, data in by_person.items():
        if not data["name"]:
            continue

        # Prioritize positions (Governor > President > Senator > Minister > Member)
        positions = list(data["positions"])
        primary_position = None
        for priority in ["President", "Governor", "Senate President", "Speaker",
                         "Vice President", "Minister", "Senator", "member of the Senate",
                         "member of the House"]:
            for pos in positions:
                if priority.lower() in pos.lower():
                    primary_position = pos
                    break
            if primary_position:
                break
        if not primary_position and positions:
            primary_position = positions[0]

        # Get most recent party
        parties = list(data["parties"])
        primary_party = None
        for priority in ["APC", "PDP", "LP", "NNPP", "APGA"]:
            if priority in parties:
                primary_party = priority
                break
        if not primary_party and parties:
            primary_party = parties[0]

        # Extract state from position if possible
        state = None
        for pos in positions:
            if "State" in pos:
                # "Governor of Lagos State" -> "Lagos"
                parts = pos.replace("Governor of ", "").replace(" State", "").split()
                if parts:
                    state = parts[0]
                    break

        politicians.append({
            "name": data["name"],
            "position": primary_position or "Politician",
            "party": primary_party,
            "state": state,
            "positions": list(data["positions"]),
            "parties": list(data["parties"]),
            "description": data["description"],
            "birth_date": data["birth_date"],
            "death_date": data["death_date"],
            "gender": data["gender"],
            "image": data["image"],
            "wikidata_id": data["wikidata_id"],
            "source": "wikidata"
        })

    print(f"Deduplicated to {len(politicians)} unique politicians")
    return politicians


def seed_database(use_wikidata=True, use_manual=True):
    """Seed the politician database."""
    from app.database import SessionLocal, Politician

    db = SessionLocal()

    try:
        existing = db.query(Politician).count()
        print(f"Existing politicians in DB: {existing}")

        all_politicians = []

        # Load wikidata politicians
        if use_wikidata:
            wikidata_pols = load_wikidata_politicians()
            all_politicians.extend(wikidata_pols)
            print(f"Loaded {len(wikidata_pols)} from wikidata")

        # Add/merge manual data (takes priority for enrichment)
        if use_manual:
            for p in POLITICIANS:
                slug = slugify(p["name"])
                # Check if already in wikidata list
                found = False
                for wp in all_politicians:
                    if slugify(wp["name"]) == slug:
                        # Enrich with manual data
                        wp["bio"] = p.get("bio", "")
                        if p.get("party"):
                            wp["party"] = p["party"]
                        if p.get("position"):
                            wp["position"] = p["position"]
                        if p.get("state"):
                            wp["state"] = p["state"]
                        wp["source"] = "wikidata+manual"
                        found = True
                        break

                if not found:
                    all_politicians.append({
                        "name": p["name"],
                        "position": p.get("position", "Politician"),
                        "party": p.get("party"),
                        "state": p.get("state"),
                        "bio": p.get("bio", ""),
                        "source": "manual"
                    })
            print(f"After manual enrichment: {len(all_politicians)} total")

        added = 0
        updated = 0

        for p in all_politicians:
            slug = slugify(p["name"])
            existing_pol = db.query(Politician).filter(Politician.slug == slug).first()

            # Build data JSON
            data_dict = {
                "seeded_at": datetime.now().isoformat(),
                "source": p.get("source", "unknown")
            }
            if p.get("bio"):
                data_dict["bio"] = p["bio"]
            if p.get("description"):
                data_dict["description"] = p["description"]
            if p.get("positions"):
                data_dict["positions"] = p["positions"]
            if p.get("parties"):
                data_dict["parties"] = p["parties"]
            if p.get("birth_date"):
                data_dict["birth_date"] = p["birth_date"]
            if p.get("death_date"):
                data_dict["death_date"] = p["death_date"]
            if p.get("gender"):
                data_dict["gender"] = p["gender"]
            if p.get("image"):
                data_dict["image"] = p["image"]
            if p.get("wikidata_id"):
                data_dict["wikidata_id"] = p["wikidata_id"]

            if existing_pol:
                existing_pol.name = p["name"]
                if p.get("party"):
                    existing_pol.party = p["party"]
                if p.get("position"):
                    existing_pol.position = p["position"]
                if p.get("state"):
                    existing_pol.state = p["state"]
                existing_pol.data_json = json.dumps(data_dict)
                updated += 1
            else:
                new_pol = Politician(
                    slug=slug,
                    name=p["name"],
                    party=p.get("party"),
                    position=p.get("position", "Politician"),
                    state=p.get("state"),
                    data_json=json.dumps(data_dict)
                )
                db.add(new_pol)
                added += 1

        db.commit()
        final_count = db.query(Politician).count()

        print(f"\n{'='*50}")
        print(f"SEEDING COMPLETE")
        print(f"{'='*50}")
        print(f"Added: {added}")
        print(f"Updated: {updated}")
        print(f"Total in DB: {final_count}")
        print(f"{'='*50}")

        print(f"\nSample politicians:")
        for p in db.query(Politician).limit(10).all():
            print(f"  - {p.name} | {p.position} | {p.party} | {p.state}")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


def list_politicians(source="all"):
    """List all politicians in seed data."""
    if source == "manual":
        pols = POLITICIANS
        print(f"Manual enrichment data: {len(pols)} politicians\n")
    elif source == "wikidata":
        pols = load_wikidata_politicians()
        print(f"Wikidata: {len(pols)} politicians\n")
    else:
        wikidata_pols = load_wikidata_politicians()
        print(f"Wikidata: {len(wikidata_pols)} politicians")
        print(f"Manual: {len(POLITICIANS)} politicians")
        print(f"(Manual data enriches wikidata records for key figures)\n")
        pols = wikidata_pols

    # Group by position type
    positions = {}
    for p in pols:
        pos = p.get("position", "Unknown")
        if pos not in positions:
            positions[pos] = []
        positions[pos].append(p["name"])

    # Show top positions
    for pos, names in sorted(positions.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"{pos} ({len(names)}):")
        for name in names[:5]:  # Show first 5
            print(f"  - {name}")
        if len(names) > 5:
            print(f"  ... and {len(names) - 5} more")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed politicians database")
    parser.add_argument("--list", action="store_true", help="List politicians without seeding")
    parser.add_argument("--count", action="store_true", help="Just show count")
    parser.add_argument("--wikidata", action="store_true", help="Use wikidata only (skip manual)")
    parser.add_argument("--manual", action="store_true", help="Use manual data only (skip wikidata)")

    args = parser.parse_args()

    if args.count:
        wikidata_pols = load_wikidata_politicians()
        print(f"Wikidata politicians: {len(wikidata_pols)}")
        print(f"Manual enrichment: {len(POLITICIANS)}")
    elif args.list:
        if args.wikidata:
            list_politicians("wikidata")
        elif args.manual:
            list_politicians("manual")
        else:
            list_politicians("all")
    else:
        use_wikidata = not args.manual
        use_manual = not args.wikidata
        seed_database(use_wikidata=use_wikidata, use_manual=use_manual)
