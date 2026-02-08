from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.models import ProductModel, GatewayVersion, EdgeVersion, OrchestratorVersion
from app.pdf_processor import process_all_pdfs
from app.version_processor import process_all_pdfs_gateway_edge
from app.llm_provider import get_llm_provider, get_analysis_llm_provider
from app.pdf_tools import PDF_RETRIEVAL_TOOLS, execute_pdf_tool, list_available_pdfs
from typing import List, Any
from pydantic import BaseModel
from datetime import datetime
import os
import json

app = FastAPI(
    title="Bleu Hackathon Orange API",
    description="API pour le hackathon Bleu Orange",
    version="1.0.0",
    docs_url="/swagger",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.post("/api/process", tags=["PDF Processing"])
async def process(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Traite tous les PDFs dans le dossier assets et extrait TOUTES les informations:
    - Produits (hardware et software)
    - Versions (Gateway, Edge, Orchestrator)
    - End of life dates et statuts
    - Fonctionnalités et instructions d'upgrade
    
    Ce endpoint unifié combine le traitement des produits et des versions.
    """
    try:
        assets_dir = "/app/assets"
        if not os.path.exists(assets_dir):
            raise HTTPException(status_code=404, detail=f"Dossier assets non trouvé: {assets_dir}")
        
        pdf_files = [f for f in os.listdir(assets_dir) if f.endswith('.pdf')]
        if not pdf_files:
            raise HTTPException(status_code=404, detail="Aucun fichier PDF trouvé dans le dossier assets")
        
        # Traiter les PDFs pour les produits
        products_results = process_all_pdfs(assets_dir, db)
        
        # Traiter les PDFs pour les versions (Gateway, Edge, Orchestrator)
        versions_results = process_all_pdfs_gateway_edge(assets_dir, db)
        
        return {
            "status": "success",
            "products": {
                "processed": len(products_results),
                "message": f"{len(products_results)} produits extraits"
            },
            "versions": {
                "total_gateways": versions_results["total_gateways"],
                "total_edges": versions_results["total_edges"],
                "total_orchestrators": versions_results["total_orchestrators"],
                "processed_files": versions_results["processed_files"],
                "errors": versions_results["errors"],
                "message": f"{versions_results['total_gateways']} gateways, {versions_results['total_edges']} edges, {versions_results['total_orchestrators']} orchestrators extraits"
            },
            "total_pdfs": len(pdf_files),
            "message": f"Traitement complet: {len(products_results)} produits et {versions_results['total_gateways'] + versions_results['total_edges'] + versions_results['total_orchestrators']} versions extraits"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement: {str(e)}")


@app.get("/api/products", response_model=List[dict], tags=["Products"])
async def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Récupère la liste des produits extraits des PDFs
    """
    products = db.query(ProductModel).offset(skip).limit(limit).all()
    return [
        {
            "id": p.id,
            "model_name": p.model_name,
            "product_type": p.product_type,
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


@app.get("/api/products/{product_id}", tags=["Products"])
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


@app.delete("/api/products/{product_id}", tags=["Products"])
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


@app.get("/api/gateways", response_model=List[dict], tags=["Versions"])
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
            "upgrade_instructions": g.upgrade_instructions,
            "notes": g.notes,
            "source_file": g.source_file,
            "created_at": g.created_at.isoformat() if g.created_at else None
        }
        for g in gateways
    ]


@app.get("/api/edges", response_model=List[dict], tags=["Versions"])
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
            "upgrade_instructions": e.upgrade_instructions,
            "notes": e.notes,
            "source_file": e.source_file,
            "created_at": e.created_at.isoformat() if e.created_at else None
        }
        for e in edges
    ]


@app.get("/api/orchestrators", response_model=List[dict], tags=["Versions"])
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
            "upgrade_instructions": o.upgrade_instructions,
            "notes": o.notes,
            "source_file": o.source_file,
            "created_at": o.created_at.isoformat() if o.created_at else None
        }
        for o in orchestrators
    ]


@app.get("/api/eol-summary", tags=["Versions"])
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


class VersionInfo(BaseModel):
    """Modèle pour les informations de version - Upgrade vers LTS automatique
    
    Args:
        component: Type de composant (gateway, edge, orchestrator)
        current_version: Version actuellement installée
    """
    component: str  # gateway, edge, orchestrator
    current_version: str


