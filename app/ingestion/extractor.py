"""Hybrid extraction pipeline combining regex and LLM"""
import re
from typing import Dict, Any, List, Optional
import logging
from app.ingestion.normalizer import Normalizer
from app.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class HeuristicExtractor:
    """Rule-based extraction using regex patterns"""
    
    # Regex patterns for extraction
    VERSION_PATTERN = re.compile(
        r'v?(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)',
        re.IGNORECASE
    )
    
    MODEL_PATTERN = re.compile(
        r'\b([A-Z]{2,4}[-\s]?\d{3,4}[A-Z]?)\b',  # e.g., EG-400, SD-WAN-500
        re.IGNORECASE
    )
    
    EOL_DATE_PATTERN = re.compile(
        r'(?:end of life|eol|discontinued|deprecated).*?(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\w+\s+\d{1,2},?\s+\d{4}|\w+\s+\d{4})',
        re.IGNORECASE | re.DOTALL
    )
    
    REPLACEMENT_PATTERN = re.compile(
        r'(?:replac(?:ed?|ement)|migrat(?:e|ion)|upgrad(?:e|ing))\s+(?:to|with|by)\s+([A-Z]{2,4}[-\s]?\d{3,4}[A-Z]?)',
        re.IGNORECASE
    )
    
    def extract_versions(self, text: str) -> List[str]:
        """Extract version numbers from text"""
        versions = self.VERSION_PATTERN.findall(text)
        return list(set(versions))  # Remove duplicates
    
    def extract_models(self, text: str) -> List[str]:
        """Extract model names from text"""
        models = self.MODEL_PATTERN.findall(text)
        return list(set(models))
    
    def extract_eol_date(self, text: str) -> Optional[str]:
        """Extract EOL date from text"""
        match = self.EOL_DATE_PATTERN.search(text)
        if match:
            return match.group(1)
        return None
    
    def extract_replacement_models(self, text: str) -> List[str]:
        """Extract replacement model names"""
        replacements = self.REPLACEMENT_PATTERN.findall(text)
        return list(set(replacements))
    
    def is_eol_mentioned(self, text: str) -> bool:
        """Check if EOL is mentioned in text"""
        eol_keywords = r'\b(end of life|eol|deprecated|discontinued|unsupported|obsolete)\b'
        return bool(re.search(eol_keywords, text, re.IGNORECASE))
    
    def extract_facts(self, text: str, chunk_id: str) -> Dict[str, Any]:
        """
        Extract facts using heuristics.
        
        Returns:
            Dictionary with extracted data and confidence
        """
        facts = {
            "vendor": None,
            "product_family": None,
            "model": None,
            "model_aliases": [],
            "software_version": None,
            "eol_status": "UNKNOWN",
            "eol_date": None,
            "replacement_models": [],
            "compatible_versions": [],
            "upgrade_instructions": None,
            "notes": None,
            "source_chunk_id": chunk_id,
            "evidence": {}
        }
        
        # Extract data
        versions = self.extract_versions(text)
        models = self.extract_models(text)
        eol_date = self.extract_eol_date(text)
        replacements = self.extract_replacement_models(text)
        is_eol = self.is_eol_mentioned(text)
        
        # Populate facts
        if versions:
            facts["software_version"] = versions[0]
            facts["compatible_versions"] = versions
            facts["evidence"]["software_version"] = versions
        
        if models:
            facts["model"] = models[0]
            if len(models) > 1:
                facts["model_aliases"] = models[1:]
            facts["evidence"]["model"] = models
        
        if eol_date:
            facts["eol_date"] = eol_date
            facts["evidence"]["eol_date"] = [eol_date]
        
        if replacements:
            facts["replacement_models"] = replacements
            facts["evidence"]["replacement_models"] = replacements
        
        if is_eol:
            facts["eol_status"] = "EOL"
            facts["evidence"]["eol_status"] = ["EOL keywords found"]
        
        # Calculate confidence based on extracted fields
        confidence = self._calculate_confidence(facts)
        
        return {
            "extracted_data": facts,
            "confidence": confidence,
            "method": "regex"
        }
    
    def _calculate_confidence(self, facts: Dict[str, Any]) -> float:
        """Calculate confidence score for heuristic extraction"""
        score = 0.0
        
        # Base score for each non-null field
        key_fields = ["model", "software_version", "eol_status", "eol_date"]
        for field in key_fields:
            if facts.get(field):
                score += 0.2
        
        # Evidence boosts confidence
        if facts.get("evidence"):
            score += 0.2
        
        return min(score, 0.9)  # Max 0.9 for heuristics (LLM can be higher)


