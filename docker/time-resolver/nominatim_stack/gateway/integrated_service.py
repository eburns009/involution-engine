#!/usr/bin/env python3
"""
Integrated Address-to-Timezone Service
=====================================

Phase 4: Full pipeline integration service that combines:
1. Address geocoding (using the geocoding gateway)
2. Historical timezone resolution (using Time Resolver)

This service provides the complete workflow:
Address → Coordinates → Historical Timezone Resolution

Perfect for applications that need to determine historical timezones
for any address, accounting for complex timezone changes over time.
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
import os
GEOCODING_SERVICE_URL = os.getenv("GEOCODING_SERVICE_URL", "http://localhost:8086")
TIME_RESOLVER_URL = os.getenv("TIME_RESOLVER_URL", "http://localhost:8082")
DEFAULT_TIMEOUT = 30

app = FastAPI(
    title="Integrated Address-to-Timezone Service",
    description="Complete pipeline: Address → Coordinates → Historical Timezone",
    version="1.0.0"
)

# Request/Response Models
class AddressTimeRequest(BaseModel):
    """Request model for address-based time resolution"""
    address: str = Field(..., description="Address to resolve")
    local_datetime: str = Field(..., description="Local datetime (YYYY-MM-DDTHH:MM:SS)")
    parity_profile: str = Field(default="strict_history", description="Parity profile for timezone resolution")
    geocoding_limit: int = Field(default=1, ge=1, le=5, description="Maximum geocoding results to consider")

class CoordinateInfo(BaseModel):
    """Coordinate information from geocoding"""
    latitude: float
    longitude: float
    display_name: str
    address_components: Dict[str, str]

class TimezoneResolution(BaseModel):
    """Timezone resolution result"""
    utc: str
    zone_id: str
    confidence: str
    provenance: Dict

class IntegratedResponse(BaseModel):
    """Response model for integrated address-to-timezone resolution"""
    success: bool
    address_query: str
    local_datetime: str

    # Geocoding results
    geocoding_success: bool
    coordinates: Optional[CoordinateInfo] = None
    geocoding_error: Optional[str] = None

    # Timezone resolution results
    timezone_success: bool
    timezone_result: Optional[TimezoneResolution] = None
    timezone_error: Optional[str] = None

    # Overall result
    final_utc: Optional[str] = None
    final_timezone: Optional[str] = None
    processing_notes: List[str] = []

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    geocoding_available: bool
    time_resolver_available: bool
    version: str

# Helper Functions
def check_service_health(url: str, endpoint: str = "/health") -> bool:
    """Check if a service is available"""
    try:
        response = requests.get(f"{url}{endpoint}", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def geocode_address(address: str, limit: int = 1) -> Dict:
    """Geocode an address using the geocoding service"""
    try:
        response = requests.get(
            f"{GEOCODING_SERVICE_URL}/geocode",
            params={"address": address, "limit": limit},
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Geocoding failed: {e}")
        raise

def resolve_timezone(latitude: float, longitude: float, local_datetime: str, parity_profile: str) -> Dict:
    """Resolve timezone using Time Resolver service"""
    try:
        payload = {
            "local_datetime": local_datetime,
            "place": {
                "lat": latitude,
                "lon": longitude
            },
            "parity_profile": parity_profile
        }

        response = requests.post(
            f"{TIME_RESOLVER_URL}/v1/time/resolve",
            json=payload,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Time resolution failed: {e}")
        raise

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    geocoding_available = check_service_health(GEOCODING_SERVICE_URL)
    time_resolver_available = check_service_health(TIME_RESOLVER_URL)

    status = "healthy" if (geocoding_available and time_resolver_available) else "degraded"

    return HealthResponse(
        status=status,
        geocoding_available=geocoding_available,
        time_resolver_available=time_resolver_available,
        version="1.0.0"
    )

@app.post("/resolve", response_model=IntegratedResponse)
async def resolve_address_timezone(request: AddressTimeRequest):
    """
    Complete address-to-timezone resolution pipeline

    This endpoint:
    1. Geocodes the provided address to get coordinates
    2. Uses those coordinates to resolve the historical timezone
    3. Returns the complete result with provenance information
    """

    processing_notes = []

    # Initialize response
    response = IntegratedResponse(
        success=False,
        address_query=request.address,
        local_datetime=request.local_datetime,
        geocoding_success=False,
        timezone_success=False,
        processing_notes=processing_notes
    )

    try:
        # Step 1: Geocode the address
        processing_notes.append("Starting address geocoding...")

        try:
            geocoding_result = geocode_address(request.address, request.geocoding_limit)

            if not geocoding_result.get("success") or not geocoding_result.get("results"):
                response.geocoding_error = "No geocoding results found"
                processing_notes.append("❌ Geocoding failed: No results")
                return response

            # Use the first/best result
            best_result = geocoding_result["results"][0]

            response.coordinates = CoordinateInfo(
                latitude=best_result["latitude"],
                longitude=best_result["longitude"],
                display_name=best_result["display_name"],
                address_components=best_result["address_components"]
            )

            response.geocoding_success = True
            processing_notes.append(f"✅ Geocoded to: {best_result['display_name']}")
            processing_notes.append(f"📍 Coordinates: {best_result['latitude']}, {best_result['longitude']}")

        except Exception as e:
            response.geocoding_error = str(e)
            processing_notes.append(f"❌ Geocoding service error: {e}")
            return response

        # Step 2: Resolve timezone for the coordinates
        processing_notes.append("Starting historical timezone resolution...")

        try:
            timezone_result = resolve_timezone(
                response.coordinates.latitude,
                response.coordinates.longitude,
                request.local_datetime,
                request.parity_profile
            )

            response.timezone_result = TimezoneResolution(
                utc=timezone_result["utc"],
                zone_id=timezone_result["zone_id"],
                confidence=timezone_result["confidence"],
                provenance=timezone_result.get("provenance", {})
            )

            response.timezone_success = True
            response.final_utc = timezone_result["utc"]
            response.final_timezone = timezone_result["zone_id"]

            processing_notes.append(f"✅ Timezone resolved: {timezone_result['zone_id']}")
            processing_notes.append(f"🕐 {request.local_datetime} local → {timezone_result['utc']} UTC")

            # Check for historical patches
            patches_applied = timezone_result.get("provenance", {}).get("patches_applied", [])
            if patches_applied:
                processing_notes.append(f"🔧 Applied patches: {', '.join(patches_applied)}")
            else:
                processing_notes.append("🔧 No historical patches applied")

        except Exception as e:
            response.timezone_error = str(e)
            processing_notes.append(f"❌ Time resolution error: {e}")
            return response

        # Success!
        response.success = True
        processing_notes.append("🎉 Complete pipeline successful!")

        return response

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        processing_notes.append(f"❌ Pipeline error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal pipeline error"
        )

@app.get("/resolve", response_model=IntegratedResponse)
async def resolve_address_timezone_get(
    address: str = Query(..., description="Address to resolve"),
    local_datetime: str = Query(..., description="Local datetime (YYYY-MM-DDTHH:MM:SS)"),
    parity_profile: str = Query(default="strict_history", description="Parity profile"),
    geocoding_limit: int = Query(default=1, ge=1, le=5, description="Max geocoding results")
):
    """
    Complete address-to-timezone resolution (GET method for simple queries)
    """
    request = AddressTimeRequest(
        address=address,
        local_datetime=local_datetime,
        parity_profile=parity_profile,
        geocoding_limit=geocoding_limit
    )
    return await resolve_address_timezone(request)

# Test endpoints for validation
@app.get("/test/fort-knox-1943")
async def test_fort_knox_1943():
    """Test case: Fort Knox 1943 (should apply historical patches)"""
    request = AddressTimeRequest(
        address="Fort Knox, Kentucky",
        local_datetime="1943-06-15T14:30:00",
        parity_profile="strict_history"
    )
    return await resolve_address_timezone(request)

@app.get("/test/modern-nyc")
async def test_modern_nyc():
    """Test case: Modern NYC (no patches expected)"""
    request = AddressTimeRequest(
        address="New York, NY",
        local_datetime="2023-06-15T14:30:00",
        parity_profile="strict_history"
    )
    return await resolve_address_timezone(request)

@app.get("/test/parity-comparison")
async def test_parity_comparison():
    """Test case: Compare parity profiles for same location/time"""
    results = {}

    base_request = {
        "address": "Fort Knox, Kentucky",
        "local_datetime": "1943-06-15T14:30:00"
    }

    for profile in ["strict_history", "astro_com"]:
        try:
            request = AddressTimeRequest(**base_request, parity_profile=profile)
            result = await resolve_address_timezone(request)
            results[profile] = {
                "success": result.success,
                "final_utc": result.final_utc,
                "final_timezone": result.final_timezone,
                "patches_applied": result.timezone_result.provenance.get("patches_applied", []) if result.timezone_result else []
            }
        except Exception as e:
            results[profile] = {"error": str(e)}

    return {
        "test_case": "Fort Knox 1943 Parity Profile Comparison",
        "results": results,
        "expected_difference": "strict_history should apply fort_knox_1943 patch"
    }

# Development server
if __name__ == "__main__":
    uvicorn.run(
        "integrated_service:app",
        host="0.0.0.0",
        port=8087,
        reload=True,
        log_level="info"
    )