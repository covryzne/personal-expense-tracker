# Test Plan — What “Working” Must Mean

## 1. Test layers

- **Unit:** Parser/normalizer, Pydantic schemas, Rupiah amounts, date-period resolution, category normalization, sender authorization.
- **DB integration:** Versioned Supabase migration, unique constraints, RLS, CRUD, soft-delete/restore, SQL reports. Use an isolated test database/project, never real finance data.
- **Adapter contract:** Fake WhatsApp envelopes, media/ASR/OCR mocks; verify only authorized messages invoke domain tools.
- **Live smoke:** Explicit opt-in tests on actual Muse/WhatsApp transport (message ID, sender metadata, media handling, reply output); do not claim this passes from mocks alone.

## 2. Golden fixtures (all hypothetical, NOT real expenses)

Create one Auth user A (owner) and another B (intruder). For owner A, known rows:

| Key | Local occurred_at WIB | Amount | Category | Source |
|---|---|---:|---|---|
| E1 | 2026-10-30 12:51 | Rp12.000 | food_drink | Receipt Nescafe; tender Rp100.000, change Rp88.000 |
| E2 | 2026-10-31 22:30 | Rp50.000 | transport | Voice transcription: bensin |
| E3 | 2026-11-01 00:15 | Rp2.000 | transport | Text: parkir |
| E4 | 2026-11-02 08:00 | Rp18.000 | food_drink | Text: bakso |

Expected Oct 2026 = Rp62.000, count 2; expected Nov 2026 = Rp20.000, count 2; Oct category food_drink = Rp12.000, transport = Rp50.000. E3 tests UTC-to-WIB month boundary. Count exact categories and sum. If E4 soft-deleted, Nov = Rp2.000, count 1. Restoring E4 returns Nov = Rp20.000, count 2.

## 3. Acceptance matrix

| ID | Scenario | Expected |
|---|---|---|
| T01 | Text: `kopi 12rb` | One expense with `amount_idr=12000`; category inferred or `other` |
| T02 | Text: `beli 12.500 rupiah` | Integer 12500; never decimal 12.5 |
| T03 | Voice transcript: `kemarin beli bensin lima puluh ribu` | Rp50.000 and relative WIB date from original message |
| T04 | Receipt total 12k; cash 100k; change 88k | Store 12k only |
| T05 | Receipt with five item lines and grand total | Exactly one expense; no extra item expense rows |
| T06 | `kopi 12rb, parkir 2rb` | Two rows, indices 0 and 1, correct categories |
| T07 | Repeat exactly same provider message ID | No new row; return `already_recorded` |
| T08 | Same receipt forwarded with identical merchant and printed receipt reference but new message ID | Flag likely duplicate; require user decision; do not blanket-suppress all same-amount purchases |
| T09 | `saldo 50rb` or `tarik tunai 100rb` | No expense inserted; clarify if ambiguous |
| T10 | No price visible | Ask price; do not insert |
| T11 | No merchant visible | Save permitted with null merchant; do not fabricate merchant |
| T12 | Update `kopi tadi 15k` with one clear recent match | Existing row modified; total adjusts without adding row |
| T13 | Update with 2 matching `kopi` entries | Ask which transaction; no mutation |
| T14 | Delete then report then restore | Excluded while deleted; included when restored |
| T15 | This-week query, original time on Sunday 23:59 WIB | Week starts Monday, ends next Monday correctly |
| T16 | Original time on Monday 00:01 WIB | Belongs to new week |
| T17 | Month boundary 1 Nov 00:15 WIB | Included in November, not October |
| T18 | Backfilled October purchase entered in November | Counts in October report, not November |
| T19 | SQL report for October fixture | Total Rp62,000; exactly 2 rows; by-category matches |
| T20 | Query empty date period | `0 recorded`, do not state actual spending was zero |
| T21 | Other WhatsApp sender | Unauthorized and no DB read/write |
| T22 | Supabase Auth user B reading A via publishable key | RLS denies A's rows |
| T23 | Public/anon client reading expenses | Denied; no publicly exposed data |
| T24 | Prompt injection text inside receipt | Ignored as untrusted data; no hidden tool action |
| T25 | Supabase write timeout with possible commit | Lookup by idempotency key; never blindly duplicate or falsely claim success |
| T26 | Invalid amount (0, negative, floating fraction) | Validation error; no write |
| T27 | Malformed date / conflicting receipt and user dates | Ask for clarification; no invented date |
| T28 | Multiple message replays after correction | Original ingest replay does not undo a later intentional correction |
| T29 | Very large custom report range | Validate/clamp to configured safe maximum; no unbounded LLM data dump |
| T30 | Migration and restore drill | Fresh test DB recreates schema, data restored from tested backup |

## 4. Security gates

- `.env`, service API keys, tokens, provider secrets must not be committed, logged, embedded in prompts, or shipped to browser.
- For every expense mutation and lookup, assert `user_id` comes from server-side sender mapping and is used as a filter.
- Test RLS policies for `anon`, `authenticated` user A, and B in isolated Supabase project.
- Verify API functions cannot be executed by unauthorized roles; restrict grants for any RPC function.
- Whitelist only known agent tool actions and fields. Test SQL-injection-like strings in merchant/description are stored as inert text.
- Owner authorization must be checked **before** reading a private record to resolve a conversational target.

## 5. Operational gates

- Idempotent create after provider retries, including unknown-outcome DB timeout.
- Log statuses/errors with correlation IDs but never full credentials, raw photos, raw voice, or entire private finance rows.
- Backups land outside the database project; restoration is reproducible.
- Migration changes are checked into Git; no manual untracked remote changes.
- Live channel success requires **real** inbound text, voice, photo processing and reply confirmation. If access missing, record as `BLOCKED`, not `PASS`.

## 6. Evidence checklist agent must report

Produce a concise final verification report with:

- Implemented files and changed paths.
- Migration name and whether tested/applied to staging/production.
- Unit and DB integration test commands with actual pass/fail counts.
- Example SQL/result values for fixture (no user's real data).
- Which live Muse adapter capabilities are verified vs pending.
- RLS and authorization denial test results.
- Backup/restore validation status.
- Remaining blockers/risks; do not claim deployment if only local tests ran.