class HybridExtractor:
    """Combine heuristic and LLM-based extraction"""
    
    def __init__(self, llm_client: LLMClient, use_llm: bool = True):
        """
        Args:
            llm_client: LLM client for extraction
            use_llm: Whether to use LLM (set False for faster testing)
        """
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.heuristic_extractor = HeuristicExtractor()
        self.normalizer = Normalizer()
        self.confidence_threshold = 0.6
    
    async def extract(self, text: str, chunk_id: str) -> Dict[str, Any]:
        """
        Run hybrid extraction pipeline.
        
        Args:
            text: Text chunk to process
            chunk_id: Unique chunk identifier
            
        Returns:
            Dictionary with merged extraction results
        """
        # Step 1: Heuristic extraction
        heuristic_result = self.heuristic_extractor.extract_facts(text, chunk_id)
        
        # Step 2: LLM extraction (if enabled and API available)
        llm_result = None
        if self.use_llm:
            try:
                llm_result = await self.llm_client.extract_structured_facts(text, chunk_id)
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}. Using heuristics only.")
        
        # Step 3: Merge results
        merged = self._merge_extractions(heuristic_result, llm_result)
        
        # Step 4: Normalize
        merged = self._normalize_extraction(merged)
        
        return merged
    
    def _merge_extractions(
        self,
        heuristic: Dict[str, Any],
        llm: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge heuristic and LLM extractions, preferring high-confidence sources.
        
        Strategy:
        - If LLM confidence > threshold and > heuristic, use LLM
        - Otherwise use heuristic
        - Merge evidence from both
        """
        if not llm:
            return heuristic
        
        h_data = heuristic["extracted_data"]
        h_conf = heuristic["confidence"]
        l_data = llm["extracted_data"]
        l_conf = llm["confidence"]
        
        merged_data = {}
        evidence = {}
        
        # Determine which source to trust for each field
        for field in h_data.keys():
            h_val = h_data.get(field)
            l_val = l_data.get(field)
            
            # Special handling for arrays and objects
            if field == "evidence":
                # Merge evidence from both
                h_ev = h_val or {}
                l_ev = l_val or {}
                evidence = {**h_ev, **l_ev}
                continue
            
            # Prefer LLM if high confidence
            if l_conf >= self.confidence_threshold and l_val:
                merged_data[field] = l_val
            elif h_val:
                merged_data[field] = h_val
            elif l_val:
                merged_data[field] = l_val
            else:
                merged_data[field] = None
        
        merged_data["evidence"] = evidence
        
        # Use max confidence
        confidence = max(h_conf, l_conf)
        
        # Method is hybrid if both were used
        method = "hybrid" if llm else "regex"
        
        return {
            "extracted_data": merged_data,
            "confidence": confidence,
            "method": method
        }
    
    def _normalize_extraction(self, extraction: Dict[str, Any]) -> Dict[str, Any]:
        """Apply normalization to extracted data"""
        data = extraction["extracted_data"]
        
        # Normalize vendor
        if data.get("vendor"):
            data["vendor"] = self.normalizer.normalize_vendor_name(data["vendor"])
        
        # Normalize model
        if data.get("model"):
            data["model"] = self.normalizer.normalize_model_name(data["model"])
        
        # Normalize version
        if data.get("software_version"):
            data["software_version"] = self.normalizer.normalize_version_string(data["software_version"])
        
        # Normalize compatible versions
        if data.get("compatible_versions"):
            data["compatible_versions"] = [
                self.normalizer.normalize_version_string(v)
                for v in data["compatible_versions"]
                if v
            ]
        
        # Normalize EOL date
        if data.get("eol_date"):
            data["eol_date"] = self.normalizer.parse_date(data["eol_date"])
        
        # Normalize EOL status
        if data.get("eol_status"):
            data["eol_status"] = self.normalizer.normalize_eol_status(data["eol_status"])
        
        extraction["extracted_data"] = data
        return extraction
