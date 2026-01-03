"""
Entity Extractor for Nigerian Historical Documents

Uses Claude to extract structured entities from historical text,
including people, organizations, events, places, and dates.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class EntityCategory(Enum):
    """Categories of entities to extract"""
    PERSON = "person"
    ORGANIZATION = "organization"
    PLACE = "place"
    EVENT = "event"
    DATE = "date"
    POSITION = "position"
    POLICY = "policy"
    LAW = "law"
    MONEY = "money"


@dataclass
class ExtractedEntity:
    """An entity extracted from text"""
    name: str
    category: EntityCategory
    context: str  # The sentence/paragraph where it was found

    # Additional details
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Relationships found in the text
    relationships: List[Dict] = field(default_factory=list)

    # Source tracking
    source_text_id: Optional[str] = None
    confidence: float = 0.9

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "context": self.context[:200] + "..." if len(self.context) > 200 else self.context,
            "aliases": self.aliases,
            "attributes": self.attributes,
            "relationships": self.relationships,
            "confidence": self.confidence,
        }


class EntityExtractor:
    """
    Extract structured entities from Nigerian historical text.

    Uses Claude for intelligent extraction with Nigerian context.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

        # Nigerian-specific entity patterns
        self.patterns = {
            "nigerian_names": [
                r"\b(Chief|Dr\.?|Prof\.?|Gen\.?|Col\.?|Alhaji|Alhaja|Otunba|Asiwaju|Oba|Ooni|Emir)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+",
            ],
            "nigerian_places": [
                r"\b(Lagos|Abuja|Kano|Ibadan|Port Harcourt|Kaduna|Benin City|Enugu|Onitsha|Jos|Ilorin|Abeokuta|Owerri|Calabar|Sokoto|Maiduguri)\b",
                r"\b[A-Z][a-z]+\s+State\b",
            ],
            "dates": [
                r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4}\b",
                r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
                r"\b\d{4}\b",
            ],
            "organizations": [
                r"\b(?:NCNC|AG|NPC|NPN|UPN|NPP|PDP|APC|APGA|LP|SDP|NRC)\b",
                r"\b(?:NNPC|EFCC|INEC|CBN|NTA|FRCN)\b",
            ],
            "events": [
                r"\bcoup\b",
                r"\belection\b",
                r"\bindependence\b",
                r"\bcivil war\b",
                r"\bBiafra\b",
            ],
        }

    async def extract_entities(
        self,
        text: str,
        source_id: Optional[str] = None,
        use_claude: bool = True,
    ) -> List[ExtractedEntity]:
        """
        Extract entities from text.

        Args:
            text: The text to extract entities from
            source_id: ID of the source document
            use_claude: Whether to use Claude for extraction (vs regex only)
        """

        entities = []

        # First pass: Regex-based extraction for known patterns
        regex_entities = self._extract_with_regex(text)
        entities.extend(regex_entities)

        # Second pass: Claude-based extraction for deeper understanding
        if use_claude:
            claude_entities = await self._extract_with_claude(text)
            entities.extend(claude_entities)

        # Deduplicate by name
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity.name.lower() not in seen:
                seen.add(entity.name.lower())
                entity.source_text_id = source_id
                unique_entities.append(entity)

        return unique_entities

    def _extract_with_regex(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using regex patterns"""
        entities = []

        # Nigerian names/titles
        for pattern in self.patterns["nigerian_names"]:
            for match in re.finditer(pattern, text):
                name = match.group()
                context = self._get_context(text, match.start(), match.end())

                entities.append(ExtractedEntity(
                    name=name,
                    category=EntityCategory.PERSON,
                    context=context,
                    confidence=0.8,
                ))

        # Places
        for pattern in self.patterns["nigerian_places"]:
            for match in re.finditer(pattern, text):
                name = match.group()
                context = self._get_context(text, match.start(), match.end())

                entities.append(ExtractedEntity(
                    name=name,
                    category=EntityCategory.PLACE,
                    context=context,
                    confidence=0.9,
                ))

        # Organizations
        for pattern in self.patterns["organizations"]:
            for match in re.finditer(pattern, text):
                name = match.group()
                context = self._get_context(text, match.start(), match.end())

                entities.append(ExtractedEntity(
                    name=name,
                    category=EntityCategory.ORGANIZATION,
                    context=context,
                    confidence=0.95,
                ))

        # Dates
        for pattern in self.patterns["dates"]:
            for match in re.finditer(pattern, text):
                date_str = match.group()
                context = self._get_context(text, match.start(), match.end())

                entities.append(ExtractedEntity(
                    name=date_str,
                    category=EntityCategory.DATE,
                    context=context,
                    confidence=0.95,
                ))

        return entities

    async def _extract_with_claude(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using Claude for deeper understanding"""

        try:
            from anthropic import Anthropic
        except ImportError:
            logger.warning("anthropic package not installed, skipping Claude extraction")
            return []

        client = Anthropic()

        # Limit text length
        if len(text) > 10000:
            text = text[:10000] + "..."

        prompt = f"""Extract all named entities from this Nigerian historical text.

For each entity, provide:
1. name: The entity's name
2. category: One of [person, organization, place, event, date, position, policy, law]
3. aliases: Other names/titles for this entity
4. attributes: Key facts (birth_year, death_year, party, position, etc.)
5. relationships: Connections to other entities (e.g., "member_of: NCNC", "succeeded: Balewa")

Focus on Nigerian historical context. Include:
- Political figures (with their parties, positions)
- Military officers (with ranks, roles)
- Organizations (political parties, government agencies)
- Events (coups, elections, protests, policies)
- Places (states, cities, regions)
- Important dates

TEXT:
{text}

Return a JSON array of entities. Example format:
[
  {{
    "name": "Nnamdi Azikiwe",
    "category": "person",
    "aliases": ["Zik", "Zik of Africa"],
    "attributes": {{
      "birth_year": 1904,
      "death_year": 1996,
      "positions": ["Governor-General", "President"],
      "party": "NCNC",
      "ethnic_group": "Igbo"
    }},
    "relationships": [
      {{"type": "founded", "target": "NCNC"}},
      {{"type": "preceded", "target": "Tafawa Balewa"}}
    ]
  }}
]

Return ONLY the JSON array, no other text."""

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Handle code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            entities_data = json.loads(response_text)

            # Convert to ExtractedEntity objects
            entities = []
            for item in entities_data:
                try:
                    category = EntityCategory(item.get("category", "person"))
                except ValueError:
                    category = EntityCategory.PERSON

                entity = ExtractedEntity(
                    name=item["name"],
                    category=category,
                    context="",  # Claude extraction doesn't have specific context
                    aliases=item.get("aliases", []),
                    attributes=item.get("attributes", {}),
                    relationships=item.get("relationships", []),
                    confidence=0.9,
                )
                entities.append(entity)

            return entities

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return []
        except Exception as e:
            logger.error(f"Claude extraction error: {e}")
            return []

    def _get_context(self, text: str, start: int, end: int, window: int = 100) -> str:
        """Get surrounding context for an entity"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    async def extract_relationships(
        self,
        entities: List[ExtractedEntity],
        text: str,
    ) -> List[Dict]:
        """
        Extract relationships between entities in a text.

        Uses Claude to understand the connections.
        """

        try:
            from anthropic import Anthropic
        except ImportError:
            return []

        if len(entities) < 2:
            return []

        entity_names = [e.name for e in entities[:20]]  # Limit for API

        client = Anthropic()

        prompt = f"""Analyze the relationships between these Nigerian historical entities:

ENTITIES:
{json.dumps(entity_names, indent=2)}

TEXT:
{text[:5000]}

Extract relationships between the entities. Types include:
- member_of (person -> organization)
- leader_of (person -> organization)
- succeeded (person -> person)
- preceded (person -> person)
- allied_with (person -> person)
- opposed (person -> person)
- participated_in (person -> event)
- located_in (place -> place)
- occurred_in (event -> place)
- caused (event -> event)

Return a JSON array:
[
  {{"source": "Entity1", "type": "relationship_type", "target": "Entity2", "context": "brief explanation"}}
]

Return ONLY the JSON array."""

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text)

        except Exception as e:
            logger.error(f"Relationship extraction error: {e}")
            return []


# Convenience function
async def extract_entities_from_text(
    text: str,
    source_id: Optional[str] = None,
    use_claude: bool = True,
) -> List[ExtractedEntity]:
    """Convenience function to extract entities from text"""
    extractor = EntityExtractor()
    return await extractor.extract_entities(text, source_id, use_claude)


async def demo_extraction():
    """Demo entity extraction"""

    print("=" * 60)
    print("NIGERIA KNOWLEDGE SYSTEM - Entity Extraction Demo")
    print("=" * 60)

    sample_text = """
    On January 15, 1966, a group of young military officers led by Major Chukwuma
    Kaduna Nzeogwu staged Nigeria's first military coup. The coup resulted in the
    deaths of Prime Minister Sir Abubakar Tafawa Balewa, Premier of the Northern
    Region Sir Ahmadu Bello (the Sardauna of Sokoto), and Premier of the Western
    Region Chief Samuel Ladoke Akintola.

    General Johnson Aguiyi-Ironsi, who was the head of the Nigerian Army, assumed
    power and became the first military Head of State. He abolished the federal
    structure and introduced a unitary system of government through Decree No. 34
    of 1966. This action was seen as an attempt to create an Igbo-dominated government.

    On July 29, 1966, a counter-coup led by Northern officers removed General Ironsi.
    Lieutenant Colonel Yakubu Gowon emerged as the new Head of State. The political
    tensions eventually led to the Nigerian Civil War (1967-1970), also known as the
    Biafran War, when the Eastern Region under Colonel Odumegwu Ojukwu declared
    independence as the Republic of Biafra.
    """

    extractor = EntityExtractor()

    # Regex-only extraction (fast, no API needed)
    print("\n[1] Regex-based extraction...")
    regex_entities = extractor._extract_with_regex(sample_text)
    print(f"Found {len(regex_entities)} entities:")
    for entity in regex_entities[:10]:
        print(f"  - {entity.name} ({entity.category.value})")

    # Full extraction with Claude (if available)
    print("\n[2] Claude-based extraction...")
    try:
        from anthropic import Anthropic
        entities = await extractor.extract_entities(sample_text, use_claude=True)
        print(f"Found {len(entities)} entities:")
        for entity in entities[:15]:
            print(f"  - {entity.name} ({entity.category.value})")
            if entity.attributes:
                print(f"    Attributes: {entity.attributes}")
            if entity.relationships:
                print(f"    Relationships: {entity.relationships}")
    except ImportError:
        print("  Anthropic package not installed. Run: pip install anthropic")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(demo_extraction())
