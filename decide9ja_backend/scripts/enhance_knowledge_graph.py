#!/usr/bin/env python3
"""
Knowledge Graph Enhancement Script

Implements 5 major improvements:
1. Enrich Entity Relationships - Link Wikipedia to Wikidata, succession chains
2. Parse Excel Data Rows - Make economic data points queryable
3. Full-Text Search Index - Semantic search across all content
4. State-Level Profiles - Complete profiles for 36 states + FCT
5. Timeline/Era Navigation - Navigate history by era and year

Run: python scripts/enhance_knowledge_graph.py
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path("./nigeria_knowledge_data")
KG_DIR = DATA_DIR / "knowledge_graph"
ENHANCED_DIR = DATA_DIR / "enhanced"
ENHANCED_DIR.mkdir(parents=True, exist_ok=True)


# Nigerian States with metadata
NIGERIAN_STATES = {
    "Abia": {"capital": "Umuahia", "zone": "South East", "created": 1991},
    "Adamawa": {"capital": "Yola", "zone": "North East", "created": 1991},
    "Akwa Ibom": {"capital": "Uyo", "zone": "South South", "created": 1987},
    "Anambra": {"capital": "Awka", "zone": "South East", "created": 1991},
    "Bauchi": {"capital": "Bauchi", "zone": "North East", "created": 1976},
    "Bayelsa": {"capital": "Yenagoa", "zone": "South South", "created": 1996},
    "Benue": {"capital": "Makurdi", "zone": "North Central", "created": 1976},
    "Borno": {"capital": "Maiduguri", "zone": "North East", "created": 1976},
    "Cross River": {"capital": "Calabar", "zone": "South South", "created": 1967},
    "Delta": {"capital": "Asaba", "zone": "South South", "created": 1991},
    "Ebonyi": {"capital": "Abakaliki", "zone": "South East", "created": 1996},
    "Edo": {"capital": "Benin City", "zone": "South South", "created": 1991},
    "Ekiti": {"capital": "Ado Ekiti", "zone": "South West", "created": 1996},
    "Enugu": {"capital": "Enugu", "zone": "South East", "created": 1991},
    "FCT": {"capital": "Abuja", "zone": "North Central", "created": 1976},
    "Gombe": {"capital": "Gombe", "zone": "North East", "created": 1996},
    "Imo": {"capital": "Owerri", "zone": "South East", "created": 1976},
    "Jigawa": {"capital": "Dutse", "zone": "North West", "created": 1991},
    "Kaduna": {"capital": "Kaduna", "zone": "North West", "created": 1967},
    "Kano": {"capital": "Kano", "zone": "North West", "created": 1967},
    "Katsina": {"capital": "Katsina", "zone": "North West", "created": 1987},
    "Kebbi": {"capital": "Birnin Kebbi", "zone": "North West", "created": 1991},
    "Kogi": {"capital": "Lokoja", "zone": "North Central", "created": 1991},
    "Kwara": {"capital": "Ilorin", "zone": "North Central", "created": 1967},
    "Lagos": {"capital": "Ikeja", "zone": "South West", "created": 1967},
    "Nasarawa": {"capital": "Lafia", "zone": "North Central", "created": 1996},
    "Niger": {"capital": "Minna", "zone": "North Central", "created": 1976},
    "Ogun": {"capital": "Abeokuta", "zone": "South West", "created": 1976},
    "Ondo": {"capital": "Akure", "zone": "South West", "created": 1976},
    "Osun": {"capital": "Osogbo", "zone": "South West", "created": 1991},
    "Oyo": {"capital": "Ibadan", "zone": "South West", "created": 1976},
    "Plateau": {"capital": "Jos", "zone": "North Central", "created": 1976},
    "Rivers": {"capital": "Port Harcourt", "zone": "South South", "created": 1967},
    "Sokoto": {"capital": "Sokoto", "zone": "North West", "created": 1976},
    "Taraba": {"capital": "Jalingo", "zone": "North East", "created": 1991},
    "Yobe": {"capital": "Damaturu", "zone": "North East", "created": 1991},
    "Zamfara": {"capital": "Gusau", "zone": "North West", "created": 1996},
}

# Nigerian political eras
NIGERIAN_ERAS = {
    "pre_colonial": {
        "name": "Pre-Colonial Era",
        "start": None,
        "end": "1861-01-01",
        "description": "Period before British colonial rule, featuring various kingdoms and empires"
    },
    "colonial": {
        "name": "Colonial Era",
        "start": "1861-01-01",
        "end": "1960-10-01",
        "description": "Period of British colonial rule from Lagos annexation to independence"
    },
    "first_republic": {
        "name": "First Republic",
        "start": "1960-10-01",
        "end": "1966-01-15",
        "description": "Nigeria's first democratic government under Tafawa Balewa"
    },
    "military_era_1": {
        "name": "First Military Era",
        "start": "1966-01-15",
        "end": "1979-10-01",
        "description": "Military governments of Ironsi, Gowon, Mohammed, and Obasanjo"
    },
    "civil_war": {
        "name": "Nigerian Civil War (Biafra)",
        "start": "1967-07-06",
        "end": "1970-01-15",
        "description": "War between Nigeria and secessionist Biafra"
    },
    "second_republic": {
        "name": "Second Republic",
        "start": "1979-10-01",
        "end": "1983-12-31",
        "description": "Democratic government under Shehu Shagari"
    },
    "military_era_2": {
        "name": "Second Military Era",
        "start": "1983-12-31",
        "end": "1999-05-29",
        "description": "Military governments of Buhari, Babangida, Abacha, Abubakar"
    },
    "fourth_republic": {
        "name": "Fourth Republic",
        "start": "1999-05-29",
        "end": None,
        "description": "Current democratic era from Obasanjo to present"
    }
}

# Nigerian presidents/heads of state for succession chains
NIGERIAN_LEADERS = [
    {"id": "azikiwe", "name": "Nnamdi Azikiwe", "position": "President", "start": "1960-10-01", "end": "1966-01-15", "party": "NCNC"},
    {"id": "balewa", "name": "Abubakar Tafawa Balewa", "position": "Prime Minister", "start": "1960-10-01", "end": "1966-01-15", "party": "NPC"},
    {"id": "ironsi", "name": "Johnson Aguiyi-Ironsi", "position": "Military Head of State", "start": "1966-01-15", "end": "1966-07-29", "party": "Military"},
    {"id": "gowon", "name": "Yakubu Gowon", "position": "Military Head of State", "start": "1966-07-29", "end": "1975-07-29", "party": "Military"},
    {"id": "mohammed", "name": "Murtala Mohammed", "position": "Military Head of State", "start": "1975-07-29", "end": "1976-02-13", "party": "Military"},
    {"id": "obasanjo_mil", "name": "Olusegun Obasanjo", "position": "Military Head of State", "start": "1976-02-13", "end": "1979-10-01", "party": "Military"},
    {"id": "shagari", "name": "Shehu Shagari", "position": "President", "start": "1979-10-01", "end": "1983-12-31", "party": "NPN"},
    {"id": "buhari_mil", "name": "Muhammadu Buhari", "position": "Military Head of State", "start": "1983-12-31", "end": "1985-08-27", "party": "Military"},
    {"id": "babangida", "name": "Ibrahim Babangida", "position": "Military President", "start": "1985-08-27", "end": "1993-08-26", "party": "Military"},
    {"id": "shonekan", "name": "Ernest Shonekan", "position": "Interim Head of State", "start": "1993-08-26", "end": "1993-11-17", "party": "Civilian"},
    {"id": "abacha", "name": "Sani Abacha", "position": "Military Head of State", "start": "1993-11-17", "end": "1998-06-08", "party": "Military"},
    {"id": "abubakar", "name": "Abdulsalami Abubakar", "position": "Military Head of State", "start": "1998-06-08", "end": "1999-05-29", "party": "Military"},
    {"id": "obasanjo", "name": "Olusegun Obasanjo", "position": "President", "start": "1999-05-29", "end": "2007-05-29", "party": "PDP"},
    {"id": "yardua", "name": "Umaru Musa Yar'Adua", "position": "President", "start": "2007-05-29", "end": "2010-05-05", "party": "PDP"},
    {"id": "jonathan", "name": "Goodluck Jonathan", "position": "President", "start": "2010-05-06", "end": "2015-05-29", "party": "PDP"},
    {"id": "buhari", "name": "Muhammadu Buhari", "position": "President", "start": "2015-05-29", "end": "2023-05-29", "party": "APC"},
    {"id": "tinubu", "name": "Bola Ahmed Tinubu", "position": "President", "start": "2023-05-29", "end": None, "party": "APC"},
]


class KnowledgeGraphEnhancer:
    """Enhances the knowledge graph with relationships, economic data, search, states, and timeline"""

    def __init__(self):
        self.entities = {}
        self.relationships = []
        self.economic_data = []  # Queryable economic data points
        self.state_profiles = {}
        self.timeline = defaultdict(list)  # year -> events
        self.era_entities = {}
        self.full_text_index = {}  # word -> [entity_ids]
        self.stats = defaultdict(int)

    def load_existing_data(self):
        """Load existing knowledge graph data"""
        logger.info("Loading existing knowledge graph...")

        # Find latest entities file
        entities_files = list(KG_DIR.glob("entities_*.json"))
        if not entities_files:
            logger.error("No entities file found. Run build_knowledge_graph.py first.")
            return False

        latest = max(entities_files, key=lambda f: f.stat().st_mtime)
        with open(latest, encoding="utf-8") as f:
            data = json.load(f)
            self.entities = data.get("entities", {})

        logger.info(f"  Loaded {len(self.entities)} entities")

        # Load relationships
        rel_files = list(KG_DIR.glob("relationships_*.json"))
        if rel_files:
            latest_rel = max(rel_files, key=lambda f: f.stat().st_mtime)
            with open(latest_rel, encoding="utf-8") as f:
                data = json.load(f)
                self.relationships = data.get("relationships", [])
            logger.info(f"  Loaded {len(self.relationships)} relationships")

        return True

    def load_excel_data(self):
        """Load raw Excel data for economic parsing"""
        excel_dir = DATA_DIR / "excel_imports"
        raw_files = list(excel_dir.glob("*_raw_*.json"))
        if not raw_files:
            logger.warning("No raw Excel data found")
            return

        latest = max(raw_files, key=lambda f: f.stat().st_mtime)
        with open(latest, encoding="utf-8") as f:
            return json.load(f)

    # ===========================================
    # 1. ENRICH ENTITY RELATIONSHIPS
    # ===========================================

    def enrich_relationships(self):
        """Link Wikipedia to Wikidata, build succession chains"""
        logger.info("Enriching entity relationships...")

        # Build name -> entity lookup
        name_to_entities = defaultdict(list)
        for eid, entity in self.entities.items():
            name = entity.get("name", "").lower().strip()
            if name:
                name_to_entities[name].append(eid)
                # Also index partial names
                for word in name.split():
                    if len(word) > 3:
                        name_to_entities[word].append(eid)

        # Link Wikipedia articles to Wikidata entities
        for eid, entity in self.entities.items():
            if entity.get("source") != "wikipedia":
                continue

            wiki_name = entity.get("name", "").lower().strip()

            # Find matching Wikidata entity
            for other_id, other in self.entities.items():
                if other.get("source") != "wikidata":
                    continue

                wd_name = other.get("name", "").lower().strip()

                if wiki_name == wd_name or wiki_name in wd_name or wd_name in wiki_name:
                    self.relationships.append({
                        "source": eid,
                        "target": other_id,
                        "type": "same_as",
                        "confidence": 0.9 if wiki_name == wd_name else 0.7
                    })
                    self.stats["wiki_wikidata_links"] += 1
                    break

        # Build succession chains for leaders
        for i, leader in enumerate(NIGERIAN_LEADERS):
            leader_id = f"leader_{leader['id']}"

            # Add/update leader entity
            if leader_id not in self.entities:
                self.entities[leader_id] = {
                    "id": leader_id,
                    "type": "person_leader",
                    "name": leader["name"],
                    "position": leader["position"],
                    "party": leader["party"],
                    "start_date": leader["start"],
                    "end_date": leader["end"],
                    "source": "historical_data"
                }
                self.stats["leaders_added"] += 1

            # Add succession relationship
            if i > 0:
                prev_leader = NIGERIAN_LEADERS[i - 1]
                prev_id = f"leader_{prev_leader['id']}"
                self.relationships.append({
                    "source": leader_id,
                    "target": prev_id,
                    "type": "succeeded"
                })
                self.stats["succession_links"] += 1

        logger.info(f"  Created {self.stats['wiki_wikidata_links']} Wikipedia-Wikidata links")
        logger.info(f"  Added {self.stats['leaders_added']} leader entities")
        logger.info(f"  Created {self.stats['succession_links']} succession links")

    # ===========================================
    # 2. PARSE ECONOMIC DATA ROWS
    # ===========================================

    def parse_economic_data(self):
        """Parse Excel data into queryable economic data points"""
        logger.info("Parsing economic data rows...")

        excel_data = self.load_excel_data()
        if not excel_data:
            return

        sheets = excel_data.get("sheets", {})

        # Process each economic sheet
        economic_sheets = {
            "NATIONAL ECONOMIC DATA": "national_economic",
            "INFLATION DATA": "inflation",
            "INTEREST RATE": "interest_rate",
            "EXCHANGE RATE": "exchange_rate",
            "GDP GROWTH": "gdp_growth",
            "FG MACROECONOMIC DATA": "macroeconomic",
            "NATIONAL DEBT": "national_debt",
            "CRUDE OIL PRODUCTION": "oil_production",
            "POPULATION": "population",
        }

        for sheet_name, category in economic_sheets.items():
            records = sheets.get(sheet_name, [])
            if not records:
                continue

            for record in records:
                # Extract common fields
                indicator = record.get("INDICATOR", record.get("Item", ""))
                year = record.get("YEAR", record.get("Year"))
                value = record.get("VALUE (NGN)", record.get("VALUE (%)",
                         record.get("VALUE", record.get("Value"))))
                source = record.get("SOURCE", "Excel Import")

                if not indicator or not year:
                    continue

                # Clean up year
                try:
                    if isinstance(year, str):
                        year = int(re.search(r'\d{4}', str(year)).group())
                    else:
                        year = int(year)
                except:
                    continue

                # Create data point
                data_point = {
                    "id": f"econ_{category}_{indicator[:20]}_{year}".lower().replace(" ", "_"),
                    "category": category,
                    "indicator": indicator,
                    "year": year,
                    "value": value,
                    "source": source,
                    "unit": self._get_unit(sheet_name, indicator)
                }

                self.economic_data.append(data_point)
                self.stats["economic_data_points"] += 1

                # Add to timeline
                self.timeline[year].append({
                    "type": "economic",
                    "description": f"{indicator}: {value}",
                    "category": category
                })

        # Process state-level data
        state_sheets = ["STATE FAAC ALLOCATION", "LGA FAAC ALLOCATION",
                       "STATES SECTORAL APPROVED EXPEND"]

        for sheet_name in state_sheets:
            records = sheets.get(sheet_name, [])
            for record in records:
                state = record.get("STATE", record.get("State", ""))
                year = record.get("YEAR", record.get("Year"))

                if state and year:
                    # Normalize state name
                    state_norm = state.strip().title()
                    if state_norm not in self.state_profiles:
                        self.state_profiles[state_norm] = {
                            "name": state_norm,
                            "economic_data": [],
                            "allocations": []
                        }

                    self.state_profiles[state_norm]["allocations"].append(record)
                    self.stats["state_data_points"] += 1

        logger.info(f"  Parsed {self.stats['economic_data_points']} economic data points")
        logger.info(f"  Parsed {self.stats['state_data_points']} state-level data points")

    def _get_unit(self, sheet_name: str, indicator: str) -> str:
        """Determine the unit for an economic indicator"""
        if "INFLATION" in sheet_name or "GROWTH" in sheet_name:
            return "percent"
        elif "RATE" in sheet_name:
            return "rate"
        elif "NGN" in indicator or "Naira" in indicator:
            return "NGN"
        elif "USD" in indicator or "Dollar" in indicator:
            return "USD"
        elif "POPULATION" in sheet_name:
            return "people"
        elif "OIL" in sheet_name:
            return "barrels"
        return "value"

    # ===========================================
    # 3. FULL-TEXT SEARCH INDEX
    # ===========================================

    def build_full_text_index(self):
        """Build full-text search index across all content"""
        logger.info("Building full-text search index...")

        # Stop words to skip
        stop_words = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
                     "is", "are", "was", "were", "be", "been", "being", "have", "has",
                     "had", "do", "does", "did", "will", "would", "could", "should",
                     "may", "might", "must", "shall", "can", "this", "that", "these",
                     "those", "it", "its", "with", "as", "by", "from", "or", "but"}

        def tokenize(text: str) -> List[str]:
            """Tokenize text into searchable words"""
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            return [w for w in words if w not in stop_words]

        for eid, entity in self.entities.items():
            # Index name
            name = entity.get("name", "")
            for word in tokenize(name):
                if word not in self.full_text_index:
                    self.full_text_index[word] = []
                if eid not in self.full_text_index[word]:
                    self.full_text_index[word].append(eid)

            # Index content/description
            content = entity.get("content", entity.get("content_preview",
                      entity.get("description", "")))
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            content = str(content) if content else ""
            if content:
                for word in tokenize(content[:2000]):  # Limit content length
                    if word not in self.full_text_index:
                        self.full_text_index[word] = []
                    if eid not in self.full_text_index[word]:
                        self.full_text_index[word].append(eid)

            self.stats["indexed_entities"] += 1

        logger.info(f"  Indexed {self.stats['indexed_entities']} entities")
        logger.info(f"  Created {len(self.full_text_index)} unique word entries")

    # ===========================================
    # 4. STATE-LEVEL PROFILES
    # ===========================================

    def build_state_profiles(self):
        """Build complete profiles for 36 states + FCT"""
        logger.info("Building state profiles...")

        for state_name, metadata in NIGERIAN_STATES.items():
            state_id = f"state_{state_name.lower().replace(' ', '_')}"

            # Create or update state entity
            self.entities[state_id] = {
                "id": state_id,
                "type": "state",
                "name": f"{state_name} State" if state_name != "FCT" else "Federal Capital Territory",
                "short_name": state_name,
                "capital": metadata["capital"],
                "geopolitical_zone": metadata["zone"],
                "year_created": metadata["created"],
                "source": "reference_data"
            }

            # Link existing entities to this state
            state_lower = state_name.lower()
            for eid, entity in list(self.entities.items()):
                if eid == state_id:
                    continue

                # Check if entity mentions this state
                name = entity.get("name", "").lower()
                content = entity.get("content", entity.get("description", ""))
                if isinstance(content, list):
                    content = " ".join(str(c) for c in content)
                content = str(content).lower() if content else ""
                state_label = entity.get("stateLabel", "").lower()

                if state_lower in name or state_lower in state_label:
                    self.relationships.append({
                        "source": eid,
                        "target": state_id,
                        "type": "located_in"
                    })
                    self.stats["state_entity_links"] += 1

            # Merge any existing state data
            if state_name in self.state_profiles:
                self.entities[state_id]["economic_data"] = self.state_profiles[state_name].get("allocations", [])[:10]

            self.stats["state_profiles_created"] += 1

        logger.info(f"  Created {self.stats['state_profiles_created']} state profiles")
        logger.info(f"  Created {self.stats['state_entity_links']} state-entity links")

    # ===========================================
    # 5. TIMELINE/ERA NAVIGATION
    # ===========================================

    def build_timeline(self):
        """Build timeline and era navigation"""
        logger.info("Building timeline and era navigation...")

        # Create era entities
        for era_id, era_data in NIGERIAN_ERAS.items():
            self.era_entities[era_id] = {
                "id": f"era_{era_id}",
                "type": "era",
                "name": era_data["name"],
                "description": era_data["description"],
                "start_date": era_data["start"],
                "end_date": era_data["end"],
                "source": "reference_data"
            }
            self.entities[f"era_{era_id}"] = self.era_entities[era_id]
            self.stats["eras_added"] += 1

        # Link entities to eras
        for eid, entity in list(self.entities.items()):
            if eid.startswith("era_"):
                continue

            # Try to determine entity's era from dates
            start_date = entity.get("start_date", entity.get("date", ""))
            if not start_date:
                continue

            try:
                if isinstance(start_date, str):
                    year = int(re.search(r'\d{4}', start_date).group())
                else:
                    year = int(start_date)
            except:
                continue

            # Determine which era
            era = self._get_era_for_year(year)
            if era:
                self.relationships.append({
                    "source": eid,
                    "target": f"era_{era}",
                    "type": "occurred_during"
                })
                self.stats["era_links"] += 1

                # Add to timeline
                self.timeline[year].append({
                    "type": "entity",
                    "entity_id": eid,
                    "name": entity.get("name", ""),
                    "entity_type": entity.get("type", "")
                })

        # Add key historical events to timeline
        historical_events = [
            (1960, "Independence", "Nigeria gains independence from Britain"),
            (1963, "Republic", "Nigeria becomes a republic"),
            (1966, "First Coup", "Military coup ends First Republic"),
            (1967, "Civil War Begins", "Biafran secession and civil war"),
            (1970, "Civil War Ends", "End of Nigerian Civil War"),
            (1979, "Second Republic", "Return to civilian rule"),
            (1983, "Buhari Coup", "Military takeover by Buhari"),
            (1993, "June 12", "Annulled election and political crisis"),
            (1999, "Fourth Republic", "Return to democracy"),
            (2015, "APC Victory", "First opposition victory in presidential election"),
            (2023, "Tinubu Elected", "Bola Tinubu becomes president"),
        ]

        for year, name, description in historical_events:
            event_id = f"event_{year}_{name.lower().replace(' ', '_')}"
            self.entities[event_id] = {
                "id": event_id,
                "type": "historical_event",
                "name": name,
                "description": description,
                "year": year,
                "source": "reference_data"
            }
            self.timeline[year].append({
                "type": "event",
                "entity_id": event_id,
                "name": name,
                "description": description
            })
            self.stats["historical_events"] += 1

        logger.info(f"  Added {self.stats['eras_added']} era entities")
        logger.info(f"  Created {self.stats['era_links']} era links")
        logger.info(f"  Added {self.stats['historical_events']} historical events")
        logger.info(f"  Timeline spans {min(self.timeline.keys()) if self.timeline else 0} - {max(self.timeline.keys()) if self.timeline else 0}")

    def _get_era_for_year(self, year: int) -> Optional[str]:
        """Determine which era a year falls into"""
        for era_id, era_data in NIGERIAN_ERAS.items():
            start = era_data["start"]
            end = era_data["end"]

            start_year = int(start[:4]) if start else 0
            end_year = int(end[:4]) if end else 9999

            if start_year <= year <= end_year:
                return era_id

        return None

    # ===========================================
    # SAVE ENHANCED DATA
    # ===========================================

    def save(self):
        """Save all enhanced data"""
        logger.info("Saving enhanced knowledge graph...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save enhanced entities
        entities_file = ENHANCED_DIR / f"entities_enhanced_{timestamp}.json"
        with open(entities_file, "w", encoding="utf-8") as f:
            json.dump({
                "total": len(self.entities),
                "entities": self.entities
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved {len(self.entities)} entities to {entities_file}")

        # Save enhanced relationships
        rel_file = ENHANCED_DIR / f"relationships_enhanced_{timestamp}.json"
        with open(rel_file, "w", encoding="utf-8") as f:
            json.dump({
                "total": len(self.relationships),
                "relationships": self.relationships
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved {len(self.relationships)} relationships")

        # Save economic data index
        econ_file = ENHANCED_DIR / f"economic_data_{timestamp}.json"
        with open(econ_file, "w", encoding="utf-8") as f:
            json.dump({
                "total": len(self.economic_data),
                "data_points": self.economic_data
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved {len(self.economic_data)} economic data points")

        # Save full-text index
        index_file = ENHANCED_DIR / f"full_text_index_{timestamp}.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_words": len(self.full_text_index),
                "index": self.full_text_index
            }, f, ensure_ascii=False)
        logger.info(f"  Saved full-text index with {len(self.full_text_index)} words")

        # Save timeline
        timeline_file = ENHANCED_DIR / f"timeline_{timestamp}.json"
        with open(timeline_file, "w", encoding="utf-8") as f:
            json.dump({
                "years": len(self.timeline),
                "timeline": dict(sorted(self.timeline.items()))
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved timeline with {len(self.timeline)} years")

        # Save state profiles
        states_file = ENHANCED_DIR / f"state_profiles_{timestamp}.json"
        state_data = {sid: self.entities[sid] for sid in self.entities
                     if sid.startswith("state_")}
        with open(states_file, "w", encoding="utf-8") as f:
            json.dump({
                "total": len(state_data),
                "states": state_data
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved {len(state_data)} state profiles")

        # Save latest reference
        latest_file = ENHANCED_DIR / "latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump({
                "entities_file": str(entities_file),
                "relationships_file": str(rel_file),
                "economic_data_file": str(econ_file),
                "full_text_index_file": str(index_file),
                "timeline_file": str(timeline_file),
                "states_file": str(states_file),
                "enhanced_at": datetime.now().isoformat(),
                "stats": dict(self.stats)
            }, f, indent=2)

        # Print summary
        print("\n" + "=" * 60)
        print("KNOWLEDGE GRAPH ENHANCEMENT COMPLETE")
        print("=" * 60)
        print(f"\nEntities: {len(self.entities)}")
        print(f"Relationships: {len(self.relationships)}")
        print(f"Economic Data Points: {len(self.economic_data)}")
        print(f"Full-Text Index Words: {len(self.full_text_index)}")
        print(f"Timeline Years: {len(self.timeline)}")
        print(f"State Profiles: {len(state_data)}")
        print(f"\nOutput: {ENHANCED_DIR}")
        print("=" * 60)

    def enhance(self):
        """Run all enhancements"""
        print("=" * 60)
        print("NIGERIA KNOWLEDGE GRAPH ENHANCER")
        print("=" * 60)

        if not self.load_existing_data():
            return

        # Run all 5 enhancements
        self.enrich_relationships()
        self.parse_economic_data()
        self.build_full_text_index()
        self.build_state_profiles()
        self.build_timeline()

        # Save
        self.save()


def main():
    enhancer = KnowledgeGraphEnhancer()
    enhancer.enhance()


if __name__ == "__main__":
    main()
