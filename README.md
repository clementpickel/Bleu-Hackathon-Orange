# Release Notes Decision Support System

Production-ready **Python FastAPI backend** for analyzing router/gateway/VCO release-note PDFs and providing intelligent decision support for operators regarding EOL status, upgrades, and compatibility.

## Features

- 📄 **PDF Ingestion**: Automatically parse and chunk PDF release notes from `assets/` directory
- 🤖 **Hybrid Extraction**: Combine regex/heuristics with LLM (Grok) for accurate fact extraction
- 🗄️ **PostgreSQL Database**: Store structured facts with full audit trail
- 🔍 **Vector Search**: Semantic search over release note chunks using FAISS or Qdrant
- 📊 **Compatibility Engine**: Deterministic graph-based upgrade path computation
- 🚀 **REST API**: Clean FastAPI endpoints for integration with dashboards
- 🧪 **Comprehensive Tests**: Unit and integration tests with >80% coverage

## Architecture

```
project/
├── app/
│   ├── main.py                    # FastAPI application
│   ├── api/routes.py              # API endpoints
│   ├── core/config.py             # Configuration management
│   ├── db/                        # SQLAlchemy models & session
│   ├── ingestion/                 # PDF loading, chunking, extraction
│   ├── vector/                    # Vector store abstraction
│   ├── llm/                       # LLM client (Grok + Mock)
│   ├── compatibility/             # Upgrade graph engine
│   ├── services/                  # Business logic
│   └── schemas/                   # Pydantic models
├── assets/                        # PDF release notes (add yours here)
├── tests/                         # Pytest test suite
├── alembic/                       # Database migrations
├── docker-compose.yml             # Docker services
└── requirements.txt               # Python dependencies
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ (included in Docker Compose)

### 1. Clone and Setup

```bash
git clone <your-repo>
cd Bleu-Hackathon-Orange

# Copy environment template
cp .env.example .env

# Edit .env with your settings
# IMPORTANT: Set your GROK_API_KEY for production use
```

### 2. Start Services with Docker Compose

```bash
# Start PostgreSQL and API
docker-compose up -d

# Check logs
docker-compose logs -f api
```

The API will be available at `http://localhost:8000`

- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 3. Run Database Migrations

```bash
# Migrations run automatically in Docker
# For manual migration:
docker-compose exec api alembic upgrade head
```

### 4. Add PDF Files

Place your release note PDFs in the `assets/` directory:

```bash
assets/
├── vendor_a/
│   ├── release_notes_v4.pdf
│   └── release_notes_v5.pdf
└── vendor_b/
    └── gateway_eol_notice.pdf
```

### 5. Ingest PDFs

```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "X-API-Key: dev_api_key_change_in_production"
```

Response:
```json
{
  "files_parsed": 3,
  "chunks_created": 145,
  "extractions_count": 145,
  "models_created": 8,
  "versions_created": 24,
  "warnings": [],
  "duration_seconds": 87.3
}
```

## API Usage

All endpoints require `X-API-Key` header for authentication.

### Get Models

```bash
curl -X GET "http://localhost:8000/api/v1/models" \
  -H "X-API-Key: dev_api_key_change_in_production"
```

Response:
```json
[
  {
    "id": 1,
    "vendor": "Acme",
    "product_family": "Enterprise Gateways",
    "model_name": "EG-400",
    "aliases": ["EG400"],
    "created_at": "2026-02-06T10:00:00Z",
    "updated_at": null
  }
]
```

### Get Model Lifecycle

```bash
curl -X GET "http://localhost:8000/api/v1/model/1" \
  -H "X-API-Key: dev_api_key_change_in_production"
```

Response:
```json
{
  "model_id": 42,
  "vendor": "Acme",
  "model_name": "EG-400",
  "eol_status": "EOL",
  "eol_date": "2024-06-30",
  "recommended_replacements": ["EG-500"],
  "versions": [
    {
      "version": "4.2.1",
      "eol_status": "EOL",
      "eol_date": "2024-06-30",
      "release_date": null
    },
    {
      "version": "5.0.2",
      "eol_status": "SUPPORTED",
      "release_date": "2025-01-15",
      "eol_date": null
    }
  ]
}
```

### Natural Language Query

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "X-API-Key: dev_api_key_change_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which EG-400 versions are end of life?",
    "context": {},
    "top_k": 5
  }'
