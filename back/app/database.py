from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
import os
import time
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/hackathon"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialise la base de données en créant toutes les tables avec retry logic"""
    max_retries = 5
    retry_interval = 2
    
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized successfully")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_interval)
            else:
                logger.error(f"Failed to initialize database after {max_retries} attempts: {e}")
                raise


def get_db():
    """Dependency pour obtenir une session de base de données"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
