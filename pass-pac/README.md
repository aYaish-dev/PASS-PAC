# PASS-PAC

PASS-PAC is a local-first professional web dashboard for authorized RFID/NFC physical access security assessment. It includes database-backed assessment sessions, dataset-driven simulator scans, rule-based findings, controlled measurements, research reports, card details, and a safe read-only Proxmark3 integration. Authentication and card write/clone workflows are not implemented yet.

## Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: Python, FastAPI, SQLAlchemy
- Database: PostgreSQL
- Local runtime: Docker Compose
- Local folders: `reports/` and `mock-data/`
- Device bridge: Windows host-side Proxmark bridge for safe status and read-only identify commands

## Project Structure

```text
pass-pac/
|-- frontend/
|-- backend/
|-- database/
|-- reports/
|-- mock-data/
|-- docs/
|-- tools/
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

On Windows, start the Proxmark bridge in a second terminal when using the physical device:

```powershell
.\tools\start_proxmark_bridge.ps1
```

3. Open the local URLs:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Run on macOS (Simulator Mode)

The macOS setup runs the complete web application and simulator without a physical Proxmark3. Install Git and Docker Desktop for Mac, start Docker Desktop, and then run:

```bash
git clone https://github.com/aYaish-dev/PASS-PAC.git
cd PASS-PAC/pass-pac
cp .env.example .env
docker compose up --build
```

Wait until the frontend, backend, and PostgreSQL containers report that they are ready, then open:

- Dashboard: http://localhost:3000
- Sessions: http://localhost:3000/sessions
- Backend health: http://localhost:8000/health
- API documentation: http://localhost:8000/docs

Create a session with mode `simulator`, start it, and run a simulator scan. Physical Proxmark integration currently uses the Windows host bridge and is not required for simulator operation on macOS.

Stop the application with `Control-C`, followed by:

```bash
docker compose down
```

After the first clone, later updates only require:

```bash
git pull
docker compose up --build
```

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

## Session Management and Simulator

Session and evidence APIs:

- `GET|POST /api/v1/sessions`
- `GET|PATCH|DELETE /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/start`
- `POST /api/v1/sessions/{session_id}/stop`
- `POST /api/v1/sessions/{session_id}/scan/simulate`
- `GET /api/v1/sessions/{session_id}/cards`
- `GET /api/v1/sessions/{session_id}/findings`
- `GET /api/v1/cards` and `GET /api/v1/cards/{card_id}`
- `GET /api/v1/cards/{card_id}/dataset-correlation`
- `GET /api/v1/cards/{card_id}/intelligence`
- `GET /api/v1/cards/{card_id}/assurance?policy_id=university-standard`
- `GET|PUT|DELETE /api/v1/cards/{card_id}/assurance-evidence`
- `GET /api/v1/assurance/policies`
- `GET /api/v1/findings`
- `PATCH /api/v1/findings/{finding_id}`
- `GET|POST /api/v1/sessions/{session_id}/assessments`
- `GET /api/v1/sessions/{session_id}/assessments/{assessment_id}`
- `GET|POST /api/v1/sessions/{session_id}/commands`
- `GET /api/v1/sessions/{session_id}/recipes`
- `POST /api/v1/sessions/{session_id}/recipes/{recipe_key}`
- `GET /api/v1/sessions/{session_id}/assurance?policy_id=university-standard`
- `GET /api/v1/sessions/{session_id}/capabilities`
- `GET /api/v1/sessions/{session_id}/evidence-guidance?policy_id=university-standard`
- `GET|POST /api/v1/sessions/{session_id}/traces`
- `POST /api/v1/sessions/{session_id}/traces/device-buffer`
- `GET|DELETE /api/v1/sessions/{session_id}/traces/{trace_id}`

Open `http://localhost:3000/sessions` to create a session. Start it, run a simulator scan, review the generated finding, and open a detected card for normalized data, raw evidence, and recommendations.

The simulator reads `mock-data/flipper-imported-cards.json` by default. This file currently contains local simulator examples plus imported UberGuidoZ Flipper samples. Rebuild it from an authorized local dataset clone with:

