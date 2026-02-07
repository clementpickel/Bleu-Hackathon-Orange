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
Analyse le texte suivant extrait d'un PDF sur des produits SD-WAN et extrait les informations générales des PRODUITS HARDWARE au format JSON.

IMPORTANT - Définition d'un PRODUIT valide:
✓ PRODUIT VALIDE = modèle hardware physique avec numéro/référence spécifique
   Exemples: Edge 680, Edge 840 Wi-Fi, Edge 840, Gateway, Orchestrator
✗ PRODUIT INVALIDE = version software 
   Exemples: "VeloCloud 6.3.1", "Arista VeloCloud SD-WAN 6.3.1", "Software version 5.4.0"

RÈGLES D'EXTRACTION ET NORMALISATION:
1. Chercher les références de produits hardware avec des numéros de modèle (510, 620, 3800, etc.)
2. Inclure TOUS les suffixes et variantes: -W, -5G, -LTE, Wi-Fi, Non-Wi-Fi, N, v, etc.
3. Accepter différents formats de nommage puis NORMALISER selon ces règles:
   - "VMware SD-WAN Edge 680" → "Edge 680"
   - "VeloCloud Edge 840" → "Edge 840"
   - "Arista Edge 510" → "Edge 510"
   - "VCG", "VCG-300", "Virtual Cloud Gateway", "VeloCloud Gateway" → "Gateway"
   - "VCO", "VeloCloud Orchestrator", "VMware SD-WAN Orchestrator" → "Orchestrator"
4. TOUJOURS retirer les préfixes de marque: VMware, VeloCloud, Arista, Broadcom
5. Format de sortie standardisé:
   - Edge devices: "Edge XXX" (ex: Edge 680, Edge 840 Wi-Fi)
   - Gateway: "Gateway" (sans numéro sauf si spécifique comme Gateway 6200)
   - Orchestrator: "Orchestrator"
6. NE PAS regrouper plusieurs modèles: si "Edge 840 et Edge 680" → créer DEUX entrées distinctes
7. Différencier les variantes: "Edge 680 Wi-Fi" ≠ "Edge 680N Non-Wi-Fi" (deux produits distincts)

TYPES DE PRODUITS À DÉTECTER:
- Edge devices: tout modèle avec "Edge" + numéro (Edge 680, Edge 840, Edge 680N, etc.)
- Gateway: VCG, Gateway, Virtual Cloud Gateway → normaliser vers "Gateway"
- Orchestrator: VCO, Orchestrator → normaliser vers "Orchestrator"
- Autres: tout équipement SD-WAN physique avec référence spécifique

EXEMPLES DE NORMALISATION:
Avant normalisation → Après normalisation
- "VMware SD-WAN Edge 840" → "Edge 840" ✓
- "VeloCloud Edge 680 Wi-Fi" → "Edge 680 Wi-Fi" ✓
- "VCG" → "Gateway" ✓
- "VeloCloud Gateway" → "Gateway" ✓
- "VCO" → "Orchestrator" ✓
- "VMware SD-WAN Orchestrator" → "Orchestrator" ✓
- "Arista Edge 510N Non-Wi-Fi" → "Edge 510N Non-Wi-Fi" ✓

