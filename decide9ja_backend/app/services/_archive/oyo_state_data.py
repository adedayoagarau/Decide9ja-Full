# FIX 4: OYO STATE DATA
# File: app/data/oyo_state_reps.py
#
# Problem: No Oyo State representatives in database
# Solution: Add all Oyo State senators and House of Reps members

OYO_STATE_DATA = {
    "state": "Oyo",
    "governor": {
        "name": "Seyi Makinde",
        "full_name": "Engr. Oluseyi Abiodun Makinde",
        "party": "PDP",
        "title": "Governor of Oyo State",
        "since": "May 29, 2019",
        "term": "2nd term (2023-2027)",
        "bio": "Engineer and businessman, first elected in 2019 and re-elected in 2023.",
    },
    "deputy_governor": {
        "name": "Bayo Lawal",
        "full_name": "Barr. Adebayo Abdul-Raheem Lawal",
        "party": "PDP",
        "title": "Deputy Governor of Oyo State",
        "since": "May 29, 2023",
    },
    "senators": [
        {
            "name": "Kola Balogun",
            "full_name": "Senator Kola Balogun",
            "party": "PDP",
            "senatorial_district": "Oyo South",
            "title": "Senator, Oyo South Senatorial District",
            "lgas_covered": [
                "Ibadan North", "Ibadan North-East", "Ibadan North-West",
                "Ibadan South-East", "Ibadan South-West", "Ibarapa Central",
                "Ibarapa East", "Ibarapa North", "Ido", "Oluyole", "Ona Ara"
            ],
            "since": "June 2023",
        },
        {
            "name": "Sharafadeen Alli",
            "full_name": "Senator Sharafadeen Alli",
            "party": "APC",
            "senatorial_district": "Oyo Central",
            "title": "Senator, Oyo Central Senatorial District",
            "lgas_covered": [
                "Afijio", "Akinyele", "Atiba", "Egbeda", "Lagelu",
                "Ogbomosho North", "Ogbomosho South", "Oyo East",
                "Oyo West", "Surulere", "Ogo Oluwa"
            ],
            "since": "June 2023",
        },
        {
            "name": "Abdulfatai Buhari",
            "full_name": "Senator Abdulfatai Buhari",
            "party": "APC",
            "senatorial_district": "Oyo North",
            "title": "Senator, Oyo North Senatorial District",
            "lgas_covered": [
                "Atisbo", "Irepo", "Iseyin", "Itesiwaju", "Iwajowa",
                "Kajola", "Olorunsogo", "Orelope", "Ori Ire",
                "Saki East", "Saki West"
            ],
            "since": "June 2023",
        },
    ],
    "house_of_reps": [
        {
            "name": "Stanley Adedeji Olajide",
            "party": "APC",
            "constituency": "Ibadan North",
            "lgas_covered": ["Ibadan North"],
            "title": "House of Representatives Member, Ibadan North Federal Constituency",
        },
        {
            "name": "Oluwole Oke",
            "party": "PDP",
            "constituency": "Ibadan South-West/Ibadan North-West",
            "lgas_covered": ["Ibadan South-West", "Ibadan North-West"],
            "title": "House of Representatives Member, Ibadan South-West/Ibadan North-West Federal Constituency",
        },
        {
            "name": "Kazeem Oyewale Adeyinka",
            "party": "PDP",
            "constituency": "Ibadan South-East/Ibadan North-East",
            "lgas_covered": ["Ibadan South-East", "Ibadan North-East"],
            "title": "House of Representatives Member, Ibadan South-East/Ibadan North-East Federal Constituency",
        },
        {
            "name": "Abass Adigun Agboworin",
            "party": "APC",
            "constituency": "Ido/Oluyole",
            "lgas_covered": ["Ido", "Oluyole"],
            "title": "House of Representatives Member, Ido/Oluyole Federal Constituency",
        },
        {
            "name": "Adewunmi Onanuga",
            "party": "PDP",
            "constituency": "Ona Ara/Egbeda",
            "lgas_covered": ["Ona Ara", "Egbeda"],
            "title": "House of Representatives Member, Ona Ara/Egbeda Federal Constituency",
        },
        {
            "name": "Muraina Ajibola",
            "party": "PDP",
            "constituency": "Ibarapa Central/Ibarapa North",
            "lgas_covered": ["Ibarapa Central", "Ibarapa North"],
            "title": "House of Representatives Member, Ibarapa Central/Ibarapa North Federal Constituency",
        },
        {
            "name": "Jide Olatunbosun",
            "party": "APC",
            "constituency": "Saki East/Saki West/Atisbo",
            "lgas_covered": ["Saki East", "Saki West", "Atisbo"],
            "title": "House of Representatives Member, Saki East/Saki West/Atisbo Federal Constituency",
        },
        {
            "name": "Shina Abiola Peller",
            "party": "APC",
            "constituency": "Iseyin/Itesiwaju/Kajola/Iwajowa",
            "lgas_covered": ["Iseyin", "Itesiwaju", "Kajola", "Iwajowa"],
            "title": "House of Representatives Member, Iseyin/Itesiwaju/Kajola/Iwajowa Federal Constituency",
        },
        {
            "name": "Akintunde Olajide",
            "party": "APC",
            "constituency": "Ogbomosho North/Ogbomosho South/Orire",
            "lgas_covered": ["Ogbomosho North", "Ogbomosho South", "Ori Ire"],
            "title": "House of Representatives Member, Ogbomosho North/Ogbomosho South/Orire Federal Constituency",
        },
        {
            "name": "Segun Dokun Odebunmi",
            "party": "APC",
            "constituency": "Surulere/Ogo Oluwa",
            "lgas_covered": ["Surulere", "Ogo Oluwa"],
            "title": "House of Representatives Member, Surulere/Ogo Oluwa Federal Constituency",
        },
        {
            "name": "Michael Okunlade",
            "party": "PDP",
            "constituency": "Afijio/Atiba/Oyo East/Oyo West",
            "lgas_covered": ["Afijio", "Atiba", "Oyo East", "Oyo West"],
            "title": "House of Representatives Member, Afijio/Atiba/Oyo East/Oyo West Federal Constituency",
        },
        {
            "name": "Tolulope Akande-Sadipe",
            "party": "APC",
            "constituency": "Ibarapa East/Ibarapa East",
            "lgas_covered": ["Ibarapa East"],
            "title": "House of Representatives Member, Oluyole Federal Constituency",
        },
        {
            "name": "Saheed Fijabi",
            "party": "APC",
            "constituency": "Akinyele/Lagelu",
            "lgas_covered": ["Akinyele", "Lagelu"],
            "title": "House of Representatives Member, Akinyele/Lagelu Federal Constituency",
        },
        {
            "name": "Fadeyi Dipo Olajide",
            "party": "APC",
            "constituency": "Irepo/Olorunsogo/Orelope",
            "lgas_covered": ["Irepo", "Olorunsogo", "Orelope"],
            "title": "House of Representatives Member, Irepo/Olorunsogo/Orelope Federal Constituency",
        },
    ],
    "senatorial_district_mapping": {
        # Oyo South
        "ibadan north": "Oyo South",
        "ibadan north-east": "Oyo South",
        "ibadan north-west": "Oyo South",
        "ibadan south-east": "Oyo South",
        "ibadan south-west": "Oyo South",
        "ibarapa central": "Oyo South",
        "ibarapa east": "Oyo South",
        "ibarapa north": "Oyo South",
        "ido": "Oyo South",
        "oluyole": "Oyo South",
        "ona ara": "Oyo South",
        
        # Oyo Central
        "afijio": "Oyo Central",
        "akinyele": "Oyo Central",
        "atiba": "Oyo Central",
        "egbeda": "Oyo Central",
        "lagelu": "Oyo Central",
        "ogbomosho north": "Oyo Central",
        "ogbomosho south": "Oyo Central",
        "oyo east": "Oyo Central",
        "oyo west": "Oyo Central",
        "surulere": "Oyo Central",
        "ogo oluwa": "Oyo Central",
        
        # Oyo North
        "atisbo": "Oyo North",
        "irepo": "Oyo North",
        "iseyin": "Oyo North",
        "itesiwaju": "Oyo North",
        "iwajowa": "Oyo North",
        "kajola": "Oyo North",
        "olorunsogo": "Oyo North",
        "orelope": "Oyo North",
        "ori ire": "Oyo North",
        "saki east": "Oyo North",
        "saki west": "Oyo North",
    }
}


