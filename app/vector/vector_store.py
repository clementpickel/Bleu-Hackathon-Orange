"""Vector store abstraction with FAISS and Qdrant implementations"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pickle
import os
from pathlib import Path
import logging
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector stores"""
    
    @abstractmethod
    async def add_vectors(
        self,
        chunk_ids: List[str],
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add vectors to the store"""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_text: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Returns:
            List of dictionaries with keys: chunk_id, score, metadata
        """
        pass
    
    @abstractmethod
    async def delete_all(self) -> None:
        """Delete all vectors from the store"""
        pass


class EmbeddingModel:
    """Wrapper for embedding model"""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.embedding_model
        logger.info(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.dimension = settings.embedding_dimension
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts"""
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return np.array(embeddings)
    
    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.embed([text])[0]


class FAISSVectorStore(VectorStore):
    """FAISS-based vector store for local deployment"""
    
    def __init__(self, index_path: str = None):
        self.index_path = Path(index_path or settings.faiss_index_path)
        self.index_path.mkdir(exist_ok=True)
        
        self.index_file = self.index_path / "index.faiss"
        self.metadata_file = self.index_path / "metadata.pkl"
        
        self.embedding_model = EmbeddingModel()
        self.dimension = self.embedding_model.dimension
        
        self.index = None
        self.chunk_ids: List[str] = []
        self.metadata: List[Dict[str, Any]] = []
        
        # Try to load existing index
        self._load_index()
    
    def _load_index(self) -> None:
        """Load existing FAISS index from disk"""
        if self.index_file.exists() and self.metadata_file.exists():
            try:
                import faiss
                self.index = faiss.read_index(str(self.index_file))
                
                with open(self.metadata_file, 'rb') as f:
                    data = pickle.load(f)
                    self.chunk_ids = data['chunk_ids']
                    self.metadata = data['metadata']
                
                logger.info(f"Loaded FAISS index with {len(self.chunk_ids)} vectors")
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}. Starting fresh.")
                self.index = None
    
    def _save_index(self) -> None:
        """Save FAISS index to disk"""
        import faiss
        faiss.write_index(self.index, str(self.index_file))
        
        with open(self.metadata_file, 'wb') as f:
            pickle.dump({
                'chunk_ids': self.chunk_ids,
                'metadata': self.metadata
            }, f)
        
        logger.info(f"Saved FAISS index with {len(self.chunk_ids)} vectors")
    
    async def add_vectors(
        self,
        chunk_ids: List[str],
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add vectors to FAISS index"""
        import faiss
        
        if not texts:
            return
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} texts")
        embeddings = self.embedding_model.embed(texts)
        
        # Initialize index if needed
        if self.index is None:
            self.index = faiss.IndexFlatL2(self.dimension)
            logger.info(f"Created new FAISS index with dimension {self.dimension}")
        
        # Add to index
        self.index.add(embeddings.astype('float32'))
        self.chunk_ids.extend(chunk_ids)
        
        if metadata:
            self.metadata.extend(metadata)
        else:
            self.metadata.extend([{} for _ in chunk_ids])
        
        # Save to disk
        self._save_index()
        
        logger.info(f"Added {len(chunk_ids)} vectors to FAISS index")
    
    async def search(
        self,
        query_text: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search FAISS index for similar vectors"""
        if self.index is None or len(self.chunk_ids) == 0:
            logger.warning("FAISS index is empty")
            return []
        
        # Generate query embedding
        query_embedding = self.embedding_model.embed_single(query_text)
        
        # Search
        k = min(k, len(self.chunk_ids))
        distances, indices = self.index.search(
            query_embedding.astype('float32').reshape(1, -1),
            k
        )
        
        # Format results
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < len(self.chunk_ids):
                results.append({
                    'chunk_id': self.chunk_ids[idx],
                    'score': float(1.0 / (1.0 + dist)),  # Convert distance to similarity
                    'distance': float(dist),
                    'metadata': self.metadata[idx],
                    'rank': i + 1
                })
        
        return results
    
    async def delete_all(self) -> None:
        """Delete all vectors from FAISS index"""
        self.index = None
        self.chunk_ids = []
        self.metadata = []
        
        # Remove files
        if self.index_file.exists():
            self.index_file.unlink()
        if self.metadata_file.exists():
            self.metadata_file.unlink()
        
        logger.info("Deleted FAISS index")


class QdrantVectorStore(VectorStore):
    """Qdrant-based vector store for production deployment"""
    
    def __init__(self, collection_name: str = "release_notes"):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError:
            raise ImportError("qdrant-client not installed. Install with: pip install qdrant-client")
        
        self.collection_name = collection_name
        self.embedding_model = EmbeddingModel()
        self.dimension = self.embedding_model.dimension
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None
        )
        
        # Create collection if it doesn't exist
        try:
            self.client.get_collection(collection_name)
            logger.info(f"Connected to existing Qdrant collection: {collection_name}")
        except Exception:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE)
            )
            logger.info(f"Created new Qdrant collection: {collection_name}")
    
    async def add_vectors(
        self,
        chunk_ids: List[str],
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add vectors to Qdrant collection"""
        from qdrant_client.models import PointStruct
        
        if not texts:
            return
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} texts")
        embeddings = self.embedding_model.embed(texts)
        
        # Prepare points
        points = []
        for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
            point_metadata = metadata[i] if metadata else {}
            point_metadata['chunk_id'] = chunk_id
            
            points.append(PointStruct(
                id=hash(chunk_id) & 0x7FFFFFFFFFFFFFFF,  # Positive int64
                vector=embedding.tolist(),
                payload=point_metadata
            ))
        
        # Upload to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        logger.info(f"Added {len(chunk_ids)} vectors to Qdrant collection")
    
    async def search(
        self,
        query_text: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search Qdrant collection for similar vectors"""
        # Generate query embedding
        query_embedding = self.embedding_model.embed_single(query_text)
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding.tolist(),
            limit=k
        )
        
        # Format results
        formatted = []
        for i, result in enumerate(results):
            formatted.append({
                'chunk_id': result.payload.get('chunk_id'),
                'score': float(result.score),
                'metadata': {k: v for k, v in result.payload.items() if k != 'chunk_id'},
                'rank': i + 1
            })
        
        return formatted
    
    async def delete_all(self) -> None:
        """Delete all vectors from Qdrant collection"""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            logger.info(f"Deleted Qdrant collection: {self.collection_name}")
            
            # Recreate empty collection
            from qdrant_client.models import Distance, VectorParams
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE)
            )
        except Exception as e:
            logger.error(f"Failed to delete Qdrant collection: {e}")


def get_vector_store() -> VectorStore:
    """Factory function to get appropriate vector store"""
    if settings.vector_db == "qdrant":
        try:
            logger.info("Using Qdrant vector store")
            return QdrantVectorStore()
        except Exception as e:
            logger.warning(f"Failed to initialize Qdrant, falling back to FAISS: {e}")
            return FAISSVectorStore()
    else:
        logger.info("Using FAISS vector store")
        return FAISSVectorStore()
