# User Guide Page — Design Spec

**Date:** 22 April 2026
**Status:** Approved
**Author:** Goose / Sketch (CSFLA AI Team)

---

## Goal

Add a `/help` page to the CSFLA Research Application — a static, single-scrolling user guide covering all features, accessible to all authenticated roles.

---

## Architecture

- New route: `GET /help` in `app/api/routes/ui.py`
- New template: `app/templates/help.html` extending `base.html`
- No backend data required — fully static HTML content
- No new dependencies

---

## Layout

Two-column layout within the standard app frame:

```
┌─────────────────────────────────────────────────────────┐
│ App nav (existing)                                       │
├──────────────┬──────────────────────────────────────────┤
│              │                                          │
│  Table of    │  Guide content                           │
│  Contents    │  (scrollable)                            │
│  (sticky)    │                                          │
│              │                                          │
│  § 1         │  ## 1. Getting started                   │
│  § 2         │  ...                                     │
│  § 3         │  ## 2. The dashboard                     │
│  § 4         │  ...                                     │
│  § 5         │                                          │
│  § 6         │                                          │
│  § 7         │                                          │
└──────────────┴──────────────────────────────────────────┘
```

- Left column: ~220px, `position: sticky; top: var(--space-6)` — scrolls with the page until it hits the top, then sticks
- Right column: fills remaining width, standard card padding
- On mobile (< 768px): table of contents moves above content, no longer sticky
- Anchor links in the TOC use smooth scroll (`scroll-behavior: smooth` on html element)

---

## Navigation

Add a **"Help"** nav item to the sidebar in `base.html`, visible to all authenticated roles. Positioned after the last existing nav item before admin items.

`active_nav` value: `"help"`

---

## Access Control

- Route requires authenticated session (same as all other UI routes)
- No role restriction — viewer, researcher, and admin all see the full page
- Admin-only sections are labelled with a visible `ADMIN ONLY` badge
- Researcher-and-admin sections are labelled with a `RESEARCHER & ADMIN` badge
- Labels inform rather than restrict — no content is hidden

---

## Content Sections

### 1. Getting started
*All roles*

- How to log in (Microsoft account via the sign-in button)
- Overview of the navigation sidebar: what each item is and who can see it
- How to log out

### 2. The dashboard
*All roles*

- What "Total Cohort" means (all members, not just sufferers)
- What "Diagnosed" and "Suspected" mean and how they differ
- What "Countries" counts
- The three dashboard charts and what they show
- The "Last import" badge and what it means

### 3. Standard reports
*All roles*

One sub-section per report. Each explains:
- What the report shows and why it matters
- How to use the filters
- How to interpret suppressed cells (< 10 members)
- Any caveats specific to that report

Reports covered:
- R1: Cohort Overview
- R2: Diagnostic Status Profile
- R3: CSF Leak Type Distribution
- R4: Cause of Leak Analysis
- R5: Geographic Distribution
- R6: Membership Growth & Trends
- R7: Cause × Type Cross-Analysis

### 4. Custom report builder
*Researcher & Admin badge*

- How to create a new custom report (choose metrics, add filters, name it)
- How to run a saved report
- How to edit or delete a saved report
- Note that custom reports are personal — not shared between users

### 5. Importing data
*Admin only badge*

- What file format is expected (CSV export from the membership system)
- Required columns: `id`, `dateOfBirth`, `gender`, `country`, `postcodeZipCode`, `memberStatus`, `csfLeakType`, `causeOfLeak`, `memberSince`
- Optional columns: `manualStart`, `dateCreated` (used as fallback for membership year)
- Step-by-step import process: navigate to Import, upload file, review summary, confirm
- What happens to PII (pseudonymised on load — raw data never stored)
- What to do if the import fails (check the error message, re-export from membership system)

### 6. Managing users
*Admin only badge*

- Users are managed in Azure (Microsoft Entra ID), not within the app
- Step-by-step: how to add a new user and assign them a role
- The three roles explained: Admin, Researcher, Viewer
- How to remove a user's access (remove their role assignment in Entra ID)
- Note: changes take effect at the user's next login

### 7. Data privacy
*All roles*

- What data is stored: pseudonymised health and demographic data only — no names, email addresses, or direct identifiers
- What pseudonymisation means: a one-way process — the app cannot reverse it to identify individuals
- Legal basis: UK GDPR / EU GDPR — legitimate interests and public task (charity research purpose)
- Data location: UK South Azure region — data does not leave the UK/EEA
- Who has access: only users with assigned roles in the system
- Retention: governed by the charity's data retention policy
- For questions: direct users to the charity's Data Protection Officer

---

## Styling

- Uses existing CSS variables and component classes throughout (`card`, `label-small`, `data-table`, etc.)
- Section headings use `<h3>` (matching report page headings)
- Role badges styled as small inline labels: background `var(--color-bg-subtle)`, border `1px solid var(--color-border)`, `font-size: var(--font-size-xs)`, `border-radius: 4px`, padding `2px 6px`
- `ADMIN ONLY` badge uses `var(--color-warning)` tint background
- `RESEARCHER & ADMIN` badge uses `var(--color-primary)` tint background
- TOC links use `color: var(--color-text-muted)` when inactive, `var(--color-primary)` when active section is in view (via IntersectionObserver)

---

## Files to Create / Modify

| File | Change |
|---|---|
| `app/templates/help.html` | New file — full guide content |
| `app/api/routes/ui.py` | Add `GET /help` route |
| `app/templates/base.html` | Add "Help" nav item |

---

## Out of Scope

- Editable/CMS guide content (deferred — static for now)
- Search within the guide
- Per-role content filtering (sections labelled, not hidden)
- Video or interactive walkthrough content
