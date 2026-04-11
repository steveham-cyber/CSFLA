# Action Tracker

Last updated: 2026-04-11 (v10)

> This file tracks all open, in-progress, and completed actions across the project. Update it whenever an action is resolved or a new one is identified. Review at the start of each session.

---

## Open — Awaiting Owner / External

| # | Action | Owner | Raised by | Notes |
|---|---|---|---|---|
| A-01 | Complete and sign off DPIA v0.1 | Data protection lead + Board | Lex | Draft at `DPIA v0.1 (Draft for Review).md`. Read, correct, and get approved before go-live. |
| A-02 | Obtain Data Processing Agreement with Anthropic (Claude API) | Owner / Data protection lead | Lex | Required before Claude API goes live in production. Check if Anthropic's standard DPA covers UK/EU GDPR adequacy. |
| A-09 | Produce threat model and security requirements document | Cipher | Goose | Now unblocked. Full Azure stack confirmed: Entra ID, Azure hosting, Azure Key Vault. |
| A-05 | Take advice on EU GDPR Article 27 representative obligation | Owner / legal adviser | Lex | Charity processes EU residents' health data systematically. Quick legal question — needed before go-live. |
| A-06 | Request research-specific export from membership system | Owner | Lex | Membership system should produce an export that excludes auth fields (password, verification codes, login IPs) entirely, rather than relying on the pipeline to strip them. Defence in depth. |

---

## Open — Team (In Progress or Pending)

| # | Action | Owner | Raised by | Notes |
|---|---|---|---|---|
| A-07 | Cipher and Lex sign-off on Data Architecture Spec v0.3 | Cipher + Lex | Atlas | Draft at `Data Architecture Spec v0.3 (Draft for Review).md`. All review issues resolved. Return for final sign-off. |
| A-08 | Update Privacy Policy to v1.1 | Lex | Lex | Pending DPIA approval (A-01). Will reference the research application and pseudonymisation pipeline. |
| A-09 | Produce threat model and security requirements document | Cipher | Goose | Begins after Atlas's architecture spec (A-07) is drafted. Lex review also required. |
| A-10 | Sign off pseudonymisation spec and pipeline design | Cipher + Lex | Goose | Joint sign-off required before Bolt begins any data pipeline implementation. Unblocked once A-07 is complete. |
| A-11 | Initialise GitHub repository and push scaffolding | Bolt | Goose | Local scaffolding complete. Push to private GitHub repo when ready. Branch protection to be configured on push. |

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
