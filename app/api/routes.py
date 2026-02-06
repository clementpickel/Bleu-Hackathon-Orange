"""API routes for the release notes decision support system"""
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import logging

from app.db.session import get_db
from app.db.models import Model, SoftwareVersion, PDFChunk
from app.schemas.pydantic_schemas import (
    ModelResponse, ModelLifecycle, VersionInfo,
    SoftwareVersionResponse, ChunkResponse,
    UpgradePathRequest, UpgradePathResponse, UpgradeStep,
    QueryRequest, QueryResponse,
    IngestionSummary, ReindexResponse, APIResponse
)
from app.services.ingest_service import IngestionService
from app.services.query_service import QueryService
from app.vector.vector_store import get_vector_store
from app.llm.llm_client import get_llm_client
from app.compatibility.graph import UpgradePathEngine
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# Dependency for API key authentication
async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header"""
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return x_api_key


@router.post("/ingest", response_model=IngestionSummary, tags=["Ingestion"])
async def ingest_pdfs(
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Ingest all PDFs from assets directory.
    
    - Parses PDFs
    - Creates text chunks
    - Runs hybrid extraction pipeline
    - Stores facts in database
    - Indexes chunks in vector store
    """
    try:
        vector_store = get_vector_store()
        llm_client = get_llm_client()
        
        service = IngestionService(
            db=db,
            vector_store=vector_store,
            llm_client=llm_client,
            assets_path=settings.assets_path
        )
        
        summary = await service.ingest_all_pdfs()
        return summary
    
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/reindex", response_model=ReindexResponse, tags=["Ingestion"])
async def reindex_vectors(
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Reindex all chunks in vector store.
    
    Useful after changing embedding model or vector store backend.
    """
    try:
        vector_store = get_vector_store()
        llm_client = get_llm_client()
        
        service = IngestionService(
            db=db,
            vector_store=vector_store,
            llm_client=llm_client
        )
        
        result = await service.reindex_vectors()
        return result
    
    except Exception as e:
        logger.error(f"Reindexing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reindexing failed: {str(e)}")


@router.get("/models", response_model=List[ModelResponse], tags=["Models"])
async def get_models(
    vendor: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get list of models with optional vendor filter.
    """
    query = select(Model)
    if vendor:
        query = query.where(Model.vendor == vendor)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    models = result.scalars().all()
    
    return models


@router.get("/model/{model_id}", response_model=ModelLifecycle, tags=["Models"])
async def get_model_lifecycle(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get detailed lifecycle information for a model including all versions and EOL status.
    """
    # Get model
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get versions
    result = await db.execute(
        select(SoftwareVersion)
        .where(SoftwareVersion.model_id == model_id)
        .order_by(SoftwareVersion.normalized_version)
    )
    versions = result.scalars().all()
    
    # Determine overall EOL status
    eol_versions = [v for v in versions if v.eol_status == 'EOL']
    supported_versions = [v for v in versions if v.eol_status == 'SUPPORTED']
    
    overall_eol_status = 'EOL' if eol_versions and not supported_versions else 'SUPPORTED'
    overall_eol_date = max([v.eol_date for v in eol_versions if v.eol_date], default=None)
    
    # Get replacement models (would need more logic in production)
    recommended_replacements = []
    
    version_infos = [
        VersionInfo(
            version=v.version_string,
            eol_status=v.eol_status,
            eol_date=v.eol_date,
            release_date=v.release_date
        )
        for v in versions
    ]
    
    return ModelLifecycle(
        model_id=model.id,
        vendor=model.vendor,
        model_name=model.model_name,
        eol_status=overall_eol_status,
        eol_date=overall_eol_date,
        recommended_replacements=recommended_replacements,
        versions=version_infos
    )


@router.post("/query", response_model=QueryResponse, tags=["Query"])
async def query_system(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Query the system with natural language.
    
    - Performs database lookup for facts
    - Searches for relevant PDF chunks via vector search
    - Uses LLM to generate comprehensive answer
    - Identifies potential upgrade paths
    """
    try:
        vector_store = get_vector_store()
        llm_client = get_llm_client()
        upgrade_engine = UpgradePathEngine()
        
        service = QueryService(
            db=db,
            vector_store=vector_store,
            llm_client=llm_client,
            upgrade_engine=upgrade_engine
        )
        
        result = await service.query(
            question=request.query,
            context=request.context,
            top_k=request.top_k
        )
        
        return QueryResponse(**result)
    
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/upgrade-path", response_model=UpgradePathResponse, tags=["Upgrade"])
async def get_upgrade_path(
    request: UpgradePathRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get deterministic upgrade path between two versions.
    
    Returns step-by-step upgrade instructions with:
    - Mandatory intermediate versions
    - Risk levels
    - Estimated downtime
    - References to release notes
    """
    try:
        upgrade_engine = UpgradePathEngine()
        
        # Get version IDs
        result = await db.execute(
            select(SoftwareVersion)
            .where(
                SoftwareVersion.model_id == request.model_id,
                SoftwareVersion.version_string.in_([request.current_version, request.target_version])
            )
        )
        versions = {v.version_string: v for v in result.scalars().all()}
        
        if request.current_version not in versions:
            raise HTTPException(status_code=404, detail=f"Current version not found: {request.current_version}")
        if request.target_version not in versions:
            raise HTTPException(status_code=404, detail=f"Target version not found: {request.target_version}")
        
        from_version_id = versions[request.current_version].id
        to_version_id = versions[request.target_version].id
        
        # Compute path
        path = await upgrade_engine.compute_upgrade_path(
            db=db,
            model_id=request.model_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id
        )
        
        if not path:
            raise HTTPException(
                status_code=404,
                detail=f"No upgrade path found from {request.current_version} to {request.target_version}"
            )
        
        # Format response
        steps = []
        for step in path['steps']:
            steps.append(UpgradeStep(
                step=f"{step['from_version']} -> {step['to_version']}",
                notes=step.get('notes'),
                references=[],
                risk=step.get('risk_level', 'LOW'),
                requires_backup=step.get('requires_backup', True),
                requires_reboot=step.get('requires_reboot', True),
                estimated_downtime_minutes=step.get('estimated_downtime_minutes')
            ))
        
        return UpgradePathResponse(
            model_id=request.model_id,
            from_version=request.current_version,
            to_version=request.target_version,
            steps=steps,
            overall_risk=path['overall_risk'],
            total_estimated_downtime_minutes=path.get('total_estimated_downtime_minutes')
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upgrade path computation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upgrade path computation failed: {str(e)}")


@router.get("/chunks/{chunk_id}", response_model=ChunkResponse, tags=["Chunks"])
async def get_chunk(
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get raw chunk text and extraction results.
    """
    result = await db.execute(
        select(PDFChunk).where(PDFChunk.chunk_id == chunk_id)
    )
    chunk = result.scalar_one_or_none()
    
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    return chunk


@router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
