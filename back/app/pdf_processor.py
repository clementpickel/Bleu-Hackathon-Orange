import os
from openai import OpenAI
from pypdf import PdfReader
from typing import Dict, Any
import json
from sqlalchemy.orm import Session
from app.models import ProductModel

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


def extract_info_with_openai(text: str, filename: str) -> Dict[str, Any]:
    """Utilise OpenAI pour extraire les informations structurées du texte"""
    prompt = f"""
Analyse le texte suivant extrait d'un PDF sur des produits SD-WAN et extrait les informations suivantes au format JSON:
- model_name: le nom du modèle/produit
- version: la version du logiciel/firmware
- end_of_life: la date de fin de vie ou fin de support si mentionnée
- functionalities: une liste des fonctionnalités principales
- release_date: la date de release si mentionnée
- description: un résumé court du produit/version

Si une information n'est pas disponible, utilise null.

Nom du fichier: {filename}

Texte:
{text[:4000]}

Réponds uniquement avec le JSON, sans texte additionnel.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Tu es un assistant qui extrait des informations structurées de documents techniques."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        raise Exception(f"Erreur lors de l'appel à OpenAI: {str(e)}")


def process_pdf_and_store(pdf_path: str, filename: str, db: Session) -> ProductModel:
    """Traite un PDF et stocke les informations dans la base de données"""
    # Extraire le texte
    text = extract_text_from_pdf(pdf_path)
    
    # Extraire les informations avec OpenAI
    extracted_data = extract_info_with_openai(text, filename)
    
    # Créer l'entrée dans la base de données
    product = ProductModel(
        model_name=extracted_data.get("model_name", "Unknown"),
        version=extracted_data.get("version", "Unknown"),
        end_of_life=extracted_data.get("end_of_life"),
        functionalities=extracted_data.get("functionalities"),
        release_date=extracted_data.get("release_date"),
        description=extracted_data.get("description"),
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
