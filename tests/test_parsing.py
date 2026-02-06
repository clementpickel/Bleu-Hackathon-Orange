"""Test PDF parsing and chunking"""
import pytest
from pathlib import Path
from app.ingestion.pdf_loader import PDFLoader, PDFDocument
from app.ingestion.chunker import PDFChunker


def test_pdf_loader_init():
    """Test PDFLoader initialization"""
    loader = PDFLoader("test_assets")
    assert loader.assets_path == Path("test_assets")


def test_chunker_init():
    """Test PDFChunker initialization"""
    chunker = PDFChunker(max_chunk_size=1000, min_chunk_size=100, overlap=50)
    assert chunker.max_chunk_size == 1000
    assert chunker.min_chunk_size == 100
    assert chunker.overlap == 50


def test_chunker_split_by_paragraphs():
    """Test paragraph splitting"""
    chunker = PDFChunker()
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    paragraphs = chunker.split_by_paragraphs(text)
    assert len(paragraphs) == 3
    assert paragraphs[0] == "First paragraph."


def test_chunker_is_section_header():
    """Test section header detection"""
    chunker = PDFChunker()
    
    # Test keywords
    assert chunker.is_section_header("END OF LIFE NOTICE")
    assert chunker.is_section_header("Compatibility Information")
    assert chunker.is_section_header("Upgrade Instructions")
    
    # Test numbered headers
    assert chunker.is_section_header("1. Introduction")
    assert chunker.is_section_header("2.1 Overview")
    
    # Not headers
    assert not chunker.is_section_header("This is a regular paragraph with no special formatting.")


def test_chunker_generate_chunk_id():
    """Test chunk ID generation is deterministic"""
    chunker = PDFChunker()
    
    chunk_id1 = chunker.generate_chunk_id("test.pdf", "1-3", "Sample text")
    chunk_id2 = chunker.generate_chunk_id("test.pdf", "1-3", "Sample text")
    
    assert chunk_id1 == chunk_id2
    assert "chunk:test.pdf::pages(1-3)" in chunk_id1


def test_chunker_chunk_document():
    """Test document chunking"""
    # Create mock PDFDocument
    text = """
    Release Notes for EG-400
    
    Version 4.2.1 is now end of life as of June 30, 2024.
    
    Users should upgrade to version 5.0.2 which is currently supported.
    
    Compatibility Information
    
    Version 4.2.1 is compatible with versions 4.2.0 and 4.2.2.
    Upgrading from 4.2.1 to 5.0.2 requires intermediate version 4.3.5.
    """
    
    pdf_doc = PDFDocument(
        path="test.pdf",
        text=text,
        pages=1,
        metadata={"page_texts": [text]}
    )
    
    chunker = PDFChunker(max_chunk_size=200, min_chunk_size=50)
    chunks = chunker.chunk_document(pdf_doc)
    
    assert len(chunks) > 0
    assert all(chunk.pdf_path == "test.pdf" for chunk in chunks)
    assert all(chunk.page_range for chunk in chunks)
    assert all(len(chunk.text) >= chunker.min_chunk_size or len(chunks) == 1 for chunk in chunks)


def test_heuristic_extractor():
    """Test heuristic extraction"""
    from app.ingestion.extractor import HeuristicExtractor
    
    extractor = HeuristicExtractor()
    
    # Test version extraction
    text = "Version 4.2.1 is now available. Users on v3.5 should upgrade."
    versions = extractor.extract_versions(text)
    assert "4.2.1" in versions
    assert "3.5" in versions
    
    # Test model extraction
    text = "The EG-400 and SD-WAN-500 models are affected."
    models = extractor.extract_models(text)
    assert len(models) >= 1
    
    # Test EOL detection
    text = "This version is end of life as of December 2024."
    assert extractor.is_eol_mentioned(text)
    
    # Test replacement extraction
    text = "Users should replace the old model with EG-500."
    replacements = extractor.extract_replacement_models(text)
    assert "EG-500" in replacements


def test_normalizer():
    """Test data normalization"""
    from app.ingestion.normalizer import Normalizer
    
    normalizer = Normalizer()
    
    # Test vendor normalization
    assert normalizer.normalize_vendor_name("cisco systems") == "Cisco"
    assert normalizer.normalize_vendor_name("CISCO") == "Cisco"
    
    # Test version normalization
    assert normalizer.normalize_version_string("v4.2.1") == "4.2.1"
    assert normalizer.normalize_version_string("Version 5.0") == "5.0.0"
    assert normalizer.normalize_version_string("Release 3.1.2") == "3.1.2"
    
    # Test date parsing
    assert normalizer.parse_date("2024-06-30") == "2024-06-30"
    assert normalizer.parse_date("June 30, 2024") == "2024-06-30"
    assert normalizer.parse_date("06/30/2024") == "2024-06-30"
    
    # Test EOL status normalization
    assert normalizer.normalize_eol_status("end of life") == "EOL"
    assert normalizer.normalize_eol_status("supported") == "SUPPORTED"
    assert normalizer.normalize_eol_status("unknown") == "UNKNOWN"
    
    # Test version comparison
    assert normalizer.compare_versions("1.0.0", "2.0.0") == -1
    assert normalizer.compare_versions("2.0.0", "1.0.0") == 1
    assert normalizer.compare_versions("1.0.0", "1.0.0") == 0


@pytest.mark.asyncio
async def test_hybrid_extractor_with_mock_llm():
    """Test hybrid extraction with mock LLM"""
    from app.ingestion.extractor import HybridExtractor
    from app.llm.llm_client import MockLLMClient
    
    llm_client = MockLLMClient()
    extractor = HybridExtractor(llm_client, use_llm=True)
    
    text = """
    Model EG-400 Version 4.2.1 End of Life Notice
    
    This version will reach end of life on June 30, 2024.
    Users should upgrade to version 5.0.2.
    """
    
    result = await extractor.extract(text, "test_chunk_1")
    
    assert result['extracted_data'] is not None
    assert result['confidence'] > 0
    assert result['method'] in ['regex', 'llm', 'hybrid']