```

Response:
```json
{
  "answer_text": "According to the release notes, EG-400 version 4.2.1 reached end of life on June 30, 2024. Users should upgrade to version 5.0.2 which is currently supported.",
  "facts_used": [1, 2],
  "references": ["chunk:assets/eg400_release.pdf::pages(3-4)::abc123"],
  "recommended_actions": [
    {
      "action": "Upgrade to version 5.0.2",
      "reason": "Version 4.2.1 is EOL and no longer supported",
      "priority": "HIGH"
    }
  ],
  "upgrade_paths": [],
  "confidence": 0.92
}
```

### Get Upgrade Path

```bash
curl -X POST "http://localhost:8000/api/v1/upgrade-path" \
  -H "X-API-Key: dev_api_key_change_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": 42,
    "current_version": "4.2.1",
    "target_version": "5.0.2"
  }'
```

Response:
```json
{
  "model_id": 42,
  "from_version": "4.2.1",
  "to_version": "5.0.2",
  "steps": [
    {
      "step": "4.2.1 -> 4.3.5",
      "notes": "Apply patch 4.3.5: hotfix for bootloader; must be installed first",
      "references": ["chunk:assets/release_notes/acme_eg/relnotes_v4_3.pdf::pages(3-4)::xyz789"],
      "risk": "MED",
      "requires_backup": true,
      "requires_reboot": true,
      "estimated_downtime_minutes": 30
    },
    {
      "step": "4.3.5 -> 5.0.2",
      "notes": "Major upgrade, requires full reconfiguration",
      "references": ["chunk:assets/release_notes/acme_eg/relnotes_v5.pdf::pages(7-9)::def456"],
      "risk": "HIGH",
      "requires_backup": true,
      "requires_reboot": true,
      "estimated_downtime_minutes": 120
    }
  ],
  "overall_risk": "HIGH",
  "total_estimated_downtime_minutes": 150
}
```

## Development

### Local Setup (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with local settings

# Start PostgreSQL (via Docker or local install)
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=dbuser \
  -e POSTGRES_PASSWORD=dbpass \
  -e POSTGRES_DB=release_notes_db \
  postgres:15-alpine

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_compatibility.py -v
```

### Using Qdrant Instead of FAISS

```bash
# Start with Qdrant profile
docker-compose --profile qdrant up -d

# Update .env
VECTOR_DB=qdrant
QDRANT_URL=http://localhost:6333

# Restart API
docker-compose restart api
```

## LLM Provider Configuration

The system uses an abstract `LLMClient` interface, making it easy to swap providers.

### Available Providers

The system supports multiple LLM providers out of the box:

#### 1. Grok (X.AI)

```bash
LLM_PROVIDER=grok
GROK_API_KEY=your_grok_key_here
GROK_API_URL=https://api.x.ai/v1
GROK_MODEL=grok-beta
```

#### 2. OpenAI

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key_here
OPENAI_API_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4-turbo-preview
```

Supported OpenAI models:
- `gpt-4-turbo-preview` - Best for complex extraction (recommended)
- `gpt-4` - Reliable, accurate results
- `gpt-3.5-turbo` - Faster, lower cost

#### 3. Mock (Testing)

```bash
LLM_PROVIDER=mock
```

Uses deterministic responses for testing without API calls.

### Switching Providers

To switch providers, simply update your `.env` file:

```bash
# Switch from Grok to OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...
```

Then restart the application:
```bash
docker-compose restart api
```

### Adding a New Provider (e.g., Claude, Gemini)

1. Create new client class in [app/llm/llm_client.py](app/llm/llm_client.py):

```python
class ClaudeClient(LLMClient):
    async def extract_structured_facts(self, text, chunk_id, metadata):
        # Claude-specific implementation
        pass
    
    async def answer_question(self, question, facts, context_chunks):
        # Claude-specific implementation
        pass
```

2. Update factory function:

```python
def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    provider = provider or settings.llm_provider
    if provider == "claude":
        return ClaudeClient()
    elif provider == "openai":
        return OpenAIClient()
    elif provider == "grok":
        return GrokClient()
    else:
        return MockLLMClient()
