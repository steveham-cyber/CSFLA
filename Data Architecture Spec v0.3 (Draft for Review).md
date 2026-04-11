# Data Architecture Specification v0.3
## CSF Leak Association — Research Data Application

**Document status:** Draft v0.3 — pending Cipher and Lex sign-off  
**Prepared by:** Atlas (Data Architect)  
**Date drafted:** 2026-04-11 | Updated: 2026-04-11  
**Changes in v0.2:** Confirmed controlled vocabularies (Q-01); outward code reduction confirmed for all European postcodes (Q-02); key store updated to Azure Key Vault (Q-03); gender confirmed as male/female (Q-04); email_consent and is_volunteer removed as operational fields only (Q-05).  
**Changes in v0.3:** C-SEC-01 — Key Vault approach clarified (KV secret, single fetch); C-SEC-02 — age band consolidated to `70_over`; C-SEC-03/L-GDPR-01 — erasure register added to schema and ETL spec, erasure procedure corrected; C-SEC-04 — `imported_by` description corrected.  
**Review required from:** Cipher (security), Lex (compliance)  
**Sign-off required before:** Bolt begins any data pipeline implementation  

---

## 1. Design Principles

1. **PII never enters the research database.** The pipeline boundary is absolute — only the fields listed in Section 3 (transformed as specified) are written to the research DB.
2. **Pseudonymisation key and research data are always separated.** Different host, different credentials, different encryption keys where feasible.
3. **The pipeline is an allowlist, not a blocklist.** Only explicitly approved fields pass through. New fields require a schema change and review — they cannot slip in accidentally.
4. **Dates are always reduced.** No full timestamps stored. Year or year-month only, depending on research value.
5. **Free text never enters the research database.** All retained fields are structured/categorical.
6. **Fail closed.** If a record fails validation or transformation, it is rejected and logged — it does not pass through in a partial or untransformed state.

---

## 2. System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMBERSHIP SYSTEM                        │
│            (Craft CMS — csfleak.uk)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │  CSV export (manual or scheduled)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   IMPORT PIPELINE                           │
│                                                             │
│  Step 1 — Geographic filter                                 │
│           Drop all records where country is not             │
│           UK or EEA member state. Log dropped count.        │
│                                                             │
│  Step 2 — Schema validation                                 │
│           Confirm expected columns are present.             │
│           Reject import if schema has changed.              │
│                                                             │
│  Step 3 — Record validation                                 │
│           Per-record checks (see Section 4).                │
│           Invalid records are logged and skipped.           │
│                                                             │
│  Step 4 — Pseudonymisation                                  │
│           Generate pseudo_id from member_id via HMAC.       │
│           Transform all fields per Section 3.               │
│                                                             │
│  Step 5 — Upsert to Research DB                             │
│           Insert new records; update changed fields         │
│           on existing pseudo_ids. Log batch summary.        │
└────────────┬──────────────────────────┬─────────────────────┘
             │                          │
             ▼                          ▼
