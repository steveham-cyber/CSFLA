# Wireframes v0.3
## CSF Leak Association — Research Data Application

**Document status:** v0.3 — All open items resolved. Brand palette confirmed from Quisk Style Guide.
**Prepared by:** Sketch (UX/UI Designer)  
**Date:** 2026-04-11 | Updated: 2026-04-11  
**Changes in v0.3:** W-01 resolved — brand colours extracted from Quisk Style Guide (Sept 2021). Inter font family confirmed. CSS variables written to `app/static/css/main.css`.  
**For:** Bolt (implementation), Nova (research accuracy review), Cipher (privacy review)

---

## Design Principles Applied

1. **Aggregate only** — no screen ever displays an individual member record. Every number represents a group.
2. **Suppression is visible** — when k<10, data is not hidden silently. A suppression notice is shown in place of the data.
3. **Context always present** — every chart or metric shows its denominator ("of 1,847 sufferers with known leak type").
4. **Export scope is limited** — export buttons produce report output (charts as PNG, data as CSV of aggregates). No raw data export anywhere.
5. **Destructive actions require confirmation** — importing data, deleting batches.
6. **Colour-blind-safe palette** — all charts use a sequential or diverging palette safe for deuteranopia/protanopia. No red/green encoding.

---

## Palette & Typography Notes (for Bolt)

> ✓ **W-01 RESOLVED** — Colours confirmed from Quisk Style Guide (Sept 2021). CSS variables written to `app/static/css/main.css`. Do not override these values without design sign-off.

```
SOURCE: Quisk Style Guide, 1 Sept 2021

── Brand Blues ──────────────────────────────────────────────
Title / heading blue:   #334D6E   (Inter-Black headings)
Primary action blue:    #4C98C6   (buttons, CTAs, nav active)
Bright link blue:       #438AE1   (links, interactive elements)
Deep gradient end:      #29508E   (gradient anchors)
Teal accent:            #286F8C   (secondary gradient)

── Text ─────────────────────────────────────────────────────
Body text:              #424752
Muted / secondary:      #424752 at opacity 0.7

── Backgrounds ──────────────────────────────────────────────
Page background:        #EAF0F5
Card / surface:         #F2F5FA
Dark surface (nav):     #394256
Darkest surface:        #272D3B
Border:                 #E1E4EC
Shape fill (subtle):    #D7E4EF

── Accent ───────────────────────────────────────────────────
Yellow (highlight/warn): #FFC55C   (brand accent — not red/green)
White:                   #FFFFFF

── Chart palette (colour-blind safe, derived from brand blues)
  #334D6E  #4C98C6  #438AE1  #9CC9FF  #FFC55C  #286F8C

── Suppressed cells ─────────────────────────────────────────
  #D7E4EF with hatched pattern (not colour alone)

── Typography ───────────────────────────────────────────────
Font family:  Inter (Inter-Regular, Inter-Medium, Inter-Bold, Inter-Black)
              Load via Google Fonts: https://fonts.google.com/specimen/Inter
Title:        Inter-Black, 60px / 64px, letter-spacing: -1.25px
Section head: Inter-Black, adapted size
Body:         Inter-Regular, 17px / 25px
Small label:  Inter-Regular, 13px, letter-spacing: 1px, opacity 0.7
Metric:       Inter-Black, tabular-nums
```

---

## Screen 1 — Application Shell (persistent layout)

```
┌─────────────────────────────────────────────────────────────────────┐
│  ╔═══════════╗  CSFLA Research                    [Steve Hamilton ▾] │
│  ║  CSF Leak ║                                     [researcher role] │
│  ║   Assoc.  ║                                                       │
│  ╚═══════════╝                                                       │
├──────────┬──────────────────────────────────────────────────────────┤
│          │                                                           │
│ ▣ Dashboard                                                          │
│           │                  MAIN CONTENT AREA                      │
│ ↑ Import  │                                                          │
│           │                                                          │
│ ▦ Reports │                                                          │
│  Standard │                                                          │
│  Custom   │                                                          │
│           │                                                          │
│ ✦ AI      │                                                          │
│  Analysis │                                                          │
│           │                                                          │
│ ─────     │                                                          │
│           │                                                          │
│ ⚙ Admin   │                                                          │
│  (admin   │                                                          │
│   only)   │                                                          │
│           │                                                          │
│ ↩ Sign out│                                                          │
│           │                                                          │
│ v0.1.0    │                                                          │
└──────────┴──────────────────────────────────────────────────────────┘
```

