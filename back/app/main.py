from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.models import ProductModel, GatewayVersion, EdgeVersion, OrchestratorVersion
from app.pdf_processor import process_all_pdfs
from app.version_processor import process_all_pdfs_gateway_edge
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
            "document_date": p.document_date,
            "is_end_of_life": p.is_end_of_life,
            "end_of_life_date": p.end_of_life_date,
            "end_of_support_date": p.end_of_support_date,
            "status": p.status,
            "functionalities": p.functionalities,
            "alternatives": p.alternatives,
            "release_date": p.release_date,
            "description": p.description,
            "notes": p.notes,
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


@app.post("/process-versions", tags=["PDF Processing", "Versions"])
async def process_versions(db: Session = Depends(get_db)):
    """
    Traite tous les PDFs pour extraire les versions Gateway, Edge et Orchestrator avec dates EOL
    
    Extrait spécifiquement:
    - Versions de Gateway (software uniquement)
    - Versions d'Edge (software uniquement)
    - Versions d'Orchestrator/VCO (software uniquement)
    - Dates de fin de vie et statuts
    """
    try:
        assets_dir = "/app/assets"
        if not os.path.exists(assets_dir):
            raise HTTPException(status_code=404, detail=f"Dossier assets non trouvé: {assets_dir}")
        
        pdf_files = [f for f in os.listdir(assets_dir) if f.endswith('.pdf')]
        if not pdf_files:
            raise HTTPException(status_code=404, detail="Aucun fichier PDF trouvé dans le dossier assets")
        
        # Traiter les PDFs
        results = process_all_pdfs_gateway_edge(assets_dir, db)
        
        return {
            "status": "success",
            "total_gateways": results["total_gateways"],
            "total_edges": results["total_edges"],
            "total_orchestrators": results["total_orchestrators"],
            "processed_files": results["processed_files"],
            "errors": results["errors"],
            "message": f"{results['total_gateways']} gateways, {results['total_edges']} edges, {results['total_orchestrators']} orchestrators extraits"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement: {str(e)}")


@app.get("/gateways", response_model=List[dict], tags=["Versions"])
async def get_gateways(skip: int = 0, limit: int = 100, eol_only: bool = False, db: Session = Depends(get_db)):
    """
    Récupère la liste des versions Gateway (software uniquement)
    
    - eol_only: si True, retourne uniquement les versions en fin de vie
    """
    query = db.query(GatewayVersion)
    if eol_only:
        query = query.filter(GatewayVersion.is_end_of_life == True)
    
    gateways = query.offset(skip).limit(limit).all()
    return [
        {
            "id": g.id,
            "version": g.version,
            "document_date": g.document_date,
            "release_date": g.release_date,
            "end_of_life_date": g.end_of_life_date,
            "end_of_support_date": g.end_of_support_date,
            "is_end_of_life": g.is_end_of_life,
            "status": g.status,
            "features": g.features,
            "notes": g.notes,
            "source_file": g.source_file,
            "created_at": g.created_at.isoformat() if g.created_at else None
        }
        for g in gateways
    ]


@app.get("/edges", response_model=List[dict], tags=["Versions"])
async def get_edges(skip: int = 0, limit: int = 100, eol_only: bool = False, db: Session = Depends(get_db)):
    """
    Récupère la liste des versions Edge (software uniquement)
    
    - eol_only: si True, retourne uniquement les versions en fin de vie
    """
    query = db.query(EdgeVersion)
    if eol_only:
        query = query.filter(EdgeVersion.is_end_of_life == True)
    
    edges = query.offset(skip).limit(limit).all()
    return [
        {
            "id": e.id,
            "version": e.version,
            "document_date": e.document_date,
            "release_date": e.release_date,
            "end_of_life_date": e.end_of_life_date,
            "end_of_support_date": e.end_of_support_date,
            "is_end_of_life": e.is_end_of_life,
            "status": e.status,
            "features": e.features,
            "notes": e.notes,
            "source_file": e.source_file,
            "created_at": e.created_at.isoformat() if e.created_at else None
        }
        for e in edges
    ]


@app.get("/orchestrators", response_model=List[dict], tags=["Versions"])
async def get_orchestrators(skip: int = 0, limit: int = 100, eol_only: bool = False, db: Session = Depends(get_db)):
    """
    Récupère la liste des versions Orchestrator/VCO (software uniquement)
    
    - eol_only: si True, retourne uniquement les versions en fin de vie
    """
    query = db.query(OrchestratorVersion)
    if eol_only:
        query = query.filter(OrchestratorVersion.is_end_of_life == True)
    
    orchestrators = query.offset(skip).limit(limit).all()
    return [
        {
            "id": o.id,
            "version": o.version,
            "document_date": o.document_date,
            "release_date": o.release_date,
            "end_of_life_date": o.end_of_life_date,
            "end_of_support_date": o.end_of_support_date,
            "is_end_of_life": o.is_end_of_life,
            "status": o.status,
            "features": o.features,
            "notes": o.notes,
            "source_file": o.source_file,
            "created_at": o.created_at.isoformat() if o.created_at else None
        }
        for o in orchestrators
    ]


@app.get("/eol-summary", tags=["Versions"])
async def get_eol_summary(db: Session = Depends(get_db)):
    """
    Résumé des produits en fin de vie
    """
    total_gateways = db.query(GatewayVersion).count()
    eol_gateways = db.query(GatewayVersion).filter(GatewayVersion.is_end_of_life == True).count()
    
    total_edges = db.query(EdgeVersion).count()
    eol_edges = db.query(EdgeVersion).filter(EdgeVersion.is_end_of_life == True).count()
    
    total_orchestrators = db.query(OrchestratorVersion).count()
    eol_orchestrators = db.query(OrchestratorVersion).filter(OrchestratorVersion.is_end_of_life == True).count()
    
    return {
        "gateways": {
            "total": total_gateways,
            "end_of_life": eol_gateways,
            "active": total_gateways - eol_gateways
        },
        "edges": {
            "total": total_edges,
            "end_of_life": eol_edges,
            "active": total_edges - eol_edges
        },
        "orchestrators": {
            "total": total_orchestrators,
            "end_of_life": eol_orchestrators,
            "active": total_orchestrators - eol_orchestrators
        }
    }
