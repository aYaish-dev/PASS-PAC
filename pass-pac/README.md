# PASS-PAC

PASS-PAC is a local-first professional web dashboard foundation for authorized RFID/NFC physical access security assessment. The project runs locally only.

## Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: Python, FastAPI, SQLAlchemy
- Database: PostgreSQL
- Local runtime: Docker Compose
- Local folders: `reports/` and `mock-data/`

## Project Structure

```text
pass-pac/
|-- frontend/
|-- backend/
|-- database/
|-- reports/
|-- mock-data/
|-- docs/
|-- docker-compose.yml
|-- README.md
|-- .env.example
`-- .gitignore
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

## Test Session Management

Open Swagger at http://localhost:8000/docs and use the `sessions` endpoints:

- `GET /api/v1/sessions`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `PATCH /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/start`
- `POST /api/v1/sessions/{session_id}/stop`
- `DELETE /api/v1/sessions/{session_id}`

Example create request:

```json
{
  "session_name": "Lobby baseline assessment",
  "description": "Authorized local simulator session",
  "mode": "simulator",
  "environment": "local"
}
```

Frontend test path:

1. Open http://localhost:3000.
2. Select `Manage Sessions`.
3. Create a session.
4. Select the session name or `Open` to enter the operator panel.
5. Use `Start`, `Stop`, and `Delete` from the sessions table or operator panel.

## Test Simulator Scan

The simulator uses local card samples from `mock-data/sample-cards.json`.

API test path:

1. Create a session with `POST /api/v1/sessions`.
2. Start it with `POST /api/v1/sessions/{session_id}/start`.
3. Run a simulated scan:

```bash
curl -X POST http://localhost:8000/api/v1/sessions/{session_id}/scan/simulate \
  -H "Content-Type: application/json" \
  -d "{}"
```

4. List detected cards for the session:

```bash
curl http://localhost:8000/api/v1/sessions/{session_id}/cards
```

Frontend test path:

1. Open http://localhost:3000/sessions.
2. Create a session.
3. Select the session name or `Open`.
4. Select `Start Session`.
5. Choose optional simulator filters.
6. Select `Run Simulated Scan`.
7. Confirm the detected card table and latest raw evidence update.

## Test Operator Panel

Open a session details page at:

```text
http://localhost:3000/sessions/{session_id}
```

The operator panel shows:

- Session information
- Start/stop/delete controls
- Simulated scan controls
- Detected card table
- Latest normalized evidence JSON

## Current Scope

Implemented:
- FastAPI backend
- `/health` endpoint
- PostgreSQL connection through Docker Compose
- SQLAlchemy `scan_sessions` table
- SQLAlchemy `detected_cards` table
- Session CRUD and start/stop APIs
- Simulated scan API
- Local mock LF/HF/NFC card data
- Next.js dashboard page
- Sessions management page
- Session details / operator panel page
- Tailwind CSS setup
- Local reports and mock data folders
- Placeholder boundary for future Proxmark adapter

Not implemented yet:
- Authentication
- Real RFID/NFC scans
- Card details page
- Risk analysis engine
- Report generation
- Proxmark integration