EXEMPLES INCORRECTS:
- "VeloCloud SD-WAN" ✗ (pas de numéro de modèle)
- "Edge" ✗ (trop générique)
- "version 6.3.1" ✗ (c'est du software)
- "Edge 840 et Edge 680" ✗ (plusieurs produits)

Format JSON attendu (array de produits):

{{
  "document_date": "date de publication du document/PDF au format DD/MM/YYYY (chercher dans header, footer)",
  "products": [
    {{
      "model_name": "nom du modèle complet (ex: Edge 710-W, Gateway, Edge 840 Wi-Fi)",
      "is_end_of_life": true/false,
      "end_of_life_date": "date de fin de vie au format DD/MM/YYYY si mentionnée",
      "end_of_support_date": "date de fin de support au format DD/MM/YYYY si mentionnée",
      "status": "Active|Deprecated|End of Life",
      "functionalities": ["liste des fonctionnalités principales"],
      "alternatives": ["liste des produits alternatifs recommandés"],
      "release_date": "date de première release au format DD/MM/YYYY si mentionnée",
      "description": "résumé du produit hardware",
      "notes": "notes importantes sur EOL, migration, alternatives"
    }}
  ]
}}

IMPORTANT - FORMAT DES DATES:
TOUTES les dates doivent être au format DD/MM/YYYY (jour/mois/année).
Exemples: "15/03/2025", "01/12/2026", "30/06/2024"

ATTENTION: 
- Extraire TOUS les produits hardware mentionnés dans le document
- Chaque produit distinct doit avoir sa propre entrée dans le tableau "products"
- Si "Edge 840 et Edge 680" → créer DEUX entrées distinctes
- Ne PAS inclure les numéros de version software dans model_name
- TOUJOURS inclure le suffixe du modèle (-W, -5G, -LTE, Wi-Fi, Non-Wi-Fi) s'il est mentionné
- Si aucun produit hardware n'est trouvé, retourner {{"products": []}}

Nom du fichier: {filename}

Texte (premiers 8000 caractères pour détecter tous les produits):
{text[:8000]}

Réponds uniquement avec le JSON contenant TOUS les produits hardware trouvés, sans texte additionnel.
"""
    
    return provider.extract_info(text, prompt)


def process_pdf_and_store(pdf_path: str, filename: str, db: Session) -> list[ProductModel]:
    """Traite un PDF et stocke TOUS les produits trouvés dans la base de données"""
    # Extraire le texte
    text = extract_text_from_pdf(pdf_path)
    
    # Extraire les informations avec le LLM
    extracted_data = extract_info_with_llm(text, filename)
    
    products_created = []
    document_date = extracted_data.get("document_date")
    
    # Traiter chaque produit trouvé
    products_list = extracted_data.get("products", [])
    if not products_list:
        return []
    
    for product_data in products_list:
        model_name = product_data.get("model_name")
        if not model_name or model_name == "null":
            continue
        
        # Vérifier si le produit existe déjà
        existing = db.query(ProductModel).filter(ProductModel.model_name == model_name).first()
        if existing:
            products_created.append(existing)
            continue
        
        # Créer l'entrée dans la base de données
        product = ProductModel(
            model_name=model_name,
            document_date=document_date,  # Date du document (commune à tous)
            is_end_of_life=product_data.get("is_end_of_life", False),
            end_of_life_date=product_data.get("end_of_life_date"),
            end_of_support_date=product_data.get("end_of_support_date"),
            status=product_data.get("status"),
            functionalities=product_data.get("functionalities"),
            alternatives=product_data.get("alternatives"),
            release_date=product_data.get("release_date"),
            description=product_data.get("description"),
            notes=product_data.get("notes"),
            source_file=filename,
            raw_data=product_data
        )
        
        db.add(product)
        products_created.append(product)
    
    db.commit()
    for product in products_created:
        if product.id is None:  # Refresh only newly created products
            db.refresh(product)
    
    return products_created


def process_all_pdfs(assets_dir: str, db: Session) -> list[ProductModel]:
    """Traite tous les PDFs dans le dossier assets"""
    results = []
    
    if not os.path.exists(assets_dir):
        raise Exception(f"Le dossier {assets_dir} n'existe pas")
    
    pdf_files = [f for f in os.listdir(assets_dir) if f.endswith('.pdf')]
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(assets_dir, pdf_file)
        try:
            products = process_pdf_and_store(pdf_path, pdf_file, db)  # Now returns a list
            if products:  # Only add if valid products were extracted
                results.extend(products)  # Use extend instead of append
        except Exception as e:
            print(f"Erreur lors du traitement de {pdf_file}: {str(e)}")
            continue
    
    return results
