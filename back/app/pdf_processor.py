import os
from pypdf import PdfReader
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models import ProductModel
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


def extract_info_with_llm(text: str, filename: str) -> Dict[str, Any]:
    """Utilise le LLM configuré pour extraire les informations structurées du texte"""
    provider = get_llm_provider()
    
    prompt = f"""
Analyse le texte suivant extrait d'un PDF sur des produits SD-WAN et extrait les informations générales du produit au format JSON:

{{
  "model_name": "nom du modèle/produit",
  "is_end_of_life": true/false,
  "end_of_life_date": "date de fin de vie si mentionnée",
  "end_of_support_date": "date de fin de support si mentionnée",
  "status": "Active|Deprecated|End of Life",
  "functionalities": ["liste des fonctionnalités principales"],
  "alternatives": ["liste des produits alternatifs recommandés en remplacement"],
  "release_date": "date de première release si mentionnée",
  "description": "résumé du produit et de son utilisation",
  "notes": "notes importantes sur EOL, migration, etc."
}}

Si une information n'est pas disponible, utilise null.

Nom du fichier: {filename}

Texte (premiers 5000 caractères):
{text[:5000]}

Réponds uniquement avec le JSON, sans texte additionnel.
"""
    
    return provider.extract_info(text, prompt)


def process_pdf_and_store(pdf_path: str, filename: str, db: Session) -> ProductModel:
    """Traite un PDF et stocke les informations dans la base de données"""
    # Extraire le texte
    text = extract_text_from_pdf(pdf_path)
    
    # Extraire les informations avec le LLM
    extracted_data = extract_info_with_llm(text, filename)
    
    # Créer l'entrée dans la base de données
    product = ProductModel(
        model_name=extracted_data.get("model_name", "Unknown"),
        is_end_of_life=extracted_data.get("is_end_of_life", False),
        end_of_life_date=extracted_data.get("end_of_life_date"),
        end_of_support_date=extracted_data.get("end_of_support_date"),
        status=extracted_data.get("status"),
        functionalities=extracted_data.get("functionalities"),
        alternatives=extracted_data.get("alternatives"),
        release_date=extracted_data.get("release_date"),
        description=extracted_data.get("description"),
        notes=extracted_data.get("notes"),
        source_file=filename,
        raw_data=extracted_data
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return product


def process_all_pdfs(assets_dir: str, db: Session) -> list[ProductModel]:
    """Traite tous les PDFs dans le dossier assets"""
    results = []
    
    if not os.path.exists(assets_dir):
        raise Exception(f"Le dossier {assets_dir} n'existe pas")
    
    pdf_files = [f for f in os.listdir(assets_dir) if f.endswith('.pdf')]
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(assets_dir, pdf_file)
        try:
            product = process_pdf_and_store(pdf_path, pdf_file, db)
            results.append(product)
        except Exception as e:
            print(f"Erreur lors du traitement de {pdf_file}: {str(e)}")
            continue
    
    return results
