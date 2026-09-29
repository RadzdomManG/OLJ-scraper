# Launch audit — 29 September 2026

## Verified behavior

- Rolling archive: SQLite and Supabase hold 1,882 unique jobs at the audit snapshot; the watcher prunes the oldest discovered record after 5,000.
- Job API: customers must have an active code and a saved niche profile. Every stored job is available to every customer; the profile determines match badges only. Pagination runs against the Supabase archive. Owner controls and event keys are absent from customer JSON.
- Membership: distinct codes keep distinct profiles; the browser can edit its profile without entering the code again. Owner and customer cookies persist across visits. Revoked or expired codes fail protected requests and the page checks membership every 30 seconds.
- Live delivery: the updated three-customer test showed all four seeded jobs to every customer, including an unmatched Accounting job. A new VA job appeared in all three open pages without refresh in **2.63 seconds locally** and **4.70 seconds on production** after database insertion; only the VA profile showed a perfect-match badge. A 30-second refresh remains as fallback. These figures exclude the source site's own publishing and polling delay.
- Presentation: customer job cards and table show salary, work type, original posted text or exact posted time, exact detected time, niche score, original link, and incremental **Load more** navigation. Customer controls are limited to title/keyword search. Source names and advanced filters appear only for the owner, who can also view stage and notification state.
- Posting times: both accounts now see a live relative age and exact PHT clock time when the source supplies a verified timestamp. Relative-only source labels are marked unverified because they become stale after archiving; **Found** always uses the watcher's first detection time. The compact layout, branding glyph, search field, and salary currency decoding were corrected.
- Security: Supabase `jobs`, `access_codes`, `viewer_preferences`, `niche_taxonomy`, and `owner_sessions` are private to the server role. Tokens and codes are not embedded in customer responses. Temporary test codes and synthetic jobs were removed after tests.

## Test evidence

- Python unit tests: 14 passed.
- Frontend lint and production build: passed.
- Membership smoke: code admission, profile persistence, expiry, use limit, and API isolation passed.
- Owner smoke: sign-in and access-code creation, edit, revoke, delete passed.
- Browser smoke: profile onboarding, job list without source controls, and Load more checked.
- Three-customer Realtime tests: isolated inserts delivered in 2.08 and 2.68 seconds; synthetic jobs were removed afterward.
- Production browser and membership tests passed at `https://aurelius-job-portal.vercel.app` after the full-archive update. Customer JSON omits source identifiers; the rendered jobs page has only title/keyword search and Load more. A ComfyUI customer saw the entire archive, including unmatched jobs.
- Source probe and historical field counts: [source data audit](SOURCE_DATA_AUDIT.md).

## Launch limits

- **PeoplePerHour and Contra** cannot be claimed as live, no-sign-in sources; **Guru** currently returns HTTP 403. Their status must remain visible to the owner.
- Source polling is bounded by each site's update cadence and rate limits. A 20-second watcher loop does not guarantee every site or every post appears within 20 seconds.
- The local watcher must remain running. For 24/7 use, run it under a service manager on an always-on machine or host.
- Rotate any production credentials that were pasted into chat before public launch. Keep only server-side secrets in deployment settings.
- Telegram is currently unconfigured in the running local watcher, so no Telegram message can be sent until a bot token and chat ID are supplied.