class UpgradeAnalysisRequest(BaseModel):
    """Requête pour l'analyse de chemin d'upgrade vers LTS
    
    **REQUIS**: Les 3 composants (orchestrator, gateway, edge) doivent être fournis
    car l'écosystème SD-WAN est interdépendant.
    
    Stratégie LTS AUTOMATIQUE: Tous les composants sont automatiquement upgradés vers leur
    dernière version stable non-EOL. Le système identifiera TOUTES les versions intermédiaires nécessaires.
    """
    versions: List[VersionInfo]


@app.post("/api/analyze-upgrade-path", tags=["Analysis"])
async def analyze_upgrade_path(request: UpgradeAnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyse le chemin d'upgrade pour une liste de composants et leurs versions
    
    Utilise un modèle avec réflexion (o1-mini) pour analyser les dépendances
    et générer un plan d'upgrade séquentiel.
    
    Comprend les patterns de versions:
    - Instructions pour "5.X" s'appliquent à toutes les versions 5.x (5.0.0, 5.1.2, etc.)
    - Instructions pour "5.0.X" s'appliquent à toutes les versions 5.0.x (5.0.0, 5.0.1, etc.)
    
    Exemple de requête:
    {
        "versions": [
            {"component": "gateway", "current_version": "5.4.0", "target_version": "6.2.0"},
            {"component": "edge", "current_version": "4.5.0", "target_version": "6.4.0"},
            {"component": "orchestrator", "current_version": "5.2.0", "target_version": "5.5.0"}
        ]
    }
    """
    try:
        import re
        provider = get_llm_provider()
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        def matches_version_pattern(version: str, pattern: str) -> bool:
            """Vérifie si une version correspond à un pattern (5.X, 5.0.X, etc.)"""
            if 'X' not in pattern and 'x' not in pattern:
                return version == pattern
            
            # Convertir pattern en regex: 5.X -> 5\.\d+, 5.0.X -> 5\.0\.\d+
            regex_pattern = pattern.upper().replace('.', r'\.').replace('X', r'\d+')
            return bool(re.match(f"^{regex_pattern}$", version))
        
        # Construire le contexte enrichi
        context_parts = []
        context_parts.append(f"DATE ACTUELLE: {current_date}\n")
        context_parts.append("=== CONFIGURATION ACTUELLE ET CIBLES ===\n")
        
        all_instructions = {}
        
        for version_info in request.versions:
            component = version_info.component.lower()
            current_ver = version_info.current_version
            target_ver = version_info.target_version
            
            context_parts.append(f"\n--- {component.upper()} ---")
            context_parts.append(f"Version actuelle: {current_ver}")
            if target_ver:
                context_parts.append(f"Version cible: {target_ver}")
            
            # Récupérer TOUTES les versions entre current et target (+ patterns)
            if component == "gateway":
                Model = GatewayVersion
            elif component == "edge":
                Model = EdgeVersion
            elif component == "orchestrator":
                Model = OrchestratorVersion
            else:
                continue
            
            # Récupérer toutes les versions disponibles pour ce composant
            all_vers = db.query(Model).all()
            
            # Filtrer celles qui sont pertinentes
            relevant_versions = []
            seen_versions = set()
            
            for ver in all_vers:
                # Ajouter current et target
                if ver.version in [current_ver, target_ver]:
                    if ver.version not in seen_versions:
                        relevant_versions.append(ver)
                        seen_versions.add(ver.version)
                # Ajouter les versions avec patterns qui matchent current_ver ou target_ver
                elif 'X' in ver.version or 'x' in ver.version:
                    if matches_version_pattern(current_ver, ver.version) or (target_ver and matches_version_pattern(target_ver, ver.version)):
                        if ver.version not in seen_versions:
                            relevant_versions.append(ver)
                            seen_versions.add(ver.version)
            
            all_instructions[component] = []
            for ver in relevant_versions:
                ver_info = {
                    "version": ver.version,
                    "release_date": ver.release_date,
                    "eol_date": ver.end_of_life_date,
                    "is_eol": ver.is_end_of_life,
                    "instructions": ver.upgrade_instructions or []
                }
                all_instructions[component].append(ver_info)
                
                context_parts.append(f"\nVersion {ver.version}:")
                if ver.release_date:
                    context_parts.append(f"  📅 Release: {ver.release_date}")
                if ver.end_of_life_date:
                    context_parts.append(f"  ⏰ EOL: {ver.end_of_life_date}")
                if ver.is_end_of_life:
                    context_parts.append(f"  ⚠️ **END OF LIFE**")
                if ver.upgrade_instructions:
                    context_parts.append(f"  📋 Instructions d'upgrade:")
                    for instruction in ver.upgrade_instructions:
                        context_parts.append(f"    • {instruction}")
        
        context = "\n".join(context_parts)
        
        # Prompt optimisé pour modèle avec réflexion
        prompt = f"""Tu es un expert en infrastructure SD-WAN (VeloCloud/VMware/Arista).

{context}

=== RÈGLES IMPORTANTES ===
1. **DÉPENDANCES**: Edge dépend de Gateway, Gateway dépend d'Orchestrator
2. **ORDRE OBLIGATOIRE**: Orchestrator PUIS Gateway PUIS Edge
3. **PATTERNS DE VERSIONS**: Les instructions pour "5.X" s'appliquent à toutes les versions 5.x (5.0.0, 5.1.2, 5.4.0, etc.)
4. **COMPATIBILITÉ**: Vérifier que chaque composant est compatible avec les versions des autres composants
5. **PRÉ-REQUIS**: ESXi, dépendances système, versions minimales requises
6. **HARDWARE**: TOUS les composants hardware (appliances physiques Edge/Gateway) nécessitent également un upgrade et doivent être considérés dans le plan. Vérifier les EOL hardware et les remplacements nécessaires.

=== CONTEXTE D'ANALYSE ===
Ce prompt est utilisé pour analyser un chemin d'upgrade complet incluant:
- Software versions (Orchestrator/Gateway/Edge)
- Hardware appliances (modèles physiques qui peuvent être EOL)
- Dépendances entre composants
- Versions intermédiaires nécessaires
- Pré-requis système (ESXi, RAM, CPU, etc.)

=== TÂCHE ===
Génère un plan d'upgrade structuré sous format JSON avec les champs suivants:
- reasoning: Explication détaillée de ton raisonnement sur l'ordre des opérations, les dépendances, et les considérations hardware
- risks: Liste des risques avec severity (critical|high|medium|low), description, et mitigation
- steps: Liste ordonnée des étapes d'upgrade avec:
  * step_number: numéro de l'étape
  * component: orchestrator|gateway|edge
  * action: upgrade|replace|validate
  * from_version: version de départ
  * to_version: version cible
  * duration_minutes: durée estimée
  * prerequisites: liste des pré-requis (ex: ["ESXi 6.7 U3 minimum", "Backup completed", "Hardware model X"])
  * instructions: liste des instructions détaillées
  * validation: liste des tests de validation
  * rollback: liste des étapes de rollback
  * hardware_notes: notes spécifiques sur le hardware si applicable
- total_duration_minutes: Durée totale estimée
- recommended_maintenance_window: Fenêtre de maintenance recommandée (jour et horaire)
- critical_notes: Liste des avertissements importants et considérations hardware

IMPORTANT: Retourne UNIQUEMENT le JSON valide, sans markdown ni texte additionnel.
"""
        
        # Utiliser le modèle avec réflexion
        result = provider.analyze_with_reasoning(prompt)
        
        return {
            "status": "success",
            "result": result,
            "input_versions": [v.dict() for v in request.versions],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")


@app.post("/api/analyze-upgrade-with-pdfs", tags=["Analysis"])
async def analyze_upgrade_with_pdfs(request: UpgradeAnalysisRequest, db: Session = Depends(get_db)):
    """
    Génère un guide d'upgrade TEXTE complet pour upgrader TOUS les composants vers LTS.
    
    🎯 **OBJECTIF**: Upgrade de TOUS les composants vers leur version LTS (Long Term Support)
    ⚠️ **IMPORTANT**: Il y aura TOUJOURS des étapes intermédiaires - pas de sauts directs!
    🔗 **REQUIS**: Les 3 composants (orchestrator, gateway, edge) DOIVENT être fournis car ils sont interdépendants
    
    Cette version AVANCÉE permet au LLM de:
    - Lister les PDFs disponibles
    - Récupérer le contenu des PDFs des versions LTS cibles
    - Rechercher des informations sur les chemins d'upgrade supportés
    
    Le LLM génère un guide CLAIR et STRUCTURÉ étape par étape pour:
    - Upgrader TOUS les composants (appliances et VMs) vers leurs versions LTS
    - Identifier TOUTES les versions intermédiaires obligatoires (pas de sauts directs!)
    - Assurer la compatibilité entre composants à chaque étape
    - Respecter l'ordre des dépendances (Orchestrator → Gateway → Edge)
    - Fournir des instructions précises avec validation et rollback
    
    Exemple de requête (TOUS les composants requis):
    {
        "versions": [
            {"component": "orchestrator", "current_version": "5.2.0"},
            {"component": "gateway", "current_version": "5.4.0"},
            {"component": "edge", "current_version": "4.5.0"}
        ]
    }
    
    **STRATÉGIE LTS AUTOMATIQUE**: 
    - Tous les composants sont automatiquement upgradés vers leur dernière version LTS
    - Exemple de sortie attendue:
      1. Upgrade Orchestrator from 5.2.0 to 5.4.0
      2. Upgrade Gateway from 5.4.0 to 5.6.0
      3. Upgrade Edge from 4.5.0 to 5.0.0
      4. Upgrade Orchestrator from 5.4.0 to 6.0.0
      5. Upgrade Gateway from 5.6.0 to 6.2.0
      6. Upgrade Orchestrator from 6.0.0 to 6.4.0 (LTS)
      7. Upgrade Gateway from 6.2.0 to 6.4.0 (LTS)
      8. Upgrade Edge from 5.0.0 to 6.4.0 (LTS)
    
    Retourne: Guide en format TEXTE avec liste numérotée des étapes + détails complets.
    
    Note: Les PDFs fournis sont ceux des versions LTS finales, pas des versions actuelles.
    """
    try:
        import re
        provider = get_analysis_llm_provider()  # Use dedicated analysis provider with function calling
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        # Validation: Vérifier que les 3 composants sont fournis (écosystème interdépendant)
        components_provided = set()
        invalid_components = []
        
        for v in request.versions:
            component_lower = v.component.lower().strip()
            
            # Nettoyer les noms de composants courants
            if "gateway" in component_lower or "gateaway" in component_lower:
                components_provided.add("gateway")
            elif "edge" in component_lower:
                components_provided.add("edge")
            elif "orchestrator" in component_lower or "vco" in component_lower:
                components_provided.add("orchestrator")
            else:
                invalid_components.append(v.component)
        
        # Vérifier les composants invalides
        if invalid_components:
            raise HTTPException(
                status_code=400,
                detail=f"Composant(s) invalide(s): {', '.join(invalid_components)}. "
                       f"Utilisez uniquement: 'orchestrator', 'gateway', 'edge' (casse insensible). "
                       f"Exemples corrects: 'edge' (pas 'Edge 840'), 'gateway' (pas 'Gateaway')"
            )
        
        required_components = {"orchestrator", "gateway", "edge"}
        
        if not required_components.issubset(components_provided):
            missing = required_components - components_provided
            raise HTTPException(
                status_code=400, 
                detail=f"Écosystème incomplet: Les composants suivants sont manquants: {', '.join(missing)}. "
                       f"L'écosystème SD-WAN nécessite TOUS les composants (orchestrator, gateway, edge) car ils sont interdépendants. "
                       f"Format requis: {{ \"versions\": [{{ \"component\": \"orchestrator\", \"current_version\": \"X.X.X\" }}, "
                       f"{{ \"component\": \"gateway\", \"current_version\": \"X.X.X\" }}, "
                       f"{{ \"component\": \"edge\", \"current_version\": \"X.X.X\" }}] }}"
            )
        
        # Créer l'exécuteur de tools qui a accès à la DB
        def tool_executor(function_name: str, arguments: dict) -> dict:
            return execute_pdf_tool(function_name, arguments, db)
        
        # Construire le contexte initial avec version overview
        context_parts = []
        context_parts.append(f"DATE ACTUELLE: {current_date}\n")
        
        # === AJOUT: SD-WAN SOFTWARE VERSION OVERVIEW (par défaut) ===
        context_parts.append("=== SD-WAN SOFTWARE VERSION OVERVIEW ===\n")
        
        # Gateway Versions
        all_gateways = db.query(GatewayVersion).order_by(GatewayVersion.version.desc()).all()
        if all_gateways:
            context_parts.append("📡 GATEWAY VERSIONS:")
            for gw in all_gateways[:15]:  # Top 15 versions
                eol_marker = " ⚠️ EOL" if gw.is_end_of_life else ""
                release = f" (Released: {gw.release_date})" if gw.release_date else ""
                pdf = f" [PDF: {gw.source_file}]" if gw.source_file else ""
                context_parts.append(f"  • {gw.version}{eol_marker}{release}{pdf}")
        
        # Edge Versions
        all_edges = db.query(EdgeVersion).order_by(EdgeVersion.version.desc()).all()
        if all_edges:
            context_parts.append("\n🔷 EDGE VERSIONS:")
            for edge in all_edges[:15]:  # Top 15 versions
                eol_marker = " ⚠️ EOL" if edge.is_end_of_life else ""
                release = f" (Released: {edge.release_date})" if edge.release_date else ""
                pdf = f" [PDF: {edge.source_file}]" if edge.source_file else ""
                context_parts.append(f"  • {edge.version}{eol_marker}{release}{pdf}")
        
        # Orchestrator Versions
        all_orchestrators = db.query(OrchestratorVersion).order_by(OrchestratorVersion.version.desc()).all()
        if all_orchestrators:
            context_parts.append("\n🎛️ ORCHESTRATOR VERSIONS:")
            for orch in all_orchestrators[:15]:  # Top 15 versions
                eol_marker = " ⚠️ EOL" if orch.is_end_of_life else ""
                release = f" (Released: {orch.release_date})" if orch.release_date else ""
                pdf = f" [PDF: {orch.source_file}]" if orch.source_file else ""
                context_parts.append(f"  • {orch.version}{eol_marker}{release}{pdf}")
        
        context_parts.append("\n=== CONFIGURATION ACTUELLE ET CIBLES LTS ===\n")
        context_parts.append("🎯 OBJECTIF: Tous les composants doivent être upgradés vers leur version LTS (dernière version stable non-EOL)\n")
        
        # Liste des PDFs disponibles pour information
        available_pdfs = list_available_pdfs("all", db)
        context_parts.append(f"\n📁 PDFs disponibles: {available_pdfs['total']} fichiers")
        context_parts.append("Tu peux utiliser les outils (tools) pour consulter les PDFs des versions cibles.\n")
        
        for version_info in request.versions:
            component_raw = version_info.component.lower().strip()
            current_ver = version_info.current_version
            
            # Normaliser le nom du composant
            if "gateway" in component_raw or "gateaway" in component_raw:
                component = "gateway"
            elif "edge" in component_raw:
                component = "edge"
            elif "orchestrator" in component_raw or "vco" in component_raw:
                component = "orchestrator"
            else:
                continue  # Skip invalid components (already validated above)
            
            # Récupérer le modèle approprié
            if component == "gateway":
                Model = GatewayVersion
            elif component == "edge":
                Model = EdgeVersion
            elif component == "orchestrator":
                Model = OrchestratorVersion
            else:
                continue
            
            # Déterminer automatiquement la version LTS (dernière version non-EOL)
            lts_version = db.query(Model).filter(
                Model.is_end_of_life == False
            ).order_by(Model.version.desc()).first()
            
            if lts_version:
                lts_ver = lts_version.version
                context_parts.append(f"\n--- {component.upper()} ---")
                context_parts.append(f"Version actuelle: {current_ver}")
                context_parts.append(f"Version cible (LTS): {lts_ver} ✨")
                
                # Show LTS version PDF information
                context_parts.append(f"\n📄 PDF de la version LTS {lts_version.version}:")
                if lts_version.source_file:
                    context_parts.append(f"  Fichier: {lts_version.source_file}")
                if lts_version.release_date:
                    context_parts.append(f"  📅 Release: {lts_version.release_date}")
                if lts_version.end_of_life_date:
                    context_parts.append(f"  ⏰ EOL: {lts_version.end_of_life_date}")
            else:
                context_parts.append(f"\n--- {component.upper()} ---")
                context_parts.append(f"Version actuelle: {current_ver}")
                context_parts.append(f"⚠️ Aucune version LTS trouvée")
        
        context = "\n".join(context_parts)
        
        # Prompt avec awareness des tools
        prompt = f"""Tu es un expert en infrastructure SD-WAN (VeloCloud/VMware/Arista).

{context}

=== OUTILS DISPONIBLES ===
Tu as accès à 3 outils puissants:
1. **list_available_pdfs**: Liste tous les PDFs disponibles avec métadonnées
2. **get_pdf_content**: Récupère le contenu complet d'un PDF spécifique
3. **search_pdf_for_version**: Recherche une version spécifique dans tous les PDFs

UTILISE CES OUTILS pour:
- Récupérer les PDFs des **versions cibles/voulues** (target versions)
- Lire les release notes et instructions détaillées pour les versions cibles
- Vérifier les pré-requis et compatibilités des nouvelles versions
- Identifier les versions intermédiaires nécessaires pour atteindre la cible

=== RÈGLES IMPORTANTES ===
1. **DÉPENDANCES**: Edge dépend de Gateway, Gateway dépend d'Orchestrator
2. **COMPATIBILITÉ**: Vérifier que chaque composant est compatible avec les autres
3. **PRÉ-REQUIS**: ESXi, dépendances système, versions minimales requises
4. **UTILISER LES PDFS**: Récupère les informations détaillées depuis les PDFs sources
5. **NE PAS UTILISER** les version RXXXX-YYYYMMDD-GA
6. **⚠️ UPGRADES MULTI-ÉTAPES CRITIQUES**: Les sauts de version directs ne sont RAREMENT possibles!
   - Un upgrade de 1.8.0 → 3.2.0 peut nécessiter des étapes intermédiaires (ex: 1.8.0 → 2.0.0 → 3.0.0 → 3.2.0)
   - TOUJOURS vérifier dans les PDFs si des versions intermédiaires sont requises
   - Identifier TOUTES les versions de passage nécessaires pour maintenir la compatibilité
   - Respecter les chemins d'upgrade recommandés par le fabricant

=== 🛡️ ÉTAPE DE PLANNING ET VALIDATION (CRITIQUE) ===
**AVANT de commencer la consultation des PDFs**, tu DOIS effectuer une analyse de faisabilité:

1. **PHASE DE PLANNING INITIAL** (avant consultation PDFs):
   - Analyser l'écart de versions entre current et target pour chaque composant
   - Identifier les sauts de versions majeurs (ex: 4.x → 6.x) qui nécessitent forcément des étapes intermédiaires
   - Vérifier que les versions actuelles peuvent "survivre" pendant l'upgrade des autres composants
   - ⚠️ **RISQUE CRITIQUE**: Un Edge 4.x peut perdre la connectivité si l'Orchestrator passe directement en 6.x

2. **VALIDATION DE COMPATIBILITÉ À CHAQUE ÉTAPE**:
   - Après chaque étape d'upgrade planifiée, vérifier que TOUS les composants restent compatibles
   - Exemple: Si Orchestrator passe de 5.2 → 6.0, vérifier que Edge 4.2 peut toujours communiquer
   - Si incompatibilité détectée, AJOUTER des étapes intermédiaires pour maintenir la compatibilité
   - Utiliser les PDFs pour confirmer les matrices de compatibilité

3. **CONTRÔLE FINAL DE FAISABILITÉ** (après génération du plan):
   - Valider que la procédure complète est réalisable sans perte de connectivité
   - Vérifier que chaque étape respecte les prérequis des étapes précédentes
   - S'assurer qu'aucun composant ne se retrouve isolé pendant le processus
   - Confirmer que l'ordre Orchestrator → Gateway → Edge est maintenu avec compatibilité garantie

**STRATÉGIE DE SÉCURITÉ**:
- Privilégier les upgrades progressives et coordonnées (tous les composants avancent ensemble)
- Si un composant est trop ancien, le faire progresser AVANT d'upgrader les autres
- Exemple: Si Edge est en 4.x et Orchestrator/Gateway en 5.x, upgrade Edge vers 5.x AVANT de monter Orchestrator/Gateway vers 6.x

=== TÂCHE ===
Génère un guide d'upgrade CONCIS en format TEXTE avec UNE SEULE section:

📝 **PLAN D'UPGRADE ÉTAPE PAR ÉTAPE**

⚠️ **FORMAT REQUIS**: Liste numérotée UNIQUEMENT, une ligne par upgrade

EXEMPLE DU FORMAT ATTENDU:
1. Mettre à jour l'Orchestrator de la version 2.1.0 à la version 2.5.0.
2. Mettre à jour l'Orchestrator de la version 2.5.0 à la version 3.0.0.
3. Mettre à jour le Gateway de la version 2.0.0 à la version 2.5.0.
4. Mettre à jour l'Edge de la version 1.8.0 à la version 2.0.0.
5. Mettre à jour le Gateway de la version 2.5.0 à la version 3.0.0.
6. Mettre à jour l'Edge de la version 2.0.0 à la version 3.0.0.
7. Mettre à jour l'Orchestrator de la version 3.0.0 à la version 3.2.0.
8. Mettre à jour le Gateway de la version 3.0.0 à la version 3.2.0.
9. Mettre à jour l'Edge de la version 3.0.0 à la version 3.2.0.

**RÈGLES STRICTES**:
- Format EXACT: "X. Mettre à jour le [Component] de la version [version actuelle] à la version [version cible]."
- UNE SEULE ligne par étape d'upgrade
- INCLURE TOUTES les versions intermédiaires nécessaires
- PAS de descriptions, PAS de détails, SEULEMENT la liste numérotée
- Utiliser "Orchestrator" (pas VCO), "Gateway", "Edge" dans les noms
- Utiliser les noms complet des Edges (ex: "Edge 840") si mentionné dans les instructions d'upgrade
- Terminer chaque ligne par un point

**IMPORTANT**: 
- Génère UNIQUEMENT la liste numérotée, rien d'autre
- Pas de résumé, pas d'analyse, pas de notes
- Juste les étapes d'upgrade en français, format strict

**INSTRUCTIONS D'EXÉCUTION**: 
- Consulte les PDFs disponibles avec list_available_pdfs pour identifier les versions
- Base ton analyse sur les chemins d'upgrade documentés dans les PDFs
- IL Y AURA TOUJOURS des versions intermédiaires (pas de sauts de 4.x à 6.x)
- Respecte STRICTEMENT l'ordre: Orchestrator → Gateway → Edge
- Génère UNIQUEMENT la liste numérotée, sans explications supplémentaires
"""
        
        # Fonction de validation de la réponse
        def validate_upgrade_plan(result: Any, components: dict) -> dict:
            """
            Valide que le plan d'upgrade répond aux critères de qualité et sécurité.
            
            Args:
                result: Peut être un str ou un dict avec le contenu de la réponse
                components: Dict des versions actuelles par composant
            
            Returns:
                dict avec 'valid' (bool), 'comments' (list), 'score' (int 0-100)
            """
            comments = []
            score = 100
            
            # Extraire le texte du résultat (peut être dict ou str)
            text_result = ""
            if isinstance(result, dict):
                # Essayer d'extraire le texte depuis différents champs possibles
                if 'reasoning' in result:
                    text_result = str(result['reasoning'])
                elif 'content' in result:
                    text_result = str(result['content'])
                elif 'result' in result:
                    text_result = str(result['result'])
                else:
                    # Convertir tout le dict en string
                    text_result = json.dumps(result, ensure_ascii=False)
            else:
                text_result = str(result)
            
            # Vérifier que la réponse contient des étapes numérotées
            import re
            steps = re.findall(r'^\d+\.\s+Mettre à jour', text_result, re.MULTILINE | re.IGNORECASE)
            if len(steps) == 0:
                comments.append("❌ CRITIQUE: Aucune étape d'upgrade numérotée trouvée")
                score -= 50
            else:
                comments.append(f"✅ {len(steps)} étapes d'upgrade détectées")
            
            # Vérifier la présence des 3 composants dans le plan
            has_orchestrator = bool(re.search(r'Orchestrator', text_result, re.IGNORECASE))
            has_gateway = bool(re.search(r'Gateway', text_result, re.IGNORECASE))
            has_edge = bool(re.search(r'Edge', text_result, re.IGNORECASE))
            
            if not has_orchestrator:
                comments.append("⚠️ MANQUANT: Aucune mise à jour d'Orchestrator trouvée")
                score -= 20
            if not has_gateway:
                comments.append("⚠️ MANQUANT: Aucune mise à jour de Gateway trouvée")
                score -= 20
            if not has_edge:
                comments.append("⚠️ MANQUANT: Aucune mise à jour d'Edge trouvée")
                score -= 20
            
            if has_orchestrator and has_gateway and has_edge:
                comments.append("✅ Les 3 composants sont présents dans le plan")
            
            # Vérifier l'ordre des composants (Orchestrator avant Gateway avant Edge)
            orchestrator_positions = [m.start() for m in re.finditer(r'Orchestrator', text_result, re.IGNORECASE)]
            gateway_positions = [m.start() for m in re.finditer(r'Gateway', text_result, re.IGNORECASE)]
            edge_positions = [m.start() for m in re.finditer(r'Edge(?!\s*\d)', text_result, re.IGNORECASE)]
            
            if orchestrator_positions and gateway_positions and edge_positions:
                # Vérifier que le premier Orchestrator apparaît avant le premier Gateway
                if orchestrator_positions[0] > gateway_positions[0]:
                    comments.append("⚠️ ORDRE: Gateway mis à jour avant Orchestrator (ordre non respecté)")
                    score -= 15
                
                # Vérifier que le premier Gateway apparaît avant le premier Edge
                if gateway_positions[0] > edge_positions[0]:
                    comments.append("⚠️ ORDRE: Edge mis à jour avant Gateway (ordre non respecté)")
                    score -= 15
            
            # Vérifier la présence de versions dans les étapes
            version_pattern = r'\d+\.\d+\.\d+'
            versions_found = re.findall(version_pattern, text_result)
            if len(versions_found) < 4:  # Au minimum 2 étapes avec from/to versions
                comments.append("⚠️ VERSIONS: Peu de numéros de version détectés dans le plan")
                score -= 10
            else:
                comments.append(f"✅ {len(versions_found)} références de version trouvées")
            
            # Vérifier que les versions actuelles sont présentes
            for v in components.values():
                if v and v not in text_result:
                    comments.append(f"⚠️ Version actuelle {v} non trouvée dans le plan")
                    score -= 5
            
            # Validation finale
            is_valid = score >= 60  # Seuil minimum de 60/100
            
            if is_valid:
                comments.append(f"✅ VALIDATION RÉUSSIE - Score: {score}/100")
            else:
                comments.append(f"❌ VALIDATION ÉCHOUÉE - Score: {score}/100 (minimum requis: 60)")
            
            return {
                'valid': is_valid,
                'comments': comments,
                'score': score
            }
        
        # Extraire les versions actuelles pour la validation
        current_versions = {
            v.component: v.current_version 
            for v in request.versions
        }
        
        # Boucle de retry avec validation
        max_retries = 3
        validation_results = []
        
        for attempt in range(max_retries):
            # Générer le plan d'upgrade
            result = provider.analyze_with_tools(
                prompt=prompt,
                tools=PDF_RETRIEVAL_TOOLS,
                tool_executor=tool_executor,
                max_iterations=8
            )
            
            # Valider la réponse
            validation = validate_upgrade_plan(result, current_versions)
            validation_results.append({
                'attempt': attempt + 1,
                'validation': validation
            })
            
            # Si la validation est réussie, arrêter
            if validation['valid']:
                return {
                    "status": "success",
                    "result": result,
                    "prompt": prompt,
                    "input_versions": [v.dict() for v in request.versions],
                    "method": "function_calling_with_pdfs",
                    "validation": validation,
                    "attempts": attempt + 1,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            
            # Sinon, ajouter un feedback au prompt pour le prochain essai
            if attempt < max_retries - 1:
                feedback = "\n\n=== ⚠️ FEEDBACK DE VALIDATION ===\n"
                feedback += f"Tentative {attempt + 1} invalide (score: {validation['score']}/100):\n"
                for comment in validation['comments']:
                    feedback += f"  {comment}\n"
                feedback += "\nRÉGÉNÈRE un plan d'upgrade en respectant STRICTEMENT le format demandé.\n"
                prompt += feedback
        
        # Si après 3 tentatives, aucune validation réussie, retourner la meilleure tentative
        best_validation = max(validation_results, key=lambda x: x['validation']['score'])
        
        return {
            "status": "partial_success",
            "result": result,
            "prompt": prompt,
            "input_versions": [v.dict() for v in request.versions],
            "method": "function_calling_with_pdfs",
            "validation": best_validation['validation'],
            "attempts": max_retries,
            "all_validations": validation_results,
            "warning": f"Aucune tentative n'a atteint le score minimum (meilleur: {best_validation['validation']['score']}/100)",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")


@app.get("/api/list-pdfs", tags=["PDFs"])
async def list_pdfs_endpoint(component_type: str = "all", db: Session = Depends(get_db)):
    """
    Liste tous les PDFs disponibles avec leurs métadonnées.
    
    Parameters:
    - component_type: Filtrer par type (gateway, edge, orchestrator, ou all)
    
    Returns:
    - Liste des PDFs avec versions couvertes, dates, tailles
    """
    try:
        result = list_available_pdfs(component_type, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


