# Bleu-Hackathon-Orange
Projet 1 - SD-WAN Velocloud

## 🚀 Quick Start

### Démarrer l'application avec Docker

1. **Démarrer tous les services**
```bash
docker-compose up --build
```

2. **Démarrer en arrière-plan**
```bash
docker-compose up -d --build
```

3. **Arrêter les services**
```bash
docker-compose down
```

4. **Arrêter et supprimer les volumes**
```bash
docker-compose down -v
```

5. **Accéder à l'application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger UI: http://localhost:8000/swagger
- ReDoc: http://localhost:8000/redoc

## 🌐 Live Demo

- **Frontend**: https://bleu_front.clementpickel.fr
- **Backend API**: https://bleu.clementpickel.fr
- **API Documentation**: https://bleu.clementpickel.fr/swagger

## 📦 Architecture

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite
- **Database**: SQLite
- **LLM**: OpenAI GPT-4 avec function calling pour analyse des PDFs, llama-3.3-70b-versatile pour l'extraction d'information des PDFs

## 🔑 Fonctionnalités

- Extraction automatique d'informations depuis les PDFs SD-WAN
- Analyse intelligente des chemins d'upgrade avec validation
- Génération de plans d'upgrade multi-composants (Orchestrator, Gateway, Edge)
- Système de validation et retry avec feedback progressif
- API RESTful complète avec documentation Swagger
