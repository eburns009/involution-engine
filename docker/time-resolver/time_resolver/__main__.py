"""
Time Resolver Service - Main entry point
"""

if __name__ == "__main__":
    from .api import app
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"Starting Time Resolver API on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )