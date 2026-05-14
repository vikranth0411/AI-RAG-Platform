# AI RAG Platform

Production-oriented starter architecture for a full-stack AI-powered Retrieval-Augmented Generation application.

## Stack

- Backend: Python, FastAPI, PostgreSQL, SQLAlchemy, LangChain, ChromaDB, Sentence Transformers
- Frontend: React, Vite, Tailwind CSS
- Infrastructure: Docker Compose

## Planned Capabilities

- JWT authentication
- File uploads
- RAG pipeline
- Groq Llama integration
- Natural language to SQL
- AI code understanding
- Chat system
- Conversation memory

This repository currently contains architecture and boilerplate only. Feature logic is intentionally not implemented yet.

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── workers/
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── pages/
│   │   ├── routes/
│   │   ├── services/
│   │   └── styles/
│   ├── Dockerfile
│   └── package.json
├── data/
│   ├── chroma/
│   └── uploads/
├── docker-compose.yml
└── .env.example
```

## Local Development

1. Create environment file:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker compose up --build
```

3. Open:

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

## Backend Notes

The backend is organized by responsibility:

- `api/`: HTTP route modules and dependency wiring
- `core/`: settings, security, logging, and shared application configuration
- `db/`: database session and migration integration
- `models/`: SQLAlchemy ORM models
- `schemas/`: Pydantic request and response contracts
- `repositories/`: database access layer
- `services/`: business and AI orchestration services
- `workers/`: background task entry points

## Frontend Notes

The frontend uses feature-oriented organization:

- `features/`: domain-specific UI and state modules
- `components/`: shared reusable components
- `services/`: API clients
- `routes/`: route definitions
- `lib/`: framework-neutral helpers and configuration

