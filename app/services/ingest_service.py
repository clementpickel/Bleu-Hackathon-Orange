"""Ingestion service for processing PDFs"""
import time
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.ingestion.pdf_loader import PDFLoader
from app.ingestion.chunker import PDFChunker
from app.ingestion.extractor import HybridExtractor
from app.db.models import PDFChunk, Extraction, Model, SoftwareVersion
from app.vector.vector_store import VectorStore
from app.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting and processing PDFs"""
    
    def __init__(
        self,
        db: AsyncSession,
        vector_store: VectorStore,
        llm_client: LLMClient,
        assets_path: str = "assets"
    ):
        self.db = db
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.assets_path = assets_path
        
        self.pdf_loader = PDFLoader(assets_path)
        self.chunker = PDFChunker()
        self.extractor = HybridExtractor(llm_client, use_llm=True)
    
    async def ingest_all_pdfs(self) -> Dict[str, Any]:
        """
        Load all PDFs, chunk, extract, and store in DB and vector store.
        
        Returns:
            Summary dictionary with statistics and warnings
        """
        start_time = time.time()
        
        summary = {
            'files_parsed': 0,
            'chunks_created': 0,
            'extractions_count': 0,
            'models_created': 0,
            'versions_created': 0,
            'warnings': []
        }
        
        # Step 1: Load PDFs
        logger.info(f"Loading PDFs from {self.assets_path}")
        pdf_documents = self.pdf_loader.load_all_pdfs()
        summary['files_parsed'] = len(pdf_documents)
        
        if not pdf_documents:
            summary['warnings'].append(f"No PDFs found in {self.assets_path}")
            summary['duration_seconds'] = time.time() - start_time
            return summary
        
        all_chunks = []
        
        # Step 2: Chunk documents
        logger.info("Chunking documents")
        for pdf_doc in pdf_documents:
            try:
                chunks = self.chunker.chunk_document(pdf_doc)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"Failed to chunk {pdf_doc.path}: {e}")
                summary['warnings'].append(f"Chunking failed for {pdf_doc.path}: {str(e)}")
        
        summary['chunks_created'] = len(all_chunks)
        logger.info(f"Created {len(all_chunks)} chunks")
        
        # Step 3: Store chunks in database
        logger.info("Storing chunks in database")
        for chunk in all_chunks:
            try:
                # Check if chunk already exists
                result = await self.db.execute(
                    select(PDFChunk).where(PDFChunk.chunk_id == chunk.chunk_id)
                )
                existing = result.scalar_one_or_none()
                
                if not existing:
                    db_chunk = PDFChunk(
                        chunk_id=chunk.chunk_id,
                        pdf_path=chunk.pdf_path,
                        page_range=chunk.page_range,
                        text=chunk.text
                    )
                    self.db.add(db_chunk)
            except Exception as e:
                logger.error(f"Failed to store chunk {chunk.chunk_id}: {e}")
                summary['warnings'].append(f"Failed to store chunk: {str(e)}")
        
        await self.db.commit()
        
        # Step 4: Extract facts from chunks
        logger.info("Extracting facts from chunks")
        for i, chunk in enumerate(all_chunks):
            try:
                if i % 10 == 0:
                    logger.info(f"Processing chunk {i+1}/{len(all_chunks)}")
                
                extraction_result = await self.extractor.extract(chunk.text, chunk.chunk_id)
                
                # Store extraction
                db_extraction = Extraction(
                    chunk_id=chunk.chunk_id,
                    extracted_json=extraction_result['extracted_data'],
                    confidence=extraction_result['confidence'],
                    method=extraction_result['method']
                )
                self.db.add(db_extraction)
                summary['extractions_count'] += 1
                
                # Store structured data (models and versions)
                await self._store_structured_data(extraction_result['extracted_data'])
                
            except Exception as e:
                logger.error(f"Failed to extract from chunk {chunk.chunk_id}: {e}")
                summary['warnings'].append(f"Extraction failed for chunk: {str(e)}")
        
        await self.db.commit()
        
        # Step 5: Add chunks to vector store
        logger.info("Adding chunks to vector store")
        try:
            chunk_ids = [c.chunk_id for c in all_chunks]
            texts = [c.text for c in all_chunks]
            metadata = [{'pdf_path': c.pdf_path, 'page_range': c.page_range} for c in all_chunks]
            
            await self.vector_store.add_vectors(chunk_ids, texts, metadata)
        except Exception as e:
            logger.error(f"Failed to add to vector store: {e}")
            summary['warnings'].append(f"Vector store indexing failed: {str(e)}")
        
        # Count models and versions created
        result = await self.db.execute(select(Model))
        summary['models_created'] = len(result.scalars().all())
        
        result = await self.db.execute(select(SoftwareVersion))
        summary['versions_created'] = len(result.scalars().all())
        
        summary['duration_seconds'] = time.time() - start_time
        
        logger.info(f"Ingestion complete: {summary}")
        return summary
    
    async def _store_structured_data(self, extracted_data: Dict[str, Any]) -> None:
        """Store extracted models and versions in database"""
        vendor = extracted_data.get('vendor')
        model_name = extracted_data.get('model')
        
        # Skip if essential fields are missing
        if not model_name or not vendor:
            return  # Skip if no model or vendor identified
        
        # Find or create model
        result = await self.db.execute(
            select(Model).where(
                Model.vendor == vendor,
                Model.model_name == model_name
            )
        )
        model = result.scalar_one_or_none()
        
        if not model:
            model = Model(
                vendor=vendor,
                product_family=extracted_data.get('product_family'),
                model_name=model_name,
                aliases=extracted_data.get('model_aliases', [])
            )
            self.db.add(model)
            await self.db.flush()  # Get model.id
        
        # Store version if present
        version_string = extracted_data.get('software_version')
        if version_string:
            result = await self.db.execute(
                select(SoftwareVersion).where(
                    SoftwareVersion.model_id == model.id,
                    SoftwareVersion.version_string == version_string
                )
            )
            version = result.scalar_one_or_none()
            
            if not version:
                from app.ingestion.normalizer import Normalizer
                normalizer = Normalizer()
                
                version = SoftwareVersion(
                    model_id=model.id,
                    version_string=version_string,
                    normalized_version=normalizer.normalize_version_string(version_string),
                    eol_status=extracted_data.get('eol_status', 'UNKNOWN'),
                    eol_date=normalizer.parse_date(extracted_data.get('eol_date')),
                    notes=extracted_data.get('notes')
                )
                self.db.add(version)
    
    async def reindex_vectors(self) -> Dict[str, Any]:
        """Reindex all chunks in vector store"""
        start_time = time.time()
        
        # Clear existing index
        await self.vector_store.delete_all()
        
        # Get all chunks from database
        result = await self.db.execute(select(PDFChunk))
        chunks = result.scalars().all()
        
        if not chunks:
            return {
                'chunks_reindexed': 0,
                'duration_seconds': time.time() - start_time
            }
        
        # Add to vector store
        chunk_ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]
        metadata = [{'pdf_path': c.pdf_path, 'page_range': c.page_range} for c in chunks]
        
        await self.vector_store.add_vectors(chunk_ids, texts, metadata)
        
        return {
            'chunks_reindexed': len(chunks),
            'duration_seconds': time.time() - start_time
        }
