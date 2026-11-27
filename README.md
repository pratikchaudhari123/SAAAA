# SAAAA — Education ERP SaaS

**Web portal foundation** based on the Government College of Engineering Amravati MIS tender **GCOEA/MIS/ET-01/2026-2027** (59 pages).

**Important:** This is an early frontend demo, NOT production software, a completed educational ERP, or evidence of eligibility for the tender. All example metrics, students and activity are synthetic. Demo student additions live only in memory and disappear after a refresh. The demo entry screen has **no real authentication**.

## Run locally on Mac

```bash
git clone https://github.com/pratikchaudhari123/SAAAA.git
cd SAAAA
git switch feat/tender-web-portal-foundation
npm install
npm run dev
```

Then open the URL shown by Vite (usually **http://127.0.0.1:5173**). Choose the demonstration institution and click **Enter demo workspace**.

### Try the initial workflows
- Open the overview dashboard; see labelled synthetic metrics and activity.
- Navigate through the eight tender ERP modules, plus accreditation and system administration.
- Choose **Student Admissions** then **Student Directory**.
- Add an example student, filter by status, search by student/program and export CSV.
- Switch light/dark appearance; test at phone width.

## Verification

```bash
npm test
npm run build
```

Local metadata tests passed (3/3). A production build has **not been verified locally**, because the isolated authoring environment cannot install npm packages. The GitHub Actions workflow is intended to independently test the build after commit. Review its results before relying on the code.

## Technology decisions
- React, TypeScript and Vite web client.
- Planned Django REST Framework backend and PostgreSQL database.
- Modular monolith with server-enforced access control and dedicated institution database option.
- Later Flutter Android/iOS clients sharing documented APIs.
- No paid AI API needed for normal campus ERP operation.

## Documents
- [Architecture](docs/ARCHITECTURE.md)
- [Tender compliance matrix](docs/TENDER_COMPLIANCE_MATRIX.md)
- [Current implementation status](docs/IMPLEMENTATION_STATUS.md)

## Privacy and commercial caution
**This GitHub repository was public when work began.** Do not commit real student data, question papers, fees/bank details, secrets, vendor agreements or private college documents. Consider making the repository private before commercial development. A tender-compliant delivery would require functional modules, integrations, audits, mobile apps, training, support and independent bidder eligibility.

**Source rights:** Tender includes perpetual licence, documentation and source code handover provisions. Resolve licence, ownership and third-party component approval terms before production use.
