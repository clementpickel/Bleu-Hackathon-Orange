from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.models import ProductModel
from app.pdf_processor import process_all_pdfs
from typing import List
import os

app = FastAPI(
    title="Bleu Hackathon Orange API",
    description="API pour le hackathon Bleu Orange",
    version="1.0.0",
    docs_url="/swagger",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def startup_event():
    """Initialise la base de données au démarrage"""
    init_db()


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Retourne le statut de santé de l'API
    """
    return {"status": "healthy", "service": "bleu-hackathon-orange"}


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint
    
    Page d'accueil de l'API
    """
    return {"message": "Welcome to Bleu Hackathon Orange API"}


@app.post("/process-pdfs", tags=["PDF Processing"])
async def process_pdfs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Traite tous les PDFs dans le dossier assets et extrait les informations
    
    Utilise OpenAI pour extraire les modèles, versions, end of life et fonctionnalités
    """
    try:
        assets_dir = "/app/assets"
        if not os.path.exists(assets_dir):
            raise HTTPException(status_code=404, detail=f"Dossier assets non trouvé: {assets_dir}")
        
        pdf_files = [f for f in os.listdir(assets_dir) if f.endswith('.pdf')]
        if not pdf_files:
            raise HTTPException(status_code=404, detail="Aucun fichier PDF trouvé dans le dossier assets")
        
        # Traiter les PDFs
        results = process_all_pdfs(assets_dir, db)
        
        return {
            "status": "success",
            "processed": len(results),
            "total_pdfs": len(pdf_files),
            "message": f"{len(results)} PDFs traités avec succès"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement: {str(e)}")


@app.get("/products", response_model=List[dict], tags=["Products"])
async def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Récupère la liste des produits extraits des PDFs
    """
    products = db.query(ProductModel).offset(skip).limit(limit).all()
    return [
        {
            "id": p.id,
            "model_name": p.model_name,
            "version": p.version,
            "end_of_life": p.end_of_life,
            "functionalities": p.functionalities,
            "release_date": p.release_date,
            "description": p.description,
            "source_file": p.source_file,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in products
    ]


@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """
    Récupère un produit spécifique par son ID
    """
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    return {
        "id": product.id,
        "model_name": product.model_name,
        "version": product.version,
        "end_of_life": product.end_of_life,
        "functionalities": product.functionalities,
        "release_date": product.release_date,
        "description": product.description,
        "source_file": product.source_file,
        "raw_data": product.raw_data,
        "created_at": product.created_at.isoformat() if product.created_at else None
    }


@app.delete("/products/{product_id}", tags=["Products"])
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """
    Supprime un produit de la base de données
    """
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    db.delete(product)
    db.commit()
    
    return {"status": "success", "message": f"Produit {product_id} supprimé"}
