import os
from pypdf import PdfReader
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models import ProductModel, GatewayVersion, EdgeVersion
from app.llm_provider import get_llm_provider


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrait le texte d'un fichier PDF"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise Exception(f"Erreur lors de la lecture du PDF: {str(e)}")


def extract_gateway_edge_info(text: str, filename: str) -> Dict[str, Any]:
    """Extrait les informations de Gateway et Edge avec leurs versions et dates EOL"""
    provider = get_llm_provider()
    
    prompt = f"""
Analyse le texte suivant extrait d'un PDF sur des produits SD-WAN (VeloCloud/Arista) et extrait les informations au format JSON.

Le document peut contenir des informations sur:
- Des versions de logiciel Gateway
- Des modèles d'Edge (équipements physiques)
- Des dates de fin de vie (End of Life)
- Des dates de fin de support

Extrait les informations suivantes au format JSON:

{{
  "document_type": "gateway_version" | "edge_model" | "lifecycle" | "release_notes",
  "gateways": [
    {{
      "model": "VeloCloud Gateway",
      "version": "version du logiciel",
      "release_date": "date de release",
      "end_of_life_date": "date de fin de vie si mentionnée",
      "end_of_support_date": "date de fin de support si mentionnée",
      "is_end_of_life": true/false,
      "status": "Active|Deprecated|End of Life",
      "features": ["liste des fonctionnalités"],
      "notes": "notes importantes"
    }}
  ],
  "edges": [
    {{
      "model": "nom du modèle Edge (ex: Edge 510, Edge 840)",
      "version": "version firmware/software",
      "release_date": "date de release",
      "end_of_life_date": "date de fin de vie si mentionnée",
      "end_of_support_date": "date de fin de support si mentionnée",
      "is_end_of_life": true/false,
      "status": "Active|Deprecated|End of Life",
      "features": ["liste des fonctionnalités"],
      "hardware_specs": {{"specs matérielles si disponibles"}},
      "notes": "notes importantes"
    }}
  ],
  "general_info": {{
    "description": "résumé du document",
    "key_points": ["points importants"]
  }}
}}

Si une information n'est pas disponible, utilise null. Si le document ne contient pas de gateways ou edges, laisse les listes vides.

Nom du fichier: {filename}

Texte (premiers 6000 caractères):
{text[:6000]}

Réponds uniquement avec le JSON, sans texte additionnel.
"""
    
    return provider.extract_info(text, prompt)


def process_pdf_with_gateway_edge(pdf_path: str, filename: str, db: Session) -> Dict[str, Any]:
    """Traite un PDF et stocke les informations de Gateway et Edge dans la base de données"""
    # Extraire le texte
    text = extract_text_from_pdf(pdf_path)
    
    # Extraire les informations avec le LLM
    extracted_data = extract_gateway_edge_info(text, filename)
    
    results = {
        "gateways": [],
        "edges": [],
        "filename": filename
    }
    
    # Traiter les Gateways
    gateways = extracted_data.get("gateways", [])
    for gw in gateways:
        gateway = GatewayVersion(
            gateway_model=gw.get("model", "Unknown"),
            version=gw.get("version") or "Unknown",
            release_date=gw.get("release_date"),
            end_of_life_date=gw.get("end_of_life_date"),
            end_of_support_date=gw.get("end_of_support_date"),
            is_end_of_life=gw.get("is_end_of_life", False),
            status=gw.get("status"),
            features=gw.get("features"),
            notes=gw.get("notes"),
            source_file=filename,
            raw_data=gw
        )
        db.add(gateway)
        results["gateways"].append(gateway)
    
    # Traiter les Edges
    edges = extracted_data.get("edges", [])
    for ed in edges:
        edge = EdgeVersion(
            edge_model=ed.get("model", "Unknown"),
            version=ed.get("version") or "Unknown",
            release_date=ed.get("release_date"),
            end_of_life_date=ed.get("end_of_life_date"),
            end_of_support_date=ed.get("end_of_support_date"),
            is_end_of_life=ed.get("is_end_of_life", False),
            status=ed.get("status"),
            features=ed.get("features"),
            hardware_specs=ed.get("hardware_specs"),
            notes=ed.get("notes"),
            source_file=filename,
            raw_data=ed
        )
        db.add(edge)
        results["edges"].append(edge)
    
    db.commit()
    
    return results


def process_all_pdfs_gateway_edge(assets_dir: str, db: Session) -> Dict[str, Any]:
    """Traite tous les PDFs pour extraire les informations Gateway et Edge"""
    results = {
        "total_gateways": 0,
        "total_edges": 0,
        "processed_files": [],
        "errors": []
    }
    
    if not os.path.exists(assets_dir):
        raise Exception(f"Le dossier {assets_dir} n'existe pas")
    
    pdf_files = [f for f in os.listdir(assets_dir) if f.endswith('.pdf')]
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(assets_dir, pdf_file)
        try:
            file_results = process_pdf_with_gateway_edge(pdf_path, pdf_file, db)
            results["total_gateways"] += len(file_results["gateways"])
            results["total_edges"] += len(file_results["edges"])
            results["processed_files"].append({
                "filename": pdf_file,
                "gateways": len(file_results["gateways"]),
                "edges": len(file_results["edges"])
            })
        except Exception as e:
            error_msg = f"Erreur lors du traitement de {pdf_file}: {str(e)}"
            print(error_msg)
            results["errors"].append(error_msg)
            continue
    
    return results
