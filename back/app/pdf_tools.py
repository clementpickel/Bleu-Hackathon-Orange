"""PDF Tools for LLM Function Calling"""
from typing import List, Dict, Any, Optional
import os
import pypdf
from sqlalchemy.orm import Session
from app.models import GatewayVersion, EdgeVersion, OrchestratorVersion


# Function definitions for LLM tool calling
PDF_RETRIEVAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_available_pdfs",
            "description": "List all available PDF documents that contain version information for gateway, edge, or orchestrator components. Returns metadata about each PDF including the filename, component type, and versions covered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_type": {
                        "type": "string",
                        "enum": ["gateway", "edge", "orchestrator", "all"],
                        "description": "Filter PDFs by component type. Use 'all' to get all PDFs."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pdf_content",
            "description": "Retrieve the full text content of a specific PDF document. Use this to get detailed information about upgrade instructions, prerequisites, or compatibility details for a specific version.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_filename": {
                        "type": "string",
                        "description": "The filename of the PDF to retrieve (e.g., 'release_notes_v5.4.pdf')"
                    },
                    "page_range": {
                        "type": "string",
                        "description": "Optional: specific page range to extract (e.g., '10-15' for pages 10 to 15, or '5' for page 5 only). Omit to get full document."
                    }
                },
                "required": ["pdf_filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_pdf_for_version",
            "description": "Search for specific version information across all PDFs. Returns relevant excerpts and the source PDF filename.",
            "parameters": {
                "type": "object",
                "properties": {
                    "version_number": {
                        "type": "string",
                        "description": "The version number to search for (e.g., '5.4.0' or '6.2')"
                    },
                    "component_type": {
                        "type": "string",
                        "enum": ["gateway", "edge", "orchestrator", "all"],
                        "description": "Component type to narrow the search. Defaults to 'all' if not specified."
                    },
                    "search_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Additional keywords to search for (e.g., ['upgrade', 'prerequisites', 'compatibility']). Can be omitted or empty."
                    }
                },
                "required": ["version_number"]
            }
        }
    }
]


def list_available_pdfs(component_type: str = "all", db: Session = None) -> Dict[str, Any]:
    """List all available PDFs with metadata"""
    assets_dir = "/app/assets"
    pdf_files = []
    
    if not os.path.exists(assets_dir):
        return {"pdfs": [], "total": 0, "error": "Assets directory not found"}
    
    # Map source files from database to component types
    pdf_metadata = {}
    
    if db:
        # Get all versions with source files
        for Model in [GatewayVersion, EdgeVersion, OrchestratorVersion]:
            comp_type = Model.__tablename__.replace('_versions', '')
            versions = db.query(Model).filter(Model.source_file.isnot(None)).all()
            
            for ver in versions:
                filename = ver.source_file
                if filename not in pdf_metadata:
                    pdf_metadata[filename] = {
                        "filename": filename,
                        "component_types": [],
                        "versions": [],
                        "dates": set()
                    }
                
                if comp_type not in pdf_metadata[filename]["component_types"]:
                    pdf_metadata[filename]["component_types"].append(comp_type)
                
                pdf_metadata[filename]["versions"].append({
                    "version": ver.version,
                    "component": comp_type,
                    "is_eol": ver.is_end_of_life,
                    "eol_date": ver.end_of_life_date
                })
                
                if ver.document_date:
                    pdf_metadata[filename]["dates"].add(ver.document_date)
    
    # List actual PDF files
    for root, dirs, files in os.walk(assets_dir):
        for file in files:
            if file.endswith('.pdf'):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, assets_dir)
                
                # Get metadata if available
                metadata = pdf_metadata.get(file, {
                    "filename": file,
                    "component_types": ["unknown"],
                    "versions": [],
                    "dates": set()
                })
                
                # Filter by component type
                if component_type != "all":
                    if component_type not in metadata.get("component_types", []):
                        continue
                
                pdf_files.append({
                    "filename": file,
                    "relative_path": relative_path,
                    "component_types": metadata.get("component_types", []),
                    "versions_count": len(metadata.get("versions", [])),
                    "sample_versions": [v["version"] for v in metadata.get("versions", [])][:5],
                    "document_dates": list(metadata.get("dates", [])),
                    "file_size_kb": round(os.path.getsize(full_path) / 1024, 2)
                })
    
    return {
        "pdfs": pdf_files,
        "total": len(pdf_files),
        "filter": component_type
    }


