import os
from pypdf import PdfReader
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models import ProductModel, GatewayVersion, EdgeVersion, OrchestratorVersion
from app.llm_provider import get_llm_provider
from datetime import datetime


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
    current_date = datetime.now().strftime("%d/%m/%Y")
    
    prompt = f"""
Analyse le texte suivant extrait d'un PDF sur des produits SD-WAN (VeloCloud/Arista) et extrait les informations au format JSON.

DATE ACTUELLE: {current_date}

IMPORTANT: Il existe 3 types de software distincts (UN seul software par type):
- Gateway: logiciel pour passerelles/gateways
- Edge: logiciel pour équipements edge
- Orchestrator (VCO): logiciel pour contrôleur/orchestrateur

Pour chaque type, extrait UNIQUEMENT le numéro de version (ex: "6.4.0", "5.2.1").
NE PAS inclure le nom du produit dans la version.

Exemples CORRECTS:
- Version: "6.4.0" ✓
- Version: "5.2.1" ✓

Exemples INCORRECTS:
- Version: "VeloCloud Gateway v6.4.0" ✗
- Version: "Edge 510 v5.2.1" ✗

Extrait les informations suivantes au format JSON:

{{
  "document_type": "gateway_version" | "edge_version" | "orchestrator_version" | "lifecycle" | "release_notes",
  "gateways": [
    {{
      "version": "X.Y.Z uniquement, sans nom de produit",
      "document_date": "date de publication du document/PDF au format DD/MM/YYYY (chercher 'Last Updated', 'Published', 'Document Date')",
      "release_date": "date de release de cette version software au format DD/MM/YYYY",
      "end_of_life_date": "date de fin de vie au format DD/MM/YYYY si mentionnée",
      "end_of_support_date": "date de fin de support au format DD/MM/YYYY si mentionnée",
      "is_end_of_life": true/false (calculer automatiquement: true si end_of_life_date < DATE ACTUELLE, false sinon),
      "status": "Active|Deprecated|End of Life (déterminer en fonction de is_end_of_life)",
      "features": ["liste des fonctionnalités"],
      "upgrade_instructions": ["liste d'instructions importantes pour l'upgrade: pré-requis, dépendances, versions ESXi requises, versions Gateway/Edge/Orchestrator nécessaires, etc."],
      "notes": "notes importantes"
    }}
  ],
  "edges": [
    {{
      "version": "X.Y.Z uniquement, sans nom de produit",
      "document_date": "date de publication du document/PDF au format DD/MM/YYYY",
      "release_date": "date de release de cette version software au format DD/MM/YYYY",
      "end_of_life_date": "date de fin de vie au format DD/MM/YYYY si mentionnée",
      "end_of_support_date": "date de fin de support au format DD/MM/YYYY si mentionnée",
      "is_end_of_life": true/false (calculer automatiquement: true si end_of_life_date < DATE ACTUELLE, false sinon),
      "status": "Active|Deprecated|End of Life (déterminer en fonction de is_end_of_life)",
      "features": ["liste des fonctionnalités"],
      "upgrade_instructions": ["liste d'instructions importantes pour l'upgrade: depuis quelle version peut-on upgrader, versions Gateway requises, pré-requis, etc."],
      "notes": "notes importantes"
    }}
  ],
  "orchestrators": [
    {{
      "version": "X.Y.Z uniquement, sans nom de produit",
      "document_date": "date de publication du document/PDF au format DD/MM/YYYY",
      "release_date": "date de release de cette version software au format DD/MM/YYYY",
      "end_of_life_date": "date de fin de vie au format DD/MM/YYYY si mentionnée",
      "end_of_support_date": "date de fin de support au format DD/MM/YYYY si mentionnée",
      "is_end_of_life": true/false (calculer automatiquement: true si end_of_life_date < DATE ACTUELLE, false sinon),
      "status": "Active|Deprecated|End of Life (déterminer en fonction de is_end_of_life)",
      "features": ["liste des fonctionnalités"],
      "upgrade_instructions": ["liste d'instructions importantes pour l'upgrade: versions Gateway/Edge compatibles, pré-requis, dépendances, etc."],
      "notes": "notes importantes"
    }}
  ],
  "general_info": {{
    "description": "résumé du document",
    "key_points": ["points importants"]
  }}
}}

IMPORTANT - FORMAT DES DATES:
TOUTES les dates doivent être au format DD/MM/YYYY (jour/mois/année).
Exemples: "15/03/2025", "01/12/2026", "30/06/2024"

Si une information n'est pas disponible, utilise null. Si le document ne contient pas de gateways, edges ou orchestrators, laisse les listes vides.

Nom du fichier: {filename}

Texte (premiers 6000 caractères):
{text[:6000]}

Réponds uniquement avec le JSON, sans texte additionnel.
"""
    
    return provider.extract_info(text, prompt)


