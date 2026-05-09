# PASS-PAC

PASS-PAC is a local-first professional web dashboard foundation for authorized RFID/NFC physical access security assessment. This initial skeleton runs locally only and does not implement authentication, scans, reports, or Proxmark integration yet.

## Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: Python, FastAPI
- Database: PostgreSQL
- Local runtime: Docker Compose
- Local folders: `reports/` and `mock-data/`

## Project Structure

```text
pass-pac/
├── frontend/
├── backend/
├── database/
├── reports/
├── mock-data/
├── docs/
├── docker-compose.yml
├── README.md
├── .env.example
└── .gitignore
```

## Run Locally

1. Copy the example environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Start the local services:

```bash
docker compose up --build
```

3. Open the local URLs:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Backend Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "PASS-PAC Backend"
}
```

## Current Scope

Implemented:
- Initial FastAPI backend
- `/health` endpoint
- Initial Next.js dashboard page
- Tailwind CSS setup
- Docker Compose with frontend, backend, and PostgreSQL
- Local reports and mock data folders
- Placeholder boundary for future Proxmark adapter

Not implemented yet:
- Authentication
- RFID/NFC scans
- Report generation
- Proxmark integration
