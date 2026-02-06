# API Usage Examples

This document provides comprehensive examples for using the Release Notes Decision Support API.

## Authentication

All API requests require the `X-API-Key` header:

```bash
export API_KEY="dev_api_key_change_in_production"
```

## 1. Health Check

Check if the API is running:

```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "healthy"}
```

## 2. Ingest PDFs

Process all PDF files in the `assets/` directory:

```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "X-API-Key: $API_KEY"
```

Expected response:
```json
{
  "files_parsed": 5,
  "chunks_created": 234,
  "extractions_count": 234,
  "models_created": 12,
  "versions_created": 48,
  "warnings": [],
  "duration_seconds": 145.7
}
```

## 3. List All Models

Get all hardware models in the database:

```bash
curl -X GET "http://localhost:8000/api/v1/models" \
  -H "X-API-Key: $API_KEY"
```

With vendor filter:

```bash
curl -X GET "http://localhost:8000/api/v1/models?vendor=Cisco" \
  -H "X-API-Key: $API_KEY"
```

Response:
```json
[
  {
    "id": 1,
    "vendor": "Cisco",
    "product_family": "SD-WAN",
    "model_name": "vEdge-1000",
    "aliases": ["vEdge1000", "vEdge-1K"],
    "created_at": "2026-02-06T10:30:00Z",
    "updated_at": null
  },
  {
    "id": 2,
    "vendor": "Cisco",
    "product_family": "SD-WAN",
    "model_name": "vEdge-2000",
    "aliases": [],
    "created_at": "2026-02-06T10:30:15Z",
    "updated_at": null
  }
]
```

## 4. Get Model Lifecycle Details

Get complete lifecycle information for a specific model:

```bash
curl -X GET "http://localhost:8000/api/v1/model/1" \
  -H "X-API-Key: $API_KEY"
```

Response:
```json
{
  "model_id": 1,
  "vendor": "Cisco",
  "model_name": "vEdge-1000",
  "eol_status": "EOL",
  "eol_date": "2024-12-31",
  "recommended_replacements": ["vEdge-2000"],
  "versions": [
    {
      "version": "17.2.10",
      "eol_status": "EOL",
      "eol_date": "2024-06-30",
      "release_date": "2020-03-15"
    },
    {
      "version": "17.3.5",
      "eol_status": "EOL",
      "eol_date": "2024-12-31",
      "release_date": "2021-05-20"
    },
    {
      "version": "20.5.1",
      "eol_status": "SUPPORTED",
      "eol_date": null,
      "release_date": "2023-11-10"
    }
  ]
}
```

## 5. Natural Language Query

Ask questions about the release notes:

### Example 1: EOL Status

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which Cisco vEdge models are end of life?",
    "context": {"vendor": "Cisco"},
    "top_k": 5
  }'
```

Response:
```json
{
  "answer_text": "Based on the release notes, the Cisco vEdge-1000 has reached end of life as of December 31, 2024. All versions prior to 20.x are no longer supported. Users should migrate to vEdge-2000 or upgrade to version 20.5.1 or later.",
  "facts_used": [1, 2, 5],
  "references": [
    "chunk:assets/cisco/vedge_eol_notice.pdf::pages(1-2)::a1b2c3",
    "chunk:assets/cisco/vedge_migration_guide.pdf::pages(3-4)::d4e5f6"
  ],
  "recommended_actions": [
    {
      "action": "Upgrade to version 20.5.1",
      "reason": "Current supported version with latest security patches",
      "priority": "HIGH"
    },
    {
      "action": "Plan migration to vEdge-2000",
      "reason": "vEdge-1000 hardware is EOL",
      "priority": "MED"
    }
  ],
  "upgrade_paths": [],
  "confidence": 0.89
}
```

### Example 2: Version Compatibility

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can I upgrade directly from version 17.2.10 to 20.5.1?",
    "context": {},
    "top_k": 5
  }'
```

