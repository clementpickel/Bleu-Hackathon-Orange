from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class ProductModel(Base):
    """Table pour stocker les informations extraites des PDFs"""
    __tablename__ = "product_models"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(255), nullable=False)
    version = Column(String(100), nullable=False)
    end_of_life = Column(String(255), nullable=True)
    functionalities = Column(JSON, nullable=True)  # Stocke les fonctionnalités en JSON
    release_date = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    source_file = Column(String(255), nullable=True)  # Nom du PDF source
    raw_data = Column(JSON, nullable=True)  # Données brutes extraites
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ProductModel(model={self.model_name}, version={self.version})>"
