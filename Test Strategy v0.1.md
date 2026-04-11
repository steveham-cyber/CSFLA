# Test Strategy v0.1
## CSF Leak Association — Research Data Application

**Document status:** v0.1  
**Prepared by:** Probe (Test Engineer)  
**Date:** 2026-04-11  
**For:** Bolt (implementation), Cipher (security review of test coverage)

---

## 1. Testing Philosophy

This system handles pseudonymised health data. A bug in the report engine is inconvenient. A bug in the pseudonymisation pipeline or the k≥10 enforcement is a compliance and privacy incident. The test strategy reflects that hierarchy.

**Priority order:**
1. Pipeline integrity — PII never enters the research DB
2. Geographic filter — non-UK/EEA records never enter the research DB
3. Pseudonymisation correctness — stable, irreversible, consistent
4. k≥10 enforcement — at the query layer, not just the UI
5. Statistical accuracy — reports produce correct outputs
6. API role enforcement — users can only do what their role permits
7. Everything else

Tests in categories 1–4 are **blocking** — the pipeline must not be deployed without them passing. Tests in 5–7 gate feature completion.

---

## 2. Test Layers

| Layer | Tool | Scope |
|---|---|---|
| Unit | pytest | Individual functions — transformation, validation, HMAC, statistics |
| Integration | pytest + httpx + real PostgreSQL | Pipeline end-to-end, API endpoints, DB state |
| Security | pytest (dedicated suite) | PII leak, k<10 bypass, role escalation |
| Performance | pytest-benchmark | Pipeline throughput, report query time |
| Accessibility | axe-core (via Playwright) | WCAG AA on key screens |
| End-to-end | Playwright | Critical user journeys in browser |

---

## 3. Test Environment

### 3.1 Local

```
PostgreSQL:     Docker container (postgres:16-alpine)
                Separate test DB per test run — created and torn down by conftest.py
                Never the production or staging DB.

Key Vault:      Local HMAC with a fixed test key (TEST_PSEUDONYMISATION_KEY env var)
                Never connects to Azure Key Vault in tests.
                Test key: deterministic, documented, never used in production.

Auth:           Mocked Entra ID tokens — signed with test key, not real Entra ID
                conftest.py provides helper to generate tokens with arbitrary roles.
```

### 3.2 CI (GitHub Actions)

- PostgreSQL service container
- Test key in GitHub Actions secrets (separate from production key)
- All tests run on every PR to `main`
- Coverage report generated — minimum 80% line coverage enforced

### 3.3 Test Data

All test data is synthetic — no real member records ever used in tests. Fixtures in `tests/fixtures/`:
- `sample_import_valid.csv` — 50 UK/EU records with all field variations
- `sample_import_mixed.csv` — 30 UK/EU + 20 non-European (for geographic filter tests)
- `sample_import_pii_check.csv` — malformed records designed to test PII detection
- `sample_import_schema_change.csv` — missing/renamed columns (for schema validation tests)

---

## 4. Critical Test Specifications

### 4.1 PII Detection Tests (BLOCKING)

These tests verify the pipeline's core privacy guarantee. The research DB must never contain PII.

```
TEST: PII fields stripped from research DB
  Given: A valid import CSV with real-looking PII in strip-list fields
  When:  The pipeline runs to completion
  Then:  The research DB contains no record with any of:
           - firstName, lastName, fullName
           - email, username
           - password (any form)
           - phoneNumber
           - streetAddress, townCity
           - full dateOfBirth
           - full postcodeZipCode (only outward code allowed)
           - cpEditUrl, uid, membershipNumber
           - verificationCode, lastLoginAttemptIp

TEST: PII check halts import on failure
  Given: A pipeline deliberately patched to skip a strip step
  When:  The PII check runs on the transformed record
  Then:  The import halts entirely
         The database transaction is rolled back
         No records from this batch exist in the DB
         An error is raised with clear message
```

### 4.2 Geographic Filter Tests (BLOCKING)

```
TEST: Non-European records excluded
  Given: A CSV with 30 UK/EU records and 20 non-European records
         (United States: 10, Canada: 5, Australia: 5)
  When:  The pipeline runs
  Then:  Exactly 30 records are in the research DB
         0 records with country=United States, Canada, or Australia
         Import batch shows skipped_records = 20

TEST: All UK country variants accepted
  Given: Records with country values: England, Scotland, Wales,
         Northern Ireland, United Kingdom, UK, Great Britain
  Then:  All 7 variants pass the geographic filter

TEST: All EEA member states accepted
  Given: One record per EEA member state (27 states + Iceland, Liechtenstein, Norway)
  Then:  All 30 records pass the geographic filter

TEST: Ambiguous country value rejected
  Given: A record with country = "Europa" (not in allowlist)
  Then:  Record is excluded, logged as 'out_of_scope_geography'

TEST: Empty country field
  Given: A record with null/empty country field
  Then:  Record is excluded (fail closed — not assumed to be in scope)
```

