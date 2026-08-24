# PASS-PAC

PASS-PAC (Portable Physical Access Security Assessment Platform) is a local-first dashboard for authorized RFID/NFC physical-access security research. It combines repeatable evidence collection, credential normalization, dataset-aware risk analysis, a documented 0-10 assurance score, controlled measurements, and local PDF/CSV research outputs.

The project was developed by Abdallah I. F. Yaish and Maria Riham Boukerou at Istanbul Medipol University under the supervision of Malik Geylani.

## Implemented Platform

- Next.js, React, TypeScript, and Tailwind CSS operator dashboard
- FastAPI and PostgreSQL backend managed with Docker Compose
- Assessment session lifecycle and credential evidence records
- Simulator data derived from public Flipper-format RFID/NFC samples
- Read-only Proxmark3 Easy 512K integration through a Windows host bridge
- LF/HF reconnaissance, parsed metadata, dataset correlation, and risk findings
- Systematic security assurance scoring with confidence and evidence coverage
- Controlled research measurements, session comparison, and PDF/CSV export
- Automated backend rule and service tests

PASS-PAC is intended only for owned or explicitly authorized credentials. Authentication, credential writing, and cloning are not part of the implemented platform.

## Quick Start

Install Docker Desktop, start it, and run:

```bash
git clone https://github.com/aYaish-dev/PASS-PAC.git
cd PASS-PAC/pass-pac
cp .env.example .env
docker compose up --build
```

Open:

- Dashboard: http://localhost:3000
- Backend: http://localhost:8000
- API documentation: http://localhost:8000/docs

Stop the stack with `Ctrl+C`, then run `docker compose down`.

## Documentation

See [pass-pac/README.md](pass-pac/README.md) for the complete setup guide, simulator workflow, Proxmark bridge instructions, API examples, and research methodology documentation.