**Notes:**
- Left nav is always visible on desktop (≥1024px). Collapses to icon-only at 768–1023px. Bottom tab bar on mobile.
- User name and role shown in top-right. Role label always visible — reinforces what the user can and cannot do.
- Admin section only visible to admin role. Hidden entirely for researcher and viewer.
- No notification bell, no profile page. User management is in Entra ID, not the app.

---

## Screen 2 — Research Dashboard

```
┌─────────────────────────────────────────────────────────────────────┐
│ Research Dashboard                          Last import: 08 Apr 2026 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐│
│  │ Total Cohort │  │  Diagnosed   │  │   Suspected  │  │Countries ││
│  │              │  │              │  │              │  │          ││
│  │    2,847     │  │   1,203      │  │    1,012     │  │    24    ││
│  │   members    │  │  42.3%       │  │   35.5%      │  │ UK + EU  ││
│  │              │  │  of sufferers│  │  of sufferers│  │          ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘│
│                                                                      │
│  ┌─────────────────────────────┐  ┌──────────────────────────────┐  │
│  │ Member Status               │  │ CSF Leak Type                │  │
│  │                             │  │ (sufferers with known type)  │  │
│  │  ████ Diagnosed    42.3%    │  │                              │  │
│  │  ████ Suspected    35.5%    │  │    ████ Spinal       54%     │  │
│  │  ████ Former        8.1%    │  │    ████ Cranial      18%     │  │
│  │  ████ Family/Friend 9.7%    │  │    ████ Both         14%     │  │
│  │  ████ Med. Prof.    4.4%    │  │    ████ Unknown      14%     │  │
│  │                             │  │                              │  │
│  │ [View full report →]        │  │ [View full report →]         │  │
│  └─────────────────────────────┘  └──────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Cohort Growth                              [View full report →] │ │
│  │                                                                 │ │
│  │  400 ┤                                              ▄▄          │ │
│  │  300 ┤                                    ▄▄    ▄▄▄▄██          │ │
│  │  200 ┤                          ▄▄    ▄▄▄▄██▄▄▄▄████▄          │ │
│  │  100 ┤              ▄▄     ▄▄▄▄▄██▄▄▄▄████████████████          │ │
│  │    0 └──────────────────────────────────────────────────        │ │
│  │       2016  2017  2018  2019  2020  2021  2022  2023  2024      │ │
│  │                                         New members per year    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

**Notes:**
- Metric cards: large number, contextual denominator below in muted text. No sparklines — keep it clear.
- "Last import" date shown top-right. If no import in >90 days, show a warning indicator.
- All chart preview cards link to their full report.
- No individual member data anywhere on this screen.

---

## Screen 3 — Import Dashboard (admin only)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Data Import                                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │          ┌─────────────────────────────────────┐             │  │
│  │          │                                     │             │  │
│  │          │      ↑  Drop CSV file here           │             │  │
│  │          │         or click to browse           │             │  │
│  │          │                                     │             │  │
│  │          │      Accepted: .csv  Max: 50MB       │             │  │
│  │          └─────────────────────────────────────┘             │  │
│  │                                                               │  │
│  │  ⚠ This will process real member data. The pipeline will     │  │
│  │    pseudonymise all records before storage. Non-European      │  │
│  │    records will be excluded automatically.                    │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Import History                                                      │
│  ┌──────────────┬───────────┬───────────┬──────┬────────┬────────┐  │
│  │ Date         │ Imported  │ Skipped   │ Excl.│ Errors │        │  │
│  ├──────────────┼───────────┼───────────┼──────┼────────┼────────┤  │
│  │ 08 Apr 2026  │ 2,847     │ 312 (geo) │ 4    │ 0      │[Detail]│  │
│  │ 10 Jan 2026  │ 2,701     │ 298 (geo) │ 2    │ 0      │[Detail]│  │
│  │ 05 Oct 2025  │ 2,598     │ 287 (geo) │ 3    │ 0      │[Detail]│  │
│  └──────────────┴───────────┴───────────┴──────┴────────┴────────┘  │
│                                                                      │
│  Columns: Date | Imported (in-scope records written) |               │
│           Skipped (out-of-scope geography) |                         │
│           Excluded (failed validation) | Errors | Detail link        │
└──────────────────────────────────────────────────────────────────────┘
```

