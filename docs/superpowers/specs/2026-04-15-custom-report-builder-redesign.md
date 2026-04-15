# Custom Report Builder — Redesign Spec

**Date:** 2026-04-15
**Status:** Approved — ready for implementation planning

---

## Goal

Replace the existing block-composition custom report builder with a true ad-hoc query builder: researchers select fields to group by, apply per-field filters from populated dropdowns, and get a flat table of member counts. Reports can be saved and reloaded.

---

## Background

The original implementation composed pre-built statistical report blocks (r1–r8) onto a canvas. This did not match user needs. The correct mental model is a GROUP BY query builder: pick dimensions, apply filters, get a count table.

---

## Fields Available

Six fields are available as grouping dimensions and filters:

| Key | Label | Source | Value type |
|---|---|---|---|
| `country` | Country | `members.country` | Dynamic — distinct values from DB |
| `gender` | Gender | `members.gender` | Dynamic — distinct values from DB |
| `age_band` | Age Band | `members.age_band` | Dynamic — distinct values from DB |
| `leak_type` | CSF Leak Type | `csf_leak_types.leak_type` | Enum — spinal, cranial, spinalAndCranial, unknown |
| `cause_group` | Cause Group | `causes_of_leak.cause` → grouped | Enum — Iatrogenic, Connective Tissue Disorder, Spontaneous / Structural, Traumatic, Unknown / Not disclosed |
| `individual_cause` | Individual Cause | `causes_of_leak.cause` | Enum — 16 controlled values |

Membership status, region, member_since_year, and referral_source are **not** available in the custom builder.

`leak_type`, `cause_group`, and `individual_cause` are one-to-many per member — a member with multiple values will appear in multiple combinations, which is the correct analytical behaviour.

---

## Data Model

The existing `custom_reports` and `custom_report_audit` tables are kept unchanged. Only the `definition` JSONB column changes shape.

### Definition JSONB — new shape

```json
{
  "dimensions": ["country", "gender", "cause_group"],
  "filters": {
    "country": ["England", "Scotland"],
    "gender": ["Female"]
  }
}
```

**Validation rules:**
- `dimensions`: required, array of 1–6 valid field keys, no duplicates
- `filters`: optional, keys must be valid field keys, values are non-empty arrays of valid values for that field
- A field may appear in both `dimensions` and `filters` simultaneously

### Migration

Existing saved reports use the old block-based definition shape and are incompatible. The migration script will truncate `custom_report_audit` and `custom_reports` before deploying the new schema. No backward-compatibility layer.

---

## API

All endpoints under `/api/custom-reports/`. All require researcher role minimum.

### `GET /fields`

Returns all available fields with labels and allowed values. Dynamic fields query `DISTINCT` from the DB. Enum fields return hardcoded controlled vocabularies. Replaces the old `/blocks` endpoint.

**Response:**
```json
{
  "fields": [
    { "key": "country", "label": "Country", "values": ["England", "Scotland", ...] },
    { "key": "gender", "label": "Gender", "values": ["Female", "Male", ...] },
    { "key": "age_band", "label": "Age Band", "values": ["18–24", "25–34", ...] },
    { "key": "leak_type", "label": "CSF Leak Type", "values": ["spinal", "cranial", "spinalAndCranial", "unknown"] },
    { "key": "cause_group", "label": "Cause Group", "values": ["Iatrogenic", "Connective Tissue Disorder", ...] },
    { "key": "individual_cause", "label": "Individual Cause", "values": ["spinalSurgery", ...] }
  ]
}
```

### `POST /run`

Executes a definition without saving. Takes `{dimensions, filters}`, builds and runs the SQL query, returns the result table.

**Response:**
```json
{
  "columns": ["country", "gender", "cause_group"],
  "rows": [
    { "country": "England", "gender": "Female", "cause_group": "Iatrogenic", "member_count": 84 }
  ],
  "total_shown": 847,
  "suppressed_count": 3
}
```

`suppressed_count` is the number of GROUP BY combinations that had fewer than 10 members and were excluded from `rows`.

### `GET /` — List saved reports

Returns the current user's saved reports ordered by `updated_at DESC`. Scoped to `created_by = user.id`.

### `POST /` — Create report (201)

Creates a new saved report. Validates definition shape. Writes `create` audit row.

### `GET /{id}` — Get report

Returns the saved report definition. 404 if not owned by current user.

### `POST /{id}` — Update report

Updates name, description, or definition. Writes `update` audit row.

### `POST /{id}/delete` — Delete report (204)

Deletes the report. Audit row survives (nullable `report_id`). Writes `delete` audit row.

### `POST /{id}/run` — Run saved report

Loads the stored definition, executes the query, writes `run` audit row, returns same response shape as `POST /run`.

---

## SQL Query Builder

The query is built dynamically from the definition. All queries use `COUNT(DISTINCT m.pseudo_id)` to avoid double-counting when joining one-to-many tables.

