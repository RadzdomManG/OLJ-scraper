# Source data audit — 29 September 2026

This is a live probe and archive snapshot, not a guarantee that third-party sites will keep the same markup. The probe output is in `data/source_audit.json`; rerun with `python scripts/audit_sources.py`.

| Source | Live public listing | Detail data | Archive jobs | Salary present | Work type present | Exact posted time |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| OnlineJobs.ph | 30 | Verified | 1,309 | 1,293 | 1,293 | 1,309 |
| Freelancer | 46 | Verified | 221 | 214 | 0 | 0 |
| PeoplePerHour | Blocked by challenge | Unavailable | 0 | 0 | 0 | 0 |
| Wellfound | 10 | Verified | 1 | 1 | 1 | 1 |
| Remotive | 16 | Verified | 16 | 0 | 16 | 16 |
| Contra | Login required | Unavailable | 0 | 0 | 0 | 0 |
| We Work Remotely | 85 | RSS fields verified | 85 | 0 | 85 | 85 |
| Guru | HTTP 403 | Unavailable | 20 historical | 13 | 20 | 0 |
| Jobicy | 200 | Verified | 200 | 97 | 200 | 200 |
| Himalayas | 100 | Public feed verified | 20 | 2 | 20 | 20 |
| VirtualStaff.ph | 10 | Verified | 10 | 10 | 10 | 10 |

The archive had **1,882 unique event keys** at the snapshot. All 1,882 have a description; 252 have no salary and 237 have no work type. Missing source fields display as **Not provided**. Freelancer's relative posted label is preserved as source text; it is never converted into a fabricated exact timestamp. The detail backfill enriched 214 Freelancer, 10 VirtualStaff, 98 Jobicy, 16 Remotive, 20 Himalayas, and 7 We Work Remotely records. Some older detail URLs were no longer available. We Work Remotely's current pages lack the structured `JobPosting` block used by the generic detail parser; current collection relies on its valid RSS fields.

The source probe checks available public listings, not every page or every job on a site. Sites can delay publication or rate limit requests. PeoplePerHour, Contra, and Guru are not reliable account-free live sources in the present environment; the owner status page shows those failures. No challenge bypass or credential reuse is attempted.

Times are shown in Philippine time. **Posted** uses an exact source clock time only when provided; otherwise the original source phrase or **Not provided** appears. **Detected** is the watcher's own timestamp. The two values are kept separate.
