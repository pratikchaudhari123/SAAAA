# SAAAA — team evaluation handover

This is a synthetic, local evaluation prototype, not a tender-compliant production delivery. Use the development branch only. Do not expose this development server to the internet or import actual college records without authorization.

## Existing developer installation

Use the existing saaaa-erp Docker project, database backup and migrations. Do not run the new team compose stack on a Mac already using port 8100. Preserve all existing data.

## Fresh team clone (ports 8100 and 5175 must be free)

Prerequisites: Git, Node/npm, Python 3, Docker with Compose. Run from a new clone of the development branch.

```bash
git clone --branch feat/tender-web-portal-foundation https://github.com/pratikchaudhari123/SAAAA.git
cd SAAAA
bash scripts/team_setup.sh
```

Open http://127.0.0.1:5175/ and use Sign in to SAAAA. The script prints a private credentials file path. Do not share the file in chat or commit it. Every run of the seed command creates a new isolated synthetic institution; do not repeatedly seed unnecessarily.

## Demonstration sequence

1. Administrator: review live dashboard; review department, program, period and course masters.
2. Academics: inspect course offering, classroom, enrolled students and lecture schedule. Attempt duplicate or conflicting scheduling; it must be rejected.
3. Faculty: open assigned course schedule, record attendance by individual lecture. Other faculty offerings must not be visible in the new academic endpoint.
4. Student: sign in with assigned student account; see own fees, hostel and legacy attendance under My campus; see own course schedule and session attendance under Academics.
5. Examination controller: open Examinations, inspect preconfigured regular exam, verify application, close application window, enter marks (0–100 in the sample), publish only after all applications have marks.
6. Student: verify published result appears; marks must not be visible before publication.
7. Finance/warden/admissions: use verified legacy operational workflows.
8. Administrator: use Connected systems to register a synthetic source and validate a CSV import. The inbox is staged; no actual biometric validation occurs.
9. Principal: refresh dashboard to inspect scheduled classes, exam status, fees and hostel metrics.

Sample thresholds and dates are synthetic policies, not actual GCOEA rules.

## Verification status

Baseline 6499654: user's Mac reported 17 backend tests, 3 frontend metadata tests, 92 HTTP acceptance checks and 24 Connect acceptance checks, all passing; 16 institutional tables.

New release: 7 new models and 2 new backend test methods. Expected 23 institutional tables and 19 backend tests. New release is not yet verified on the user's Mac. Frontend metadata tests do not exercise browser buttons. The two prior live scripts assume the existing saaaa-erp-api-1 container and gcoea-demo institution; do not run them unchanged on the fresh team stack.

## Remaining high-priority engineering work

- Complete custom multi-role permission engine, department-level restrictions across legacy APIs, account lifecycle and recovery.
- Recurring timetable, holiday calendar, batch/sub-batch configuration, syllabus and LMS. Current sessions are explicitly scheduled, not automatically generated.
- Biometric identity mapping, authorized hardware adapters and event-to-session processing; no external device connected.
- Exam fees, hall tickets, automatic exam timetable/seating, question papers, answer-sheet scanning, encrypted identifiers, examiner assignment, question-level marks, digital annotation, moderation, revaluation and CO–PO reports.
- Full HR, financial accounting, placement, alumni, document issuance and accreditation workflows.
- Historical migration and provider integrations, Android/iOS, secure production deployment, backup recovery, load tests, independent security testing.
- Migration files must be reconciled with the existing developer migration history and committed before a reproducible production release. Fresh team setup generates migrations only for an isolated new database.

The college must provide approved policy definitions, authorized historical export, device inventory and vendor API/SDK access. Its actual data, hardware and software are not connected. Bidder eligibility and commercial/contractual compliance require independent review.

## Latest verification and account administration

On the existing developer Mac, release 7cb76b0 passed 19 backend tests, three frontend metadata tests, 92 existing HTTP checks and 24 Connect HTTP checks (138 checks combined). All 23 institutional tables were migrated successfully. The synthetic team dataset was generated. Independent fresh-clone and browser acceptance are not yet verified.

New follow-up release adds Institution Setup > User accounts: admin-only staff/student account creation, linking an active unlinked student and generated passwords returned once. Password expiry, recovery, role changes and full multi-role permissions remain pending. Two new backend test methods and scripts/academic_acceptance.py cover provisioning and the academic/exam lifecycle. These new changes require runtime verification. Expected backend test count: 21. On the existing developer stack run python3 scripts/academic_acceptance.py after backend restart; it creates a separate synthetic institution and disables disposable accounts afterward. No real GCOEA data is used.

## Verified baseline 34b2c3c and question evaluation follow-up

The developer Mac reported 21 backend tests, 3 frontend metadata tests and 86 new academic HTTP acceptance checks, all passing, at 34b2c3c. Prior 92 operational and 24 integration HTTP checks passed at 7cb76b0. Combined historical count: 226 checks, not 226 independent tender requirements. GitHub Web checks also passed at 34b2c3c.

New release: Examinations > Question evaluation. COE/admin enters question codes, maxima, optional CO/Bloom labels while the exam is open; maxima must equal the exam maximum before closing. After exam date is reached and applications close, assign an unmarked application to an authorized faculty account. Faculty sees its assigned book reference, enters question marks and submits. Controller reviews, returns with a reason or approves. Approved totals populate the exam application; results cannot publish until all question evaluations are approved. Existing total-marks exams without a question plan remain supported. The book reference is a random UUID, not an encrypted printed barcode or a scanned answer sheet. Faculty identity masking applies to this evaluation API only, not all legacy directory endpoints. No scan upload, PDF viewer, graphical annotation, optional-question rules, rubric calculations, examiner reassignment or revaluation is included. Incorrect question plan entries cannot yet be edited in the pilot. Use a fresh synthetic examination if necessary.

Three new models: ExamQuestion, BookEvaluation and QuestionScore. Expected 26 institutional tables, 22 backend test methods. New code requires migration/build and runtime verification before being presented as working. Do not seed additional institutions unnecessarily; use the existing team demo or create a synthetic exam in it. For a live walkthrough configure Q1=40 and Q2=60 on a 100-mark exam, assign an examiner, enter 32 and 52, submit, approve and publish 84/100. Use synthetic records only.