```sql
SELECT
  [dimension columns],
  COUNT(DISTINCT m.pseudo_id) AS member_count
FROM members m
[LEFT JOIN csf_leak_types clt ON clt.pseudo_id = m.pseudo_id]   -- if leak_type in dimensions or filters
[LEFT JOIN causes_of_leak col ON col.pseudo_id = m.pseudo_id]   -- if cause_group or individual_cause in dimensions or filters
WHERE
  [filter conditions]
GROUP BY
  [dimension columns]
HAVING
  COUNT(DISTINCT m.pseudo_id) >= 10
ORDER BY
  [dimension columns]
```

`cause_group` uses a `CASE WHEN col.cause IN (...) THEN 'GroupName' ...` expression (the existing `CAUSE_GROUP_CASE_EXPR` constant from `reports/__init__.py`).

A second query counts suppressed combinations:

```sql
SELECT COUNT(*) FROM (
  SELECT COUNT(DISTINCT m.pseudo_id) AS n
  FROM members m ...
  GROUP BY [dimensions]
  HAVING COUNT(DISTINCT m.pseudo_id) < 10
) suppressed
```

---

## Cohort Suppression

The `HAVING COUNT(DISTINCT m.pseudo_id) >= 10` clause is applied unconditionally on every query. Suppressed combinations are never returned in `rows`. The response always includes `suppressed_count`. When `suppressed_count > 0`, the UI displays an amber notice:

> ⚠ **N combinations hidden** — fewer than 10 members each. These are not shown to protect member privacy.

---

## UI

The custom report builder page replaces the existing `report_builder.html` template and `report_builder.js`. It uses the existing CSS design tokens and component patterns throughout.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Custom Reports          [name input]  [New] [Save] [▶ Run]  │
├─────────────────────────────────────────────────────────────┤
│ Saved: [Report A ×] [Report B] [Report C]                   │
├──────────────────────┬──────────────────────────────────────┤
│  LEFT PANEL          │  RIGHT PANEL                         │
│  ─────────────────   │  ─────────────────────────────────   │
│  GROUP BY            │  Results                             │
│  [● Country  1st]    │  ⚠ 3 combinations hidden             │
│  [● Gender   2nd]    │  ┌──────────────────────────────┐    │
│  [● CauseGrp 3rd]    │  │ Country│Gender│CauseGrp│Count│    │
│  [  Age Band + add]  │  │ England│Female│Iatrogenic│ 84 │    │
│  [  LeakType + add]  │  │ ...    │ ...  │  ...   │ .. │    │
│                      │  └──────────────────────────────┘    │
│  FILTERS             │                                      │
│  Country: [dropdown] │                                      │
│  [England ×][Wales ×]│                                      │
│  Gender: [dropdown]  │                                      │
│  [Female ×]          │                                      │
└──────────────────────┴──────────────────────────────────────┘
```

### Left panel — dimensions

Six field pills, each toggled on/off by clicking. Active pills show their order (1st, 2nd, 3rd…) in a small badge. Maximum 6 active. Individual Cause is visually de-emphasised with a note about high suppression risk.

### Left panel — filters

A filter section appears automatically for each active dimension. Additionally, a small **"Filter on another field"** `<select>` at the bottom of the filter panel lets users add a filter on any field that is not currently a dimension — this narrows the population without adding that field as a table column (e.g. filter to Female members without showing Gender as a column).

Each filter block shows:
- A `<select>` dropdown populated from `/fields` — pick a value to add to the filter
- Removable tag chips for currently active filter values
- A remove button on the filter block itself (for filter-only fields; dimension filters are removed by toggling the dimension off)

### Right panel — results

- Header: "Results" + metadata (member count shown, last run time)
- Amber suppression notice when `suppressed_count > 0`
- A card-wrapped `<table>` with one column per dimension + a right-aligned Members count column
- Empty state before first run: "Select fields and press Run"

### Save flow

- Report name input in page header (required before save)
- **Save** writes to `POST /` (new) or `POST /{id}` (existing)
- After first save, URL updates to `/reports/builder/{id}`
- Saved reports bar shows all saved reports as clickable chips; clicking loads that report's definition into the builder

### Styling

All colours, spacing, radius, and typography from `main.css` design tokens. No new CSS classes introduced beyond what is needed. Table uses the same `.card`-style container and thead/tbody patterns as the existing report views.

---

## Tests

- Unit tests for the SQL builder: correct JOIN selection, correct HAVING clause, suppression count query
- API tests: fields endpoint returns 6 fields; run endpoint returns correct shape; CRUD ownership enforcement; suppression_count in response; 401/403 enforcement
- UI route tests: builder pages require auth

---

## Files

| Action | Path |
|---|---|
| Modify | `app/db/models.py` — no schema change, migration script added |
| Replace | `app/api/routes/custom_reports.py` — new query builder logic |
| Delete | `app/reports/blocks.py` — no longer used by custom reports |
| Replace | `app/templates/report_builder.html` |
| Replace | `app/static/js/report_builder.js` |
| Add | `app/db/migrations/truncate_custom_reports.sql` |
| Modify | `app/tests/test_api/test_custom_reports.py` |
