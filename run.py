#!/usr/bin/env python3
"""
Utility script to run the application locally without Docker
"""
import sys
import os

# Add app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings
    
    print("=" * 60)
    print("Release Notes Decision Support API")
    print("=" * 60)
    print(f"Environment: {'DEBUG' if settings.debug else 'PRODUCTION'}")
    print(f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'Not configured'}")
    print(f"Vector Store: {settings.vector_db.upper()}")
    print(f"Assets Path: {settings.assets_path}")
    print("=" * 60)
    print()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
