"""PDF loading and text extraction"""
import os
from pathlib import Path
from typing import List, Dict, Any
import fitz  # PyMuPDF
import logging

logger = logging.getLogger(__name__)


class PDFDocument:
    """Represents a loaded PDF document"""
    
    def __init__(self, path: str, text: str, pages: int, metadata: Dict[str, Any]):
        self.path = path
        self.text = text
        self.pages = pages
        self.metadata = metadata


class PDFLoader:
    """Load and extract text from PDF files"""
    
    def __init__(self, assets_path: str = "assets"):
        self.assets_path = Path(assets_path)
    
    def find_pdfs(self) -> List[Path]:
        """Recursively find all PDF files in assets directory"""
        if not self.assets_path.exists():
            logger.warning(f"Assets path does not exist: {self.assets_path}")
            return []
        
        pdf_files = list(self.assets_path.rglob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files in {self.assets_path}")
        return pdf_files
    
    def extract_text_from_pdf(self, pdf_path: Path) -> PDFDocument:
        """
        Extract text from a single PDF file using PyMuPDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            PDFDocument with extracted text and metadata
        """
        try:
            # Convert Path to string explicitly for Docker compatibility
            doc = fitz.open(str(pdf_path))
            full_text = ""
            page_texts = []
            
            # Get total pages before iterating
            total_pages = len(doc)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                page_text = page.get_text("text")
                page_texts.append(page_text)
                full_text += page_text + "\n"
            
            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
                "modification_date": doc.metadata.get("modDate", ""),
                "page_texts": page_texts,  # Store per-page text for chunking
            }
            
            doc.close()
            
            logger.info(f"Extracted text from {pdf_path.name}: {total_pages} pages, {len(full_text)} characters")
            
            return PDFDocument(
                path=str(pdf_path),
                text=full_text,
                pages=len(page_texts),
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            raise
    
    def load_all_pdfs(self) -> List[PDFDocument]:
        """Load and extract text from all PDFs in assets directory"""
        pdf_files = self.find_pdfs()
        documents = []
        
        for pdf_file in pdf_files:
            try:
                doc = self.extract_text_from_pdf(pdf_file)
                documents.append(doc)
            except Exception as e:
                logger.error(f"Failed to load {pdf_file}: {e}")
                continue
        
        logger.info(f"Successfully loaded {len(documents)} out of {len(pdf_files)} PDF files")
        return documents
