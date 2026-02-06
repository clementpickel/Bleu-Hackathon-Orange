"""FastAPI application for Release Notes Decision Support System"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes import router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Release Notes Decision Support API",
    description="Production-ready API for analyzing router/gateway release notes",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Release Notes Decision Support API")
    logger.info(f"Vector DB: {settings.vector_db}")
    logger.info(f"Assets path: {settings.assets_path}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Release Notes Decision Support API")


@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "service": "Release Notes Decision Support API",
        "version": "1.0.0",
        "status": "running"
    }