```powershell
python mock-data\tools\import_flipper.py --source C:\Datasets\Flipper --merge-existing mock-data\sample-cards.json --output mock-data\flipper-imported-cards.json
```

Run the repeatable backend rule, parser, and session tests with:

```powershell
docker compose --env-file .env exec -T backend python -m unittest discover -s app/tests -v
```

Frontend checks:

```powershell
docker compose --env-file .env exec -T frontend npm run lint
docker compose --env-file .env exec -T frontend npm run build
```

## Proxmark3 Easy 512K Integration Foundation

The project includes the first safe Proxmark integration boundary. It is inspired by Proxmark3GUI and Phosphor ideas such as configurable client path, serial-port awareness, live command output, and operation status. The bridge exposes only allowlisted status and read-only identify commands.

Current device API:

- `GET /api/v1/device/proxmark/status`
- `POST /api/v1/device/proxmark/probe`
- `POST /api/v1/device/proxmark/identify/hf`
- `POST /api/v1/device/proxmark/identify/lf`
- `GET /api/v1/cards/profiles`

The bridge only runs these read-only commands:

```text
hw version
hw status
hw tune
hf search
lf search
hf 14a info
emv pse -s2
emv search -s
emv reader
emv list
hf mf info
hf mfu info
hf 15 info
hf mfdes info
hf iclass info
lf em 410x reader
lf hid reader
lf t55xx info
trace list -t 14a
trace list -t mf
trace list -t des
trace list -t 7816
trace list -t 15
trace list -t iclass
```

No cloning, writing, erase, dump, autopwn, key recovery, or brute-force workflow is implemented.

## Advanced ISO 14443-A and EMV Acquisition

The Session Operator Panel provides an **Advanced EMV** assessment profile for authorized contactless payment test cards. The workflow runs:

1. `hf search` and `hf 14a info` for transport identity, ATQA, SAK, ATS, and UID classification.
2. `emv pse -s2` for PPSE application discovery.
3. `emv search -s` for known payment-application AID enumeration.
4. `emv reader` for bounded GPO and application-record evidence.
5. `emv list` for a redacted ISO 7816 command history.

The parser retains application identifiers, payment-system mapping, application labels, language/currency metadata, effective and expiration dates, masked PAN (last four only), PAN sequence, status words, APDU counts, and evidence-presence flags. Full PAN, track data, cardholder name, and verification values are redacted before they reach FastAPI or PostgreSQL. The Windows wrapper starts the Proxmark client with `--incognito`, preventing command history and Proxmark session-log files for these runs.

See `docs/advanced-emv-acquisition.md` for the data-handling boundary and interpretation limits.

## Phase A: Guided Evidence Engine

The Session Operator Panel now includes a **Guided Evidence** workspace. It evaluates the current session against the selected assurance policy and returns a ranked evidence-acquisition sequence. Recommendations are deterministic and explain their rationale, expected evidence, safety tier, affected credentials, and any execution blocker.

The command and recipe definitions are stored once in `backend/app/core/proxmark_capabilities.json`. The FastAPI backend, Windows bridge, operator console, and guidance engine all derive their approved read-only commands from this versioned registry. Registry validation rejects state-changing entries in Phase A.

Phase A supports:

- device and antenna baseline recommendations
- protocol-specific HF/LF metadata recipes
- assurance-gap guidance for authentication, key management, clone/replay resistance, reader enforcement, and lifecycle controls
- controlled baseline and post-remediation experiment sequencing
- critical-path prioritization and passive trace-analysis guidance
- explicit evidence coverage, unknowns, and policy status for every credential

Methodology and current limitations are documented in `docs/guided-evidence-methodology.md`.

## Reader Transaction Analyzer

PASS-PAC 0.9 adds passive transaction-trace analysis. The Session Operator Panel can import complete Proxmark `trace list` text or retrieve and analyze the device's existing trace buffer through an audited command. Supported interpretations are ISO 14443-A, MIFARE Classic, MIFARE DESFire, ISO 7816-4, ISO 15693, and iCLASS.

