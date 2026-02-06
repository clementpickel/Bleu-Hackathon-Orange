"""Query service for answering natural language questions"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import logging

from app.db.models import Model, SoftwareVersion, PDFChunk, Extraction
from app.vector.vector_store import VectorStore
from app.llm.llm_client import LLMClient
from app.compatibility.graph import UpgradePathEngine
from app.schemas.pydantic_schemas import UpgradePathResponse, UpgradeStep

logger = logging.getLogger(__name__)


class QueryService:
    """Service for handling natural language queries"""
    
    def __init__(
        self,
        db: AsyncSession,
        vector_store: VectorStore,
        llm_client: LLMClient,
        upgrade_engine: UpgradePathEngine
    ):
        self.db = db
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.upgrade_engine = upgrade_engine
    
    async def query(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Answer a natural language question.
        
        Args:
            question: User's question
            context: Optional filters (vendor, model, etc.)
            top_k: Number of relevant chunks to retrieve
            
        Returns:
            Dictionary with answer, facts used, and recommended actions
        """
        logger.info(f"Processing query: {question}")
        
        # Step 1: Quick database lookup for facts
        facts = await self._lookup_facts(question, context)
        logger.info(f"Found {len(facts)} facts from database")
        
        # Step 2: Vector search for relevant chunks
        try:
            search_results = await self.vector_store.search(question, k=top_k)
            logger.info(f"Found {len(search_results)} relevant chunks")
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            search_results = []
        
        # Step 3: Get chunk details
        context_chunks = await self._get_chunk_details(search_results)
        
        # Step 4: Call LLM to generate answer
        try:
            answer = await self.llm_client.answer_question(question, facts, context_chunks)
        except Exception as e:
            logger.error(f"LLM answer generation failed: {e}")
            answer = {
                'answer_text': f"Error generating answer: {str(e)}",
                'facts_used': [],
                'references': [],
                'recommended_actions': [],
                'confidence': 0.0
            }
        
        # Step 5: Identify potential upgrade paths
        upgrade_paths = await self._identify_upgrade_paths(facts, answer)
        
        return {
            'answer_text': answer.get('answer_text', ''),
            'facts_used': answer.get('facts_used', []),
            'references': answer.get('references', []),
            'recommended_actions': answer.get('recommended_actions', []),
            'upgrade_paths': upgrade_paths,
            'confidence': answer.get('confidence', 0.0)
        }
    
    async def _lookup_facts(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Lookup relevant facts from database"""
        facts = []
        
        # Extract keywords from question
        question_lower = question.lower()
        
        # Search for models
        model_query = select(Model)
        if context and context.get('vendor'):
            model_query = model_query.where(Model.vendor == context['vendor'])
        
        result = await self.db.execute(model_query.limit(20))
        models = result.scalars().all()
        
        for model in models:
            # Check if model is mentioned in question
            if model.model_name.lower() in question_lower:
                # Get versions for this model
                version_result = await self.db.execute(
                    select(SoftwareVersion)
                    .where(SoftwareVersion.model_id == model.id)
                )
                versions = version_result.scalars().all()
                
                facts.append({
                    'type': 'model',
                    'id': model.id,
                    'vendor': model.vendor,
                    'model_name': model.model_name,
                    'product_family': model.product_family,
                    'versions': [
                        {
                            'id': v.id,
                            'version_string': v.version_string,
                            'eol_status': v.eol_status,
                            'eol_date': str(v.eol_date) if v.eol_date else None
                        }
                        for v in versions
                    ]
                })
        
        # Search for EOL status if mentioned
        if 'eol' in question_lower or 'end of life' in question_lower:
            result = await self.db.execute(
                select(SoftwareVersion)
                .where(SoftwareVersion.eol_status == 'EOL')
                .limit(10)
            )
            eol_versions = result.scalars().all()
            
            for version in eol_versions:
                facts.append({
                    'type': 'version',
                    'id': version.id,
                    'model_id': version.model_id,
                    'version_string': version.version_string,
                    'eol_status': version.eol_status,
                    'eol_date': str(version.eol_date) if version.eol_date else None
                })
        
        return facts
    
    async def _get_chunk_details(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get full chunk details from database"""
        chunks = []
        
        for result in search_results:
            chunk_id = result['chunk_id']
            
            chunk_result = await self.db.execute(
                select(PDFChunk).where(PDFChunk.chunk_id == chunk_id)
            )
            chunk = chunk_result.scalar_one_or_none()
            
            if chunk:
                chunks.append({
                    'chunk_id': chunk.chunk_id,
                    'text': chunk.text,
                    'pdf_path': chunk.pdf_path,
                    'page_range': chunk.page_range,
                    'score': result.get('score', 0.0)
                })
        
        return chunks
    
    async def _identify_upgrade_paths(
        self,
        facts: List[Dict[str, Any]],
        answer: Dict[str, Any]
    ) -> List[UpgradePathResponse]:
        """Identify potential upgrade paths based on facts and answer"""
        upgrade_paths = []
        
        # Look for models with EOL versions that have supported versions
        model_facts = [f for f in facts if f.get('type') == 'model']
        
        for model_fact in model_facts:
            versions = model_fact.get('versions', [])
            eol_versions = [v for v in versions if v['eol_status'] == 'EOL']
            supported_versions = [v for v in versions if v['eol_status'] == 'SUPPORTED']
            
            if eol_versions and supported_versions:
                # Suggest upgrading from EOL to latest supported
                latest_supported = supported_versions[-1]  # Assume sorted
                
                for eol_version in eol_versions[:1]:  # Just first one
                    try:
                        path = await self.upgrade_engine.compute_upgrade_path(
                            self.db,
                            model_fact['id'],
                            eol_version['id'],
                            latest_supported['id']
                        )
                        
                        if path:
                            upgrade_paths.append(self._format_upgrade_path(path))
                    except Exception as e:
                        logger.error(f"Failed to compute upgrade path: {e}")
        
        return upgrade_paths[:3]  # Return max 3 paths
    
    def _format_upgrade_path(self, path: Dict[str, Any]) -> UpgradePathResponse:
        """Format upgrade path for API response"""
        steps = []
        for step in path['steps']:
            steps.append(UpgradeStep(
                step=f"{step['from_version']} -> {step['to_version']}",
                notes=step.get('notes'),
                references=[],  # Would need to look up chunk references
                risk=step.get('risk_level', 'LOW'),
                requires_backup=step.get('requires_backup', True),
                requires_reboot=step.get('requires_reboot', True),
                estimated_downtime_minutes=step.get('estimated_downtime_minutes')
            ))
        
        return UpgradePathResponse(
            model_id=path['model_id'],
            from_version=path['steps'][0]['from_version'] if path['steps'] else '',
            to_version=path['steps'][-1]['to_version'] if path['steps'] else '',
            steps=steps,
            overall_risk=path['overall_risk'],
            total_estimated_downtime_minutes=path.get('total_estimated_downtime_minutes')
        )