def get_oyo_representatives(lga: str) -> dict:
    """
    Get all representatives for a given LGA in Oyo State.
    
    Args:
        lga: Local Government Area name
    
    Returns:
        dict with governor, senator, house_rep info
    """
    lga_lower = lga.lower().strip()
    
    result = {
        "state": "Oyo",
        "lga": lga,
        "governor": OYO_STATE_DATA["governor"],
        "deputy_governor": OYO_STATE_DATA["deputy_governor"],
        "senator": None,
        "house_rep": None,
        "senatorial_district": None,
        "federal_constituency": None,
    }
    
    # Find senatorial district
    senatorial_district = OYO_STATE_DATA["senatorial_district_mapping"].get(lga_lower)
    result["senatorial_district"] = senatorial_district
    
    # Find senator
    for senator in OYO_STATE_DATA["senators"]:
        if lga_lower in [l.lower() for l in senator["lgas_covered"]]:
            result["senator"] = senator
            break
    
    # Find House of Reps member
    for rep in OYO_STATE_DATA["house_of_reps"]:
        if lga_lower in [l.lower() for l in rep["lgas_covered"]]:
            result["house_rep"] = rep
            result["federal_constituency"] = rep["constituency"]
            break
    
    return result


def format_oyo_reps_response(lga: str) -> str:
    """Format representatives info for WhatsApp response."""
    reps = get_oyo_representatives(lga)
    
    lines = [f"Here are your representatives for *{lga}, Oyo State*:\n"]
    
    # Governor
    gov = reps["governor"]
    lines.append(f"🏛️ *GOVERNOR*")
    lines.append(f"   {gov['name']} ({gov['party']})")
    lines.append(f"   {gov['term']}\n")
    
    # Senator
    if reps["senator"]:
        sen = reps["senator"]
        lines.append(f"🏛️ *SENATOR* ({reps['senatorial_district']})")
        lines.append(f"   {sen['name']} ({sen['party']})")
    else:
        lines.append(f"🏛️ *SENATOR*: Data not available")
    lines.append("")
    
    # House of Reps
    if reps["house_rep"]:
        rep = reps["house_rep"]
        lines.append(f"🏛️ *HOUSE OF REPS* ({reps['federal_constituency']})")
        lines.append(f"   {rep['name']} ({rep['party']})")
    else:
        lines.append(f"🏛️ *HOUSE OF REPS*: Data not available")
    
    lines.append("\nWant to know more about any of them?")
    
    return "\n".join(lines)