Response:
```json
{
  "answer_text": "Direct upgrade from 17.2.10 to 20.5.1 is not supported. You must first upgrade to intermediate version 17.3.5, then to 18.4.x, before upgrading to 20.5.1. This ensures proper configuration migration and prevents data loss.",
  "facts_used": [6, 8, 9],
  "references": [
    "chunk:assets/cisco/upgrade_guide_v20.pdf::pages(5-7)::g7h8i9"
  ],
  "recommended_actions": [
    {
      "action": "Follow multi-step upgrade path",
      "reason": "Direct upgrade not supported; requires intermediate versions",
      "priority": "HIGH"
    },
    {
      "action": "Backup configuration before upgrade",
      "reason": "Major version upgrade with potential breaking changes",
      "priority": "HIGH"
    }
  ],
  "upgrade_paths": [
    {
      "model_id": 1,
      "from_version": "17.2.10",
      "to_version": "20.5.1",
      "steps": [
        {
          "step": "17.2.10 -> 17.3.5",
          "notes": "Apply critical patches",
          "references": [],
          "risk": "LOW",
          "requires_backup": true,
          "requires_reboot": true,
          "estimated_downtime_minutes": 20
        },
        {
          "step": "17.3.5 -> 18.4.6",
          "notes": "Intermediate version required",
          "references": [],
          "risk": "MED",
          "requires_backup": true,
          "requires_reboot": true,
          "estimated_downtime_minutes": 30
        },
        {
          "step": "18.4.6 -> 20.5.1",
          "notes": "Major version upgrade",
          "references": [],
          "risk": "HIGH",
          "requires_backup": true,
          "requires_reboot": true,
          "estimated_downtime_minutes": 60
        }
      ],
      "overall_risk": "HIGH",
      "total_estimated_downtime_minutes": 110
    }
  ],
  "confidence": 0.92
}
```

### Example 3: Feature Inquiry

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What new features are in version 20.5.1?",
    "context": {},
    "top_k": 3
  }'
```

## 6. Compute Upgrade Path

Get deterministic upgrade path with detailed steps:

```bash
curl -X POST "http://localhost:8000/api/v1/upgrade-path" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": 1,
    "current_version": "17.2.10",
    "target_version": "20.5.1"
  }'
```

Response:
```json
{
  "model_id": 1,
  "from_version": "17.2.10",
  "to_version": "20.5.1",
  "steps": [
    {
      "step": "17.2.10 -> 17.3.5",
      "notes": "Apply security patches and bug fixes. No configuration changes required.",
      "references": [
        "chunk:assets/cisco/release_notes_17_3.pdf::pages(2-3)::j1k2l3"
      ],
      "risk": "LOW",
      "requires_backup": true,
      "requires_reboot": true,
      "estimated_downtime_minutes": 20
    },
    {
      "step": "17.3.5 -> 18.4.6",
      "notes": "Intermediate version required for configuration schema migration. Review deprecated features list.",
      "references": [
        "chunk:assets/cisco/release_notes_18_4.pdf::pages(1-2)::m4n5o6"
      ],
      "risk": "MED",
      "requires_backup": true,
      "requires_reboot": true,
      "estimated_downtime_minutes": 30
    },
    {
      "step": "18.4.6 -> 20.5.1",
      "notes": "Major version upgrade. New TLS requirements. Update CLI syntax for policy configurations. Test in lab environment first.",
      "references": [
        "chunk:assets/cisco/release_notes_20_5.pdf::pages(5-8)::p7q8r9",
        "chunk:assets/cisco/upgrade_guide_v20.pdf::pages(10-15)::s1t2u3"
      ],
      "risk": "HIGH",
      "requires_backup": true,
      "requires_reboot": true,
      "estimated_downtime_minutes": 60
    }
  ],
  "overall_risk": "HIGH",
  "total_estimated_downtime_minutes": 110
}
```

## 7. Get Chunk Details

Retrieve raw PDF chunk and extraction results:

```bash
curl -X GET "http://localhost:8000/api/v1/chunks/chunk:assets/cisco/vedge_eol_notice.pdf::pages(1-2)::a1b2c3" \
  -H "X-API-Key: $API_KEY"