### 4.3 Pseudonymisation Tests (BLOCKING)

```
TEST: Stability — same input always produces same output
  Given: member_id = "12345"
  When:  HMAC computed twice with same test key
  Then:  Both outputs are identical

TEST: Uniqueness — different inputs produce different outputs
  Given: member_ids "12345", "12346", "99999"
  Then:  All three pseudo_ids are distinct

TEST: Irreversibility — pseudo_id cannot be reversed
  Given: A pseudo_id
  Then:  No function in the codebase accepts a pseudo_id and returns a member_id
         (Static analysis check — grep for any inverse-HMAC pattern)

TEST: Cross-import consistency
  Given: member_id "12345" imported in batch 1
  When:  Same member_id imported in batch 2
  Then:  pseudo_id is identical in both import_batches

TEST: Key isolation — test key ≠ production key
  Given: TEST_PSEUDONYMISATION_KEY env var
  Then:  The value is not equal to any value in Azure Key Vault
         (Enforced by CI: test key is a fixed known string, never a real secret)
```

### 4.4 k≥10 Enforcement Tests (BLOCKING)

These tests target the **query layer**, not the UI. The UI is irrelevant — if the API returns suppressed data in the response body, the test fails regardless of what the UI does with it.

```
TEST: Report endpoint suppresses small cohorts
  Given: A research DB with 8 members matching a specific filter
  When:  GET /api/reports/standard/2 with that filter applied
  Then:  HTTP 200 response
         Response body does NOT contain numeric data for that cohort
         Response body contains suppression indicator

TEST: k<10 check cannot be bypassed via URL manipulation
  Given: A cohort of 5 members
  When:  Various URL parameter manipulations attempted
         (e.g. limit=100, offset=0, format=raw)
  Then:  All return suppressed indicator, not data

TEST: k≥10 enforced at SQL level
  Given: A direct database query (bypassing API) for a group of 8
  Then:  The query itself returns 0 rows or a suppressed result
         (Query-layer HAVING COUNT(*) >= 10 enforced)

TEST: Exact boundary — 9 members suppressed, 10 members shown
  Given: A cohort of exactly 9 members
  Then:  Data suppressed
  Given: A cohort of exactly 10 members
  Then:  Data returned

TEST: AI analysis endpoint respects k≥10
  Given: A request to the AI analysis endpoint referencing a group of 8
  Then:  The group data is not included in the payload sent to Claude API
```

### 4.5 Import Idempotency Tests

```
TEST: Re-importing same CSV produces same DB state
  Given: A CSV imported as batch 1
  When:  The identical CSV imported again as batch 2
  Then:  member count is unchanged
         No duplicate pseudo_ids
         last_updated_batch updated on all records
         first_seen_batch unchanged on all records

TEST: Updated fields reflected on re-import
  Given: A member with age_band '30_39' imported in batch 1
  When:  Same member with dateOfBirth updated (now age_band '40_49') in batch 2
  Then:  member record shows age_band '40_49'
         first_seen_batch still points to batch 1

TEST: Deleted member not re-added on re-import
  Given: A pseudo_id manually deleted from research DB (erasure request)
  When:  An import containing that member_id runs
  Then:  The member is NOT re-added
         (Pipeline must check erasure list before upsert)
         Note to Bolt: Erasure list needs to be designed — track deleted pseudo_ids
```

### 4.6 Schema Validation Tests

```
TEST: Import halts on schema change
  Given: A CSV missing the 'csfLeakType' column
  When:  Pipeline runs
  Then:  Import halts before any records processed
         No records written to DB
         Error: 'Schema change detected — expected column csfLeakType not found'

TEST: Import halts on unexpected new column
  Given: A CSV with an extra column 'newHealthField'
  Then:  Import halts — new field requires review before processing
```

### 4.7 Statistical Accuracy Tests

```
TEST: Count reports produce correct totals
  Given: A research DB with 50 known synthetic records
         (25 diagnosed, 15 suspected, 10 other)
  When:  Report 2 (Diagnostic Status Profile) runs
  Then:  diagnosed count = 25, suspected count = 15

TEST: Percentage calculations correct
  Given: 25 diagnosed out of 40 sufferers (diagnosed + suspected)
  Then:  diagnosed % = 62.5%
         Denominator documented as 'sufferers' (not total cohort)

TEST: Multi-value field counts correct (Report 4, Report 7)
  Given: 3 members each with 2 causes of leak
         3 members with 1 cause of leak
  When:  Cause of leak report runs
  Then:  Total cause entries = 9 (not 6)
         Denominator = 6 members (not 9)

TEST: Chi-square test (Report 7)
  Given: A 2×2 contingency table with known chi-square value
  When:  Report 7 statistical test runs
  Then:  chi-square statistic within 0.001 of expected value
         p-value correctly classified (< 0.05 / >= 0.05)
```