**Import progress state (shown after file selected):**
```
  ┌───────────────────────────────────────────────────────────────┐
  │ Processing: members_export_apr2026.csv                        │
  │                                                               │
  │  ✓ File validated                                             │
  │  ✓ Schema verified                                            │
  │  ✓ Geographic filter: 312 non-European records excluded       │
  │  ◌ Pseudonymising records...  ████████████░░░░  68%           │
  │  ◌ Writing to research database                               │
  │  ◌ Finalising batch record                                    │
  │                                                               │
  │  [Cancel]  (only available before DB write begins)            │
  └───────────────────────────────────────────────────────────────┘
```

**Import complete state:**
```
  ┌───────────────────────────────────────────────────────────────┐
  │ ✓ Import complete                                             │
  │                                                               │
  │  2,847  records imported                                      │
  │    312  excluded (outside UK/EEA)                             │
  │      4  skipped (validation errors — see detail)              │
  │      0  errors                                                │
  │                                                               │
  │  Raw file deleted from staging.    [View detail]  [Done]      │
  └───────────────────────────────────────────────────────────────┘
```

**Notes:**
- File is never shown by name after upload confirmation — just the processing status.
- "Raw file deleted from staging" shown explicitly so the admin knows it's gone.
- Cancelled imports roll back completely — no partial data.

---

## Screen 4 — Standard Reports List

