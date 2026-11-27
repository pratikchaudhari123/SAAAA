# SAAAA Education ERP — Architecture

## Design principle
Build one reusable platform for multiple colleges and universities. The first deliverable is a React/TypeScript web frontend. Future production system: Python Django REST Framework, PostgreSQL, Celery and institution-specific deployment options. Use a modular monolith before evaluating microservices.

## Workspaces
1. Public marketing site (planned).
2. SaaS administration and provisioning (planned).
3. Institution ERP portal (**UI foundation in this branch**).
4. Flutter apps for Android/iOS (later milestone).

## Tenant isolation
Production must enforce isolation at the **backend and database level**. For GCOEA, plan a dedicated institutional database and deployment. A visual institution dropdown is not a security boundary. Platform operator access to student/financial/exam data must be tightly controlled.

## Authentication, authorization and security
The frontend contains only a clearly labelled demonstration entry screen. Implement server-side login, MFA, session controls, hierarchical roles, granular permissions, delegated role expiry, audit trails, encrypted file storage, IP access constraints, safe secrets, restore-tested backups, penetration tests and security reviews before handling real institutional data.

## Tender-specific scope
- Academic and NEP policy configuration, timetables, biometric/facial attendance, LMS and 360-degree feedback.
- Employee management and administration.
- Fee collection, ledger, reconciliation, scholarship, Tally and gateway interfaces.
- Admissions, student certificates, NEP multiple entry/exit.
- Exam registration, confidential questions, masked encrypted barcodes, answer-sheet scanning/on-screen evaluation, results, revaluation and CO-PO attainment.
- Hostel, placements and alumni.
- NBA/NAAC/NIRF reports.
- Historical migration from 2009, Android+iOS and on-campus support.

## Ownership and licensing
Tender requires perpetual licence plus documented source code, DB structure, manuals and software bill of materials at handover. Institution-owned data remains institution-owned. Establish contractual boundaries for reusable IP; review third-party components before integration.

## Frontend prototype limitations
Synthetic statistics and student records are in browser memory; changes disappear when refreshed. No backend, no secure login, no live third-party connectors, no production eligibility or acceptance proof.

## API development milestones
Identity & tenant -> students/admissions -> finance -> academics -> exams -> remaining modules -> third-party integrations -> security and data migration -> mobile APIs. Validate every feature against the compliance matrix and UAT evidence.
