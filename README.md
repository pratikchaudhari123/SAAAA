# SAAAA — Education Cloud ERP

Independent evaluation prototype for GCOEA/MIS/ET-01/2026-2027.

SAAAA includes a React/TypeScript frontend, Django REST backend, PostgreSQL persistence, institutional authentication, admissions, fees, hostel, academic configuration and a staged integration inbox. The latest development adds relational course offerings, scheduled sessions, attendance and initial examination applications/results. Evaluation previews remain separate from authenticated operations.

**Not production-ready or a declaration of tender compliance.** The last locally verified baseline is 6499654 (17 backend tests, 3 frontend metadata tests, 116 live checks). The new academic/exam release must pass its own build, migration and acceptance tests.

## Run the fresh team evaluation

Prerequisites: Git, Node/npm, Python 3 and Docker Compose. Ports 8100 and 5175 must be free.

```bash
git clone --branch feat/tender-web-portal-foundation https://github.com/pratikchaudhari123/SAAAA.git
cd SAAAA
bash scripts/team_setup.sh
```

Open http://127.0.0.1:5175/ and sign in using the private synthetic credentials file printed by the script.

Existing developer installations must use their existing Compose stack and backup/migration process, not the fresh team setup.

## Documentation

- [Team evaluation handover](docs/TEAM_HANDOVER.md)
- [Integration contract](docs/SAAAA_CONNECT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Tender compliance matrix (initial planning snapshot)](docs/TENDER_COMPLIANCE_MATRIX.md)
- [Implementation status (initial planning snapshot)](docs/IMPLEMENTATION_STATUS.md)

## Privacy and commercial caution

This repository was public when work began. Never commit real institutional records, passwords, API keys, question papers or confidential college documents. Review access and licensing before commercial sharing. No actual GCOEA system is connected. Production security, remaining tender modules, mobile applications, source-code handover and bidder eligibility must be independently completed and verified.
