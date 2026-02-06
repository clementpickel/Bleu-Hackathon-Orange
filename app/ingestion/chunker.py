"""Text chunking logic for semantic segmentation"""
import re
import hashlib
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TextChunk:
    """Represents a chunk of text from a PDF"""
    
    def __init__(
        self,
        chunk_id: str,
        pdf_path: str,
        text: str,
        page_range: str,
        metadata: Dict[str, Any] = None
    ):
        self.chunk_id = chunk_id
        self.pdf_path = pdf_path
        self.text = text
        self.page_range = page_range
        self.metadata = metadata or {}


class PDFChunker:
    """Chunk PDF text into semantically meaningful segments"""
    
    # Keywords that indicate important sections
    SECTION_KEYWORDS = [
        "end of life", "eol", "deprecated", "discontinu",
        "compatib", "upgrade", "migration", "support",
        "release note", "version", "firmware", "software"
    ]
    
    def __init__(
        self,
        max_chunk_size: int = 1500,
        min_chunk_size: int = 200,
        overlap: int = 100
    ):
        """
        Args:
            max_chunk_size: Maximum characters per chunk
            min_chunk_size: Minimum characters per chunk (avoid tiny fragments)
            overlap: Overlap between chunks in characters
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap = overlap
    
    def generate_chunk_id(self, pdf_path: str, page_range: str, text_snippet: str) -> str:
        """Generate deterministic chunk ID"""
        # Use path, page range, and first 100 chars for uniqueness
        unique_str = f"{pdf_path}::{page_range}::{text_snippet[:100]}"
        hash_obj = hashlib.sha256(unique_str.encode())
        return f"chunk:{pdf_path}::pages({page_range})::{hash_obj.hexdigest()[:12]}"
    
    def split_by_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        # Split on double newlines or multiple spaces
        paragraphs = re.split(r'\n\s*\n|\n{2,}', text)
        # Clean up whitespace
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        return paragraphs
    
    def is_section_header(self, text: str) -> bool:
        """Check if text is likely a section header"""
        text_lower = text.lower()
        
        # Check for keywords
        for keyword in self.SECTION_KEYWORDS:
            if keyword in text_lower:
                return True
        
        # Short lines with capital letters (likely headers)
        if len(text) < 100 and text.isupper():
            return True
        
        # Lines starting with numbers (e.g., "1. Introduction")
        if re.match(r'^\d+\.?\s+[A-Z]', text):
            return True
        
        return False
    
    def chunk_by_sections(self, text: str, page_texts: List[str]) -> List[Dict[str, Any]]:
        """
        Chunk text by semantic sections, preferring to split at headers.
        
        Args:
            text: Full document text
            page_texts: List of per-page texts for page range tracking
            
        Returns:
            List of chunk dictionaries with text and page_range
        """
        paragraphs = self.split_by_paragraphs(text)
        chunks = []
        current_chunk = []
        current_size = 0
        start_page = 0
        current_page = 0
        
        # Track character position to determine page boundaries
        char_position = 0
        page_boundaries = []
        cumulative = 0
        for i, page_text in enumerate(page_texts):
            cumulative += len(page_text)
            page_boundaries.append(cumulative)
        
        def get_page_for_position(pos: int) -> int:
            """Get page number for character position"""
            for i, boundary in enumerate(page_boundaries):
                if pos < boundary:
                    return i + 1
            return len(page_boundaries)
        
        for para in paragraphs:
            para_len = len(para)
            is_header = self.is_section_header(para)
            
            # Update page tracking
            current_page = get_page_for_position(char_position)
            
            # If adding this paragraph exceeds max size, save current chunk
            if current_size + para_len > self.max_chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                if len(chunk_text) >= self.min_chunk_size:
                    end_page = get_page_for_position(char_position)
                    page_range = f"{start_page}-{end_page}" if start_page != end_page else str(start_page)
                    chunks.append({
                        "text": chunk_text,
                        "page_range": page_range,
                        "start_char": char_position - current_size,
                        "end_char": char_position
                    })
                
                # Start new chunk, possibly with overlap
                if self.overlap > 0 and current_chunk:
                    # Keep last paragraph for overlap
                    overlap_text = current_chunk[-1]
                    current_chunk = [overlap_text, para]
                    current_size = len(overlap_text) + para_len
                    start_page = get_page_for_position(char_position - len(overlap_text))
                else:
                    current_chunk = [para]
                    current_size = para_len
                    start_page = current_page
            else:
                current_chunk.append(para)
                current_size += para_len
            
            char_position += para_len + 2  # +2 for paragraph separator
        
        # Add final chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size:
                end_page = get_page_for_position(char_position)
                page_range = f"{start_page}-{end_page}" if start_page != end_page else str(start_page)
                chunks.append({
                    "text": chunk_text,
                    "page_range": page_range,
                    "start_char": char_position - current_size,
                    "end_char": char_position
                })
        
        return chunks
    
    def chunk_document(self, pdf_document) -> List[TextChunk]:
        """
        Chunk a PDFDocument into TextChunks.
        
        Args:
            pdf_document: PDFDocument instance
            
        Returns:
            List of TextChunk objects
        """
        page_texts = pdf_document.metadata.get("page_texts", [])
        
        if not page_texts:
            # Fallback: treat as single page
            page_texts = [pdf_document.text]
        
        chunk_dicts = self.chunk_by_sections(pdf_document.text, page_texts)
        
        text_chunks = []
        for chunk_dict in chunk_dicts:
            chunk_id = self.generate_chunk_id(
                pdf_document.path,
                chunk_dict["page_range"],
                chunk_dict["text"][:100]
            )
            
            text_chunk = TextChunk(
                chunk_id=chunk_id,
                pdf_path=pdf_document.path,
                text=chunk_dict["text"],
                page_range=chunk_dict["page_range"],
                metadata={
                    "start_char": chunk_dict["start_char"],
                    "end_char": chunk_dict["end_char"],
                    "doc_metadata": pdf_document.metadata
                }
            )
            text_chunks.append(text_chunk)
        
        logger.info(f"Created {len(text_chunks)} chunks from {pdf_document.path}")
        return text_chunks