The analyzer:

- normalizes reader-to-card and card-to-reader frames with timing, CRC, parity, and annotation evidence
- reconstructs common ISO 7816 APDUs and status words
- identifies selection, authentication, challenge-response, read, write, and update commands
- distinguishes an observed authentication exchange from a UID-only trust candidate
- reports repeated authentication-response candidates, modification commands, secure-messaging indicators, and trace-quality limitations
- stores the raw trace, SHA-256 evidence hash, normalized timeline, findings, confidence, and interpretation limitations in PostgreSQL

Trace conclusions are intentionally bounded. A passive RF capture does not reveal the controller's final door decision, and an incomplete capture cannot prove UID-only authorization.

Only `trace list` buffer-reading commands are added to the command allowlist. PASS-PAC does not start sniffing automatically in this phase; active capture requires a later bounded workflow with cancellation and timeout controls.

Environment variables:

```text
PROXMARK_BRIDGE_URL=
PROXMARK_CLIENT_PATH=
PROXMARK_PORT=
PROXMARK_COMMAND_TIMEOUT_SECONDS=10
```

For this Windows workstation, the bridge uses the matching ProxSpace client and `COM8`:

```powershell
PROXMARK_CLIENT_PATH=tools\proxspace_client.cmd
PROXMARK_PORT=COM8
```

Important Windows/Docker note:

- Docker Desktop on Windows usually cannot directly access a USB serial device such as a Proxmark3 Easy 512K through `COM8`.
- PASS-PAC uses a small local Windows bridge in `tools/proxmark_bridge.py` so the Docker backend can request safe hardware status without direct USB access.
- Start the bridge on Windows before probing the device from the Docker dashboard.

Start the bridge:

```powershell
cd "C:\Desktop\PASS-PAC\pass-pac"
.\tools\start_proxmark_bridge.ps1
```

Then run the Docker app with:

```text
PROXMARK_BRIDGE_URL=http://host.docker.internal:8765
PROXMARK_PORT=COM8
```

Bridge health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/status
Invoke-RestMethod http://127.0.0.1:8765/probe -Method Post
```

Read-only identify checks through the backend:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/device/proxmark/identify/hf -Method Post
Invoke-RestMethod http://localhost:8000/api/v1/device/proxmark/identify/lf -Method Post
Invoke-RestMethod http://localhost:8000/api/v1/cards/profiles
```

The bridge launcher uses the matching `v4.21611` client already installed under `C:\ProxSpace`. The allowlisted commands remain:

```powershell
hw version
hw status
hw tune
hf search
lf search
hf 14a info
emv pse -s2
emv search -s
emv reader
emv list
hf mf info
hf mfu info
hf 15 info
hf mfdes info
hf iclass info
lf em 410x reader
lf hid reader
lf t55xx info
```

If the probe reports that it cannot open `COM8`, close any existing Proxmark/Phosphor/pm3 terminal that is already connected to the device, then retry.

Successful live card detections are appended locally to:

```text
mock-data/live-card-observations.jsonl
```

The dashboard reads that local log and groups observations into saved card profiles. Live cards and saved profiles are compared with `mock-data/flipper-imported-cards.json` by an explainable weighted scorer. It considers exact UID, card and protocol family, technology, UID length, ATQA/SAK, memory layout, and LF bit length. Each match includes its score, confidence, source path, and the fields that contributed points.

The Card Details page shows the live card's dataset correlation. A score below the configured threshold is reported as no match; PASS-PAC does not force a relationship when the local dataset has insufficient evidence.

Current hardware phase includes family-specific metadata recipes, live dataset correlation, and parsing of UID classification and ISO14443-A ATS parameters. The next recommended phase is analyst review and disposition states for generated findings, followed by cross-session duplicate and anomaly analysis.

## Automated Reconnaissance v1

Create a session with mode `proxmark`, start it, and open its Operator Panel. The **Run Assessment** action performs a local, read-only workflow:

