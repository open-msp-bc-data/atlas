"""Geocoding module – convert addresses to lat/lng coordinates."""

from __future__ import annotations

from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


# ── BC city centroid fallback table ───────────────────────────────────
# Approximate centroids for common BC cities (used when geocoding fails)
BC_CITY_CENTROIDS: dict[str, tuple[float, float]] = {
    "vancouver": (49.2827, -123.1207),
    "victoria": (48.4284, -123.3656),
    "surrey": (49.1913, -122.8490),
    "burnaby": (49.2488, -122.9805),
    "richmond": (49.1666, -123.1336),
    "kelowna": (49.8880, -119.4960),
    "kamloops": (50.6745, -120.3273),
    "nanaimo": (49.1659, -123.9401),
    "prince george": (53.9171, -122.7497),
    "chilliwack": (49.1579, -121.9514),
    "abbotsford": (49.0504, -122.3045),
    "langley": (49.1044, -122.6609),
    "courtenay": (49.6878, -124.9936),
    "cranbrook": (49.5097, -115.7688),
    "penticton": (49.4991, -119.5937),
    "vernon": (50.2671, -119.2720),
    "campbell river": (50.0163, -125.2442),
    "new westminster": (49.2057, -122.9110),
    "north vancouver": (49.3200, -123.0724),
    "west vancouver": (49.3280, -123.1607),
    "coquitlam": (49.2838, -122.7932),
    "port moody": (49.2783, -122.8602),
    "maple ridge": (49.2193, -122.5984),
    "white rock": (49.0253, -122.8026),
    "trail": (49.0966, -117.7113),
    "nelson": (49.4928, -117.2948),
    "terrace": (54.5162, -128.5969),
    "fort st john": (56.2465, -120.8476),
    "dawson creek": (55.7596, -120.2353),
    "williams lake": (52.1417, -122.1417),
    "quesnel": (52.9784, -122.4927),
    "powell river": (49.8352, -124.5247),
}


# ── BC Health Authority mapping (approximate by city) ─────────────────
CITY_TO_HEALTH_AUTHORITY: dict[str, str] = {
    "vancouver": "Vancouver Coastal Health",
    "north vancouver": "Vancouver Coastal Health",
    "west vancouver": "Vancouver Coastal Health",
    "richmond": "Vancouver Coastal Health",
    "sunshine coast": "Vancouver Coastal Health",
    "powell river": "Vancouver Coastal Health",
    "squamish": "Vancouver Coastal Health",
    "whistler": "Vancouver Coastal Health",
    "surrey": "Fraser Health",
    "burnaby": "Fraser Health",
    "new westminster": "Fraser Health",
    "coquitlam": "Fraser Health",
    "port moody": "Fraser Health",
    "langley": "Fraser Health",
    "abbotsford": "Fraser Health",
    "chilliwack": "Fraser Health",
    "maple ridge": "Fraser Health",
    "white rock": "Fraser Health",
    "mission": "Fraser Health",
    "delta": "Fraser Health",
    "hope": "Fraser Health",
    "victoria": "Island Health",
    "nanaimo": "Island Health",
    "courtenay": "Island Health",
    "campbell river": "Island Health",
    "duncan": "Island Health",
    "parksville": "Island Health",
    "port alberni": "Island Health",
    "comox": "Island Health",
    "kelowna": "Interior Health",
    "kamloops": "Interior Health",
    "penticton": "Interior Health",
    "vernon": "Interior Health",
    "cranbrook": "Interior Health",
    "trail": "Interior Health",
    "nelson": "Interior Health",
    "williams lake": "Interior Health",
    "salmon arm": "Interior Health",
    "revelstoke": "Interior Health",
    "prince george": "Northern Health",
    "terrace": "Northern Health",
    "fort st john": "Northern Health",
    "dawson creek": "Northern Health",
    "quesnel": "Northern Health",
    "prince rupert": "Northern Health",
    "smithers": "Northern Health",
    "kitimat": "Northern Health",
}


def geocode_address(address: str, city: str | None = None) -> dict[str, Any]:
    """Geocode an address string using Nominatim (OpenStreetMap).

    Falls back to a city centroid if the geocoder fails or confidence is low.

    Returns:
        dict with keys: lat, lng, confidence, provider, health_authority
    """
    # Try Nominatim first
    result = _nominatim_geocode(address)
    if result and result.get("confidence", 0) >= 0.6:
        ha = _lookup_health_authority(city)
        result["health_authority"] = ha
        return result

    # Fallback: city centroid
    if city:
        return _city_centroid_fallback(city)

    return {"lat": None, "lng": None, "confidence": 0, "provider": "none", "health_authority": None}


def _nominatim_geocode(address: str) -> dict[str, Any] | None:
    """Query Nominatim for a BC address.  Returns None on failure."""
    if httpx is None:
        return None
    try:
        query = f"{address}, British Columbia, Canada"
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "ca"},
            headers={"User-Agent": "MSP-BC-Atlas/0.1 (research project)"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            hit = data[0]
            return {
                "lat": float(hit["lat"]),
                "lng": float(hit["lon"]),
                "confidence": float(hit.get("importance", 0.5)),
                "provider": "nominatim",
            }
    except Exception:
        pass
    return None


def _city_centroid_fallback(city: str) -> dict[str, Any]:
    """Return the centroid for a known BC city."""
    key = city.strip().lower()
    coords = BC_CITY_CENTROIDS.get(key)
    ha = _lookup_health_authority(city)
    if coords:
        return {
            "lat": coords[0],
            "lng": coords[1],
            "confidence": 0.4,
            "provider": "city_centroid",
            "health_authority": ha,
        }
    return {"lat": None, "lng": None, "confidence": 0, "provider": "none", "health_authority": ha}


def _lookup_health_authority(city: str | None) -> str | None:
    """Map a city name to its BC Health Authority."""
    if not city:
        return None
    return CITY_TO_HEALTH_AUTHORITY.get(city.strip().lower())
