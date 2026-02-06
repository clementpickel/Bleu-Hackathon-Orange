"""LLM client abstraction with Grok and Mock implementations"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import httpx
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


# Prompt templates
EXTRACTION_SYSTEM_PROMPT = """You are a precise extraction assistant. Input: a single chunk of a release note. Output: a JSON object with keys:
vendor, product_family, model, model_aliases, software_version, eol_status ("EOL"/"SUPPORTED"/"UNKNOWN"),
eol_date (YYYY-MM-DD or null), replacement_models (array), compatible_versions (array),
upgrade_instructions (string), notes (string), source_chunk_id.

RULES:
* Use only information present in the chunk. If unsure, set fields to null or "UNKNOWN".
* Provide 'evidence' arrays with the exact substring(s) from the chunk used to decide each field.
* OUTPUT: JSON only, no explanation."""


QUERY_ANSWERING_SYSTEM_PROMPT = """You are a technical support assistant specializing in router/gateway release notes analysis.

Given:
1. A user's natural language question
2. Structured facts from a database (models, versions, EOL status, compatibility rules)
3. Relevant text chunks from release note PDFs

Your task:
- Provide a clear, accurate answer to the question
- Cite specific facts and chunk IDs that support your answer
- If the question is about upgrade paths, identify the models and versions involved
- If information is incomplete, clearly state what is known vs unknown
- Recommend actions when appropriate (e.g., "upgrade to version X", "replace with model Y")