### 4.8 API Role Enforcement Tests

```
TEST: Unauthenticated requests rejected
  Given: No Authorization header
  When:  Any protected endpoint called
  Then:  HTTP 401

TEST: Viewer cannot trigger import
  Given: Token with role = 'viewer'
  When:  POST /api/imports/
  Then:  HTTP 403

TEST: Researcher cannot access admin endpoints
  Given: Token with role = 'researcher'
  When:  GET /api/admin/audit-log
  Then:  HTTP 403

TEST: Admin can access all endpoints
  Given: Token with role = 'admin'
  When:  All endpoints called
  Then:  No 401 or 403 responses

TEST: Role check at API layer, not just UI
  Given: A valid researcher token
  When:  Direct HTTP call to POST /api/imports/ (bypassing UI)
  Then:  HTTP 403 — role check is in the FastAPI dependency, not the frontend
```

---

## 5. Test File Structure

```
app/
└── tests/
    ├── conftest.py                    # Fixtures: test DB, test tokens, test key
    ├── fixtures/
    │   ├── sample_import_valid.csv    # 50 synthetic UK/EU records
    │   ├── sample_import_mixed.csv    # 30 UK/EU + 20 non-European
    │   ├── sample_import_pii.csv      # Designed to trigger PII check
    │   └── sample_import_schema.csv   # Missing/renamed columns
    ├── test_pipeline/
    │   ├── test_geographic_filter.py  # Section 4.2 tests
    │   ├── test_pseudonymisation.py   # Section 4.3 tests
    │   ├── test_field_transform.py    # Age band, outward code, date reduction
    │   ├── test_pii_detection.py      # Section 4.1 tests
    │   ├── test_validation.py         # Record validation rules
    │   ├── test_idempotency.py        # Section 4.5 tests
    │   └── test_schema_validation.py  # Section 4.6 tests
    ├── test_api/
    │   ├── test_auth.py               # OAuth flow, token validation
    │   ├── test_imports.py            # Import endpoint, file validation
    │   ├── test_reports.py            # Report endpoints, k≥10 (Section 4.4)
    │   └── test_admin.py              # Admin endpoints, role enforcement (4.8)
    ├── test_reports/
    │   ├── test_statistics.py         # Section 4.7 — statistical accuracy
    │   └── test_suppression.py        # k≥10 in report outputs
    └── test_security/
        ├── test_pii_in_responses.py   # No PII in any API response
        ├── test_role_bypass.py        # Section 4.8 — direct HTTP bypass attempts
        └── test_ai_constraints.py     # Section 4.4 — AI endpoint k≥10
```

---

## 6. Coverage Requirements

| Area | Minimum coverage | Rationale |
|---|---|---|
| `pipeline/` | 95% | Safety-critical — pseudonymisation and PII handling |
| `api/` | 85% | All endpoints and role checks must be tested |
| `reports/` | 90% | Statistical accuracy and k≥10 |
| `auth/` | 80% | Auth flows covered |
| Overall | 80% | CI gate — PRs blocked below this threshold |

---

## 7. CI Pipeline Integration

```yaml
# .github/workflows/test.yml (outline for Bolt)

on: [pull_request]

jobs:
  test:
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: csfleak_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio pytest-cov httpx
      - run: pytest --cov=. --cov-report=xml --cov-fail-under=80
        env:
          TEST_PSEUDONYMISATION_KEY: ${{ secrets.TEST_PSEUDONYMISATION_KEY }}
          DB_HOST: localhost
          DB_NAME: csfleak_test
          DB_USER: test
          DB_PASSWORD: test
          APP_ENV: development
```

---

## 8. Pre-Go-Live Test Sign-Off

These must all pass before the system processes real member data:

- [ ] All BLOCKING tests passing (Sections 4.1–4.4)
- [ ] 80% overall coverage in CI
- [ ] Full import test with production-sized synthetic dataset (~3,000 records)
- [ ] k≥10 bypass attempt tests all returning suppressed
- [ ] PII scan of test DB post-import confirms zero PII fields
- [ ] Role enforcement: viewer, researcher, admin all verified
- [ ] Report 7 chi-square test producing correct statistics
- [ ] Cipher sign-off on security test coverage
- [ ] Probe sign-off on statistical accuracy tests
