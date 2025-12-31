"""
Location Service for Decide9ja.
Uses Google Maps Geocoding API for coordinates → address translation.
Handles issue reporting location classification.
"""
import os
import aiohttp
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Nigerian states for validation
NIGERIAN_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi",
    "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun",
    "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
]

# Road type classification keywords
FEDERAL_ROAD_KEYWORDS = ["expressway", "highway", "trunk road", "federal road", "A1", "A2", "A3"]
STATE_ROAD_KEYWORDS = ["state road", "major road", "ring road"]


@dataclass
class LocationResult:
    """Structured location data from geocoding."""
    success: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    formatted_address: Optional[str] = None
    street: Optional[str] = None
    lga: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    road_type: Optional[str] = None
    responsible_authority: Optional[str] = None
    error_message: Optional[str] = None


async def get_location_from_coordinates(
    latitude: float,
    longitude: float
) -> LocationResult:
    """
    Convert coordinates to address using Google Maps Geocoding API.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        LocationResult with parsed address components
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.error("Google Maps API key not configured")
        return LocationResult(
            success=False,
            error_message="Location service not configured. Please type your location manually."
        )
    
    # Validate coordinates are roughly in Nigeria
    if not (4.0 <= latitude <= 14.0 and 2.5 <= longitude <= 15.0):
        return LocationResult(
            success=False,
            latitude=latitude,
            longitude=longitude,
            error_message="These coordinates appear to be outside Nigeria. Please share a location within Nigeria."
        )
    
    params = {
        "latlng": f"{latitude},{longitude}",
        "key": GOOGLE_MAPS_API_KEY,
        "result_type": "street_address|route|locality|administrative_area_level_2|administrative_area_level_1"
    }
    
    try:
        # Create SSL context for dev environment
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(GEOCODING_URL, params=params) as response:
                if response.status != 200:
                    logger.error(f"Geocoding API error: {response.status}")
                    return LocationResult(
                        success=False,
                        error_message="Location service temporarily unavailable. Please type your location manually."
                    )
                
                data = await response.json()
                
                if data.get("status") != "OK":
                    logger.warning(f"Geocoding status: {data.get('status')}")
                    return LocationResult(
                        success=False,
                        latitude=latitude,
                        longitude=longitude,
                        error_message="Could not identify this location. Please type your address manually."
                    )
                
                return _parse_geocoding_result(data, latitude, longitude)
                
    except aiohttp.ClientError as e:
        logger.error(f"Geocoding network error: {e}")
        return LocationResult(
            success=False,
            error_message="Network error. Please type your location manually."
        )
    except Exception as e:
        logger.error(f"Geocoding unexpected error: {e}")
        return LocationResult(
            success=False,
            error_message="Something went wrong. Please type your location manually."
        )


def _parse_geocoding_result(data: Dict, latitude: float, longitude: float) -> LocationResult:
    """Parse Google Geocoding API response into LocationResult."""
    results = data.get("results", [])
    
    if not results:
        return LocationResult(
            success=False,
            latitude=latitude,
            longitude=longitude,
            error_message="No address found for this location."
        )
    
    # Use the first (most specific) result
    result = results[0]
    
    street = None
    lga = None
    state = None
    country = None
    
    for component in result.get("address_components", []):
        types = component.get("types", [])
        name = component.get("long_name", "")
        
        if "route" in types or "street_address" in types:
            street = name
        elif "administrative_area_level_2" in types:  # LGA in Nigeria
            lga = name.replace(" LGA", "").replace(" Local Government", "")
        elif "administrative_area_level_1" in types:  # State
            state = name
        elif "country" in types:
            country = name
    
    # Validate it's Nigeria
    if country and country.lower() not in ["nigeria", "ng"]:
        return LocationResult(
            success=False,
            latitude=latitude,
            longitude=longitude,
            country=country,
            error_message=f"This location is in {country}. Decide9ja only covers Nigeria."
        )
    
    # Validate state is Nigerian
    if state and state not in NIGERIAN_STATES and state != "Federal Capital Territory":
        # Try to match partial
        for ns in NIGERIAN_STATES:
            if ns.lower() in state.lower() or state.lower() in ns.lower():
                state = ns
                break
    
    formatted_address = result.get("formatted_address", "")
    
    return LocationResult(
        success=True,
        latitude=latitude,
        longitude=longitude,
        formatted_address=formatted_address,
        street=street,
        lga=lga,
        state=state,
        country="Nigeria"
    )


def classify_road_type(address: str, street: Optional[str] = None) -> str:
    """
    Classify road type based on address/street name.
    
    Returns: "federal", "state", or "local"
    """
    text = f"{address or ''} {street or ''}".lower()
    
    # Check for federal road indicators
    for keyword in FEDERAL_ROAD_KEYWORDS:
        if keyword.lower() in text:
            return "federal"
    
    # Check for state road indicators
    for keyword in STATE_ROAD_KEYWORDS:
        if keyword.lower() in text:
            return "state"
    
    # Default to local
    return "local"


def get_responsible_authority(
    road_type: str,
    state: Optional[str] = None,
    lga: Optional[str] = None
) -> Dict[str, str]:
    """
    Determine responsible authority for road/infrastructure issues.
    
    Returns dict with authority name and contact info.
    """
    if road_type == "federal":
        return {
            "authority": "Federal Roads Maintenance Agency (FERMA)",
            "level": "Federal",
            "contact": "ferma@ferma.gov.ng",
            "note": "Federal roads are maintained by FERMA under the Federal Ministry of Works."
        }
    elif road_type == "state":
        authority_name = f"{state} State Ministry of Works" if state else "State Ministry of Works"
        return {
            "authority": authority_name,
            "level": "State",
            "contact": f"Contact {state} State Government" if state else "Contact your State Government",
            "note": "State roads are maintained by the State Ministry of Works."
        }
    else:  # local
        authority_name = f"{lga} Local Government" if lga else "Your Local Government"
        return {
            "authority": authority_name,
            "level": "Local",
            "contact": f"Contact {lga} LGA Secretariat" if lga else "Contact your LGA Secretariat",
            "note": "Local roads are maintained by the Local Government Area (LGA)."
        }


async def process_location_for_report(
    latitude: float,
    longitude: float
) -> Dict:
    """
    Complete location processing for issue reporting.
    Combines geocoding, classification, and authority lookup.
    
    Args:
        latitude: User's latitude
        longitude: User's longitude
        
    Returns:
        Dict with all location data and responsible authority
    """
    # Step 1: Geocode coordinates
    location = await get_location_from_coordinates(latitude, longitude)
    
    if not location.success:
        return {
            "success": False,
            "error": location.error_message,
            "coordinates": {"lat": latitude, "lng": longitude}
        }
    
    # Step 2: Classify road type
    road_type = classify_road_type(
        location.formatted_address,
        location.street
    )
    
    # Step 3: Get responsible authority
    authority = get_responsible_authority(
        road_type=road_type,
        state=location.state,
        lga=location.lga
    )
    
    return {
        "success": True,
        "coordinates": {
            "lat": latitude,
            "lng": longitude
        },
        "address": {
            "formatted": location.formatted_address,
            "street": location.street,
            "lga": location.lga,
            "state": location.state
        },
        "classification": {
            "road_type": road_type,
            "authority": authority["authority"],
            "level": authority["level"],
            "contact": authority["contact"],
            "note": authority["note"]
        }
    }


def format_location_response(location_data: Dict) -> str:
    """
    Format location data as a WhatsApp-friendly message.
    """
    if not location_data.get("success"):
        return location_data.get("error", "Could not process location.")
    
    addr = location_data.get("address", {})
    classification = location_data.get("classification", {})
    
    parts = ["📍 *Location Identified*\n"]
    
    if addr.get("street"):
        parts.append(f"Street: {addr['street']}")
    if addr.get("lga"):
        parts.append(f"LGA: {addr['lga']}")
    if addr.get("state"):
        parts.append(f"State: {addr['state']}")
    
    parts.append(f"\n🛣️ *Road Classification*: {classification.get('road_type', 'Unknown').title()}")
    parts.append(f"🏛️ *Responsible Authority*: {classification.get('authority', 'Unknown')}")
    
    if classification.get("note"):
        parts.append(f"\n💡 {classification['note']}")
    
    return "\n".join(parts)
