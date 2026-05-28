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
Imported Flipper files can also be used by setting `SIMULATOR_CARD_FILE`.

API test path:

1. Create a session with `POST /api/v1/sessions`.
2. Start it with `POST /api/v1/sessions/{session_id}/start`.
3. Run a simulated scan:

```bash
curl -X POST http://localhost:8000/api/v1/sessions/{session_id}/scan/simulate \
  -H "Content-Type: application/json" \
  -d "{}"
```

Optional simulator filters:

```json
{
  "technology": "HF/NFC",
  "card_type": "MIFARE Classic 1K",
  "source": "flipper-import",
  "dataset": "uberguidoz-flipper",
  "file_type": "nfc",
  "uid": "04:A1:B2:C3:D4:E5:80"
}
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
8. Select a card UID to open the card details page.

## Test Operator Panel

Open a session details page at:

```text
http://localhost:3000/sessions/{session_id}
```

The operator panel shows:

- Session information
- Start/stop/delete controls
- Simulated scan controls with technology, card type, source, dataset, file type, and UID filters
- Detected card table
- Latest normalized evidence JSON

## Test Card Details

Open a detected card details page at:

```text
http://localhost:3000/cards/{card_id}
```

The card details page shows:

- UID, card type, technology, frequency, protocol, and risk level
- Related session link
- Risk finding summary and recommendation
- Finding evidence JSON
- Normalized data JSON
- Raw output JSON

## Test Risk Analysis Engine

The risk analysis engine runs automatically after each simulated scan. It saves a finding for the detected card, updates the card risk level, and exposes finding APIs in Swagger.
Rules use normalized simulator evidence, including UID byte length, protocol, Flipper file type, ATQA/SAK, RFID bit length, memory summary, dataset name, and source path when those fields are available.

API test path:

1. Create a session with `POST /api/v1/sessions`.
2. Start it with `POST /api/v1/sessions/{session_id}/start`.
3. Run a simulated scan with `POST /api/v1/sessions/{session_id}/scan/simulate`.
4. List risk findings for that session:

```bash
curl http://localhost:8000/api/v1/sessions/{session_id}/findings
```

5. List risk findings for a detected card:

```bash
curl http://localhost:8000/api/v1/cards/{card_id}/findings
```

6. List all local findings:

```bash
curl http://localhost:8000/api/v1/findings
```

Frontend test path:

1. Open http://localhost:3000/sessions.
2. Create and start a simulator session.
3. Run a simulated scan.
4. Confirm the operator panel shows the generated risk finding.
5. Select the card UID and confirm the card details page shows the finding summary, recommendation, and evidence.

Backend rule-test suite:

```powershell
docker compose --env-file .env.example exec -T backend python -m unittest discover -s app/tests -v
```

The tests cover configurable LF credentials, MIFARE Classic with and without memory dumps, HID Prox, short HF UIDs, basic LF identifiers, NFC tags, imported dataset manual review, and generic manual review.

## Import Flipper Mock Data

PASS-PAC can import local Flipper Zero `.nfc` and `.rfid` files into simulator-ready card JSON.
The importer preserves parsed Flipper fields such as NFC device type, ATQA, SAK, MIFARE type, memory block/page summary, RFID key type, bit length, dataset path, and source file hash.

1. Clone or download the Flipper dataset outside this project. A sparse clone keeps only importable NFC/RFID files in the local working tree:

```powershell
git clone --depth 1 --filter=blob:none --sparse https://github.com/UberGuidoZ/Flipper.git C:\Datasets\Flipper
git -C C:\Datasets\Flipper sparse-checkout init --no-cone
git -C C:\Datasets\Flipper sparse-checkout set "/NFC/**/*.nfc" "/RFID/**/*.rfid"
```

2. Import cards into `mock-data/`, preserving the built-in LF/HF simulator samples as fallback data:

```powershell
python mock-data\tools\import_flipper.py --source C:\Datasets\Flipper --output mock-data\flipper-imported-cards.json --merge-existing mock-data\sample-cards.json
```

3. Use the imported cards in simulator mode:

```powershell
$env:SIMULATOR_CARD_FILE="flipper-imported-cards.json"
docker compose up --build
```

For a small local importer test:

```powershell
python mock-data\tools\import_flipper.py --source mock-data\fixtures\flipper-sample --output mock-data\flipper-imported-cards.example.json
```

Generated large Flipper imports are ignored by git by default. The checked-in example file is only a tiny fixture output.

To test the simulator with the checked-in Flipper example:

```powershell
$env:SIMULATOR_CARD_FILE="flipper-imported-cards.example.json"
docker compose up --build
```

Then create and start a session, run a simulated scan with `source` set to `flipper-import`, and check the generated finding evidence for `dataset_info`, `uid_format`, `memory`, and `flipper`.

## Current Scope

Implemented:
- FastAPI backend
- `/health` endpoint
- PostgreSQL connection through Docker Compose
- SQLAlchemy `scan_sessions` table
- SQLAlchemy `detected_cards` table
- Session CRUD and start/stop APIs
- Simulated scan API
- Card list and card detail APIs
- Rule-based risk analysis engine
- Dataset-aware simulator evidence normalization
- Finding model and findings APIs
- Local mock LF/HF/NFC card data
- Flipper `.nfc` / `.rfid` importer for simulator datasets
- Next.js dashboard page
- Sessions management page
- Session details / operator panel page
- Card details page
- Tailwind CSS setup
- Local reports and mock data folders
- Placeholder boundary for future Proxmark adapter

Not implemented yet:
- Authentication
- Real RFID/NFC scans
- Report generation
- Proxmark integration
