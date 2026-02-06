"""Database models"""
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, 
    ForeignKey, JSON, Float, Date, ARRAY
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class Model(Base):
    """Hardware model table"""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    vendor = Column(String(100), nullable=False, index=True)
    product_family = Column(String(100), nullable=True, index=True)
    model_name = Column(String(200), nullable=False, index=True)
    aliases = Column(JSON, default=list)  # List of alternative names
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    versions = relationship("SoftwareVersion", back_populates="model")
    compatibilities = relationship("ModelVersionCompatibility", back_populates="model")
    upgrade_paths = relationship("UpgradePath", back_populates="model")


class SoftwareVersion(Base):
    """Software version table"""
    __tablename__ = "software_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=True, index=True)
    version_string = Column(String(100), nullable=False, index=True)
    normalized_version = Column(String(100), nullable=True, index=True)  # Semantic version
    release_date = Column(Date, nullable=True)
    eol_date = Column(Date, nullable=True, index=True)
    eol_status = Column(String(20), nullable=False, default="UNKNOWN", index=True)  # EOL/SUPPORTED/UNKNOWN
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    model = relationship("Model", back_populates="versions")
    compatibilities_from = relationship(
        "ModelVersionCompatibility",
        foreign_keys="ModelVersionCompatibility.from_version_id",
        back_populates="from_version"
    )
    compatibilities_to = relationship(
        "ModelVersionCompatibility",
        foreign_keys="ModelVersionCompatibility.to_version_id",
        back_populates="to_version"
    )
    upgrade_paths_from = relationship(
        "UpgradePath",
        foreign_keys="UpgradePath.from_version_id",
        back_populates="from_version"
    )
    upgrade_paths_to = relationship(
        "UpgradePath",
        foreign_keys="UpgradePath.to_version_id",
        back_populates="to_version"
    )


class ModelVersionCompatibility(Base):
    """Version compatibility rules table"""
    __tablename__ = "model_version_compatibility"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False, index=True)
    from_version_id = Column(Integer, ForeignKey("software_versions.id"), nullable=False, index=True)
    to_version_id = Column(Integer, ForeignKey("software_versions.id"), nullable=False, index=True)
    allowed = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    model = relationship("Model", back_populates="compatibilities")
    from_version = relationship("SoftwareVersion", foreign_keys=[from_version_id])
    to_version = relationship("SoftwareVersion", foreign_keys=[to_version_id])


class UpgradePath(Base):
    """Upgrade path rules with mandatory intermediate steps"""
    __tablename__ = "upgrade_paths"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False, index=True)
    from_version_id = Column(Integer, ForeignKey("software_versions.id"), nullable=False, index=True)
    to_version_id = Column(Integer, ForeignKey("software_versions.id"), nullable=False, index=True)
    mandatory_intermediate_version_ids = Column(ARRAY(Integer), default=list)  # Ordered list of version IDs
    notes = Column(Text, nullable=True)
    risk_level = Column(String(20), default="LOW")  # LOW/MED/HIGH
    estimated_downtime_minutes = Column(Integer, nullable=True)
    requires_backup = Column(Boolean, default=True)
    requires_reboot = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    model = relationship("Model", back_populates="upgrade_paths")
    from_version = relationship("SoftwareVersion", foreign_keys=[from_version_id])
    to_version = relationship("SoftwareVersion", foreign_keys=[to_version_id])


class PDFChunk(Base):
    """PDF text chunks table"""
    __tablename__ = "pdf_chunks"
    
    chunk_id = Column(String(500), primary_key=True, index=True)
    pdf_path = Column(String(500), nullable=False, index=True)
    page_range = Column(String(50), nullable=True)  # e.g., "3-5"
    text = Column(Text, nullable=False)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    extractions = relationship("Extraction", back_populates="chunk")


class Extraction(Base):
    """Extracted facts from chunks table"""
    __tablename__ = "extractions"
    
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String(500), ForeignKey("pdf_chunks.chunk_id"), nullable=False, index=True)
    extracted_json = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=False)
    method = Column(String(20), nullable=False, index=True)  # regex/llm/hybrid
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    chunk = relationship("PDFChunk", back_populates="extractions")