def process_pdf_with_gateway_edge(pdf_path: str, filename: str, db: Session) -> Dict[str, Any]:
    """Traite un PDF et stocke les informations de Gateway, Edge et Orchestrator dans la base de données"""
    # Extraire le texte
    text = extract_text_from_pdf(pdf_path)
    
    # Extraire les informations avec le LLM
    extracted_data = extract_gateway_edge_info(text, filename)
    
    results = {
        "gateways": [],
        "edges": [],
        "orchestrators": [],
        "filename": filename
    }
    
    # Traiter les Gateways
    gateways = extracted_data.get("gateways", [])
    for gw in gateways:
        version = gw.get("version")
        if not version or version == "Unknown":
            continue
            
        # Vérifier si la version existe déjà
        existing = db.query(GatewayVersion).filter(GatewayVersion.version == version).first()
        if existing:
            continue
            
        gateway = GatewayVersion(
            version=version,
            document_date=gw.get("document_date"),
            release_date=gw.get("release_date"),
            end_of_life_date=gw.get("end_of_life_date"),
            end_of_support_date=gw.get("end_of_support_date"),
            is_end_of_life=gw.get("is_end_of_life", False),
            status=gw.get("status"),
            features=gw.get("features"),
            upgrade_instructions=gw.get("upgrade_instructions"),
            notes=gw.get("notes"),
            source_file=filename,
            raw_data=gw
        )
        db.add(gateway)
        results["gateways"].append(gateway)
    
    # Traiter les Edges
    edges = extracted_data.get("edges", [])
    for ed in edges:
        version = ed.get("version")
        if not version or version == "Unknown":
            continue
            
        # Vérifier si la version existe déjà
        existing = db.query(EdgeVersion).filter(EdgeVersion.version == version).first()
        if existing:
            continue
            
        edge = EdgeVersion(
            version=version,
            document_date=ed.get("document_date"),
            release_date=ed.get("release_date"),
            end_of_life_date=ed.get("end_of_life_date"),
            end_of_support_date=ed.get("end_of_support_date"),
            is_end_of_life=ed.get("is_end_of_life", False),
            status=ed.get("status"),
            features=ed.get("features"),
            upgrade_instructions=ed.get("upgrade_instructions"),
            notes=ed.get("notes"),
            source_file=filename,
            raw_data=ed
        )
        db.add(edge)
        results["edges"].append(edge)
    
    # Traiter les Orchestrators
    orchestrators = extracted_data.get("orchestrators", [])
    for orch in orchestrators:
        version = orch.get("version")
        if not version or version == "Unknown":
            continue
            
        # Vérifier si la version existe déjà
        existing = db.query(OrchestratorVersion).filter(OrchestratorVersion.version == version).first()
        if existing:
            continue
            
        orchestrator = OrchestratorVersion(
            version=version,
            document_date=orch.get("document_date"),
            release_date=orch.get("release_date"),
            end_of_life_date=orch.get("end_of_life_date"),
            end_of_support_date=orch.get("end_of_support_date"),
            is_end_of_life=orch.get("is_end_of_life", False),
            status=orch.get("status"),
            features=orch.get("features"),
            upgrade_instructions=orch.get("upgrade_instructions"),
            notes=orch.get("notes"),
            source_file=filename,
            raw_data=orch
        )
        db.add(orchestrator)
        results["orchestrators"].append(orchestrator)
    
    db.commit()
    
    return results


def process_all_pdfs_gateway_edge(assets_dir: str, db: Session) -> Dict[str, Any]:
    """Traite tous les PDFs pour extraire les informations Gateway, Edge et Orchestrator"""
    results = {
        "total_gateways": 0,
        "total_edges": 0,
        "total_orchestrators": 0,
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
            results["total_orchestrators"] += len(file_results["orchestrators"])
            results["processed_files"].append({
                "filename": pdf_file,
                "gateways": len(file_results["gateways"]),
                "edges": len(file_results["edges"]),
                "orchestrators": len(file_results["orchestrators"])
            })
        except Exception as e:
            error_msg = f"Erreur lors du traitement de {pdf_file}: {str(e)}"
            print(error_msg)
            results["errors"].append(error_msg)
            continue
    
    return results
