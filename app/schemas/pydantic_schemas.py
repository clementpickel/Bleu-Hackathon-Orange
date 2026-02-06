"""Pydantic schemas for API requests and responses"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime


# ===== Model Schemas =====
class ModelBase(BaseModel):
    vendor: str
    product_family: Optional[str] = None
    model_name: str
    aliases: List[str] = []


class ModelCreate(ModelBase):
    pass


class ModelResponse(ModelBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ModelLifecycle(BaseModel):
    """Detailed model lifecycle response"""
    model_id: int
    vendor: str
    model_name: str
    eol_status: str
    eol_date: Optional[date] = None
    recommended_replacements: List[str] = []
    versions: List[VersionInfo] = []


class VersionInfo(BaseModel):
    version: str
    eol_status: str
    eol_date: Optional[date] = None
    release_date: Optional[date] = None


# ===== Software Version Schemas =====
class SoftwareVersionBase(BaseModel):
    version_string: str
    normalized_version: Optional[str] = None
    release_date: Optional[date] = None
    eol_date: Optional[date] = None
    eol_status: Literal["EOL", "SUPPORTED", "UNKNOWN"] = "UNKNOWN"
    notes: Optional[str] = None


class SoftwareVersionCreate(SoftwareVersionBase):
    model_id: Optional[int] = None


class SoftwareVersionResponse(SoftwareVersionBase):
    id: int
    model_id: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ===== Extraction Schemas =====
class ExtractedFact(BaseModel):
    """Structured fact extracted from PDF chunk"""
    vendor: Optional[str] = None
    product_family: Optional[str] = None
    model: Optional[str] = None
    model_aliases: List[str] = []
    software_version: Optional[str] = None
    eol_status: Literal["EOL", "SUPPORTED", "UNKNOWN"] = "UNKNOWN"
    eol_date: Optional[str] = None  # YYYY-MM-DD or null
    replacement_models: List[str] = []
    compatible_versions: List[str] = []
    upgrade_instructions: Optional[str] = None
    notes: Optional[str] = None
    source_chunk_id: Optional[str] = None
    evidence: Dict[str, List[str]] = {}  # field -> list of text snippets


class ExtractionResponse(BaseModel):
    id: int
    chunk_id: str
    extracted_json: Dict[str, Any]
    confidence: float
    method: str
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ===== Chunk Schemas =====
class ChunkResponse(BaseModel):
    chunk_id: str
    pdf_path: str
    page_range: Optional[str] = None
    text: str
    inserted_at: datetime
    extractions: List[ExtractionResponse] = []
    
    class Config:
        from_attributes = True


# ===== Upgrade Path Schemas =====
class UpgradeStep(BaseModel):
    step: str
    notes: Optional[str] = None
    references: List[str] = []
    risk: Literal["LOW", "MED", "HIGH"] = "LOW"
    requires_backup: bool = True
    requires_reboot: bool = True
    estimated_downtime_minutes: Optional[int] = None


class UpgradePathResponse(BaseModel):
    model_id: int
    from_version: str
    to_version: str
    steps: List[UpgradeStep]
    overall_risk: Literal["LOW", "MED", "HIGH"]
    total_estimated_downtime_minutes: Optional[int] = None


class UpgradePathRequest(BaseModel):
    model_id: int
    current_version: str
    target_version: str


# ===== Query Schemas =====
class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question")
    context: Dict[str, Any] = Field(default_factory=dict, description="Optional filters")
    top_k: int = Field(default=5, description="Number of chunks to retrieve")


class QueryResponse(BaseModel):
    answer_text: str
    facts_used: List[int] = []
    recommended_actions: List[Dict[str, Any]] = []
    upgrade_paths: List[UpgradePathResponse] = []
    references: List[str] = []  # Chunk IDs
    confidence: float


# ===== Ingestion Schemas =====
class IngestionSummary(BaseModel):
    files_parsed: int
    chunks_created: int
    extractions_count: int
    models_created: int
    versions_created: int
    warnings: List[str] = []
    duration_seconds: float


class ReindexResponse(BaseModel):
    chunks_reindexed: int
    duration_seconds: float


# ===== API Response Wrapper =====
class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: List[str] = []


# Rebuild models to resolve forward references
ModelLifecycle.model_rebuild()
ChunkResponse.model_rebuild()
