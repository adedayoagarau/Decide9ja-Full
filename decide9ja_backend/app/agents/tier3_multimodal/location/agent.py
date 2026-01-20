"""
LocationProcessorAgent
======================
Processes shared locations - reverse geocoding to Nigerian LGA/State.

Cost: FREE (uses OpenStreetMap Nominatim API)

Features:
- Reverse geocoding to address
- Nigerian LGA and State extraction
- Location validation (is it in Nigeria?)
- User profile location updates

Usage:
    agent = LocationProcessorAgent()
    output = await agent.handle(AgentInput(
        location={"lat": 6.5244, "lng": 3.3792}
    ))
    # output.data contains parsed location
"""

import os
import time
import logging
import httpx
from typing import Optional, Dict, List
from datetime import datetime

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class LocationProcessorAgent(BaseAgent):
    """Processes shared locations with Nigerian context"""

    name = "location_processor"
    description = "Process and enrich location data for Nigeria"
    tier = AgentTier.MULTIMODAL
    cost_level = CostLevel.FREE  # Using free Nominatim API

    # Nigerian states (36 + FCT)
    NIGERIAN_STATES = [
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
        "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
        "Federal Capital Territory", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna",
        "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger",
        "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba",
        "Yobe", "Zamfara"
    ]

    # State capitals for context
    STATE_CAPITALS = {
        "Lagos": "Ikeja",
        "Kano": "Kano",
        "Rivers": "Port Harcourt",
        "FCT": "Abuja",
        "Oyo": "Ibadan",
        "Kaduna": "Kaduna",
        "Delta": "Asaba",
        "Anambra": "Awka",
        "Enugu": "Enugu",
        "Imo": "Owerri",
    }

    # Major cities for landmark detection
    MAJOR_CITIES = [
        "Lagos", "Kano", "Ibadan", "Abuja", "Port Harcourt", "Benin City",
        "Maiduguri", "Zaria", "Aba", "Jos", "Ilorin", "Oyo", "Enugu", "Abeokuta",
        "Onitsha", "Warri", "Sokoto", "Calabar", "Katsina", "Akure"
    ]

    # Configuration
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
    USER_AGENT = "Decide9ja/1.0 (civic-engagement-platform)"
    TIMEOUT_SECONDS = 10
    CACHE_TTL_HOURS = 24

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._location_cache: Dict[str, Dict] = {}  # coord_key -> location_data

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS)
        return self._http_client

    async def can_handle(self, input: AgentInput) -> bool:
        """Check if we have location data"""
        return bool(input.location)

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Process location and return enriched data"""
        self._call_count += 1
        start_time = time.time()

        if not input.location:
            return self.fail("No location data provided")

        lat = input.location.get("lat") or input.location.get("latitude")
        lng = input.location.get("lng") or input.location.get("longitude")

        if lat is None or lng is None:
            return self.fail("Invalid location coordinates")

        try:
            # Check cache first
            cache_key = f"{lat:.4f},{lng:.4f}"
            if cache_key in self._location_cache:
                cached = self._location_cache[cache_key]
                logger.debug("Location cache hit for %s", cache_key)
                return self._build_output(cached, lat, lng, cached=True)

            # Reverse geocode
            raw_data = await self._reverse_geocode(lat, lng)

            if not raw_data:
                return self._build_fallback_output(lat, lng)

            # Parse Nigerian location
            parsed = self._parse_nigerian_location(raw_data)

            # Cache the result
            self._location_cache[cache_key] = parsed

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Processed location in %.0fms: %s, %s (Nigeria=%s)",
                processing_time,
                parsed.get("lga"),
                parsed.get("state"),
                parsed.get("is_nigeria")
            )

            return self._build_output(parsed, lat, lng, processing_time=processing_time)

        except httpx.TimeoutException:
            logger.warning("Geocoding timeout for %s,%s", lat, lng)
            return self._build_fallback_output(lat, lng)

        except Exception as e:
            logger.exception("Location processing failed: %s", e)
            return self._build_fallback_output(lat, lng)

    async def _reverse_geocode(self, lat: float, lng: float) -> Optional[Dict]:
        """Reverse geocode using OpenStreetMap Nominatim (free)"""
        client = await self._get_client()

        try:
            response = await client.get(
                self.NOMINATIM_URL,
                params={
                    "lat": lat,
                    "lon": lng,
                    "format": "json",
                    "addressdetails": 1,
                    "zoom": 18,  # High zoom for detailed address
                },
                headers={"User-Agent": self.USER_AGENT}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning("Nominatim returned %d", response.status_code)
                return None

        except Exception as e:
            logger.error("Nominatim request failed: %s", e)
            return None

    def _parse_nigerian_location(self, data: Dict) -> Dict:
        """Parse Nominatim response for Nigerian context"""
        address = data.get("address", {})
        display_name = data.get("display_name", "Unknown location")

        # Determine if in Nigeria
        country = address.get("country", "")
        is_nigeria = country.lower() == "nigeria"

        # If not explicitly Nigeria, check if state matches Nigerian states
        state = address.get("state", "")
        if not is_nigeria and state:
            is_nigeria = any(s.lower() in state.lower() for s in self.NIGERIAN_STATES)

        # Extract state (normalize FCT)
        if "Federal Capital Territory" in state or "FCT" in state:
            state = "FCT"

        # Extract LGA
        # Nominatim uses various fields for LGA-level data
        lga = (
            address.get("county") or
            address.get("city_district") or
            address.get("suburb") or
            address.get("town") or
            address.get("city") or
            ""
        )

        # Clean up LGA name
        lga = self._clean_lga_name(lga)

        # Extract more specific location info
        locality = (
            address.get("neighbourhood") or
            address.get("suburb") or
            address.get("residential") or
            ""
        )

        road = address.get("road", "")
        landmark = address.get("amenity") or address.get("building") or ""

        # Build formatted address
        address_parts = []
        if road:
            address_parts.append(road)
        if locality and locality != lga:
            address_parts.append(locality)
        if lga:
            address_parts.append(lga)
        if state:
            address_parts.append(state)

        formatted_address = ", ".join(filter(None, address_parts))

        return {
            "address": formatted_address or display_name,
            "full_address": display_name,
            "state": state,
            "lga": lga,
            "locality": locality,
            "road": road,
            "landmark": landmark,
            "is_nigeria": is_nigeria,
            "country": country,
            "raw_address": address,
        }

    def _clean_lga_name(self, lga: str) -> str:
        """Clean up LGA name by removing common suffixes"""
        if not lga:
            return ""

        # Remove common suffixes
        suffixes = [
            " Local Government Area",
            " Local Government",
            " LGA",
            " Area Council",
            " Municipal",
        ]

        cleaned = lga
        for suffix in suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)]
                break

        return cleaned.strip()

    def _build_output(
        self,
        parsed: Dict,
        lat: float,
        lng: float,
        processing_time: float = 0,
        cached: bool = False
    ) -> AgentOutput:
        """Build output from parsed location data"""

        # Build response text
        if parsed.get("is_nigeria"):
            location_str = parsed.get("address", "your location")
            state = parsed.get("state", "")
            lga = parsed.get("lga", "")

            response_text = f"📍 I've received your location: {location_str}"

            if state and lga:
                response_text += f"\n\nThis is in *{lga}*, *{state} State*."
            elif state:
                response_text += f"\n\nThis is in *{state} State*."

            response_text += "\n\nHow can I help you with this location?"
        else:
            response_text = (
                f"📍 I've received your location, but it appears to be outside Nigeria. "
                "Decide9ja focuses on Nigerian civic information. "
                "Please share a location within Nigeria."
            )

        return AgentOutput(
            success=True,
            response_text=response_text,
            data={
                "latitude": lat,
                "longitude": lng,
                "address": parsed.get("address", "Unknown"),
                "full_address": parsed.get("full_address", ""),
                "state": parsed.get("state", ""),
                "lga": parsed.get("lga", ""),
                "locality": parsed.get("locality", ""),
                "road": parsed.get("road", ""),
                "landmark": parsed.get("landmark", ""),
                "is_nigeria": parsed.get("is_nigeria", False),
                "country": parsed.get("country", ""),
                "processing_time_ms": processing_time,
                "cached": cached,
            },
            cost_level=CostLevel.FREE,
            analytics_tags={
                "modality": "location_input",
                "is_nigeria": parsed.get("is_nigeria", False),
                "state": parsed.get("state", "unknown"),
            }
        )

    def _build_fallback_output(self, lat: float, lng: float) -> AgentOutput:
        """Build fallback output when geocoding fails"""
        # Basic Nigeria bounding box check
        # Nigeria roughly: lat 4-14, lng 2-15
        likely_nigeria = (4.0 <= lat <= 14.0) and (2.0 <= lng <= 15.0)

        response_text = (
            f"📍 I've received your location (coordinates: {lat:.4f}, {lng:.4f}).\n\n"
            "I couldn't determine the exact address, but I've saved the coordinates.\n\n"
            "How can I help you with this location?"
        )

        return AgentOutput(
            success=True,
            response_text=response_text,
            data={
                "latitude": lat,
                "longitude": lng,
                "address": f"Coordinates: {lat:.4f}, {lng:.4f}",
                "is_nigeria": likely_nigeria,
                "geocoding_failed": True,
            },
            cost_level=CostLevel.FREE,
            analytics_tags={
                "modality": "location_input",
                "geocoding_failed": True,
            }
        )

    def clear_cache(self):
        """Clear the location cache"""
        self._location_cache.clear()

    async def cleanup(self):
        """Cleanup HTTP client"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
