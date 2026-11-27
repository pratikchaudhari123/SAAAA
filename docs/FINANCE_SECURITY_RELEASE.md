# Accounting and faculty scope release

Tender Part C2(3), pp. 23–25, requires financial accounting, fee receipt postings, balance reports and Tally integration. Part C1(I), pp. 13–15, requires granular access, multiple roles and data segregation.

## What is implemented
- Admin-only ledger activation establishes a fixed evaluation chart of accounts and opening student fee receivables. Existing amounts paid are not reconstructed as historical cash or revenue. The opening snapshot is posted to receivables and opening equity.
- New fee assessments post receivables debit and fee income credit; cash/bank receipts debit the respective account and credit student receivables. Fee and ledger records commit atomically under the institution lock.
- Balanced manual journals with two or more distinct accounts, decimal currency amounts and mandatory unique request key. Protected student-fee and opening accounts cannot be manually changed. Frontend supports two-line journals.
- Receipt retries with the same optional request key return the same reference; conflicting payload rejected. The frontend sends a key and retains it on an unsuccessful request. Legacy callers without a key are still supported; they are not retry-safe.
- Trial balance, provisional accounting position, receivable reconciliation and latest 100 journals. Finance and admin only.
- Faculty directory now contains only students enrolled in the faculty member's assigned course offerings; legacy attendance requires an assigned course code and valid period. Existing records are preserved, not deleted. Administrators retain legacy access. Use relational session attendance for new classes. No institution-wide custom-role engine yet.

## Real limitations
No complete statutory financial statements, financial-year opening/closing, historical bank/assets/liabilities, configurable chart/fee heads, refunds, concessions, payable approval workflow, scholarships, payment gateway, Tally adapter, receipt reversals, or automatic financial schedules. Manual accounting movements cannot stand in for official cash or bank reconciliation. Ledger activation is optional and irreversible in this pilot. Never activate against real institutional records before approval by qualified accounting staff. Direct database edits bypass application posting; reconciliation must be investigated, not silently patched. The provisional accounting position is not an audited balance sheet.
Faculty restriction is not complete multi-role RBAC. Department-level scope for other staff, temporary delegation, role inheritance, permission groups, and permission audit remain outstanding.

## Release validation
User verified baseline 3295f67: 44 institutional tables, 11 applied migrations, career acceptance 62/62, release completion marker; GitHub Web and Backend checks passed. Latest release adds four models and two backend test methods: expected 48 tables and 31 backend tests. Expanded live operations suite tests faculty access, opening balance, automatic fee posting, retry and reconciliation. Run all four acceptance suites using scripts/verify_developer_release.sh. New release is not yet verified locally. The original migration directory was untracked; exact migration files must be committed after validation. No production readiness or tender compliance claim.

## Remaining internal development
Full custom role engine; student self-registration and lifecycle, notices and feedback; complete financial/fee operations; calendars, timetable automation; documents and exam/hostel workflows; full LMS attachments; full accreditation; mobile apps; support, backups and production security. These can be developed without college data. Real provider integration and approved institutional policies require site information. No actual GCOEA connection is established.
