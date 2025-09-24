#!/usr/bin/env python3
"""Script to get golden values for tests"""

import asyncio
from main import ChartRequest, calculate_planetary_positions
import json

async def main() -> None:
    request = ChartRequest(
        birth_time="2024-06-21T18:00:00Z",
        latitude=37.7749,
        longitude=-122.4194,
        elevation=50,
        ayanamsa="lahiri"
    )

    # Mock request object for rate limiter
    class MockRequest:
        def __init__(self) -> None:
            self.client = type('obj', (object,), {'host': '127.0.0.1'})()

    mock_req = MockRequest()

    try:
        data = await calculate_planetary_positions(request, mock_req)
        print("Golden values for 2024-06-21T18:00:00Z in San Francisco:")
        print(json.dumps(data, indent=2, default=str))

        print("\nTest assertions:")
        for planet, pos in data.items():
            print(f'assert abs(((data["{planet}"]["longitude"] - {pos.longitude:.4f} + 180) % 360) - 180) < 0.005')
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())