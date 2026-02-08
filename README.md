# Bleu-Hackathon-Orange
Projet 1 - SD-WAN Velocloud

## 🚀 Quick Start

### Backend (FastAPI)

1. **Installation des dépendances**
```bash
cd back
pip install -r requirements.txt
```

2. **Démarrer l'API**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

3. **Accéder à la documentation**
- Swagger UI: http://localhost:3000/swagger
- ReDoc: http://localhost:3000/redoc
- Health Check: http://localhost:3000/health

### Frontend (React + Vite)

1. **Installation des dépendances**
```bash
cd projet-bleu
npm install
```

2. **Démarrer le frontend**
```bash
npm run dev
```

3. **Accéder à l'application**
- Local: http://localhost:5173

## 🌐 Live Demo

- **Frontend**: https://bleu_front.clementpickel.fr
- **Backend API**: https://bleu.clementpickel.fr
- **API Documentation**: https://bleu.clementpickel.fr/swagger

## 📦 Architecture

- **Backend**: FastAPI (Python) - Port 3000
- **Frontend**: React + Vite - Port 5173
- **Database**: SQLite
- **LLM**: OpenAI GPT-4 avec function calling pour analyse des PDFs

## 🔑 Fonctionnalités

- Extraction automatique d'informations depuis les PDFs SD-WAN
- Analyse intelligente des chemins d'upgrade avec validation
- Génération de plans d'upgrade multi-composants (Orchestrator, Gateway, Edge)
- Système de validation et retry avec feedback progressif
- API RESTful complète avec documentation Swagger