OUTPUT: JSON with keys:
- answer_text (string): Complete answer in natural language
- facts_used (array of integers): IDs of facts referenced
- references (array of strings): Chunk IDs cited
- recommended_actions (array of objects): Each with keys: action (string), reason (string), priority (LOW/MED/HIGH)
- confidence (0.0-1.0): Your confidence in the answer"""


class LLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    async def extract_structured_facts(
        self,
        text: str,
        chunk_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured facts from a text chunk.
        
        Args:
            text: The text chunk to analyze
            chunk_id: Unique identifier for the chunk
            metadata: Optional metadata about the chunk
            
        Returns:
            Dictionary with extracted facts and confidence score
        """
        pass
    
    @abstractmethod
    async def answer_question(
        self,
        question: str,
        facts: List[Dict[str, Any]],
        context_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Answer a question using provided facts and context.
        
        Args:
            question: Natural language question
            facts: List of structured facts from database
            context_chunks: List of relevant text chunks
            
        Returns:
            Dictionary with answer, references, and recommended actions
        """
        pass


class GrokClient(LLMClient):
    """Grok API client implementation"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.grok_api_key
        self.api_url = api_url or settings.grok_api_url
        self.model = model or settings.grok_model
        
        if not self.api_key:
            logger.warning("Grok API key not configured")
    
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Make API call to Grok"""
        if not self.api_key:
            raise ValueError("Grok API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        
        except Exception as e:
            logger.error(f"Grok API call failed: {e}")
            raise
    
    async def extract_structured_facts(
        self,
        text: str,
        chunk_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract facts using Grok API"""
        
        user_message = f"""Chunk ID: {chunk_id}

Text:
{text}

Extract structured information and output JSON only."""
        
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response_text = await self._call_api(messages, temperature=0.1)
            
            # Parse JSON response
            # Clean up markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            extracted = json.loads(response_text.strip())
            
            # Add chunk_id if not present
            if "source_chunk_id" not in extracted or not extracted["source_chunk_id"]:
                extracted["source_chunk_id"] = chunk_id
            
            # Calculate confidence based on evidence
            confidence = self._calculate_confidence(extracted)
            
            return {
                "extracted_data": extracted,
                "confidence": confidence,
                "method": "llm"
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Grok response: {e}")
            return {
                "extracted_data": {},
                "confidence": 0.0,
                "method": "llm",
                "error": f"JSON parse error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                "extracted_data": {},
                "confidence": 0.0,
                "method": "llm",
                "error": str(e)
            }
    
    def _calculate_confidence(self, extracted: Dict[str, Any]) -> float:
        """Calculate confidence score based on extracted data"""
        score = 0.5  # Base score
        
        # Increase confidence if evidence is provided
        if "evidence" in extracted and extracted["evidence"]:
            score += 0.2
        
        # Key fields present
        key_fields = ["vendor", "model", "software_version", "eol_status"]
        present = sum(1 for f in key_fields if extracted.get(f))
        score += (present / len(key_fields)) * 0.3
        
        return min(score, 1.0)
    
    async def answer_question(
        self,
        question: str,
        facts: List[Dict[str, Any]],
        context_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Answer question using Grok API"""
        
        # Format facts and chunks
        facts_text = json.dumps(facts, indent=2)
        chunks_text = "\n\n---\n\n".join([
            f"[Chunk {c['chunk_id']}]\n{c['text'][:500]}..."
            for c in context_chunks[:5]
        ])
        
        user_message = f"""Question: {question}

Available Facts:
{facts_text}

Relevant Release Note Excerpts:
{chunks_text}

Provide a comprehensive answer in JSON format."""
        
        messages = [
            {"role": "system", "content": QUERY_ANSWERING_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response_text = await self._call_api(messages, temperature=0.2, max_tokens=1500)
            
            # Parse JSON response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            answer = json.loads(response_text.strip())
            return answer
        
        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return {
                "answer_text": f"Error generating answer: {str(e)}",
                "facts_used": [],
                "references": [],
                "recommended_actions": [],
                "confidence": 0.0
            }


class OpenAIClient(LLMClient):
    """OpenAI API client implementation"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.openai_api_key
        self.api_url = api_url or settings.openai_api_url
        self.model = model or settings.openai_model
        
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
    
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Make API call to OpenAI"""
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    async def extract_structured_facts(
        self,
        text: str,
        chunk_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract facts using OpenAI API"""
        
        user_message = f"""Chunk ID: {chunk_id}

Text:
{text}

Extract structured information and output JSON only."""
        
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response_text = await self._call_api(messages, temperature=0.1)
            
            # Parse JSON response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            extracted = json.loads(response_text.strip())
            
            # Add chunk_id if not present
            if "source_chunk_id" not in extracted or not extracted["source_chunk_id"]:
                extracted["source_chunk_id"] = chunk_id
            
            # Calculate confidence based on evidence
            confidence = self._calculate_confidence(extracted)
            
            return {
                "extracted_data": extracted,
                "confidence": confidence,
                "method": "llm"
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI response: {e}")
            return {
                "extracted_data": {},
                "confidence": 0.0,
                "method": "llm",
                "error": f"JSON parse error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                "extracted_data": {},
                "confidence": 0.0,
                "method": "llm",
                "error": str(e)
            }
    
    def _calculate_confidence(self, extracted: Dict[str, Any]) -> float:
        """Calculate confidence score based on extracted data"""
        score = 0.5  # Base score
        
        # Increase confidence if evidence is provided
        if "evidence" in extracted and extracted["evidence"]:
            score += 0.2
        
        # Key fields present
        key_fields = ["vendor", "model", "software_version", "eol_status"]
        present = sum(1 for f in key_fields if extracted.get(f))
        score += (present / len(key_fields)) * 0.3
        
        return min(score, 1.0)
    
    async def answer_question(
        self,
        question: str,
        facts: List[Dict[str, Any]],
        context_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Answer question using OpenAI API"""
        
        # Format facts and chunks
        facts_text = json.dumps(facts, indent=2)
        chunks_text = "\n\n---\n\n".join([
            f"[Chunk {c['chunk_id']}]\n{c['text'][:500]}..."
            for c in context_chunks[:5]
        ])
        
        user_message = f"""Question: {question}

Available Facts:
{facts_text}

Relevant Release Note Excerpts:
{chunks_text}

Provide a comprehensive answer in JSON format."""
        
        messages = [
            {"role": "system", "content": QUERY_ANSWERING_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response_text = await self._call_api(messages, temperature=0.2, max_tokens=1500)
            
            # Parse JSON response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            answer = json.loads(response_text.strip())
            return answer
        
        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return {
                "answer_text": f"Error generating answer: {str(e)}",
                "facts_used": [],
                "references": [],
                "recommended_actions": [],
                "confidence": 0.0
            }


class MockLLMClient(LLMClient):
    """Mock LLM client for testing"""
    
    def __init__(self):
        self.call_count = 0
    
    async def extract_structured_facts(
        self,
        text: str,
        chunk_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Return deterministic mock extraction"""
        self.call_count += 1
        
        # Simple heuristics for testing
        vendor = "TestVendor" if "vendor" in text.lower() else None
        model = "TestModel-100" if "model" in text.lower() else None
        eol_status = "EOL" if "end of life" in text.lower() or "eol" in text.lower() else "UNKNOWN"
        
        extracted = {
            "vendor": vendor,
            "product_family": "Test Family",
            "model": model,
            "model_aliases": [],
            "software_version": "1.0.0" if "version" in text.lower() else None,
            "eol_status": eol_status,
            "eol_date": "2024-12-31" if eol_status == "EOL" else None,
            "replacement_models": ["TestModel-200"] if eol_status == "EOL" else [],
            "compatible_versions": ["1.0.0", "1.1.0"],
            "upgrade_instructions": "Standard upgrade procedure",
            "notes": "Mock extraction",
            "source_chunk_id": chunk_id,
            "evidence": {
                "eol_status": ["end of life"] if eol_status == "EOL" else []
            }
        }
        
        return {
            "extracted_data": extracted,
            "confidence": 0.8,
            "method": "llm"
        }
    
    async def answer_question(
        self,
        question: str,
        facts: List[Dict[str, Any]],
        context_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Return deterministic mock answer"""
        self.call_count += 1
        
        return {
            "answer_text": f"Mock answer to: {question}. Based on {len(facts)} facts and {len(context_chunks)} chunks.",
            "facts_used": [f.get("id", 0) for f in facts[:3]],
            "references": [c.get("chunk_id", "") for c in context_chunks[:3]],
            "recommended_actions": [
                {
                    "action": "Review the release notes",
                    "reason": "To understand the full context",
                    "priority": "MED"
                }
            ],
            "confidence": 0.7
        }


def get_llm_client(provider: Optional[str] = None, use_mock: bool = False) -> LLMClient:
    """Factory function to get appropriate LLM client
    
    Args:
        provider: LLM provider to use ('grok', 'openai', or 'mock'). 
                 If None, uses settings.llm_provider
        use_mock: If True, returns MockLLMClient regardless of provider setting
    
    Returns:
        LLMClient instance
    """
    if use_mock:
        logger.info("Using MockLLMClient (explicitly requested)")
        return MockLLMClient()
    
    # Determine provider
    provider = provider or settings.llm_provider
    
    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured, falling back to MockLLMClient")
            return MockLLMClient()
        logger.info("Using OpenAIClient")
        return OpenAIClient()
    
    elif provider == "grok":
        if not settings.grok_api_key:
            logger.warning("Grok API key not configured, falling back to MockLLMClient")
            return MockLLMClient()
        logger.info("Using GrokClient")
        return GrokClient()
    
    elif provider == "mock":
        logger.info("Using MockLLMClient (configured provider)")
        return MockLLMClient()
    
    else:
        logger.warning(f"Unknown provider '{provider}', falling back to MockLLMClient")
        return MockLLMClient()