```

3. Add configuration in [app/core/config.py](app/core/config.py):

```python
claude_api_key: str = Field(default="", alias="CLAUDE_API_KEY")
claude_model: str = Field(default="claude-3-opus-20240229", alias="CLAUDE_MODEL"
```

## Key Design Decisions

### Hybrid Extraction Pipeline

- **Regex first**: Fast, deterministic extraction of version numbers, dates, models
- **LLM enrichment**: Contextual understanding, relationship extraction, ambiguity resolution
- **Confidence scoring**: Prefer high-confidence heuristics or LLM results
- **Provenance tracking**: Every fact links back to source PDF chunk with confidence

### Deterministic Compatibility Engine

- **Graph representation**: Versions as nodes, allowed upgrades as directed edges
- **Mandatory intermediates**: Some upgrades require stepping through specific versions
- **Risk levels**: LOW/MED/HIGH based on complexity and impact
- **Idempotent**: Same input always produces same output (no LLM in path computation)

### Vector Search Strategy

- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- **Local default**: FAISS for development and small deployments
- **Production option**: Qdrant for scalability and advanced features
- **Chunk strategy**: 800-1500 characters with 100-char overlap, split on semantic boundaries

## Database Schema

Key tables:

- `models`: Hardware models (vendor, model_name, aliases)
- `software_versions`: Software releases (version, EOL status, dates)
- `upgrade_paths`: Allowed upgrade routes with intermediates
- `model_version_compatibility`: Simple compatibility rules
- `pdf_chunks`: Indexed text segments from PDFs
- `extractions`: Raw LLM/heuristic outputs with provenance

## Configuration

All configuration via environment variables (`.env` file):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://dbuser:dbpass@localhost:5432/release_notes_db

# Vector Store
VECTOR_DB=faiss  # or 'qdrant'
QDRANT_URL=http://localhost:6333

# LLM
GROK_API_KEY=your_key
GROK_API_URL=https://api.x.ai/v1
LLM_MODEL=grok-beta

# Security
API_KEY=your_secure_key_here

# Application
DEBUG=False
LOG_LEVEL=INFO
ASSETS_PATH=assets
```

## Troubleshooting

### PDFs not found

- Ensure PDFs are in `assets/` directory
- Check file permissions (Docker needs read access)
- Verify path in `.env`: `ASSETS_PATH=assets`

### Database connection failed

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Manually test connection
docker-compose exec postgres psql -U dbuser -d release_notes_db
```

### Vector search not working

```bash
# Rebuild index
curl -X POST "http://localhost:8000/api/v1/reindex" \
  -H "X-API-Key: your_key"

# Check FAISS index files
ls -la faiss_index/
```

### LLM extraction failing

- Check `GROK_API_KEY` is set correctly
- System falls back to heuristics-only if LLM unavailable
- For testing, use `MockLLMClient` (automatic if no API key)

## Performance Considerations

- **Ingestion**: ~50-100 PDFs in 2-5 minutes (depends on LLM speed)
- **Query latency**: 200-500ms (vector search + DB lookup + LLM)
- **Vector search**: Sub-100ms for FAISS, ~50ms for Qdrant
- **Upgrade path**: <10ms (pure graph algorithm, no LLM)

## Security

- **API key authentication**: Required for all endpoints
- **SQL injection**: Prevented by SQLAlchemy parameterized queries
- **Input validation**: Pydantic schemas enforce type safety
- **Secrets management**: Never commit `.env` to git

**Production checklist**:
- [ ] Change default API key
- [ ] Use strong database password
- [ ] Enable HTTPS (reverse proxy)
- [ ] Rate limiting (nginx/CloudFlare)
- [ ] Monitor logs for suspicious activity

## License

See [LICENSE](LICENSE) file.

## Support

For issues or questions:
1. Check logs: `docker-compose logs api`
2. Review test suite: `pytest -v`
3. Open GitHub issue with:
   - Environment details
   - Error logs
   - Steps to reproduce

## Contributing

1. Run tests: `pytest`
2. Check code style: `black app/ tests/`
3. Update documentation
4. Submit pull request

---

**Built with**: FastAPI, PostgreSQL, SQLAlchemy, FAISS, NetworkX, PyMuPDF, Sentence Transformers

## Original Project

This project was created for: **Bleu-Hackathon-Orange - Projet 1 - SD-WAN Velocloud**
