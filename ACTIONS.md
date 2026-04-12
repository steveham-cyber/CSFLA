# Action Tracker

Last updated: 2026-04-12 (v17)

> This file tracks all open, in-progress, and completed actions across the project. Update it whenever an action is resolved or a new one is identified. Review at the start of each session.

---

## Open — Awaiting Owner / External

| # | Action | Owner | Raised by | Notes |
|---|---|---|---|---|
| A-01 | Owner and Board approve DPIA v0.2 | Data protection lead + Board | Lex | DPIA updated to v0.2 — `is_volunteer` corrected, actions 4/5/6 closed. Ready for owner read-through and Board sign-off. Blocks go-live and Privacy Policy v1.1. |
| A-02 | Obtain Data Processing Agreement with Anthropic (Claude API) | Owner / Data protection lead | Lex | Required before Claude API goes live in production. Owner to review Anthropic's standard DPA for UK/EU GDPR adequacy. AI module locked in codebase until complete. |

---

## Open — Team (In Progress or Pending)

| # | Action | Owner | Raised by | Notes |
|---|---|---|---|---|
| A-08 | Update Privacy Policy to v1.1 | Lex | Lex | Pending DPIA approval (A-01). Will reference the research application and pseudonymisation pipeline. |

---

## Completed

| # | Action | Completed | Notes |
|---|---|---|---|
| C-01 | Review membership data export (users.csv) | 2026-04-11 | Atlas and Lex reviewed. Full field inventory complete. |
| C-02 | Review Privacy Policy v1.0 | 2026-04-11 | Lex reviewed. ICO registration confirmed. Legal basis for health data research confirmed. |
| C-03 | Clarify `contactedAboutParticipationInResearch` field | 2026-04-11 | Confirmed: relates to separate NHS research programme. Strip from research pipeline entirely. |
| C-04 | Confirm data retention position | 2026-04-11 | Consultant advice confirmed: pseudonymised data may be retained indefinitely for research/statistical purposes under UK DPA 2018 s.26. |
| C-05 | Draft DPIA v0.1 | 2026-04-11 | Lex produced. Saved as `DPIA v0.1 (Draft for Review).md`. Pending owner review and approval (A-01). |
| C-06 | Create team roster and profiles | 2026-04-11 | All 9 team members profiled. See `Team/ROSTER.md`. |
| C-07 | Design application architecture | 2026-04-11 | Full architecture, stack, and implementation phases defined. See session notes. |
| C-08 | Produce Data Architecture Spec v0.1 | 2026-04-11 | Atlas produced. Superseded by v0.2. |
| C-09 | Resolve all Atlas open questions (Q-01 to Q-05) | 2026-04-11 | All 5 questions answered by owner. Data Architecture Spec updated to v0.2. |
| C-10 | Confirm OAuth provider (A-03) | 2026-04-11 | Microsoft Entra ID (M365). |
| C-11 | Confirm hosting environment (A-04) | 2026-04-11 | Azure. Full stack: Azure hosting + Entra ID + Azure Key Vault. |
| C-12 | Cipher: Threat model and security requirements v0.1 | 2026-04-11 | Saved as `Security Threat Model v0.1 (Draft for Review).md`. Pending Lex review and owner approval. |
| C-13 | Bolt: Application scaffolding and Azure Bicep | 2026-04-11 | `app/` and `infra/` created. Pipeline and AI modules locked pending sign-off. |
| C-14 | Nova: Standard report specifications v0.1 | 2026-04-11 | 8 reports specified. Saved as `Report Specifications v0.1.md`. Ready for Sketch (wireframes) and Bolt (implementation). |
| C-15 | Sketch: Wireframes v0.1 | 2026-04-11 | Superseded by v0.2. |
| C-16 | Sketch: Wireframes v0.2 — W-02/03/04 resolved | 2026-04-11 | W-02 SVG maps, W-03 browser-session AI, W-04 browser print PDF all confirmed. W-01 brand colours still pending. `Future Enhancements.md` created. |
| C-17 | Sketch: Wireframes v0.3 — W-01 resolved, brand palette confirmed | 2026-04-11 | Colours extracted from Quisk Style Guide. Wireframes updated to v0.3. CSS written to `app/static/css/main.css`. All wireframe items resolved. |
| C-18 | Probe: Test strategy v0.1 and test environment | 2026-04-11 | Test Strategy v0.1 saved. Pipeline utility modules created. conftest.py, 4 fixture CSVs, and blocking test files written. pytest.ini configured with asyncio_mode=auto. |
| C-19 | Cipher + Lex: Joint review of Data Architecture Spec v0.2 | 2026-04-11 | 4 issues raised (C-SEC-01 to C-SEC-04 / L-GDPR-01 to L-GDPR-02). Security Threat Model v0.1 signed off by Lex. Atlas produced v0.3 resolving all issues. |
| C-20 | Cipher + Lex: Sign off Data Architecture Spec v0.3 | 2026-04-11 | Both signed off. Pipeline implementation (A-10) unblocked. |
| C-21 | Bolt: Initialise GitHub repository | 2026-04-11 | Git repo initialised. 64 files committed. `.github/workflows/test.yml` CI pipeline created. Branch protection to be configured after pushing to GitHub remote. |
| C-22 | Lex: DPIA actions 4, 5, 6 resolved | 2026-04-11 | OAuth confirmed as Entra ID (4), hosting confirmed as Azure (5), Article 27 representative obligation confirmed not triggered (6). DPIA updated to v0.2. |
| C-23 | Bolt: Import pipeline implemented | 2026-04-11 | Full ETL pipeline per Data Architecture Spec v0.3. `pipeline/__init__.py`, `pipeline/key_vault.py`, `ErasureRegister` model added, `imports.py` route wired up. `azure-keyvault-secrets` added to requirements. 10 integration tests in `test_import_pipeline.py`. |
| C-24 | Bolt: All 8 standard report backends implemented | 2026-04-11 | `reports/__init__.py` updated (added `pct()` helper). `reports/r1_cohort.py` through `reports/r8_referral.py` written. `api/routes/reports.py` rewritten with 8 individual endpoints. Chi-square test in R7 (scipy). NULL referral_source handled separately in R8. k≥10 enforced throughout. |
| C-27 | Bolt: Push to GitHub and configure branch protection | 2026-04-12 | Repository pushed to steveham-cyber/CSFLA. CI workflow active. Branch protection configured on main: require PR + passing tests, no direct push, no force push. |
| C-28 | Bolt: Fix all CI test failures — 335/335 passing | 2026-04-12 | Fixed 7 failures from CI run #4: viewer role in require_researcher, r6 leak_type JOIN, sufferer count corrections (France member), admin import test, trailing slash 307 redirect. Merged as PR #1. |
| C-29 | Bolt: Fix local dev setup and real CSV parsing | 2026-04-12 | Application running locally end-to-end. Fixes: JSON array CSV format, cause vocab normalisation (5 field name mappings), MSAL OIDC scopes, same_site=lax for OAuth, TEST_PSEUDONYMISATION_KEY via pydantic-settings, numpy/scipy version pins. Merged as PR #2. All 8 reports verified with real users.csv data. |
| C-25 | Probe: Integration tests for all 8 report backends | 2026-04-11 | `app/tests/test_reports/conftest.py` with 24-member `standard_cohort` fixture (12 England / 9 Scotland / 2 Germany / 1 France). `test_r1_cohort.py` through `test_r8_referral.py` written. Tests cover structure, suppression (k≥10), filters, and empty-cohort edge cases. Transaction-rollback pattern with `db.flush()`. |
| C-26 | Sketch + Bolt: Full UI template set | 2026-04-11 | `app/templates/base.html` (app shell, nav, auth-gated admin links). `dashboard.html` (metric cards + Chart.js charts). `reports_list.html` (8 report cards). `report_view.html` (filter panel, per-report renderers, print/PDF). `import.html` (drag-drop upload, 6-step progress, history). `ai_analysis.html` (module-locked notice). `admin.html` (cohort stats + last import). CSS utilities added to `main.css` (metric-value, report-card, table-scroll, data-table, cell-suppressed, filter-input, denominator-note, etc). |