┌────────────────────┐      ┌───────────────────────────────┐
│    KEY STORE       │      │        RESEARCH DB            │
│                    │      │                               │
│  member_id →       │      │  Pseudonymised health and     │
│  pseudo_id         │      │  demographic data only.       │
│  (HMAC key)        │      │  No PII. No key material.     │
│                    │      │                               │
│  Separate host /   │      │  PostgreSQL                   │
│  credentials       │      │  Encrypted at rest            │
└────────────────────┘      └───────────────────────────────┘
```

---

## 3. Field Transformation Specification

This is the definitive allowlist. Every field not listed here is **dropped** at the pipeline boundary.

### 3.1 Identity

| Source field(s) | Research DB field | Transformation |
|---|---|---|
| `id` (internal member ID) | `pseudo_id` | `HMAC-SHA256(secret_key, id)` — see Section 5 |

### 3.2 Demographics

| Source field(s) | Research DB field | Transformation |
|---|---|---|
| `dateOfBirth` | `age_band` | Parse DOB → calculate age at import date → map to band (see below) |
| `gender` | `gender` | Retain value as-is. Null if not provided. |
| `country` | `country` | Retain value as-is (post geographic filter — UK/EEA only) |
| `countyRegionStateProvince` | `region` | Retain value as-is |
| `postcodeZipCode` | `outward_code` | All postcodes: retain outward code only (characters before the space). E.g. `G32` from `G32 8PU` (UK), `SW1A` from `SW1A 1AA`. For European formats, extract the first segment before a space or delimiter. If no clear outward code is extractable, store null. |

**Age bands:**

| Age at import | Band stored |
|---|---|
| Under 18 | `under_18` |
| 18–29 | `18_29` |
| 30–39 | `30_39` |
| 40–49 | `40_49` |
| 50–59 | `50_59` |
| 60–69 | `60_69` |
| 70 and over | `70_over` |
| Not provided | `null` |

> **Note for Lex:** Age band is recalculated on every import. A member's band will update as they age. This is intentional — it reflects their age at the time of each analysis, not at sign-up.

### 3.3 Health Data

| Source field(s) | Research DB field | Transformation |
|---|---|---|
| `memberStatus` | `member_status` | Retain structured array values only. Valid values (confirmed): `csfLeakSuffererDiagnosed`, `csfLeakSuffererSuspected`, `formerCsfLeakSufferer`, `familyFriendOfSufferer`, `medicalProfessional`, `other`. Unrecognised values logged as warning, field set to null for that record. |
| `csfLeakType` | `csf_leak_type` | Retain structured array values only. Valid values (confirmed): `spinal`, `cranial`, `spinalAndCranial`, `unknown`, `notRelevant`. Note: `notRelevant` expected for non-sufferer member types (familyFriendOfSufferer, medicalProfessional). |
| `causeOfLeak` | `cause_of_leak` | Retain structured array values only. Valid values (confirmed): `spinalSurgery`, `cranialSurgery`, `lumbarPuncture`, `epiduralAnaesthesia`, `spinalAnaesthesia`, `otherIatrogenicCause`, `ehlersDanlosSyndrome`, `marfanSyndrome`, `otherHeritableDisorderOfConnectiveTissue`, `idiopathicIntracranialHypertension`, `boneSpur`, `cystTarlovPerineuralMeningeal`, `trauma`, `other`, `unknown`, `preferNotToSay`. |

### 3.4 Membership

| Source field(s) | Research DB field | Transformation |
|---|---|---|
| `memberSince` / `manualStart` | `member_since_year` | Extract year only (e.g. `2018`). Use `memberSince` if present, fall back to `manualStart`. |

> **Note:** `isVolunteer` and `receiveEmail` are operational fields only and are excluded from the research database.

### 3.5 Referral

| Source field(s) | Research DB field | Transformation |
|---|---|---|
| `howDidYouHearAboutUs` | `referral_source` | Retain structured array values only. Drop `howDidYouHearAboutUsOther` (free text) entirely. |

### 3.6 Import Metadata

| Field | Research DB field | Notes |
|---|---|---|
| (generated) | `import_batch_id` | FK to `import_batches` table. Set during pipeline run. |
| (generated) | `first_seen_batch` | Batch ID when this pseudo_id first appeared. Set on insert, never updated. |
| (generated) | `last_updated_batch` | Batch ID of most recent upsert. Updated on every import. |

---

## 4. Record Validation Rules

Records failing any of these checks are **skipped** (not imported) and logged with reason:

| Check | Rule |
|---|---|
| Geographic scope | `country` value must map to UK or EEA member state. See Appendix A for valid country values. |
| Member ID present | `id` must be non-null and non-empty |
| Date of birth parseable | If `dateOfBirth` is present, it must be a valid date. If unparseable, set `age_band` to null (do not reject the record). |
| Health fields structured | `memberStatus`, `csfLeakType`, `causeOfLeak` must be structured array values. Unrecognised values are logged as a warning but do not reject the record — the field is set to null for that record. |
| No PII in pipeline output | Automated check: the transformed record must contain none of the fields on the strip list (Section 2 of DPIA). Pipeline fails hard if this check fails. |

---

## 5. Pseudonymisation Specification

### 5.1 Algorithm

```
pseudo_id = Base64Url( HMAC-SHA256( secret_key, str(member_id) ) )
```

- **Input:** The member's internal integer ID from the `id` field (converted to string)
- **Key:** A 256-bit (32-byte) cryptographically random secret key
- **Output:** A stable, URL-safe Base64-encoded 32-byte identifier

### 5.2 Properties

- **Stable:** The same `member_id` always produces the same `pseudo_id`, enabling longitudinal tracking across imports
- **Irreversible** without the secret key — the research database alone cannot be used to recover member identities
- **Collision-resistant:** HMAC-SHA256 output space is large enough to make collisions negligible for this dataset size

### 5.3 Key Management

| Requirement | Specification |
|---|---|
| Key storage | **Azure Key Vault** (confirmed). Store the HMAC key as an **Azure Key Vault secret**. The pipeline fetches the secret value once at batch start (a single authenticated API call via Managed Identity), holds it in memory for the duration of the import batch, then zeros the variable immediately after the batch completes. The key is never written to disk, logs, or any persistent store outside Key Vault. |
| Key rotation | Key should not be rotated without regenerating all pseudo_ids in the research DB. Rotation is a significant operation and must be planned — it is not a routine activity. |
| Key access | Only the import pipeline's Azure Managed Identity has access to the Key Vault key. No human should have routine access to the raw key material in production. Access policy enforced via Azure RBAC. |
| Key backup | Azure Key Vault provides built-in backup and geo-redundancy. Soft-delete and purge protection must be enabled to prevent accidental or malicious deletion. |
| Key separation | Azure Key Vault is entirely separate from the research DB. A compromise of the PostgreSQL instance does not expose the key. |

### 5.4 Azure Key Vault Configuration

```
Key Vault name:     csfleak-research-kv  (or equivalent)
Secret name:        pseudonymisation-key
Secret type:        Azure Key Vault secret (not a cryptographic key object)
Soft delete:        Enabled (mandatory)
Purge protection:   Enabled (mandatory — prevents secret deletion even by admins)
Access:             Pipeline Managed Identity — Secret/Get permission only
                    No human principal has Secret/Get access in production
