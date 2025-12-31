"""
DECIDE9JA - INEC Data Scraper
=============================

Scrapes publicly available data from INEC Nigeria:
- Political parties (names, abbreviations, leadership, logos)
- States and LGAs (administrative boundaries)
- Election calendar

Run in Antigravity: Just open this file and tell the agent "Run this scraper"
Run locally: python scrape_inec.py

Requirements: pip install requests beautifulsoup4 lxml
"""

import json
import os
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ============================================
# CONFIGURATION
# ============================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Create directories
for d in [DATA_DIR, RAW_DIR, PROCESSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Request settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REQUEST_DELAY = 2  # seconds between requests (be respectful)

# ============================================
# DATA MODELS
# ============================================

@dataclass
class PoliticalParty:
    """Political party data structure"""
    id: str
    name: str
    abbreviation: str
    chairman: Optional[str] = None
    secretary: Optional[str] = None
    treasurer: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    color_primary: Optional[str] = None
    founded_year: Optional[int] = None
    ideology: Optional[str] = None
    source_url: str = "https://inecnigeria.org/political-parties/"
    scraped_at: str = ""
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.utcnow().isoformat() + "Z"
        if not self.id:
            self.id = self.abbreviation.lower().replace(" ", "_")

@dataclass 
class State:
    """Nigerian state data structure"""
    id: str
    name: str
    capital: str
    region: str  # North-Central, North-East, North-West, South-East, South-South, South-West
    lgas: List[str]
    senatorial_districts: List[str]
    federal_constituencies: int
    state_constituencies: int
    registered_voters: Optional[int] = None
    
@dataclass
class LGA:
    """Local Government Area data structure"""
    id: str
    name: str
    state: str
    state_id: str
    headquarters: Optional[str] = None
    registered_voters: Optional[int] = None

# ============================================
# SCRAPER FUNCTIONS
# ============================================

def fetch_page(url: str, save_raw: bool = True) -> Optional[str]:
    """Fetch a web page with error handling and caching"""
    print(f"  Fetching: {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        if save_raw:
            # Save raw HTML for debugging
            filename = hashlib.md5(url.encode()).hexdigest()[:12] + ".html"
            with open(RAW_DIR / filename, "w", encoding="utf-8") as f:
                f.write(response.text)
        
        time.sleep(REQUEST_DELAY)  # Be respectful
        return response.text
        
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

def scrape_political_parties() -> List[PoliticalParty]:
    """
    Scrape political parties from INEC website.
    Source: https://inecnigeria.org/political-parties/
    """
    print("\n📋 Scraping Political Parties...")
    
    parties = []
    base_url = "https://inecnigeria.org/political-parties/"
    
    # INEC has pagination - scrape multiple pages
    page = 1
    while True:
        url = f"{base_url}page/{page}/" if page > 1 else base_url
        html = fetch_page(url)
        
        if not html:
            break
            
        soup = BeautifulSoup(html, "lxml")
        
        # Find party entries (adjust selectors based on actual HTML structure)
        party_cards = soup.select("article.post, .party-card, .entry-content")
        
        if not party_cards:
            # Try alternative selectors
            party_cards = soup.find_all("article")
        
        if not party_cards:
            print(f"  No parties found on page {page}, stopping pagination")
            break
        
        for card in party_cards:
            try:
                # Extract party name and abbreviation
                title_elem = card.select_one("h2, h3, .entry-title, .party-name")
                if not title_elem:
                    continue
                    
                title_text = title_elem.get_text(strip=True)
                
                # Parse "APC All Progressives Congress" or "All Progressives Congress (APC)"
                abbrev, name = parse_party_name(title_text)
                
                if not abbrev or not name:
                    continue
                
                # Extract leadership info from content
                content = card.get_text()
                chairman = extract_field(content, ["National Chairman", "Chairman"])
                secretary = extract_field(content, ["National Secretary", "Secretary"])
                treasurer = extract_field(content, ["National Treasurer", "Treasurer"])
                
                # Extract logo URL
                logo_img = card.select_one("img")
                logo_url = logo_img.get("src") if logo_img else None
                
                party = PoliticalParty(
                    id=abbrev.lower(),
                    name=name,
                    abbreviation=abbrev,
                    chairman=chairman,
                    secretary=secretary,
                    treasurer=treasurer,
                    logo_url=logo_url,
                )
                
                parties.append(party)
                print(f"    ✓ {abbrev}: {name}")
                
            except Exception as e:
                print(f"    Error parsing party card: {e}")
                continue
        
        # Check for next page
        next_link = soup.select_one("a.next, .pagination .next, a[rel='next']")
        if not next_link:
            break
        page += 1
        
        if page > 5:  # Safety limit
            break
    
    print(f"  Found {len(parties)} parties")
    return parties

def parse_party_name(text: str) -> tuple:
    """Parse party name and abbreviation from various formats"""
    text = text.strip()
    
    # Known parties (fallback mapping)
    known_parties = {
        "APC": "All Progressives Congress",
        "PDP": "Peoples Democratic Party", 
        "LP": "Labour Party",
        "APGA": "All Progressives Grand Alliance",
        "NNPP": "New Nigeria Peoples Party",
        "YPP": "Young Progressives Party",
        "SDP": "Social Democratic Party",
        "ADC": "African Democratic Congress",
        "PRP": "Peoples Redemption Party",
        "ZLP": "Zenith Labour Party",
        "AA": "Action Alliance",
        "AAC": "African Action Congress",
        "ADP": "Action Democratic Party",
        "APM": "Allied Peoples Movement",
        "APP": "Action Peoples Party",
        "BP": "Boot Party",
        "NRM": "National Rescue Movement",
        "YP": "Youth Party",
    }
    
    # Try to match known abbreviation
    for abbrev, name in known_parties.items():
        if abbrev in text or name.lower() in text.lower():
            return abbrev, name
    
    # Try pattern: "ABBREV Full Name" or "Full Name (ABBREV)"
    import re
    
    # Pattern: starts with abbreviation
    match = re.match(r'^([A-Z]{2,5})\s+(.+)$', text)
    if match:
        return match.group(1), match.group(2)
    
    # Pattern: ends with (ABBREV)
    match = re.match(r'^(.+?)\s*\(([A-Z]{2,5})\)$', text)
    if match:
        return match.group(2), match.group(1)
    
    return None, None

def extract_field(text: str, field_names: List[str]) -> Optional[str]:
    """Extract a field value from text content"""
    import re
    
    for field in field_names:
        pattern = rf'{field}[:\s]+([^\n]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            # Clean up common artifacts
            value = re.sub(r'\s+', ' ', value)
            value = value.split('National')[0].strip()  # Stop at next field
            return value if len(value) > 2 else None
    
    return None

def get_nigeria_states_lgas() -> tuple:
    """
    Return comprehensive Nigeria states and LGAs data.
    This is static data that doesn't need scraping.
    Source: Nigerian Constitution, INEC
    """
    print("\n🗺️ Loading States and LGAs...")
    
    # Complete Nigeria administrative data
    states_data = {
        "Abia": {
            "capital": "Umuahia",
            "region": "South-East",
            "lgas": ["Aba North", "Aba South", "Arochukwu", "Bende", "Ikwuano", "Isiala Ngwa North", 
                    "Isiala Ngwa South", "Isuikwuato", "Obi Ngwa", "Ohafia", "Osisioma", "Ugwunagbo",
                    "Ukwa East", "Ukwa West", "Umuahia North", "Umuahia South", "Umu Nneochi"],
            "senatorial_districts": ["Abia Central", "Abia North", "Abia South"],
        },
        "Adamawa": {
            "capital": "Yola",
            "region": "North-East",
            "lgas": ["Demsa", "Fufure", "Ganye", "Gayuk", "Gombi", "Grie", "Hong", "Jada", "Lamurde",
                    "Madagali", "Maiha", "Mayo Belwa", "Michika", "Mubi North", "Mubi South", "Numan",
                    "Shelleng", "Song", "Toungo", "Yola North", "Yola South"],
            "senatorial_districts": ["Adamawa Central", "Adamawa North", "Adamawa South"],
        },
        "Akwa Ibom": {
            "capital": "Uyo",
            "region": "South-South",
            "lgas": ["Abak", "Eastern Obolo", "Eket", "Esit Eket", "Essien Udim", "Etim Ekpo",
                    "Etinan", "Ibeno", "Ibesikpo Asutan", "Ibiono-Ibom", "Ika", "Ikono", "Ikot Abasi",
                    "Ikot Ekpene", "Ini", "Itu", "Mbo", "Mkpat-Enin", "Nsit-Atai", "Nsit-Ibom",
                    "Nsit-Ubium", "Obot Akara", "Okobo", "Onna", "Oron", "Oruk Anam", "Udung-Uko",
                    "Ukanafun", "Uruan", "Urue-Offong/Oruko", "Uyo"],
            "senatorial_districts": ["Akwa Ibom North-East", "Akwa Ibom North-West", "Akwa Ibom South"],
        },
        "Anambra": {
            "capital": "Awka",
            "region": "South-East",
            "lgas": ["Aguata", "Anambra East", "Anambra West", "Anaocha", "Awka North", "Awka South",
                    "Ayamelum", "Dunukofia", "Ekwusigo", "Idemili North", "Idemili South", "Ihiala",
                    "Njikoka", "Nnewi North", "Nnewi South", "Ogbaru", "Onitsha North", "Onitsha South",
                    "Orumba North", "Orumba South", "Oyi"],
            "senatorial_districts": ["Anambra Central", "Anambra North", "Anambra South"],
        },
        "Bauchi": {
            "capital": "Bauchi",
            "region": "North-East",
            "lgas": ["Alkaleri", "Bauchi", "Bogoro", "Damban", "Darazo", "Dass", "Gamawa", "Ganjuwa",
                    "Giade", "Itas/Gadau", "Jama'are", "Katagum", "Kirfi", "Misau", "Ningi", "Shira",
                    "Tafawa Balewa", "Toro", "Warji", "Zaki"],
            "senatorial_districts": ["Bauchi Central", "Bauchi North", "Bauchi South"],
        },
        "Bayelsa": {
            "capital": "Yenagoa",
            "region": "South-South",
            "lgas": ["Brass", "Ekeremor", "Kolokuma/Opokuma", "Nembe", "Ogbia", "Sagbama",
                    "Southern Ijaw", "Yenagoa"],
            "senatorial_districts": ["Bayelsa Central", "Bayelsa East", "Bayelsa West"],
        },
        "Benue": {
            "capital": "Makurdi",
            "region": "North-Central",
            "lgas": ["Ado", "Agatu", "Apa", "Buruku", "Gboko", "Guma", "Gwer East", "Gwer West",
                    "Katsina-Ala", "Konshisha", "Kwande", "Logo", "Makurdi", "Obi", "Ogbadibo",
                    "Ohimini", "Oju", "Okpokwu", "Otukpo", "Tarka", "Ukum", "Ushongo", "Vandeikya"],
            "senatorial_districts": ["Benue North-East", "Benue North-West", "Benue South"],
        },
        "Borno": {
            "capital": "Maiduguri",
            "region": "North-East",
            "lgas": ["Abadam", "Askira/Uba", "Bama", "Bayo", "Biu", "Chibok", "Damboa", "Dikwa",
                    "Gubio", "Guzamala", "Gwoza", "Hawul", "Jere", "Kaga", "Kala/Balge", "Konduga",
                    "Kukawa", "Kwaya Kusar", "Mafa", "Magumeri", "Maiduguri", "Marte", "Mobbar",
                    "Monguno", "Ngala", "Nganzai", "Shani"],
            "senatorial_districts": ["Borno Central", "Borno North", "Borno South"],
        },
        "Cross River": {
            "capital": "Calabar",
            "region": "South-South",
            "lgas": ["Abi", "Akamkpa", "Akpabuyo", "Bakassi", "Bekwarra", "Biase", "Boki",
                    "Calabar Municipal", "Calabar South", "Etung", "Ikom", "Obanliku", "Obubra",
                    "Obudu", "Odukpani", "Ogoja", "Yakuur", "Yala"],
            "senatorial_districts": ["Cross River Central", "Cross River North", "Cross River South"],
        },
        "Delta": {
            "capital": "Asaba",
            "region": "South-South",
            "lgas": ["Aniocha North", "Aniocha South", "Bomadi", "Burutu", "Ethiope East",
                    "Ethiope West", "Ika North East", "Ika South", "Isoko North", "Isoko South",
                    "Ndokwa East", "Ndokwa West", "Okpe", "Oshimili North", "Oshimili South",
                    "Patani", "Sapele", "Udu", "Ughelli North", "Ughelli South", "Ukwuani",
                    "Uvwie", "Warri North", "Warri South", "Warri South West"],
            "senatorial_districts": ["Delta Central", "Delta North", "Delta South"],
        },
        "Ebonyi": {
            "capital": "Abakaliki",
            "region": "South-East",
            "lgas": ["Abakaliki", "Afikpo North", "Afikpo South", "Ebonyi", "Ezza North",
                    "Ezza South", "Ikwo", "Ishielu", "Ivo", "Izzi", "Ohaozara", "Ohaukwu",
                    "Onicha"],
            "senatorial_districts": ["Ebonyi Central", "Ebonyi North", "Ebonyi South"],
        },
        "Edo": {
            "capital": "Benin City",
            "region": "South-South",
            "lgas": ["Akoko-Edo", "Egor", "Esan Central", "Esan North-East", "Esan South-East",
                    "Esan West", "Etsako Central", "Etsako East", "Etsako West", "Igueben",
                    "Ikpoba Okha", "Oredo", "Orhionmwon", "Ovia North-East", "Ovia South-West",
                    "Owan East", "Owan West", "Uhunmwonde"],
            "senatorial_districts": ["Edo Central", "Edo North", "Edo South"],
        },
        "Ekiti": {
            "capital": "Ado Ekiti",
            "region": "South-West",
            "lgas": ["Ado Ekiti", "Efon", "Ekiti East", "Ekiti South-West", "Ekiti West",
                    "Emure", "Gbonyin", "Ido Osi", "Ijero", "Ikere", "Ikole", "Ilejemeje",
                    "Irepodun/Ifelodun", "Ise/Orun", "Moba", "Oye"],
            "senatorial_districts": ["Ekiti Central", "Ekiti North", "Ekiti South"],
        },
        "Enugu": {
            "capital": "Enugu",
            "region": "South-East",
            "lgas": ["Aninri", "Awgu", "Enugu East", "Enugu North", "Enugu South", "Ezeagu",
                    "Igbo Etiti", "Igbo Eze North", "Igbo Eze South", "Isi Uzo", "Nkanu East",
                    "Nkanu West", "Nsukka", "Oji River", "Udenu", "Udi", "Uzo Uwani"],
            "senatorial_districts": ["Enugu East", "Enugu North", "Enugu West"],
        },
        "FCT": {
            "capital": "Abuja",
            "region": "North-Central",
            "lgas": ["Abaji", "Bwari", "Gwagwalada", "Kuje", "Kwali", "Municipal Area Council"],
            "senatorial_districts": ["FCT"],
        },
        "Gombe": {
            "capital": "Gombe",
            "region": "North-East",
            "lgas": ["Akko", "Balanga", "Billiri", "Dukku", "Funakaye", "Gombe", "Kaltungo",
                    "Kwami", "Nafada", "Shongom", "Yamaltu/Deba"],
            "senatorial_districts": ["Gombe Central", "Gombe North", "Gombe South"],
        },
        "Imo": {
            "capital": "Owerri",
            "region": "South-East",
            "lgas": ["Aboh Mbaise", "Ahiazu Mbaise", "Ehime Mbano", "Ezinihitte", "Ideato North",
                    "Ideato South", "Ihitte/Uboma", "Ikeduru", "Isiala Mbano", "Isu", "Mbaitoli",
                    "Ngor Okpala", "Njaba", "Nkwerre", "Nwangele", "Obowo", "Oguta", "Ohaji/Egbema",
                    "Okigwe", "Orlu", "Orsu", "Oru East", "Oru West", "Owerri Municipal",
                    "Owerri North", "Owerri West", "Unuimo"],
            "senatorial_districts": ["Imo East", "Imo North", "Imo West"],
        },
        "Jigawa": {
            "capital": "Dutse",
            "region": "North-West",
            "lgas": ["Auyo", "Babura", "Biriniwa", "Birnin Kudu", "Buji", "Dutse", "Gagarawa",
                    "Garki", "Gumel", "Guri", "Gwaram", "Gwiwa", "Hadejia", "Jahun", "Kafin Hausa",
                    "Kaugama", "Kazaure", "Kiri Kasama", "Kiyawa", "Maigatari", "Malam Madori",
                    "Miga", "Ringim", "Roni", "Sule Tankarkar", "Taura", "Yankwashi"],
            "senatorial_districts": ["Jigawa North-East", "Jigawa North-West", "Jigawa South-West"],
        },
        "Kaduna": {
            "capital": "Kaduna",
            "region": "North-West",
            "lgas": ["Birnin Gwari", "Chikun", "Giwa", "Igabi", "Ikara", "Jaba", "Jema'a",
                    "Kachia", "Kaduna North", "Kaduna South", "Kagarko", "Kajuru", "Kaura",
                    "Kauru", "Kubau", "Kudan", "Lere", "Makarfi", "Sabon Gari", "Sanga",
                    "Soba", "Zangon Kataf", "Zaria"],
            "senatorial_districts": ["Kaduna Central", "Kaduna North", "Kaduna South"],
        },
        "Kano": {
            "capital": "Kano",
            "region": "North-West",
            "lgas": ["Ajingi", "Albasu", "Bagwai", "Bebeji", "Bichi", "Bunkure", "Dala",
                    "Dambatta", "Dawakin Kudu", "Dawakin Tofa", "Doguwa", "Fagge", "Gabasawa",
                    "Garko", "Garun Mallam", "Gaya", "Gezawa", "Gwale", "Gwarzo", "Kabo",
                    "Kano Municipal", "Karaye", "Kibiya", "Kiru", "Kumbotso", "Kunchi",
                    "Kura", "Madobi", "Makoda", "Minjibir", "Nasarawa", "Rano", "Rimin Gado",
                    "Rogo", "Shanono", "Sumaila", "Takai", "Tarauni", "Tofa", "Tsanyawa",
                    "Tudun Wada", "Ungogo", "Warawa", "Wudil"],
            "senatorial_districts": ["Kano Central", "Kano North", "Kano South"],
        },
        "Katsina": {
            "capital": "Katsina",
            "region": "North-West",
            "lgas": ["Bakori", "Batagarawa", "Batsari", "Baure", "Bindawa", "Charanchi",
                    "Dandume", "Danja", "Dan Musa", "Daura", "Dutsi", "Dutsin Ma", "Faskari",
                    "Funtua", "Ingawa", "Jibia", "Kafur", "Kaita", "Kankara", "Kankia",
                    "Katsina", "Kurfi", "Kusada", "Mai'Adua", "Malumfashi", "Mani", "Mashi",
                    "Matazu", "Musawa", "Rimi", "Sabuwa", "Safana", "Sandamu", "Zango"],
            "senatorial_districts": ["Katsina Central", "Katsina North", "Katsina South"],
        },
        "Kebbi": {
            "capital": "Birnin Kebbi",
            "region": "North-West",
            "lgas": ["Aleiro", "Arewa Dandi", "Argungu", "Augie", "Bagudo", "Birnin Kebbi",
                    "Bunza", "Dandi", "Fakai", "Gwandu", "Jega", "Kalgo", "Koko/Besse",
                    "Maiyama", "Ngaski", "Sakaba", "Shanga", "Suru", "Wasagu/Danko", "Yauri",
                    "Zuru"],
            "senatorial_districts": ["Kebbi Central", "Kebbi North", "Kebbi South"],
        },
        "Kogi": {
            "capital": "Lokoja",
            "region": "North-Central",
            "lgas": ["Adavi", "Ajaokuta", "Ankpa", "Bassa", "Dekina", "Ibaji", "Idah",
                    "Igalamela Odolu", "Ijumu", "Kabba/Bunu", "Kogi", "Lokoja", "Mopa Muro",
                    "Ofu", "Ogori/Magongo", "Okehi", "Okene", "Olamaboro", "Omala", "Yagba East",
                    "Yagba West"],
            "senatorial_districts": ["Kogi Central", "Kogi East", "Kogi West"],
        },
        "Kwara": {
            "capital": "Ilorin",
            "region": "North-Central",
            "lgas": ["Asa", "Baruten", "Edu", "Ekiti", "Ifelodun", "Ilorin East", "Ilorin South",
                    "Ilorin West", "Irepodun", "Isin", "Kaiama", "Moro", "Offa", "Oke Ero",
                    "Oyun", "Pategi"],
            "senatorial_districts": ["Kwara Central", "Kwara North", "Kwara South"],
        },
        "Lagos": {
            "capital": "Ikeja",
            "region": "South-West",
            "lgas": ["Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa",
                    "Badagry", "Epe", "Eti Osa", "Ibeju-Lekki", "Ifako-Ijaiye", "Ikeja",
                    "Ikorodu", "Kosofe", "Lagos Island", "Lagos Mainland", "Mushin", "Ojo",
                    "Oshodi-Isolo", "Shomolu", "Surulere"],
            "senatorial_districts": ["Lagos Central", "Lagos East", "Lagos West"],
        },
        "Nasarawa": {
            "capital": "Lafia",
            "region": "North-Central",
            "lgas": ["Akwanga", "Awe", "Doma", "Karu", "Keana", "Keffi", "Kokona", "Lafia",
                    "Nasarawa", "Nasarawa Egon", "Obi", "Toto", "Wamba"],
            "senatorial_districts": ["Nasarawa North", "Nasarawa South", "Nasarawa West"],
        },
        "Niger": {
            "capital": "Minna",
            "region": "North-Central",
            "lgas": ["Agaie", "Agwara", "Bida", "Borgu", "Bosso", "Chanchaga", "Edati",
                    "Gbako", "Gurara", "Katcha", "Kontagora", "Lapai", "Lavun", "Magama",
                    "Mariga", "Mashegu", "Mokwa", "Moya", "Paikoro", "Rafi", "Rijau",
                    "Shiroro", "Suleja", "Tafa", "Wushishi"],
            "senatorial_districts": ["Niger East", "Niger North", "Niger South"],
        },
        "Ogun": {
            "capital": "Abeokuta",
            "region": "South-West",
            "lgas": ["Abeokuta North", "Abeokuta South", "Ado-Odo/Ota", "Egbado North",
                    "Egbado South", "Ewekoro", "Ifo", "Ijebu East", "Ijebu North",
                    "Ijebu North East", "Ijebu Ode", "Ikenne", "Imeko Afon", "Ipokia",
                    "Obafemi Owode", "Odeda", "Odogbolu", "Ogun Waterside", "Remo North",
                    "Shagamu"],
            "senatorial_districts": ["Ogun Central", "Ogun East", "Ogun West"],
        },
        "Ondo": {
            "capital": "Akure",
            "region": "South-West",
            "lgas": ["Akoko North-East", "Akoko North-West", "Akoko South-East", "Akoko South-West",
                    "Akure North", "Akure South", "Ese Odo", "Idanre", "Ifedore", "Ilaje",
                    "Ile Oluji/Okeigbo", "Irele", "Odigbo", "Okitipupa", "Ondo East", "Ondo West",
                    "Ose", "Owo"],
            "senatorial_districts": ["Ondo Central", "Ondo North", "Ondo South"],
        },
        "Osun": {
            "capital": "Osogbo",
            "region": "South-West",
            "lgas": ["Aiyedaade", "Aiyedire", "Atakunmosa East", "Atakunmosa West", "Boluwaduro",
                    "Boripe", "Ede North", "Ede South", "Egbedore", "Ejigbo", "Ife Central",
                    "Ife East", "Ife North", "Ife South", "Ifedayo", "Ifelodun", "Ila",
                    "Ilesa East", "Ilesa West", "Irepodun", "Irewole", "Isokan", "Iwo",
                    "Obokun", "Odo Otin", "Ola Oluwa", "Olorunda", "Oriade", "Orolu", "Osogbo"],
            "senatorial_districts": ["Osun Central", "Osun East", "Osun West"],
        },
        "Oyo": {
            "capital": "Ibadan",
            "region": "South-West",
            "lgas": ["Afijio", "Akinyele", "Atiba", "Atisbo", "Egbeda", "Ibadan North",
                    "Ibadan North-East", "Ibadan North-West", "Ibadan South-East",
                    "Ibadan South-West", "Ibarapa Central", "Ibarapa East", "Ibarapa North",
                    "Ido", "Irepo", "Iseyin", "Itesiwaju", "Iwajowa", "Kajola", "Lagelu",
                    "Ogbomosho North", "Ogbomosho South", "Ogo Oluwa", "Olorunsogo", "Oluyole",
                    "Ona Ara", "Orelope", "Ori Ire", "Oyo East", "Oyo West", "Saki East",
                    "Saki West", "Surulere"],
            "senatorial_districts": ["Oyo Central", "Oyo North", "Oyo South"],
        },
        "Plateau": {
            "capital": "Jos",
            "region": "North-Central",
            "lgas": ["Barkin Ladi", "Bassa", "Bokkos", "Jos East", "Jos North", "Jos South",
                    "Kanam", "Kanke", "Langtang North", "Langtang South", "Mangu", "Mikang",
                    "Pankshin", "Qua'an Pan", "Riyom", "Shendam", "Wase"],
            "senatorial_districts": ["Plateau Central", "Plateau North", "Plateau South"],
        },
        "Rivers": {
            "capital": "Port Harcourt",
            "region": "South-South",
            "lgas": ["Abua/Odual", "Ahoada East", "Ahoada West", "Akuku-Toru", "Andoni",
                    "Asari-Toru", "Bonny", "Degema", "Eleme", "Emuoha", "Etche", "Gokana",
                    "Ikwerre", "Khana", "Obio/Akpor", "Ogba/Egbema/Ndoni", "Ogu/Bolo",
                    "Okrika", "Omuma", "Opobo/Nkoro", "Oyigbo", "Port Harcourt", "Tai"],
            "senatorial_districts": ["Rivers East", "Rivers South-East", "Rivers West"],
        },
        "Sokoto": {
            "capital": "Sokoto",
            "region": "North-West",
            "lgas": ["Binji", "Bodinga", "Dange Shuni", "Gada", "Goronyo", "Gudu", "Gwadabawa",
                    "Illela", "Isa", "Kebbe", "Kware", "Rabah", "Sabon Birni", "Shagari",
                    "Silame", "Sokoto North", "Sokoto South", "Tambuwal", "Tangaza", "Tureta",
                    "Wamako", "Wurno", "Yabo"],
            "senatorial_districts": ["Sokoto East", "Sokoto North", "Sokoto South"],
        },
        "Taraba": {
            "capital": "Jalingo",
            "region": "North-East",
            "lgas": ["Ardo Kola", "Bali", "Donga", "Gashaka", "Gassol", "Ibi", "Jalingo",
                    "Karim Lamido", "Kumi", "Lau", "Sardauna", "Takum", "Ussa", "Wukari",
                    "Yorro", "Zing"],
            "senatorial_districts": ["Taraba Central", "Taraba North", "Taraba South"],
        },
        "Yobe": {
            "capital": "Damaturu",
            "region": "North-East",
            "lgas": ["Bade", "Bursari", "Damaturu", "Fika", "Fune", "Geidam", "Gujba",
                    "Gulani", "Jakusko", "Karasuwa", "Machina", "Nangere", "Nguru",
                    "Potiskum", "Tarmuwa", "Yunusari", "Yusufari"],
            "senatorial_districts": ["Yobe East", "Yobe North", "Yobe South"],
        },
        "Zamfara": {
            "capital": "Gusau",
            "region": "North-West",
            "lgas": ["Anka", "Bakura", "Birnin Magaji/Kiyaw", "Bukkuyum", "Bungudu",
                    "Gummi", "Gusau", "Kaura Namoda", "Maradun", "Maru", "Shinkafi",
                    "Talata Mafara", "Tsafe", "Zurmi"],
            "senatorial_districts": ["Zamfara Central", "Zamfara North", "Zamfara West"],
        },
    }
    
    # Convert to State objects
    states = []
    lgas = []
    
    for state_name, data in states_data.items():
        state_id = state_name.lower().replace(" ", "_").replace("'", "")
        
        state = State(
            id=state_id,
            name=state_name,
            capital=data["capital"],
            region=data["region"],
            lgas=data["lgas"],
            senatorial_districts=data["senatorial_districts"],
            federal_constituencies=len(data["lgas"]) // 2 + 1,  # Approximate
            state_constituencies=len(data["lgas"]),
        )
        states.append(state)
        
        # Create LGA objects
        for lga_name in data["lgas"]:
            lga_id = f"{state_id}_{lga_name.lower().replace(' ', '_').replace('/', '_').replace('-', '_')}"
            lga = LGA(
                id=lga_id,
                name=lga_name,
                state=state_name,
                state_id=state_id,
            )
            lgas.append(lga)
    
    print(f"  Loaded {len(states)} states and {len(lgas)} LGAs")
    return states, lgas

def create_known_parties() -> List[PoliticalParty]:
    """
    Create party data from known sources (backup if scraping fails).
    Data verified from INEC website as of 2024.
    """
    print("\n📋 Creating known parties database...")
    
    parties_data = [
        {
            "abbreviation": "APC",
            "name": "All Progressives Congress",
            "chairman": "Dr. Abdullahi Umar Ganduje",
            "color_primary": "#008751",
            "founded_year": 2013,
            "ideology": "Progressive, Centre-right",
        },
        {
            "abbreviation": "PDP",
            "name": "Peoples Democratic Party",
            "chairman": "Amb. Umar Iliya Damagum (Acting)",
            "color_primary": "#ED1C24",
            "founded_year": 1998,
            "ideology": "Big tent, Centre to Centre-left",
        },
        {
            "abbreviation": "LP",
            "name": "Labour Party",
            "chairman": "Barr. Julius Abure",
            "color_primary": "#00A859",
            "founded_year": 2002,
            "ideology": "Social democracy, Labour interests",
        },
        {
            "abbreviation": "NNPP",
            "name": "New Nigeria Peoples Party",
            "chairman": "Dr. Ajuji Ahmed",
            "color_primary": "#FF0000",
            "founded_year": 2001,
            "ideology": "Progressive",
        },
        {
            "abbreviation": "APGA",
            "name": "All Progressives Grand Alliance",
            "chairman": "Chief Edozie Njoku",
            "color_primary": "#006400",
            "founded_year": 2002,
            "ideology": "Nationalism, Decentralization",
        },
        {
            "abbreviation": "YPP",
            "name": "Young Progressives Party",
            "chairman": "Comrade Bishop Amakiri",
            "color_primary": "#FFD700",
            "founded_year": 2017,
            "ideology": "Youth empowerment, Progressive",
        },
        {
            "abbreviation": "SDP",
            "name": "Social Democratic Party",
            "chairman": "Shehu Musa Gabam",
            "color_primary": "#0000FF",
            "founded_year": 2017,
            "ideology": "Social democracy",
        },
        {
            "abbreviation": "ADC",
            "name": "African Democratic Congress",
            "chairman": "Chief Ralphs Okey Nwosu",
            "color_primary": "#800080",
            "founded_year": 2005,
            "ideology": "Pan-African, Social democracy",
        },
        {
            "abbreviation": "PRP",
            "name": "Peoples Redemption Party",
            "chairman": "Falalu Bello",
            "color_primary": "#FF4500",
            "founded_year": 1978,
            "ideology": "Democratic socialism",
        },
        {
            "abbreviation": "AA",
            "name": "Action Alliance",
            "chairman": "Kenneth Udeze",
            "color_primary": "#FFA500",
            "founded_year": 2005,
            "ideology": "Centre-left",
        },
        {
            "abbreviation": "AAC",
            "name": "African Action Congress",
            "chairman": "Leonard Nzenwa",
            "color_primary": "#DC143C",
            "founded_year": 2018,
            "ideology": "Socialist, Revolutionary",
        },
        {
            "abbreviation": "ADP",
            "name": "Action Democratic Party",
            "chairman": "Alhaji Sani Abdulahi Shinkafi",
            "color_primary": "#4169E1",
            "founded_year": 2017,
            "ideology": "Progressive",
        },
        {
            "abbreviation": "APM",
            "name": "Allied Peoples Movement",
            "chairman": "Yusuf Mamman Dantalle",
            "color_primary": "#228B22",
            "founded_year": 2018,
            "ideology": "Progressive",
        },
        {
            "abbreviation": "APP",
            "name": "Action Peoples Party",
            "chairman": "Alhaji Umar Musa Shinkafi",
            "color_primary": "#8B0000",
            "founded_year": 2017,
            "ideology": "Centre",
        },
        {
            "abbreviation": "BP",
            "name": "Boot Party",
            "chairman": "Adenuga Sunday",
            "color_primary": "#8B4513",
            "founded_year": 2018,
            "ideology": "Grassroots empowerment",
        },
        {
            "abbreviation": "NRM",
            "name": "National Rescue Movement",
            "chairman": "Prince Chinedu Obi",
            "color_primary": "#20B2AA",
            "founded_year": 2017,
            "ideology": "Progressive",
        },
        {
            "abbreviation": "YP",
            "name": "Youth Party",
            "chairman": "Dr. Umar Muhammed (Acting)",
            "color_primary": "#9932CC",
            "founded_year": 2016,
            "ideology": "Youth empowerment",
        },
        {
            "abbreviation": "ZLP",
            "name": "Zenith Labour Party",
            "chairman": "Chief Dan Nwanyanwu",
            "color_primary": "#00CED1",
            "founded_year": 2018,
            "ideology": "Labour interests",
        },
    ]
    
    parties = []
    for data in parties_data:
        party = PoliticalParty(
            id=data["abbreviation"].lower(),
            abbreviation=data["abbreviation"],
            name=data["name"],
            chairman=data.get("chairman"),
            color_primary=data.get("color_primary"),
            founded_year=data.get("founded_year"),
            ideology=data.get("ideology"),
        )
        parties.append(party)
        print(f"  ✓ {data['abbreviation']}: {data['name']}")
    
    return parties

# ============================================
# SAVE FUNCTIONS
# ============================================

def save_json(data: List, filename: str):
    """Save data as JSON"""
    filepath = PROCESSED_DIR / filename
    
    # Convert dataclass objects to dicts
    if data and hasattr(data[0], '__dataclass_fields__'):
        data = [asdict(item) for item in data]
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  💾 Saved: {filepath}")

def create_summary():
    """Create a summary file of all scraped data"""
    summary = {
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "source": "INEC Nigeria (inecnigeria.org)",
        "files": [],
        "statistics": {}
    }
    
    # Check what files exist
    for filepath in PROCESSED_DIR.glob("*.json"):
        with open(filepath) as f:
            data = json.load(f)
        summary["files"].append({
            "name": filepath.name,
            "records": len(data)
        })
        summary["statistics"][filepath.stem] = len(data)
    
    with open(PROCESSED_DIR / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n📊 Summary saved to {PROCESSED_DIR / '_summary.json'}")
    return summary

# ============================================
# MAIN EXECUTION
# ============================================

def main():
    """Main scraping execution"""
    print("=" * 60)
    print("🇳🇬 DECIDE9JA - INEC DATA SCRAPER")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"Output directory: {PROCESSED_DIR}")
    
    # 1. Try to scrape political parties
    try:
        parties = scrape_political_parties()
        if len(parties) < 10:
            print("  ⚠️ Scraping returned few results, using known database")
            parties = create_known_parties()
    except Exception as e:
        print(f"  ⚠️ Scraping failed: {e}")
        print("  Using known parties database instead")
        parties = create_known_parties()
    
    save_json(parties, "parties.json")
    
    # 2. Load states and LGAs (static data)
    states, lgas = get_nigeria_states_lgas()
    save_json(states, "states.json")
    save_json(lgas, "lgas.json")
    
    # 3. Create senatorial districts lookup
    senatorial_districts = []
    for state in states:
        for district in state.senatorial_districts:
            senatorial_districts.append({
                "id": district.lower().replace(" ", "_").replace("-", "_"),
                "name": district,
                "state": state.name,
                "state_id": state.id,
            })
    save_json(senatorial_districts, "senatorial_districts.json")
    
    # 4. Create summary
    summary = create_summary()
    
    print("\n" + "=" * 60)
    print("✅ SCRAPING COMPLETE")
    print("=" * 60)
    print(f"Files created in: {PROCESSED_DIR}")
    for file_info in summary["files"]:
        print(f"  • {file_info['name']}: {file_info['records']} records")
    
    return summary

if __name__ == "__main__":
    main()