1. Verify bridge and device configuration.
2. Probe client and firmware visibility.
3. Capture hardware status and antenna tuning evidence.
4. Search HF and LF bands.
5. Select and execute a read-only card-family metadata recipe.
6. Parse metadata into normalized fields and run dataset-aware risk rules.
7. Preserve every step and raw command result in the database evidence timeline.

Supported metadata recipes:

- ISO14443-A generic information
- MIFARE Classic information and nonce indicators
- MIFARE Ultralight and NTAG product, memory, and protection metadata
- ISO15693 system and memory metadata
- DESFire and iCLASS tag information
- EM410x and HID Prox bounded reader metadata
- T55xx configuration information

Assessment APIs:

```text
POST /api/v1/sessions/{session_id}/assessments
GET  /api/v1/sessions/{session_id}/assessments
GET  /api/v1/sessions/{session_id}/assessments/{assessment_id}
```

The Windows bridge must be running before an assessment starts. The workflow does not expose writing, cloning, dumping, key recovery, brute force, or credential modification commands.

## Analyst Review and Operator Console

Findings can be reviewed from the Session Operator Panel with these local workflow states:

```text
open
confirmed
accepted
false_positive
resolved
```

Each update stores analyst notes plus reviewed and updated timestamps. The Operator Console accepts manually typed Proxmark commands and keeps an audit history of command, output, result, error, and time. Commands are validated independently by the backend adapter and Windows bridge against the documented read-only allowlist. Commands outside that allowlist are rejected and are not sent to the device.

## Advanced Assurance

Card Details includes a cross-session credential fingerprint. PASS-PAC normalizes the UID and compares card family, protocol, ATQA, SAK, UID classification, ATS, historical bytes, memory shape, and LF bit length across stored observations. It reports stable repeated identifiers separately from conflicting identity metadata and preserves the exact changed fields for analyst review.

The Operator Console also includes reusable assessment recipes:

- Device Baseline
- HF Identity
- MIFARE Metadata
- Type 2 Metadata
- LF Identity
- LF Legacy Metadata

Every recipe displays its exact read-only command sequence, uses the shared Proxmark device lock, and stores every command result in the session audit history.

## Security Assurance Scoring

PASS-PAC uses the deterministic, explainable Credential and Access Path Security Score v2.1. Every credential path is evaluated with the same five-domain 0-10 rubric:

- Authentication strength
- Key management
- Clone and replay resistance
- Reader and backend enforcement
- Lifecycle and monitoring

Each domain receives `0`, `1`, `2`, or `unknown`. Unknown evidence is not silently treated as a technical failure or success. PASS-PAC reports a provisional score, minimum-to-maximum possible score range, evidence coverage, confidence, and policy decision. Grades require at least 80% evidence coverage.

The Card Details page separates the first three credential-derived controls into a **Credential technical rating** and reports all five controls as **Complete access-path assurance**. Operators can add dated, sourced evidence for reader/backend enforcement and lifecycle monitoring. These records are stored independently from Proxmark output and immediately recalculate coverage, grade, and policy status.

Policy profiles set acceptance thresholds without changing the underlying technical score:

- **University Standard** for general campus buildings, laboratories, and staff areas
- **Restricted Area** for high-value laboratories, data rooms, and controlled research spaces
- **Legacy Transition** for credential inventory and phased migration programs

Analyst review is reported separately as `not started`, `in progress`, or `complete`. Resolving a finding does not increase the technical score; only new technical or operational evidence can change it.

Critical indicators such as verified UID-only authorization, UID-modifiable media, conflicting identity metadata, static LF identifiers, or observed default keys are reported explicitly. They do not activate an opaque score cap. A policy can transparently reject a path containing a critical failure.

The Card Details page shows the complete calculation and lets the operator switch policy profiles. The Session Operator Panel shows the average and lowest provisional scores, evidence gaps, policy outcomes, critical-failure count, and weakest credentials first.

Research definitions and formulas are documented in:

- `docs/research-methodology.md`
- `docs/security-score-v2.md`