Logging:            Azure Key Vault diagnostic logs enabled → Log Analytics workspace
```

---

## 6. Research Database Schema

```sql
-- ============================================================
-- RESEARCH DATABASE
-- PostgreSQL — all connections via TLS
-- Tablespace encrypted at rest
-- ============================================================

-- Import batch log
CREATE TABLE import_batches (
    batch_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    imported_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    imported_by         TEXT NOT NULL,          -- Entra ID object ID of the user or service principal — never a display name
    source_filename     TEXT NOT NULL,
    total_records       INTEGER NOT NULL,
    imported_records    INTEGER NOT NULL,
    skipped_records     INTEGER NOT NULL,
    rejected_records    INTEGER NOT NULL,
    notes               TEXT
);

-- Core member research record
CREATE TABLE members (
    pseudo_id           TEXT PRIMARY KEY,       -- HMAC-derived, see Section 5
    age_band            TEXT,                   -- e.g. '30_39', 'under_18', null
    gender              TEXT,                   -- 'male', 'female', null
    country             TEXT NOT NULL,
    region              TEXT,
    outward_code        TEXT,                   -- outward postcode only (UK and European)
    member_since_year   SMALLINT,               -- year only
    referral_source     TEXT[],                 -- structured array of confirmed values
    first_seen_batch    UUID NOT NULL REFERENCES import_batches(batch_id),
    last_updated_batch  UUID NOT NULL REFERENCES import_batches(batch_id)
);

-- Health status (one or more statuses per member)
CREATE TABLE member_statuses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pseudo_id           TEXT NOT NULL REFERENCES members(pseudo_id),
    status_value        TEXT NOT NULL,          -- e.g. 'csfLeakSuffererDiagnosed'
    import_batch_id     UUID NOT NULL REFERENCES import_batches(batch_id),
    UNIQUE (pseudo_id, status_value)
);

-- CSF leak type (one or more per member)
CREATE TABLE csf_leak_types (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pseudo_id           TEXT NOT NULL REFERENCES members(pseudo_id),
    leak_type           TEXT NOT NULL,          -- e.g. 'spinal', 'cranial'
    import_batch_id     UUID NOT NULL REFERENCES import_batches(batch_id),
    UNIQUE (pseudo_id, leak_type)
);

-- Cause of leak (one or more per member)
CREATE TABLE causes_of_leak (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pseudo_id           TEXT NOT NULL REFERENCES members(pseudo_id),
    cause               TEXT NOT NULL,          -- e.g. 'trauma', 'unknown'
    import_batch_id     UUID NOT NULL REFERENCES import_batches(batch_id),
    UNIQUE (pseudo_id, cause)
);

-- Erasure register — records pseudo_ids that have been erased under GDPR Article 17.
-- The pipeline checks this table before any upsert. If a pseudo_id is present here
-- the record is skipped and logged as 'subject_erased'. This prevents erased members
-- from re-entering the research DB on future imports.
CREATE TABLE erasure_register (
    pseudo_id           TEXT PRIMARY KEY,
    erased_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    erased_by           TEXT NOT NULL,          -- Entra ID object ID of admin who actioned the erasure
    erasure_reason      TEXT                    -- Optional: e.g. 'Article 17 request', 'deceased'
);

-- Indexes for common query patterns
CREATE INDEX idx_members_country       ON members(country);
CREATE INDEX idx_members_age_band      ON members(age_band);
CREATE INDEX idx_members_gender        ON members(gender);
CREATE INDEX idx_members_since_year    ON members(member_since_year);
CREATE INDEX idx_statuses_pseudo_id    ON member_statuses(pseudo_id);
CREATE INDEX idx_leak_types_pseudo_id  ON csf_leak_types(pseudo_id);
CREATE INDEX idx_causes_pseudo_id      ON causes_of_leak(pseudo_id);
```

### 6.1 Design Notes

- **Array fields broken into child tables** (`member_statuses`, `csf_leak_types`, `causes_of_leak`): Members can have multiple values (e.g. both spinal and cranial). Separate tables make statistical queries cleaner and enforce referential integrity.
- **No timestamps beyond year:** `member_since_year` is an integer — no date type, no time component.
- **No names, emails, or contact fields anywhere in this schema.**
- **`imported_by` in audit table:** Uses the service account name or user pseudo_id — never a real name.

---

## 7. ETL Pipeline Specification

### 7.1 Trigger

Initially: manual upload via the application's admin interface.  
Future: scheduled automated export from the membership system (to be designed once manual flow is stable).

### 7.2 Processing Steps (Detail)

```
1. RECEIVE
   - Accept CSV upload via admin interface
   - Store raw file in a temporary, access-controlled staging area
   - Do NOT write to research DB at this stage