```
┌─────────────────────────────────────────────────────────────────────┐
│ Standard Reports                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐          │
│  │ 1. Cohort Overview      │  │ 2. Diagnostic Status     │          │
│  │                         │  │    Profile               │          │
│  │ Population summary,     │  │                          │          │
│  │ status breakdown,       │  │ Diagnosed vs suspected   │          │
│  │ geographic spread.      │  │ rates by demographics.   │          │
│  │                         │  │                          │          │
│  │ Last run: 08 Apr 2026   │  │ Last run: 08 Apr 2026    │          │
│  │               [Run →]   │  │               [Run →]    │          │
│  └─────────────────────────┘  └─────────────────────────┘          │
│                                                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐          │
│  │ 3. Leak Type            │  │ 4. Cause of Leak         │          │
│  │    Distribution         │  │    Analysis              │          │
│  │                         │  │                          │          │
│  │ Spinal vs cranial       │  │ Iatrogenic, connective   │          │
│  │ distribution and        │  │ tissue, spontaneous,     │          │
│  │ demographic patterns.   │  │ traumatic breakdown.     │          │
│  │                         │  │                          │          │
│  │ Last run: 08 Apr 2026   │  │ Last run: 08 Apr 2026    │          │
│  │               [Run →]   │  │               [Run →]    │          │
│  └─────────────────────────┘  └─────────────────────────┘          │
│                                                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐          │
│  │ 5. Geographic           │  │ 6. Membership Growth     │          │
│  │    Distribution         │  │    & Trends              │          │
│  │                         │  │                          │          │
│  │ UK regions and          │  │ Cohort growth and        │          │
│  │ European countries.     │  │ composition over time.   │          │
│  │                         │  │                          │          │
│  │ Last run: 08 Apr 2026   │  │ Last run: 08 Apr 2026    │          │
│  │               [Run →]   │  │               [Run →]    │          │
│  └─────────────────────────┘  └─────────────────────────┘          │
│                                                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐          │
│  │ 7. Cause × Type         │  │ 8. Referral Source       │          │
│  │    Cross-Analysis  ★    │  │    Analysis              │          │
│  │                         │  │                          │          │
│  │ Relationship between    │  │ How members discover     │          │
│  │ cause and anatomical    │  │ the charity.             │          │
│  │ location. Chi-square.   │  │                          │          │
│  │                         │  │                          │          │
│  │ Last run: 08 Apr 2026   │  │ Last run: 08 Apr 2026    │          │
│  │               [Run →]   │  │               [Run →]    │          │
│  └─────────────────────────┘  └─────────────────────────┘          │
│                                                                      │
│  ★ = High research value                                             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Screen 5 — Standard Report View (generic layout)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← Reports   Report 4: Cause of Leak Analysis                        │
│             Cohort: 2,535 sufferers  ·  Data as of: 08 Apr 2026     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Filters  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐   │
│           │ Status: All ▾│  │Country: All│  │ Years: All time ▾│   │
│           └──────────────┘  └────────────┘  └──────────────────┘   │
│           ┌──────────────┐  ┌────────────┐  [Reset filters]         │
│           │  Age: All   ▾│  │Gender: All▾│                          │
│           └──────────────┘  └────────────┘                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Cause Group Summary                    of 2,535 sufferers          │
│                                                                      │
│  Iatrogenic          ████████████████████████  847  (33.4%)         │
│  Unknown / Ndisclosed ███████████████████       612  (24.1%)         │
│  Connective Tissue   ████████████              489  (19.3%)         │
│  Spontaneous/Struct. ██████████                378  (14.9%)         │
│  Traumatic           █████                     209   (8.2%)         │
│                                                                      │
│  [▼ Show individual causes]                                          │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Breakdown by: [Leak Type ▾]  [Diagnostic Status ▾]                 │
│                                                                      │
│  Cause × Leak Type (% of cause group)                               │
│                                                                      │
│                    Spinal    Cranial   Both     Unknown              │
│  Iatrogenic        58.2%     12.4%     18.1%    11.3%               │
│  Conn. Tissue      61.1%      9.8%     22.5%     6.6%               │
│  Spontaneous       49.2%     24.3%     11.8%    14.7%               │
│  Traumatic         44.5%     28.2%     16.3%    11.0%               │
│  Unknown           38.1%     19.6%     12.4%    29.9%               │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ⚠ 3 cells suppressed (group size < 10). Shown in grey above.       │
│                                                                      │
│  [ Export report as PDF ]  [ Export data as CSV ]                   │
│    (charts + summary)        (aggregates only)                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Notes:**
- Filter bar is persistent and collapses to a "Filters (3 active)" summary on small screens.
- Cohort size updates dynamically when filters change. If filters reduce cohort below 10, the entire report shows the suppression notice and no data.
- Export CSV produces the aggregate table only — never raw records.
- Suppression notice is always shown if any cells are suppressed, even if the user might not notice the grey cells.

---

## Screen 6 — Report 7: Cause × Type Cross-Analysis (complex view)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← Reports   Report 7: Cause × Type Cross-Analysis          ★        │
│             Cohort: 2,535 sufferers  ·  Data as of: 08 Apr 2026     │
├─────────────────────────────────────────────────────────────────────┤
│  Filters  [Status: Diagnosed only ▾]  [Country: All ▾]  [Reset]    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  View: [Matrix ●]  [Heatmap ○]          Show: [Groups ●] [Detail ○] │
│                                                                      │
│  CAUSE GROUP        │  Spinal  │ Cranial │  Both   │ Unknown │ Total │
│  ───────────────────┼─────────┼─────────┼─────────┼─────────┼───────│
│  ▶ Iatrogenic       │  58.2%  │  12.4%  │  18.1%  │  11.3%  │  847  │
│  ▶ Connective Tissue│  61.1%  │   9.8%  │  22.5%  │   6.6%  │  489  │
│  ▶ Spontaneous      │  49.2%  │  24.3%  │  11.8%  │  14.7%  │  378  │
│  ▶ Traumatic        │  44.5%  │  28.2%  │  16.3%  │  11.0%  │  209  │
│  ▶ Unknown/NDiscl.  │  38.1%  │  19.6%  │  12.4%  │  29.9%  │  612  │
│                                                                      │
│  (▶ = click to expand to individual causes)                          │
│                                                                      │
│  ─── Expanded example ──────────────────────────────────────────    │
│  ▼ Iatrogenic       │  58.2%  │  12.4%  │  18.1%  │  11.3%  │  847  │
│    Lumbar Puncture  │  61.4%  │  11.2%  │  17.8%  │   9.6%  │  312  │
│    Spinal Surgery   │  72.3%  │   8.1%  │  14.2%  │   5.4%  │  198  │
│    Epidural         │  55.1%  │  14.8%  │  19.6%  │  10.5%  │  143  │
│    Spinal Anaesth.  │  54.8%  │  13.2%  │  21.4%  │  10.6%  │  ░░░  │
│    Cranial Surgery  │   ░░░   │   ░░░   │   ░░░   │   ░░░   │  ░░░  │
│    Other Iatrogenic │  48.2%  │  18.4%  │  22.1%  │  11.3%  │   87  │
│                                                                      │
│  ░░░ = suppressed (fewer than 10 members in this group)             │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Statistical Test                                                    │
│                                                                      │
│  Chi-square test of independence (cause group × leak type)          │
│                                                                      │
│  χ² = 47.3   df = 12   p < 0.001                                    │
│                                                                      │
│  There is a statistically significant association between cause      │
│  group and leak type (p < 0.001). This means the distribution of    │
│  spinal vs cranial leaks differs meaningfully across cause groups.  │
│                                                                      │
│  Note: 3 cells had expected counts < 5 and were excluded from the   │
│  test. Unknown leak type excluded from test denominator.            │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  [ Export report as PDF ]  [ Export data as CSV ]                   │
└──────────────────────────────────────────────────────────────────────┘
```

