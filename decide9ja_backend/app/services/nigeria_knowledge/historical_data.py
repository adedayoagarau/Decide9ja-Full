"""
Nigeria Historical Data Seeder

Seeds the knowledge graph with foundational Nigerian historical data
including key figures, events, and institutions.
"""

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .knowledge_graph import NigeriaKnowledgeGraph


def seed_knowledge_graph(graph: "NigeriaKnowledgeGraph"):
    """
    Seed the knowledge graph with foundational Nigerian historical data.

    This includes:
    - Nigerian political eras (Colonial, First Republic, etc.)
    - Key historical figures (Presidents, Military Heads of State)
    - Major political events (Independence, Coups, Civil War)
    - Political parties
    - Geographic entities (States, Regions)

    The full data is loaded from the built knowledge graph files.
    This function provides a minimal bootstrap for the in-memory graph.
    """
    from .knowledge_graph import Entity, EntityType, Relationship, RelationType

    # Add Nigeria as the root entity
    graph.add_entity(Entity(
        id="nigeria",
        name="Nigeria",
        entity_type=EntityType.COUNTRY,
        properties={
            "official_name": "Federal Republic of Nigeria",
            "independence_date": "1960-10-01",
            "capital": "Abuja",
            "former_capital": "Lagos",
            "population": "220000000",
            "currency": "Nigerian Naira (NGN)",
        },
        aliases=["Federal Republic of Nigeria", "Giant of Africa"],
        start_date=date(1960, 10, 1),
    ))

    # Add political eras
    eras = [
        ("colonial_era", "Colonial Nigeria", date(1861, 1, 1), date(1960, 10, 1)),
        ("first_republic", "First Republic", date(1960, 10, 1), date(1966, 1, 15)),
        ("military_era_1", "First Military Era", date(1966, 1, 15), date(1979, 10, 1)),
        ("civil_war", "Nigerian Civil War", date(1967, 7, 6), date(1970, 1, 15)),
        ("second_republic", "Second Republic", date(1979, 10, 1), date(1983, 12, 31)),
        ("military_era_2", "Second Military Era", date(1983, 12, 31), date(1999, 5, 29)),
        ("fourth_republic", "Fourth Republic", date(1999, 5, 29), None),
    ]

    for era_id, era_name, start, end in eras:
        graph.add_entity(Entity(
            id=era_id,
            name=era_name,
            entity_type=EntityType.ERA,
            start_date=start,
            end_date=end,
        ))

    # Add key historical presidents/heads of state
    leaders = [
        ("nnamdi_azikiwe", "Nnamdi Azikiwe", "President", "NCNC",
         date(1960, 10, 1), date(1966, 1, 15), ["Zik", "Zik of Africa"]),
        ("tafawa_balewa", "Abubakar Tafawa Balewa", "Prime Minister", "NPC",
         date(1960, 10, 1), date(1966, 1, 15), ["Tafawa Balewa"]),
        ("aguiyi_ironsi", "Johnson Aguiyi-Ironsi", "Military Head of State", "Military",
         date(1966, 1, 15), date(1966, 7, 29), []),
        ("yakubu_gowon", "Yakubu Gowon", "Military Head of State", "Military",
         date(1966, 7, 29), date(1975, 7, 29), []),
        ("murtala_mohammed", "Murtala Mohammed", "Military Head of State", "Military",
         date(1975, 7, 29), date(1976, 2, 13), []),
        ("olusegun_obasanjo_mil", "Olusegun Obasanjo", "Military Head of State", "Military",
         date(1976, 2, 13), date(1979, 10, 1), ["OBJ"]),
        ("shehu_shagari", "Shehu Shagari", "President", "NPN",
         date(1979, 10, 1), date(1983, 12, 31), []),
        ("muhammadu_buhari_mil", "Muhammadu Buhari", "Military Head of State", "Military",
         date(1983, 12, 31), date(1985, 8, 27), []),
        ("ibrahim_babangida", "Ibrahim Babangida", "Military President", "Military",
         date(1985, 8, 27), date(1993, 8, 26), ["IBB"]),
        ("ernest_shonekan", "Ernest Shonekan", "Interim Head of State", "Civilian",
         date(1993, 8, 26), date(1993, 11, 17), []),
        ("sani_abacha", "Sani Abacha", "Military Head of State", "Military",
         date(1993, 11, 17), date(1998, 6, 8), []),
        ("abdulsalami_abubakar", "Abdulsalami Abubakar", "Military Head of State", "Military",
         date(1998, 6, 8), date(1999, 5, 29), []),
        ("olusegun_obasanjo", "Olusegun Obasanjo", "President", "PDP",
         date(1999, 5, 29), date(2007, 5, 29), ["OBJ"]),
        ("umaru_yardua", "Umaru Musa Yar'Adua", "President", "PDP",
         date(2007, 5, 29), date(2010, 5, 5), []),
        ("goodluck_jonathan", "Goodluck Jonathan", "President", "PDP",
         date(2010, 5, 6), date(2015, 5, 29), ["GEJ"]),
        ("muhammadu_buhari", "Muhammadu Buhari", "President", "APC",
         date(2015, 5, 29), date(2023, 5, 29), ["PMB"]),
        ("bola_tinubu", "Bola Ahmed Tinubu", "President", "APC",
         date(2023, 5, 29), None, ["BAT", "Jagaban"]),
    ]

    for leader_id, name, position, party, start, end, aliases in leaders:
        graph.add_entity(Entity(
            id=leader_id,
            name=name,
            entity_type=EntityType.POLITICIAN if "President" in position else EntityType.MILITARY_OFFICER,
            properties={
                "position": position,
                "party": party,
            },
            aliases=aliases,
            start_date=start,
            end_date=end,
        ))

    # Add major political parties
    parties = [
        ("apc", "All Progressives Congress", "APC", date(2013, 2, 6)),
        ("pdp", "Peoples Democratic Party", "PDP", date(1998, 8, 31)),
        ("lp", "Labour Party", "LP", date(2002, 1, 1)),
        ("nnpp", "New Nigeria Peoples Party", "NNPP", date(2001, 1, 1)),
        ("apga", "All Progressives Grand Alliance", "APGA", date(2002, 6, 1)),
    ]

    for party_id, name, abbrev, founded in parties:
        graph.add_entity(Entity(
            id=party_id,
            name=name,
            entity_type=EntityType.POLITICAL_PARTY,
            properties={"abbreviation": abbrev},
            aliases=[abbrev],
            start_date=founded,
        ))

    # Add relationships
    # Current president is member of APC
    graph.add_relationship(Relationship(
        source_id="bola_tinubu",
        target_id="apc",
        relation_type=RelationType.MEMBER_OF,
    ))

    # Succession relationships
    graph.add_relationship(Relationship(
        source_id="bola_tinubu",
        target_id="muhammadu_buhari",
        relation_type=RelationType.SUCCEEDED,
    ))

    graph.add_relationship(Relationship(
        source_id="muhammadu_buhari",
        target_id="goodluck_jonathan",
        relation_type=RelationType.SUCCEEDED,
    ))