2. GEOGRAPHIC FILTER
   - Parse CSV headers (validate against expected schema first)
   - For each record: check `country` against EEA + UK allowlist (Appendix A)
   - Write non-matching records to rejection log with reason: 'out_of_scope_geography'
   - Continue with in-scope records only

3. SCHEMA VALIDATION
   - Confirm all expected source columns are present
   - If schema has changed (columns added, removed, renamed): HALT import
   - Alert admin — schema change requires review before processing continues

4. RECORD VALIDATION
   - Per-record checks (Section 4)
   - Invalid records: log with reason, skip, continue

5. PSEUDONYMISATION + TRANSFORMATION
   - For each valid record:
     a. Fetch secret_key from key store (single fetch at pipeline start, held in memory only)
     b. Compute pseudo_id = HMAC-SHA256(secret_key, str(id))
     c. Transform all fields per Section 3
     d. Run PII check on transformed record (must contain no strip-list fields)
     e. If PII check fails: HALT entire import, raise alert

6. UPSERT
   - Begin database transaction
   - For each transformed record:
     - Check erasure_register: if pseudo_id is present, skip this record and log reason
       as 'subject_erased' — do not insert or update
     - If pseudo_id exists in members: UPDATE changed fields, update last_updated_batch
     - If pseudo_id not in members: INSERT new record, set first_seen_batch
     - Upsert child table records (statuses, leak types, causes)
   - Commit transaction
   - Zero secret_key in memory

7. BATCH SUMMARY
   - Write import_batches record: counts, filename, timestamp, user
   - Display summary to admin: total / imported / skipped / rejected
   - Store full rejection log for audit
```

### 7.3 Error Handling

| Scenario | Behaviour |
|---|---|
| Schema change detected | Halt import. Alert admin. No data written. |
| PII detected in transformed record | Halt entire import. Alert admin. Roll back transaction. |
| Key store unavailable | Halt import. Alert admin. No data written. |
| Individual record validation failure | Skip record, log reason, continue import. |
| Database connection failure mid-import | Roll back transaction. Alert admin. |

---

## 8. Data Retention

Per the charity's legal advice and the DPIA:

- Pseudonymised research data is retained **indefinitely** for research and statistical purposes under UK DPA 2018 s.26 and UK/EU GDPR Article 89
- Import batch logs are retained indefinitely (audit purposes)
- Rejection logs are retained for **2 years** then deleted
- The raw CSV staging file is **deleted immediately** after the pipeline completes (success or failure)
- If a member exercises their right to erasure and the charity determines the research exemption does not apply: the member's `pseudo_id` and all child records are deleted from the research DB. The `pseudo_id` is then added to the `erasure_register` table. On all future imports, the pipeline will detect this `pseudo_id` and skip the record without re-inserting it. Note: the HMAC key in Key Vault is a single shared secret — there are no per-member key entries to delete. The erasure register is the mechanism that prevents future re-import.

---

## 9. Open Questions / Items for Review

All questions from v0.1 resolved. No open questions.

| # | Question | Resolution |
|---|---|---|
| Q-01 | Full list of valid values for health fields | Confirmed via screenshot. Values incorporated into Section 3.3. |
| Q-02 | Non-UK European postcode handling | Outward code reduction applies to all European postcodes. |
| Q-03 | Key store technology | Azure Key Vault confirmed. See updated Section 5.3–5.4. |
| Q-04 | Gender vocabulary | Controlled: male / female. Updated in schema. |
| Q-05 | email_consent / is_volunteer scope | Operational fields only. Excluded from research DB. |

---

## Appendix A — Geographic Scope: Valid Country Values

Records with a `country` value matching any of the following are **in scope**. All others are dropped at Step 2.

**United Kingdom:**
England, Scotland, Wales, Northern Ireland, United Kingdom, UK, Great Britain

**EEA Member States:**
Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Iceland, Ireland, Italy, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Netherlands, Norway, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden

> **Note:** This list should be validated against the actual country values present in the membership export before implementation. Bolt should implement this as a configurable allowlist, not hardcoded values.