def get_pdf_content(pdf_filename: str, page_range: str = "all") -> Dict[str, Any]:
    """Get full or partial content of a PDF"""
    assets_dir = "/app/assets"
    
    # Find the PDF file
    pdf_path = None
    for root, dirs, files in os.walk(assets_dir):
        if pdf_filename in files:
            pdf_path = os.path.join(root, pdf_filename)
            break
    
    if not pdf_path or not os.path.exists(pdf_path):
        return {
            "error": f"PDF file '{pdf_filename}' not found",
            "available_pdfs": [f for f in os.listdir(assets_dir) if f.endswith('.pdf')]
        }
    
    try:
        content = ""
        total_pages = 0
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            # Parse page range
            if page_range == "all":
                pages_to_read = range(total_pages)
            else:
                try:
                    if '-' in page_range:
                        start, end = map(int, page_range.split('-'))
                        pages_to_read = range(max(0, start-1), min(total_pages, end))
                    else:
                        page_num = int(page_range) - 1
                        pages_to_read = [page_num] if 0 <= page_num < total_pages else []
                except:
                    pages_to_read = range(total_pages)
            
            # Extract text
            for page_num in pages_to_read:
                try:
                    page = pdf_reader.pages[page_num]
                    content += f"\n--- Page {page_num + 1} ---\n"
                    content += page.extract_text()
                except Exception as e:
                    content += f"\n[Error reading page {page_num + 1}: {str(e)}]\n"
        
        return {
            "filename": pdf_filename,
            "total_pages": total_pages,
            "pages_read": len(list(pages_to_read)) if isinstance(pages_to_read, range) else len(pages_to_read),
            "page_range": page_range,
            "content": content,
            "content_length": len(content)
        }
        
    except Exception as e:
        return {
            "error": f"Error reading PDF: {str(e)}",
            "filename": pdf_filename
        }


def search_pdf_for_version(
    version_number: str,
    component_type: str = "all",
    search_terms: List[str] = None,
    db: Session = None
) -> Dict[str, Any]:
    """Search for version information across PDFs"""
    search_terms = search_terms or []
    results = []
    
    # Get list of PDFs to search
    pdf_list = list_available_pdfs(component_type, db)
    
    for pdf_info in pdf_list["pdfs"]:
        # Quick check from metadata
        if version_number in [v for v in pdf_info.get("sample_versions", [])]:
            # Get full content and search
            content_result = get_pdf_content(pdf_info["filename"])
            
            if "error" not in content_result:
                content = content_result["content"]
                
                # Search for version and terms
                relevant_sections = []
                lines = content.split('\n')
                
                for i, line in enumerate(lines):
                    if version_number in line:
                        # Get context (5 lines before and after)
                        start = max(0, i - 5)
                        end = min(len(lines), i + 6)
                        context = '\n'.join(lines[start:end])
                        
                        # Check if search terms present
                        if not search_terms or any(term.lower() in context.lower() for term in search_terms):
                            relevant_sections.append({
                                "line_number": i + 1,
                                "context": context,
                                "matches_terms": [term for term in search_terms if term.lower() in context.lower()]
                            })
                
                if relevant_sections:
                    results.append({
                        "filename": pdf_info["filename"],
                        "component_types": pdf_info["component_types"],
                        "matches_count": len(relevant_sections),
                        "excerpts": relevant_sections[:3]  # Limit to top 3 excerpts per PDF
                    })
    
    return {
        "version": version_number,
        "component_type": component_type,
        "search_terms": search_terms,
        "results": results,
        "total_pdfs_searched": len(pdf_list["pdfs"]),
        "pdfs_with_matches": len(results)
    }


def execute_pdf_tool(tool_name: str, arguments: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
    """Execute a PDF tool function"""
    
    # Clean up arguments: remove empty arrays and None values
    cleaned_args = {k: v for k, v in arguments.items() if v is not None and v != [] and v != ""}
    
    if tool_name == "list_available_pdfs":
        return list_available_pdfs(
            component_type=cleaned_args.get("component_type", "all"),
            db=db
        )
    
    elif tool_name == "get_pdf_content":
        return get_pdf_content(
            pdf_filename=cleaned_args["pdf_filename"],
            page_range=cleaned_args.get("page_range", "all")
        )
    
    elif tool_name == "search_pdf_for_version":
        return search_pdf_for_version(
            version_number=cleaned_args["version_number"],
            component_type=cleaned_args.get("component_type", "all"),
            search_terms=cleaned_args.get("search_terms"),
            db=db
        )
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}
