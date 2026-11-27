# Career pilot and on-site connection readiness

Tender reference: GCOEA/MIS/ET-01/2026-2027, Part C2 section 7 (page 31), Part B (page 12), scanning hardware page 9, data migration and commissioning page 36. This is an internal engineering note, not a signed tender compliance statement.

## New placement module
Administrator provisions placement officer, placement assistant and recruitment company accounts. A company submits its own company profile; administrator or TPO approves/rejects it. TPO/assistant/admin publishes employment, internship or training opportunities using configurable program and year range, deadline and drive date. Eligible student list is available only to institution-authorized placement staff and principal. Students save skills and summary and explicitly consent to sharing their application with the relevant company. The submitted career profile is snapshotted. A company sees its own non-withdrawn applicants, not the general student directory, eligibility lists or other company records. Close applications before shortlisting/selection. Students may withdraw submitted or shortlisted applications. Principal is read-only. All mutations are audited by actor and record ID.

Limits: invited company accounts only; no public company signup, email verification, resume files, CGPA/backlog eligibility, formal offer acceptance, placement batch/department reports, company profile edit/review reopening, or complete custom permissions. Program/year eligibility uses legacy student program text; approved institutional grading/eligibility rules still need implementation. Selection counts are application records, not unique students or verified employment. The module does not implement alumni graduation. Existing broad faculty directory access remains a separate security gap.

## Evidence gate
Last verified developer baseline d797f6f: 28 institutional tables, 23 backend tests, 3 frontend metadata tests and 109 live academic/scan checks. Earlier 92 operational and 24 Connect checks passed on preceding releases. HR release b7ea980 has code and passing GitHub web checks; local HR runtime not yet evidenced. Career release adds four models and two backend test methods. Expected combined result after both upgrades: 36 institutional tables, 27 backend tests, 12 supported role types. The new career live script runs with isolated synthetic accounts; no real college data. Run scripts/verify_developer_release.sh only on the existing developer Mac after a fast-forward update. It backs up data, checks and migrates models, compiles the frontend, waits for direct API readiness, then runs all four live suites. It does not guarantee zero downtime. Migration history must still be reviewed and committed from the original developer worktree; the repository currently lacks migration files. Do not generate a competing migration history against an existing database.

## On-site connection checklist
| Connection | Before visiting | What the institute must authorize/provide | Site acceptance evidence |
|---|---|---|---|
| Old MIS | Expand schema mapping and full migration tools | Export in previous vendor format, data dictionary, counts, historical years, identifiers | Dry run, row counts, reconciliation, signed exceptions and rollback |
| Employee biometric | Verify mapped event receiver and build revocation/remapping | Manufacturer/model, supported SDK/API, gateway network and opaque IDs | Real authorized in/out events, retries, mapping and reconciliation |
| Classroom/exam/hostel biometric | Build identity and session/movement processing | Device inventory, event format, approved rules | Real session/identity correlation and audit |
| Scanner | Build original-file retention, bulk ingestion and rescan workflow | Institute-provided scanning hardware, sample non-confidential pages, formats | Page completeness, orientation, quality and reconciliation |
| Tally | Implement balanced ledger and posting outbox | Version, licensed API, test company and ledger mapping | Test postings and accountant reconciliation |
| Payment | Implement verified signed webhook and status reconciliation | Institute-owned merchant sandbox and production approval | Successful, failed, pending, refund and duplicate transaction tests |
| CCTV | Implement scoped authorized viewing | VMS/NVR provider, access policy and supported interface | Approved cameras and denied unauthorized viewing |
| Email/SMS/WhatsApp | Implement notification outbox, retry and receipt tracking | Approved provider, templates, account and consent | Test delivery and failure handling |
| Deployment | Commit migrations, secure configuration, backups, restore, capacity/security tests | Network/firewall policy, cloud approval, authorized domains | Browser acceptance, load, security and recovery evidence |

No physical provider is connected merely by registering a source. Never access a legacy database without written authorization. Prefer read-only exports or APIs and staged migration over unrestricted remote write access. Do not store institute credentials in Git or chat.

## Next development gates
1. Verify HR and career runtime and reconcile migrations; independent fresh clone and browser test.
2. Replace fixed single-role membership with granular scoped authorization and fix legacy faculty/other staff directory exposure.
3. Add approved graduation and alumni lifecycle, followed by enrollment-linked LMS and notices.
4. Complete financial ledger and student self-registration; add institutional documents, recurring timetable and hostel lifecycle.
5. Complete examination scope (batch original-file retention, rescan, grading, barcode, hall tickets, reports).
6. Provider adapters, historical migration, accreditation, native mobile, production hardening, contractual acceptance.

The project remains an evaluation prototype. Not all mandatory modules are complete; no claim of tender compliance or bidder eligibility is made.