**Notes:**
- ▶/▼ toggle expands/collapses cause group rows. Default: all collapsed (groups only).
- Heatmap view replaces % text with colour intensity. Uses single-hue sequential scale (not red/green).
- Statistical test section always visible, even when heatmap view is active.
- Plain-language interpretation of the p-value is generated by the app (not AI) — a simple template based on the result.
- Suppressed cells show `░░░` in both Matrix and Heatmap views. In Heatmap, suppressed cells show a hatched pattern rather than a colour.

---

## Screen 7 — AI Analysis

```
┌─────────────────────────────────────────────────────────────────────┐
│ AI Analysis                                                          │
├───────────────────────────────────┬─────────────────────────────────┤
│                                   │ Data context                    │
│  ┌─────────────────────────────┐  │                                 │
│  │ Previous analyses     [New] │  │ The AI can see:                 │
│  ├─────────────────────────────┤  │                                 │
│  │ Cause distribution    ···   │  │ ✓ Cohort summary                │
│  │ 08 Apr 2026                 │  │   (2,847 members, status        │
│  │                             │  │    breakdown, country count)    │
│  │ EDS patterns          ···   │  │                                 │
│  │ 21 Mar 2026                 │  │ ✓ Active report output          │
│  │                             │  │   (Report 4 — Cause of Leak,    │
│  │ Iatrogenic trends     ···   │  │    current filters applied)     │
│  │ 14 Feb 2026                 │  │                                 │
│  │                             │  │ ✗ Individual records            │
│  └─────────────────────────────┘  │ ✗ Pseudo IDs                   │
│                                   │ ✗ Groups < 10 members           │
│                                   │                                 │
│                                   │ [Change active report ▾]        │
├───────────────────────────────────┴─────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Nova · 08 Apr 2026                                          │    │
│  │                                                             │    │
│  │ The iatrogenic cause group accounts for 33.4% of the        │    │
│  │ sufferer cohort. How does this compare to published          │    │
│  │ literature on CSF leak prevalence by cause?                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ AI · 08 Apr 2026                                            │    │
│  │                                                             │    │
│  │ Based on the report data provided: iatrogenic causes         │    │
│  │ represent 33.4% of your 2,535-member sufferer cohort.       │    │
│  │                                                             │    │
│  │ Published literature suggests iatrogenic causes, primarily  │    │
│  │ post-dural puncture headache following lumbar puncture, are │    │
│  │ among the most commonly documented CSF leak presentations   │    │
│  │ in clinical settings...                                     │    │
│  │                                 [Read more ▼]               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Ask a question about the data...                              │ │
│  │                                                     [Send →]  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ⓘ Only aggregate statistics are sent to the AI. No individual      │
│    member data is transmitted. Groups < 10 are excluded.            │
└──────────────────────────────────────────────────────────────────────┘
```

**Notes:**
- Data context panel is always visible and always accurate — it shows exactly what has been sent to the AI for this session. No surprises.
- The "✗" items are not just informational — they are enforced. The panel builds trust by being explicit.
- Privacy notice below the input is persistent, not dismissible.
- AI responses are not streamed per token — displayed in full when complete. This prevents partial health-data interpretations appearing mid-render.
- Session history is stored locally (browser session only) — not persisted to the server. Starting a new analysis clears the context.

---

