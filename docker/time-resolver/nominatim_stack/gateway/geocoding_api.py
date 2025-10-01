#!/usr/bin/env python3
"""
Geocoding API Gateway
====================

A thin API wrapper around Nominatim that provides:
1. Address-to-coordinates geocoding
2. Coordinates-to-address reverse geocoding
3. Consistent error handling and response formatting
4. Integration readiness for Time Resolver service

This service acts as a gateway between client applications and the
Nominatim geocoding service, providing a clean REST API interface.
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
import os
NOMINATIM_BASE_URL = os.getenv("NOMINATIM_BASE_URL", "http://localhost:8080")
DEFAULT_TIMEOUT = 10
DEFAULT_LIMIT = 5

app = FastAPI(
    title="Geocoding API Gateway",
    description="REST API wrapper for Nominatim geocoding service",
    version="1.0.0"
)

# Request/Response Models
class GeocodeRequest(BaseModel):
    """Request model for geocoding an address"""
    address: str = Field(..., description="Address to geocode")
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=50, description="Maximum number of results")
    country_codes: Optional[str] = Field(None, description="Comma-separated country codes (e.g., 'us,ca')")

class ReverseGeocodeRequest(BaseModel):
    """Request model for reverse geocoding coordinates"""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    zoom: int = Field(default=18, ge=1, le=18, description="Detail level (higher = more specific)")

class GeocodeResult(BaseModel):
    """Single geocoding result"""
    latitude: float
    longitude: float
    display_name: str
    address_components: Dict[str, str]
    importance: Optional[float] = None
    place_type: Optional[str] = None
    bounding_box: Optional[List[float]] = None

class GeocodeResponse(BaseModel):
    """Response model for geocoding requests"""
    success: bool
    results: List[GeocodeResult]
    count: int
    query: str
    error: Optional[str] = None

class ReverseGeocodeResponse(BaseModel):
    """Response model for reverse geocoding requests"""
    success: bool
    result: Optional[GeocodeResult]
    coordinates: str
    error: Optional[str] = None

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    nominatim_available: bool
    version: str
    uptime: str

# Helper Functions
def format_nominatim_result(result: Dict) -> GeocodeResult:
    """Convert Nominatim result to our standard format"""
    # Extract address components
    address = result.get('address', {})

    # Parse bounding box if available
    bounding_box = None
    if 'boundingbox' in result:
        try:
            bounding_box = [float(x) for x in result['boundingbox']]
        except (ValueError, TypeError):
            pass

    return GeocodeResult(
        latitude=float(result['lat']),
        longitude=float(result['lon']),
        display_name=result.get('display_name', ''),
        address_components=address,
        importance=result.get('importance'),
        place_type=result.get('type'),
        bounding_box=bounding_box
    )

def check_nominatim_health() -> bool:
    """Check if Nominatim service is available"""
    try:
        response = requests.get(f"{NOMINATIM_BASE_URL}/status.php", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    nominatim_available = check_nominatim_health()

    return HealthResponse(
        status="healthy" if nominatim_available else "degraded",
        nominatim_available=nominatim_available,
        version="1.0.0",
        uptime="unknown"  # Could track actual uptime
    )

@app.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(request: GeocodeRequest):
    """
    Geocode an address to coordinates

    Takes an address string and returns matching locations with coordinates.
    """
    try:
        # Build Nominatim search parameters
        params = {
            'q': request.address,
            'format': 'json',
            'limit': request.limit,
            'addressdetails': 1,
            'extratags': 1,
            'namedetails': 1
        }

        if request.country_codes:
            params['countrycodes'] = request.country_codes

        # Make request to Nominatim
        response = requests.get(
            f"{NOMINATIM_BASE_URL}/search",
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        # Parse results
        nominatim_results = response.json()

        if not nominatim_results:
            return GeocodeResponse(
                success=True,
                results=[],
                count=0,
                query=request.address,
                error="No results found"
            )

        # Format results
        results = []
        for result in nominatim_results:
            try:
                formatted_result = format_nominatim_result(result)
                results.append(formatted_result)
            except Exception as e:
                logger.warning(f"Failed to format result: {e}")
                continue

        return GeocodeResponse(
            success=True,
            results=results,
            count=len(results),
            query=request.address
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Nominatim request failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Geocoding service unavailable"
        )
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal geocoding error"
        )

@app.post("/reverse", response_model=ReverseGeocodeResponse)
async def reverse_geocode_coordinates(request: ReverseGeocodeRequest):
    """
    Reverse geocode coordinates to an address

    Takes latitude/longitude coordinates and returns the address.
    """
    try:
        # Build Nominatim reverse parameters
        params = {
            'lat': request.latitude,
            'lon': request.longitude,
            'format': 'json',
            'zoom': request.zoom,
            'addressdetails': 1,
            'extratags': 1,
            'namedetails': 1
        }

        # Make request to Nominatim
        response = requests.get(
            f"{NOMINATIM_BASE_URL}/reverse",
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        # Parse result
        result_data = response.json()

        if 'error' in result_data:
            return ReverseGeocodeResponse(
                success=False,
                result=None,
                coordinates=f"{request.latitude},{request.longitude}",
                error=result_data['error']
            )

        # Format result
        try:
            formatted_result = format_nominatim_result(result_data)
            return ReverseGeocodeResponse(
                success=True,
                result=formatted_result,
                coordinates=f"{request.latitude},{request.longitude}"
            )
        except Exception as e:
            logger.warning(f"Failed to format reverse result: {e}")
            return ReverseGeocodeResponse(
                success=False,
                result=None,
                coordinates=f"{request.latitude},{request.longitude}",
                error="Failed to parse result"
            )

    except requests.exceptions.RequestException as e:
        logger.error(f"Nominatim reverse request failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Reverse geocoding service unavailable"
        )
    except Exception as e:
        logger.error(f"Reverse geocoding error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal reverse geocoding error"
        )

@app.get("/geocode", response_model=GeocodeResponse)
async def geocode_address_get(
    address: str = Query(..., description="Address to geocode"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=50, description="Maximum number of results"),
    country_codes: Optional[str] = Query(None, description="Comma-separated country codes")
):
    """
    Geocode an address (GET method for simple queries)
    """
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
    """
    Reverse geocode coordinates (GET method for simple queries)
    """
    request = ReverseGeocodeRequest(
        latitude=lat,
        longitude=lon,
        zoom=zoom
    )
    return await reverse_geocode_coordinates(request)

# Development server
if __name__ == "__main__":
    uvicorn.run(
        "geocoding_api:app",
        host="0.0.0.0",
        port=8085,
        reload=True,
        log_level="info"
    )