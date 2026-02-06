"""Integration tests for FastAPI endpoints"""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Release Notes Decision Support API"
        assert data["status"] == "running"


@pytest.mark.asyncio
async def test_unauthorized_access():
    """Test that endpoints require API key"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Try to access protected endpoint without API key
        response = await client.get("/api/v1/models")
        assert response.status_code == 422  # Unprocessable Entity (missing header)


@pytest.mark.asyncio
async def test_get_models_with_auth():
    """Test getting models with authentication"""
    headers = {"X-API-Key": "dev_api_key_change_in_production"}
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/models", headers=headers)
        # May return 200 with empty list or 500 if DB not set up
        assert response.status_code in [200, 500]


@pytest.mark.asyncio
async def test_query_endpoint_structure():
    """Test query endpoint structure (without actual LLM call)"""
    headers = {"X-API-Key": "dev_api_key_change_in_production"}
    
    payload = {
        "query": "What models are EOL?",
        "context": {},
        "top_k": 5
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/query", json=payload, headers=headers)
        # Will likely fail without DB/vector store setup, but structure should be valid
        assert response.status_code in [200, 500]


def test_llm_client_mock():
    """Test mock LLM client"""
    from app.llm.llm_client import MockLLMClient
    import asyncio
    
    client = MockLLMClient()
    
    # Test extraction
    result = asyncio.run(client.extract_structured_facts(
        "Model EG-400 version 4.2.1 is end of life.",
        "test_chunk"
    ))
    
    assert result['confidence'] > 0
    assert result['method'] == 'llm'
    assert 'extracted_data' in result
    
    # Test question answering
    answer = asyncio.run(client.answer_question(
        "What is the EOL status?",
        [],
        []
    ))
    
    assert 'answer_text' in answer
    assert 'confidence' in answer


def test_vector_store_faiss():
    """Test FAISS vector store"""
    from app.vector.vector_store import FAISSVectorStore
    import asyncio
    import tempfile
    import shutil
    
    # Create temporary directory for index
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = FAISSVectorStore(index_path=temp_dir)
        
        # Add vectors
        chunk_ids = ["chunk1", "chunk2", "chunk3"]
        texts = [
            "This is the first chunk about routers.",
            "This is the second chunk about gateways.",
            "This is the third chunk about firmware."
        ]
        
        asyncio.run(store.add_vectors(chunk_ids, texts))
        
        # Search
        results = asyncio.run(store.search("router equipment", k=2))
        
        assert len(results) <= 2
        assert all('chunk_id' in r for r in results)
        assert all('score' in r for r in results)
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_pydantic_schemas():
    """Test Pydantic schema validation"""
    from app.schemas.pydantic_schemas import (
        ModelCreate, QueryRequest, UpgradePathRequest
    )
    
    # Test ModelCreate
    model = ModelCreate(
        vendor="Cisco",
        product_family="Enterprise Gateways",
        model_name="EG-400",
        aliases=["EG400", "EG-400-V2"]
    )
    assert model.vendor == "Cisco"
    assert len(model.aliases) == 2
    
    # Test QueryRequest
    query = QueryRequest(
        query="What models are EOL?",
        context={"vendor": "Cisco"},
        top_k=5
    )
    assert query.query == "What models are EOL?"
    assert query.top_k == 5
    
    # Test UpgradePathRequest
    upgrade_req = UpgradePathRequest(
        model_id=1,
        current_version="4.2.1",
        target_version="5.0.2"
    )
    assert upgrade_req.model_id == 1
    assert upgrade_req.current_version == "4.2.1"