## Screen 8 — Admin: Import Detail

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← Import   Import Detail · 08 Apr 2026 · 14:32 UTC                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Summary                                                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Total in file:     3,163   │  Imported:       2,847         │   │
│  │  Geographic excl.:    312   │  New records:      146         │   │
│  │  Validation skip:       4   │  Updated records: 2,701        │   │
│  │  Errors:                0   │  Imported by:  S. Hamilton     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Geographic Exclusions (312)                                         │
│  Countries excluded (not UK/EEA):                                    │
│  United States: 187  ·  Canada: 43  ·  Australia: 38  ·             │
│  Other: 44                                                           │
│                                                                      │
│  Validation Skips (4)                                                │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ Record #  │ Reason                      │ Action           │     │
│  ├────────────────────────────────────────────────────────────┤     │
│  │ —         │ Missing member ID           │ Skipped          │     │
│  │ —         │ Missing member ID           │ Skipped          │     │
│  │ —         │ Date of birth unparseable   │ age_band = null  │     │
│  │ —         │ Unrecognised leak type val. │ csf_leak_type    │     │
│  │           │                             │ = null           │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
│  Note: Record numbers are not shown — these relate to raw member     │
│  data and must not appear in the research system.                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Screen 9 — Admin: Audit Log

```
┌─────────────────────────────────────────────────────────────────────┐
│ Audit Log                                      [↗ View in Azure →]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Filter: [All events ▾]  [All users ▾]  [Date range: Last 30 days ▾]│
│                                                                      │
│  ┌──────────────────┬───────────────┬────────────────────┬────────┐ │
│  │ Timestamp (UTC)  │ User          │ Action             │ Detail │ │
│  ├──────────────────┼───────────────┼────────────────────┼────────┤ │
│  │ 2026-04-08 14:35 │ S. Hamilton   │ Report run         │ R4     │ │
│  │ 2026-04-08 14:33 │ S. Hamilton   │ AI analysis        │ R4     │ │
│  │ 2026-04-08 14:32 │ S. Hamilton   │ Import complete    │ B-0041 │ │
│  │ 2026-04-08 14:18 │ S. Hamilton   │ Import started     │ B-0041 │ │
│  │ 2026-04-07 09:12 │ R. Burns      │ Report run         │ R7     │ │
│  │ 2026-04-07 09:08 │ R. Burns      │ Sign in            │ —      │ │
│  └──────────────────┴───────────────┴────────────────────┴────────┘ │
│                                                                      │
│  ⓘ Full audit log with Key Vault access events is available in       │
│    Azure Log Analytics. The link above opens it directly.            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Notes:**
- User names are shown in the admin audit log (admins reviewing access need to know who did what). Names come from Entra ID, not the research DB.
- "View in Azure" links directly to the Log Analytics workspace for the full technical log.
- No health data, pseudo_ids, or query contents are shown in the log — action type and scope only.

---

## Accessibility Checklist (for Bolt's implementation)

- [ ] All charts have a "View as table" toggle — accessible alternative to visual output
- [ ] Colour is never the sole means of conveying information (suppressed cells use pattern + label, not just grey)
- [ ] All interactive elements meet 44×44px minimum touch target
- [ ] Focus indicators visible on all interactive elements (outline: 2px solid #1B4F72)
- [ ] All form inputs have associated `<label>` elements
- [ ] All images and icons have `alt` text or `aria-label`
- [ ] Error messages are associated with their inputs via `aria-describedby`
- [ ] Page title updates on navigation (SPA route changes)
- [ ] Suppression notices use `role="alert"` so screen readers announce them
- [ ] Minimum contrast ratio 4.5:1 for all body text, 3:1 for large text (WCAG AA)

---

## Responsive Breakpoints

| Breakpoint | Layout |
|---|---|
| ≥ 1280px | Full sidebar + two-column report cards |
| 1024–1279px | Full sidebar + single-column report cards |
| 768–1023px | Icon-only sidebar (tooltips on hover) |
| < 768px | Bottom tab bar (Dashboard, Reports, AI, Admin) |

---

## Open Items for Review

| # | Item | Status |
|---|---|---|
| W-01 | Confirm exact brand colours from csfleak.uk | **RESOLVED** — extracted from Quisk Style Guide (Sept 2021). See palette section above. |
| W-02 | Geographic maps | **RESOLVED** — SVG maps for v1. Interactive Leaflet.js tracked as FE-01 in `Future Enhancements.md`. |
| W-03 | AI session history | **RESOLVED** — browser session only. No server persistence. |
| W-04 | PDF export | **RESOLVED** — browser print dialog (`window.print()` with print stylesheet). Simplest to implement, no server dependency. |
