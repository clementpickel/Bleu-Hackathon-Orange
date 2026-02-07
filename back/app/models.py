from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class ProductModel(Base):
    """Table pour stocker les informations générales des produits SD-WAN"""
    __tablename__ = "product_models"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(255), nullable=False, index=True)
    product_type = Column(String(50), nullable=True)  # Edge, Gateway, Orchestrator
    is_end_of_life = Column(Boolean, default=False)
    end_of_life_date = Column(String(100), nullable=True)
    end_of_support_date = Column(String(100), nullable=True)
    status = Column(String(50), nullable=True)  # Active, Deprecated, End of Life
    functionalities = Column(JSON, nullable=True)  # Fonctionnalités principales
    alternatives = Column(JSON, nullable=True)  # Produits alternatifs recommandés
    release_date = Column(String(100), nullable=True)
    document_date = Column(String(100), nullable=True)  # Date de publication du document PDF
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    source_file = Column(String(255), nullable=True)  # Nom du PDF source
    raw_data = Column(JSON, nullable=True)  # Données brutes extraites
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ProductModel(model={self.model_name}, eol={self.is_end_of_life})>"


class GatewayVersion(Base):
    """Table pour les versions de Gateway SD-WAN (software uniquement)"""
    __tablename__ = "gateway_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(100), nullable=False, index=True, unique=True)
    release_date = Column(String(100), nullable=True)
    end_of_life_date = Column(String(100), nullable=True)
    end_of_support_date = Column(String(100), nullable=True)
    is_end_of_life = Column(Boolean, default=False)
    status = Column(String(50), nullable=True)  # Active, Deprecated, End of Life
    features = Column(JSON, nullable=True)
    document_date = Column(String(100), nullable=True)  # Date de publication du document PDF
    notes = Column(Text, nullable=True)
    source_file = Column(String(255), nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GatewayVersion(version={self.version}, eol={self.end_of_life_date})>"


class EdgeVersion(Base):
    """Table pour les versions d'Edge SD-WAN (software uniquement)"""
    __tablename__ = "edge_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(100), nullable=False, index=True, unique=True)
    release_date = Column(String(100), nullable=True)
    end_of_life_date = Column(String(100), nullable=True)
    end_of_support_date = Column(String(100), nullable=True)
    is_end_of_life = Column(Boolean, default=False)
    status = Column(String(50), nullable=True)  # Active, Deprecated, End of Life
    features = Column(JSON, nullable=True)
    document_date = Column(String(100), nullable=True)  # Date de publication du document PDF
    notes = Column(Text, nullable=True)
    source_file = Column(String(255), nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EdgeVersion(version={self.version}, eol={self.end_of_life_date})>"


class OrchestratorVersion(Base):
    """Table pour les versions d'Orchestrator/VCO SD-WAN (software uniquement)"""
    __tablename__ = "orchestrator_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(100), nullable=False, index=True, unique=True)
    release_date = Column(String(100), nullable=True)
    end_of_life_date = Column(String(100), nullable=True)
    end_of_support_date = Column(String(100), nullable=True)
    is_end_of_life = Column(Boolean, default=False)
    status = Column(String(50), nullable=True)  # Active, Deprecated, End of Life
    features = Column(JSON, nullable=True)
    document_date = Column(String(100), nullable=True)  # Date de publication du document PDF
    notes = Column(Text, nullable=True)
    source_file = Column(String(255), nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<OrchestratorVersion(version={self.version}, eol={self.end_of_life_date})>"
