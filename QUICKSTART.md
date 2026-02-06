# Quick Start Guide

Get the Release Notes Decision Support System running in under 5 minutes.

## Prerequisites

- Docker Desktop installed and running
- Git (optional, if cloning repo)

## Step 1: Clone or Download

```bash
git clone <repository-url>
cd Bleu-Hackathon-Orange
```

## Step 2: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env to configure your LLM provider
# Choose one: Grok, OpenAI, or Mock
```

### Option A: Use Grok (X.AI)

```bash
# Edit .env
LLM_PROVIDER=grok
GROK_API_KEY=your_grok_key_here
```

### Option B: Use OpenAI

```bash
# Edit .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-your_key_here
OPENAI_MODEL=gpt-4-turbo-preview  # or gpt-3.5-turbo for lower cost
```

### Option C: Use Mock (Testing)

```bash
# Edit .env
LLM_PROVIDER=mock
# No API key needed - uses deterministic test responses
```

## Step 3: Start Services

```bash
# Start PostgreSQL and the API
docker-compose up -d

# Wait 10 seconds for services to be ready
```

You should see:
```
✓ Container release_notes_db    Started
✓ Container release_notes_api   Started
```

## Step 4: Verify Installation

```bash
# Check API is running
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

Visit http://localhost:8000/docs for interactive API documentation.

## Step 5: Add Sample Data (Optional)

Create a test PDF or add your own release notes:

```bash
# Create sample directory
mkdir -p assets/test

# Add your PDF files to assets/test/
# Or download sample PDFs
```

## Step 6: Run Ingestion

```bash
# Process all PDFs in assets/
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "X-API-Key: dev_api_key_change_in_production"
```

This will:
- Parse all PDFs in `assets/`
- Extract facts using hybrid pipeline
- Build vector index for search
- Store everything in PostgreSQL

## Step 7: Query the System

Try a natural language query:

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "X-API-Key: dev_api_key_change_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which models are end of life?",
    "top_k": 5
  }'
```

## Common Commands

### View Logs
```bash
docker-compose logs -f api
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Clean Everything (including database)
```bash
docker-compose down -v
```

### Run Tests
```bash
# Install Python dependencies first
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

## Next Steps

1. **Add Real PDFs**: Place your vendor release notes in `assets/`
2. **Configure LLM**: Add `GROK_API_KEY` to `.env` for production use
3. **Explore API**: Visit http://localhost:8000/docs
4. **Read Examples**: Check `EXAMPLES.md` for detailed API usage
5. **Customize**: Modify extraction patterns in `app/ingestion/extractor.py`

## Troubleshooting

### Port 8000 already in use

```bash
# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

### Docker Build Fails

```bash
# Pull latest image
docker-compose pull

# Rebuild without cache
docker-compose build --no-cache
```

### Database Connection Error

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View database logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### No PDFs Found

Make sure PDFs are in the correct location:
```bash
ls -la assets/
```

The `assets/` directory should be at the project root level.

## Production Deployment

For production deployment:

1. **Update API Key**: Change `API_KEY` in `.env`
2. **Set Secure Database Password**: Update `POSTGRES_PASSWORD`
3. **Add Grok API Key**: Set `GROK_API_KEY` for LLM features
4. **Disable Debug Mode**: Set `DEBUG=False`
5. **Use HTTPS**: Set up reverse proxy (nginx/Traefik)
6. **Enable Monitoring**: Add logging and metrics
7. **Backup Strategy**: Schedule database backups

See `README.md` for detailed production setup.

## Getting Help

- **Documentation**: Read `README.md` for comprehensive guide
- **Examples**: See `EXAMPLES.md` for API usage examples
- **Issues**: Check logs with `docker-compose logs`
- **Tests**: Run `pytest -v` to verify functionality

## Summary

You now have a running instance of the Release Notes Decision Support API! 

**API Docs**: http://localhost:8000/docs  
**Health Check**: http://localhost:8000/health

Start by ingesting some PDFs, then query the system using natural language.