# SQL to add to database
SQL_INSERT_OYO_POLITICIANS = """
-- Insert Oyo State Governor
INSERT OR REPLACE INTO politicians (
    name, full_name, position, party, state, lga, 
    constituency_type, bio, source
) VALUES (
    'Seyi Makinde',
    'Engr. Oluseyi Abiodun Makinde',
    'Governor',
    'PDP',
    'Oyo',
    NULL,
    'state',
    'Engineer and businessman serving as Governor of Oyo State since 2019. Currently in his second term.',
    'manual_entry'
);

-- Insert Oyo Senators
INSERT OR REPLACE INTO politicians (name, position, party, state, constituency_type, senatorial_district, bio, source)
VALUES 
('Kola Balogun', 'Senator', 'PDP', 'Oyo', 'federal', 'Oyo South', 'Senator representing Oyo South Senatorial District', 'manual_entry'),
('Sharafadeen Alli', 'Senator', 'APC', 'Oyo', 'federal', 'Oyo Central', 'Senator representing Oyo Central Senatorial District', 'manual_entry'),
('Abdulfatai Buhari', 'Senator', 'APC', 'Oyo', 'federal', 'Oyo North', 'Senator representing Oyo North Senatorial District', 'manual_entry');

-- Insert Oyo House of Reps Members
INSERT OR REPLACE INTO politicians (name, position, party, state, constituency_type, federal_constituency, lgas_covered, source)
VALUES
('Stanley Adedeji Olajide', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Ibadan North', 'Ibadan North', 'manual_entry'),
('Oluwole Oke', 'House of Representatives', 'PDP', 'Oyo', 'federal', 'Ibadan South-West/Ibadan North-West', 'Ibadan South-West,Ibadan North-West', 'manual_entry'),
('Kazeem Oyewale Adeyinka', 'House of Representatives', 'PDP', 'Oyo', 'federal', 'Ibadan South-East/Ibadan North-East', 'Ibadan South-East,Ibadan North-East', 'manual_entry'),
('Abass Adigun Agboworin', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Ido/Oluyole', 'Ido,Oluyole', 'manual_entry'),
('Adewunmi Onanuga', 'House of Representatives', 'PDP', 'Oyo', 'federal', 'Ona Ara/Egbeda', 'Ona Ara,Egbeda', 'manual_entry'),
('Muraina Ajibola', 'House of Representatives', 'PDP', 'Oyo', 'federal', 'Ibarapa Central/Ibarapa North', 'Ibarapa Central,Ibarapa North', 'manual_entry'),
('Jide Olatunbosun', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Saki East/Saki West/Atisbo', 'Saki East,Saki West,Atisbo', 'manual_entry'),
('Shina Abiola Peller', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Iseyin/Itesiwaju/Kajola/Iwajowa', 'Iseyin,Itesiwaju,Kajola,Iwajowa', 'manual_entry'),
('Akintunde Olajide', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Ogbomosho North/Ogbomosho South/Orire', 'Ogbomosho North,Ogbomosho South,Ori Ire', 'manual_entry'),
('Segun Dokun Odebunmi', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Surulere/Ogo Oluwa', 'Surulere,Ogo Oluwa', 'manual_entry'),
('Michael Okunlade', 'House of Representatives', 'PDP', 'Oyo', 'federal', 'Afijio/Atiba/Oyo East/Oyo West', 'Afijio,Atiba,Oyo East,Oyo West', 'manual_entry'),
('Saheed Fijabi', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Akinyele/Lagelu', 'Akinyele,Lagelu', 'manual_entry'),
('Fadeyi Dipo Olajide', 'House of Representatives', 'APC', 'Oyo', 'federal', 'Irepo/Olorunsogo/Orelope', 'Irepo,Olorunsogo,Orelope', 'manual_entry');
"""


# === TEST ===
if __name__ == "__main__":
    print("=== OYO STATE DATA TESTS ===\n")
    
    test_lgas = ["Oluyole", "Ibadan South-West", "Ibadan North", "Saki West", "Ogbomosho North"]
    
    for lga in test_lgas:
        print(f"\n{'='*50}")
        print(f"LGA: {lga}")
        print('='*50)
        
        reps = get_oyo_representatives(lga)
        
        print(f"Senatorial District: {reps['senatorial_district']}")
        print(f"Federal Constituency: {reps['federal_constituency']}")
        
        if reps['senator']:
            print(f"Senator: {reps['senator']['name']} ({reps['senator']['party']})")
        
        if reps['house_rep']:
            print(f"House Rep: {reps['house_rep']['name']} ({reps['house_rep']['party']})")
        
        print("\n--- Formatted Response ---")
        print(format_oyo_reps_response(lga))
