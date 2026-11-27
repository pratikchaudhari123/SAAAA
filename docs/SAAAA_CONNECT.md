# SAAAA Connect — integration contract and GCOEA readiness

Scope: development branch, synthetic evaluation only. References: GCOEA/MIS/ET-01/2026-2027 pp. 9–12, 18, 20, 22–24, 28–31, 36, 43, 46–47, 53. This is an implementation note, not a signed compliance declaration.

## Implemented in this release

- Admin-only source registration, token issuance, rotation and revocation; database stores the token digest, not the token itself.
- Machine-only HTTP POST /api/connect/events/ with Authorization: Bearer TOKEN and JSON. Request fields exactly external_id, subject_ref (opaque institutional identifier, not Aadhaar), event_type (attendance/in/out), occurred_at (ISO-8601 offset required). No images, biometric templates or raw device credentials.
- Unique source/event ID, identical retry acknowledged, conflicting retry rejected, time validation, tenant-scoped inbox. A device sending an event is not proof of biometric matching, current connectivity or attendance validity.
- Admin CSV import for student_id,name,email,program,year: max 500 rows / 500 KB per batch, validate and preview, skip existing IDs, create new records as Pending, record import batch and actor. No overwrite or deletion. The file digest is an integrity check, not a signed approval. Historical status, results, financial ledgers and linked documents need separate migration specifications.
- Setup > Connected systems; optional 15-second inbox refresh. Staged events do not change attendance automatically.
- Test: python3 scripts/connect_acceptance.py (local frontend on 5175 and API container saaaa-erp-api-1). Synthetic separate institution; disables QA user and device source afterward, keeps synthetic evidence.

## Provider integration gates

| Integration | Required authorized inputs | Remaining implementation |
|---|---|---|
| Old MIS | Schema or export, data dictionary, counts, source IDs, data retention and reconciliation policy | Full historical multi-entity mapping, dry run and reconciliation; use read-only export/API |
| Biometric | Brand/model, SDK/API, authorized gateway, device identifier mapping, enrollment policy, event format | Provider adapter, student/employee mapping, timetable and exam session matching, hostel movement and exception review |
| Tally | Version, licensed API availability, company and ledger mapping, accountant approval | Transaction outbox, idempotent posting, acknowledgement and reconciliation |
| Payment | Institute-owned merchant account, sandbox credentials, settlement policy | Signed webhook verification, idempotent posting, status reconciliation, refunds |
| Scanner | Institute-provided scanning hardware details, batch format and answer-book policy | Batch upload, scan QC, confidential identifiers, assigned evaluation |
| CCTV | Authorized existing VMS/NVR, access policy | Restricted viewing via provider API; no public camera exposure |
| Messaging | Approved provider and templates, institutional consent/policy | Outbox, delivery receipts, retries |
| ORCID/Scholar | Approved supported interfaces and licensing | Profile linking and authorized metadata sync; no scraping assumptions |

No provider is reported connected merely because its name appears in the UI. Do not store credentials in Git or expose local equipment on the public internet. Production requires HTTPS, rate limits, network controls, secret management, retention controls, full audit coverage and independent security testing. Obtain institute written approval for third-party components as required by the tender. Confirm hardware ownership, licensing, API availability and recurring costs before commercial quotation.

## Real deployment order

1. Obtain authorized inventory and representative anonymized exports.
2. Validate schemas and record counts in isolated staging.
3. Build and test provider adapter against approved test environment.
4. Run initial import, reconcile totals and exceptions with institute owners.
5. Run parallel synchronization and acceptance checks; cut over only after sign-off.
6. Monitor failed events and reconcile source and destination; retain approved rollback backups.