The score describes the evidence observed by PASS-PAC. It is not a certification of the complete reader, controller, key-management, or backend access-control configuration.

## Controlled Research Measurements

Each session now has a **Research Measurements** workspace. It stores controlled trials separately from simulator samples and ordinary device observations. Operators first create an experiment batch containing authorization, equipment, firmware, antenna, location, and environmental controls. They then record every credential presentation with distance, orientation, timing, outcome, classification result, metadata quantity, extracted bytes, and RF conditions.

Linking a trial to a card observation automatically derives a SHA-256 evidence hash and fills missing card-family metadata. Session summaries calculate detection rate, correct identification, timing quartiles, technology comparisons, and the greatest distance satisfying the documented 4-of-5 repeatability rule. The **Analysis** view adds Wilson 95% confidence intervals, condition-level distance charts, partial-response counts, automated data-quality flags, and Access Path Security Score v2.1 results with evidence coverage and score ranges.

The complete data contract and calculations are documented in `docs/measurement-pipeline.md`.

## Research Reports And Remediation Comparison

The Research Measurements workspace exports an anonymized trial-level CSV, a condition-level statistical-analysis CSV, and a paginated academic PDF. All artifacts are written to `reports/session-{session_id}/` and downloaded by the browser. Operational UIDs, raw device output, keys, and door mappings are excluded; research aliases and evidence SHA-256 digests are retained.

Operators can select a batch labeled **Baseline** and a batch labeled **Post-remediation** to compare detection rate, classification accuracy, successful-identification median time, trial count, and reliable read distance. PASS-PAC reports descriptive deltas and sample sizes without claiming statistical significance.

The export boundary, CSV data dictionary, delta formula, privacy rules, and interpretation constraints are documented in `docs/reporting-methodology.md`.

## Current Scope

Implemented:

- Initial FastAPI backend
- `/health` endpoint
- Initial Next.js dashboard page
- Tailwind CSS setup
- Docker Compose with frontend, backend, and PostgreSQL
- SQLAlchemy connection to PostgreSQL
- Session create, list, update, start, stop, and delete APIs
- Sessions page, Session Details Operator Panel, and Card Details page
- Controlled experiment batches and trial-level research measurement workspace
- Detection, classification, timing-quartile, technology, and reliable-distance summaries
- Wilson 95% confidence intervals, condition-level charts, and automated quality flags
- Evidence-aware Credential and Access Path Security Score v2.1 alongside RF performance analysis
- Anonymized trial-level CSV, condition-level analysis CSV, and academic PDF research exports
- Baseline-versus-post-remediation batch comparison with transparent deltas
- Dataset-driven simulator scans stored as cards and findings
- Dataset-aware risk rules with repeatable automated tests
- Flipper `.nfc` and `.rfid` importer
- Local reports and mock data folders
- Proxmark3 status/probe adapter using a client that matches the device firmware
- Windows host-side Proxmark bridge
- Read-only HF/NFC and LF/125kHz identify panel
- Local live card observation log
- Saved card profile review with local dataset comparison
- Automated read-only assessment runs with hardware preflight and evidence timelines
- Family-specific metadata recipes with normalized fields and raw evidence
- Explainable dataset correlation for simulator, live cards, and saved profiles
- Live FNUID, ATS, historical-byte, timing, and protocol capability parsing
- Dataset and parser regression tests using repeatable fixtures
- Analyst finding status, notes, and review timestamps
- Audited read-only Operator Console with persistent command history
- Reusable multi-command assessment recipes with shared device locking
- Cross-session credential fingerprints, duplicate UID detection, and metadata anomaly evidence
- Versioned university, restricted-area, and legacy-transition assurance policies
- Explainable card scores, evidence coverage, explicit critical failures, and priority actions
- Session-level assurance rollups ordered from weakest credential to strongest
- Passive reader transaction trace import and audited Proxmark buffer retrieval
- Normalized frame timelines, APDU decoding, authentication-state analysis, and trace findings

Not implemented yet:

- Authentication
- Proxmark card read/write workflows