```

Response:
```json
{
  "chunk_id": "chunk:assets/cisco/vedge_eol_notice.pdf::pages(1-2)::a1b2c3",
  "pdf_path": "assets/cisco/vedge_eol_notice.pdf",
  "page_range": "1-2",
  "text": "CISCO VEDGE-1000 END OF LIFE ANNOUNCEMENT\n\nEffective Date: December 31, 2024\n\nCisco announces the end of life for the vEdge-1000 platform and all associated software versions prior to release 20.x...",
  "inserted_at": "2026-02-06T10:35:22Z",
  "extractions": [
    {
      "id": 1,
      "chunk_id": "chunk:assets/cisco/vedge_eol_notice.pdf::pages(1-2)::a1b2c3",
      "extracted_json": {
        "vendor": "Cisco",
        "model": "vEdge-1000",
        "eol_status": "EOL",
        "eol_date": "2024-12-31",
        "replacement_models": ["vEdge-2000"],
        "notes": "Platform end of life announcement"
      },
      "confidence": 0.95,
      "method": "hybrid",
      "timestamp": "2026-02-06T10:35:30Z"
    }
  ]
}
```

## 8. Reindex Vector Store

Rebuild the vector search index (useful after changing embedding model):

```bash
curl -X POST "http://localhost:8000/api/v1/reindex" \
  -H "X-API-Key: $API_KEY"
```

Response:
```json
{
  "chunks_reindexed": 234,
  "duration_seconds": 42.3
}
```

## Error Handling

### 401 Unauthorized

```json
{
  "detail": "Invalid API key"
}
```

Fix: Check that `X-API-Key` header matches the configured `API_KEY` in `.env`

### 404 Not Found

```json
{
  "detail": "Model not found"
}
```

Fix: Verify the model ID or version exists in the database

### 500 Internal Server Error

```json
{
  "detail": "Ingestion failed: No PDFs found in assets/"
}
```

Fix: Ensure PDF files exist in `assets/` directory

## Python Client Example

```python
import httpx
import asyncio

class ReleaseNotesClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    async def query(self, question: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/query",
                headers=self.headers,
                json={"query": question, "top_k": 5}
            )
            return response.json()
    
    async def get_upgrade_path(self, model_id: int, from_ver: str, to_ver: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/upgrade-path",
                headers=self.headers,
                json={
                    "model_id": model_id,
                    "current_version": from_ver,
                    "target_version": to_ver
                }
            )
            return response.json()

# Usage
async def main():
    client = ReleaseNotesClient(
        "http://localhost:8000",
        "dev_api_key_change_in_production"
    )
    
    result = await client.query("Which models are EOL?")
    print(result["answer_text"])
    
    path = await client.get_upgrade_path(1, "17.2.10", "20.5.1")
    print(f"Upgrade requires {len(path['steps'])} steps")
    print(f"Total downtime: {path['total_estimated_downtime_minutes']} minutes")

asyncio.run(main())
```

## Batch Operations Example

Process multiple queries:

```bash
#!/bin/bash

API_KEY="dev_api_key_change_in_production"
BASE_URL="http://localhost:8000/api/v1"

# Array of queries
queries=(
  "Which models are EOL?"
  "What is the latest version for vEdge-1000?"
  "Can I upgrade from 17.2 to 20.5?"
  "What are the security fixes in version 20.5.1?"
)

# Process each query
for query in "${queries[@]}"; do
  echo "Query: $query"
  curl -X POST "$BASE_URL/query" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$query\", \"top_k\": 3}" \
    -s | jq '.answer_text'
  echo "---"
done
```

## Monitoring & Debugging

### Check API Health

```bash
watch -n 5 'curl -s http://localhost:8000/health | jq'
```

### View Ingestion Status

```bash
# Trigger ingestion and save output
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "X-API-Key: $API_KEY" \
  | jq '.' | tee ingestion_result.json

# Check for warnings
jq '.warnings' ingestion_result.json
```

### Test Vector Search

```bash
# Query with different k values to test relevance
for k in 1 3 5 10; do
  echo "Top $k results:"
  curl -X POST "http://localhost:8000/api/v1/query" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"EOL versions\", \"top_k\": $k}" \
    -s | jq '.references | length'
done
```
