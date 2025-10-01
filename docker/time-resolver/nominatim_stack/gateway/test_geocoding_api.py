#!/usr/bin/env python3
"""
Test Geocoding API Gateway
==========================

A mock version of the geocoding API for testing API structure and
Phase 3 validation when Nominatim is not available.
"""

import json
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Test Geocoding API Gateway",
    description="Mock REST API for testing geocoding service structure",
    version="1.0.0-test"
)

# Reuse the same models as the main service
from geocoding_api import (
    GeocodeRequest, ReverseGeocodeRequest, GeocodeResult,
    GeocodeResponse, ReverseGeocodeResponse, HealthResponse
)

# Mock data for testing
MOCK_LOCATIONS = {
    "Fort Knox": {
        "lat": 37.891,
        "lon": -85.963,
        "display_name": "Fort Knox, Kentucky, United States",
        "address": {
            "military": "Fort Knox",
            "county": "Hardin County",
            "state": "Kentucky",
            "country": "United States",
            "country_code": "us"
        }
    },
    "Monaco": {
        "lat": 43.7384,
        "lon": 7.4246,
        "display_name": "Monaco, Monaco",
        "address": {
            "city": "Monaco",
            "country": "Monaco",
            "country_code": "mc"
        }
    },
    "New York": {
        "lat": 40.7128,
        "lon": -74.0060,
        "display_name": "New York, NY, United States",
        "address": {
            "city": "New York",
            "state": "New York",
            "country": "United States",
            "country_code": "us"
        }
    }
}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        nominatim_available=False,  # Mock service
        version="1.0.0-test",
        uptime="mock"
    )

@app.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(request: GeocodeRequest):
    """Mock geocode an address to coordinates"""
    try:
        # Simple mock matching
        results = []
        query_lower = request.address.lower()

        for location_name, data in MOCK_LOCATIONS.items():
            if location_name.lower() in query_lower or query_lower in location_name.lower():
                result = GeocodeResult(
                    latitude=data["lat"],
                    longitude=data["lon"],
                    display_name=data["display_name"],
                    address_components=data["address"],
                    importance=0.8,
                    place_type="mock",
                    bounding_box=None
                )
                results.append(result)

                if len(results) >= request.limit:
                    break

        return GeocodeResponse(
            success=True,
            results=results,
            count=len(results),
            query=request.address,
            error=None if results else "No mock results found"
        )

    except Exception as e:
        logger.error(f"Mock geocoding error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal mock geocoding error"
        )

@app.post("/reverse", response_model=ReverseGeocodeResponse)
async def reverse_geocode_coordinates(request: ReverseGeocodeRequest):
    """Mock reverse geocode coordinates to an address"""
    try:
        # Find closest mock location
        min_distance = float('inf')
        closest_location = None

        for location_name, data in MOCK_LOCATIONS.items():
            # Simple distance calculation
            distance = abs(data["lat"] - request.latitude) + abs(data["lon"] - request.longitude)
            if distance < min_distance:
                min_distance = distance
                closest_location = data

        if closest_location and min_distance < 1.0:  # Within ~1 degree
            result = GeocodeResult(
                latitude=closest_location["lat"],
                longitude=closest_location["lon"],
                display_name=closest_location["display_name"],
                address_components=closest_location["address"],
                importance=0.8,
                place_type="mock",
                bounding_box=None
            )

            return ReverseGeocodeResponse(
                success=True,
                result=result,
                coordinates=f"{request.latitude},{request.longitude}"
            )
        else:
            return ReverseGeocodeResponse(
                success=False,
                result=None,
                coordinates=f"{request.latitude},{request.longitude}",
                error="No mock location found nearby"
            )

    except Exception as e:
        logger.error(f"Mock reverse geocoding error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal mock reverse geocoding error"
        )

@app.get("/geocode", response_model=GeocodeResponse)
async def geocode_address_get(
    address: str = Query(..., description="Address to geocode"),
    limit: int = Query(default=5, ge=1, le=50, description="Maximum number of results"),
    country_codes: Optional[str] = Query(None, description="Comma-separated country codes")
):
    """Mock geocode an address (GET method)"""
    request = GeocodeRequest(
        address=address,
        limit=limit,
        country_codes=country_codes
    )
    return await geocode_address(request)

@app.get("/reverse", response_model=ReverseGeocodeResponse)
async def reverse_geocode_coordinates_get(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    zoom: int = Query(default=18, ge=1, le=18, description="Detail level")
):
    """Mock reverse geocode coordinates (GET method)"""
    request = ReverseGeocodeRequest(
        latitude=lat,
        longitude=lon,
        zoom=zoom
    )
    return await reverse_geocode_coordinates(request)

if __name__ == "__main__":
    uvicorn.run(
        "test_geocoding_api:app",
        host="0.0.0.0",
        port=8086,
        reload=True,
        log_level="info"
    )