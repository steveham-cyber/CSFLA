# Standard Report Specifications v0.1
## CSF Leak Association — Research Data Application

**Document status:** v0.1 — for Goose, Sketch, and Bolt review  
**Prepared by:** Nova (Medical Researcher)  
**Date:** 2026-04-11  
**Data source:** Pseudonymised research database (see Data Architecture Spec v0.2)

---

## Data Scope Note

The membership data available for analysis contains:
- **Diagnostic status** — diagnosed, suspected, former, family/friend, medical professional
- **CSF leak type** — spinal, cranial, spinal and cranial, unknown
- **Cause of leak** — 16 structured categories (iatrogenic, connective tissue, spontaneous, traumatic, unknown)
- **Demographics** — age band, gender, country, region, outward code
- **Membership tenure** — year joined

This is membership self-report data, not clinical records. It does not contain treatment histories, symptom severity scores, or outcome measures. Reports are specified to reflect what the data can reliably support. Future data collection improvements are noted where relevant.

**Minimum cohort:** All reports suppress results for any group with fewer than 10 members. Bolt must enforce this at the query layer.

---

## Report 1 — Cohort Overview

**Purpose:** A summary snapshot of the full research cohort. The starting point for any research engagement — establishes the size, composition, and nature of the population.

**Clinical value:** Contextualises all other analyses. Informs grant applications, publications, and NHS partnership work by characterising who uses the charity's services.

### Metrics

| Metric | Calculation | Display |
|---|---|---|
| Total cohort size | COUNT(pseudo_id) | Single number |
| Active / former split | COUNT by member_status IN (diagnosed, suspected) vs formerCsfLeakSufferer | Number + % |
| Sufferers vs supporters | COUNT sufferer statuses vs familyFriendOfSufferer + medicalProfessional | Number + % |
| Confirmed diagnosed | COUNT where status = csfLeakSuffererDiagnosed | Number + % of sufferers |
| Suspected (undiagnosed) | COUNT where status = csfLeakSuffererSuspected | Number + % of sufferers |
| Geographic spread | COUNT by country | Table |
| Data completeness | % of records with non-null values for key fields (leak_type, cause_of_leak, age_band, gender) | % per field |

### Filters available
None — this is always a whole-cohort report. Segmented views are in Report 2.

### Output format
Summary card metrics at the top, then a breakdown table and a single choropleth map of geographic distribution.

### Limitations
Member status is self-reported at sign-up and may not be updated when diagnosis status changes. Former members still appear in the cohort — the `formerCsfLeakSufferer` status is relevant here.

---

## Report 2 — Diagnostic Status Profile

**Purpose:** Detailed breakdown of the cohort by diagnostic status, segmented across demographic variables.

**Clinical value:** Understanding what proportion of the community is confirmed-diagnosed vs suspected informs the charity's advocacy work on diagnostic delays — a known issue in CSF leak care. Demographic patterns in diagnosis rates may reveal inequities.

### Primary breakdown

| Dimension | Values |
|---|---|
| Member status | csfLeakSuffererDiagnosed, csfLeakSuffererSuspected, formerCsfLeakSufferer |
| % diagnosed (of sufferers) | Diagnosed ÷ (Diagnosed + Suspected) × 100 |

### Cross-tabulations (each segmented by status)

| Segment | Field | Clinical rationale |
|---|---|---|
| Age band | age_band | Diagnostic rates may vary with age — younger patients may face longer diagnostic delays |
| Gender | gender | Known gender disparity in CSF leak diagnosis rates |
| Country | country | Healthcare system differences may affect diagnostic access |
| Region (UK) | region | Regional variation within the NHS |
| Membership year | member_since_year | Has the diagnosed/suspected ratio changed over time? Proxy for improving awareness |

### Filters available
Country, gender, age band, membership year range.

### Output format
Stacked bar charts for cross-tabulations. Table with absolute counts and percentages alongside each chart.

### Limitations
"Suspected" may include members awaiting investigation, members who have self-diagnosed, or members who never pursued formal diagnosis. These are not distinguishable from this data.

---

## Report 3 — CSF Leak Type Distribution

**Purpose:** Distribution of spinal, cranial, and combined leak types across the sufferer cohort.

**Clinical value:** Spinal and cranial leaks have different presentations, causes, and treatment pathways. Understanding the split in the charity's population informs which clinical areas to prioritise in research partnerships and advocacy.

### Scope
Sufferers only: exclude `familyFriendOfSufferer`, `medicalProfessional`. For `notRelevant` leak type — expected for non-sufferer members, exclude from this report.

### Primary breakdown

| Leak type | Count | % of sufferers with known type |
|---|---|---|
| Spinal | | |
| Cranial | | |
| Spinal and Cranial | | |
| Unknown | | |

**Unknown rate** is itself a meaningful metric — high unknown rates may indicate members are early in their diagnostic journey.

### Cross-tabulations

| Segment | Clinical rationale |
|---|---|
| Diagnostic status (diagnosed vs suspected) | Are suspected members more likely to have unknown type? |
| Age band | Age distribution differences between spinal and cranial presentations |
| Gender | Any gender pattern in leak type? |
| Country | Geographic variation |
| Membership year | Has the unknown rate reduced over time? (Proxy for improved diagnostics) |

### Filters available
Diagnostic status, country, gender, age band, membership year range.

### Output format
Donut chart for primary distribution. Bar charts for cross-tabulations.

### Limitations
Leak type is self-reported and may reflect patient understanding of their diagnosis rather than formal clinical classification.

---

## Report 4 — Cause of Leak Analysis

**Purpose:** Distribution of leak causes across the sufferer cohort, with category grouping for clinical interpretation.

**Clinical value:** This is the highest research value report. Understanding the relative prevalence of iatrogenic, connective tissue, spontaneous, and traumatic causes in the real-world patient population is directly relevant to NHS research and clinical guideline development. The charity's cohort may be large enough to provide meaningful population-level data on rare cause categories.

### Cause groupings

Raw causes from the data map to four clinically meaningful groups:

| Group | Causes included | Clinical meaning |
|---|---|---|
| **Iatrogenic** | spinalSurgery, cranialSurgery, lumbarPuncture, epiduralAnaesthesia, spinalAnaesthesia, otherIatrogenicCause | Caused by a medical procedure |
| **Connective Tissue Disorder** | ehlersDanlosSyndrome, marfanSyndrome, otherHeritableDisorderOfConnectiveTissue | Underlying heritable condition |
| **Spontaneous / Structural** | idiopathicIntracranialHypertension, boneSpur, cystTarlovPerineuralMeningeal | Spontaneous or structural cause |
| **Traumatic** | trauma | Physical trauma |
| **Unknown / Not disclosed** | unknown, preferNotToSay | Undetermined or not shared |

Both grouped and ungrouped (individual cause) views are required.

### Primary breakdown
Count and % for each cause group. Drill-down to individual causes within each group.

### Cross-tabulations

| Segment | Clinical rationale |
|---|---|
| Leak type (spinal / cranial / both) | Key research question: are certain causes more associated with spinal vs cranial leaks? |
| Diagnostic status | Are iatrogenic causes more commonly confirmed-diagnosed? (Clearer causation path) |
| Age band | Are connective tissue disorder causes more prevalent in younger members? |
| Gender | Known gender patterns in EDS and Marfan — does the data reflect this? |
| Country | Variation in iatrogenic rates may reflect procedural differences by healthcare system |
| Membership year | Is spontaneous/unknown cause decreasing as diagnosis improves? |

### Filters available
Cause group, individual cause, leak type, diagnostic status, country, gender, age band, membership year range.

### Output format
Grouped bar chart for cause group summary. Expandable table for individual causes. Cross-tabulation matrix as heatmap where cell values are percentages.

### Limitations
Members may have multiple causes (e.g. EDS + lumbar puncture). The data supports this (cause_of_leak is multi-value). Reports must handle multi-value correctly — a member with two causes appears in both, and denominators should be clearly documented. "Unknown" is a meaningful category, not missing data — it should not be excluded from the analysis.

---

## Report 5 — Geographic Distribution

**Purpose:** Distribution of the cohort across UK regions and European countries.

**Clinical value:** Geographic analysis supports the charity's understanding of where CSF leak patients are concentrated, potential regional variation in diagnostic rates or healthcare access, and the reach of the charity's support services. Also relevant for NHS Integrated Care Board-level advocacy.

### UK breakdown

| Level | Field used | View |
|---|---|---|
| Country | country (England / Scotland / Wales / Northern Ireland) | Map + table |
| Region | region | Table |
| Outward code density | outward_code | Density map (counts only — no rates without population denominator) |

### European breakdown
Country-level only. EEA member states with cohort size ≥ 10 shown individually; others grouped as "Other Europe".

### Cross-tabulations
Cause group by country (are iatrogenic rates different in different healthcare systems?). Diagnosed vs suspected rate by country.

### Filters available
Country group (UK / Europe), diagnostic status, leak type, cause group.

### Output format
Choropleth maps for UK and Europe. Ranked table alongside each map. Outward code view as dot density map — not choropleth (avoids misleading area-size effects).

### Limitations
Outward code data is available for UK members only. Population denominators are not available — absolute counts only, not rates per capita. Do not present outward code data as rates. Country-level European data may have small cohorts — k≥10 suppression will hide many individual countries.

---

## Report 6 — Membership Growth and Cohort Trends

**Purpose:** How the cohort has grown over time and whether its composition has changed.

**Clinical value:** Membership growth trends proxy for awareness of CSF leaks. Changes in the diagnosed/suspected ratio over time may indicate improving diagnostic pathways. Changes in cause distribution over time may reflect procedure-related incidents (e.g. a change in lumbar puncture technique guidelines).

### Metrics over time (x-axis = member_since_year)

| Metric | Chart type |
|---|---|
| New members per year | Bar chart |
| Cumulative cohort size | Line chart |
| Diagnosed % of new sufferers per year | Line chart |
| Cause group % of new sufferers per year | Stacked area chart |
| Leak type % of new sufferers per year | Stacked area chart |
| Geographic origin of new members per year | Stacked bar (UK vs Europe) |

### Filters available
Diagnostic status, country, leak type, cause group.

### Output format
All time series charts on a single scrollable report. Year range selector. Minimum year range of 3 years required before trend charts are shown (to prevent single-point misleading trends).

### Limitations
`member_since_year` reflects when someone joined the charity, not when they developed or were diagnosed with a CSF leak. Growth in membership reflects growing awareness of the charity as much as prevalence of the condition. This must be stated clearly on the report. Years with fewer than 10 new sufferer members are suppressed in cause/type breakdown charts.

---

## Report 7 — Cause × Type Cross-Analysis

**Purpose:** A dedicated research-focused report examining the relationship between cause of leak and leak type (spinal vs cranial).

**Clinical value:** This is the most clinically novel analysis the dataset supports. The relationship between cause and anatomical location of the leak is not well-documented in the literature at population scale. The charity's cohort may be one of the largest self-report datasets available for this question.

### Primary matrix

Rows: cause groups (and individual causes). Columns: leak types (spinal, cranial, spinalAndCranial, unknown). Cells: count and % of row total.

| | Spinal | Cranial | Spinal & Cranial | Unknown | Total |
|---|---|---|---|---|---|
| Iatrogenic | | | | | |
| — Lumbar puncture | | | | | |
| — Spinal surgery | | | | | |
| — Epidural | | | | | |
| — Spinal anaesthesia | | | | | |
| — Cranial surgery | | | | | |
| — Other iatrogenic | | | | | |
| Connective Tissue | | | | | |
| — EDS | | | | | |
| — Marfan | | | | | |
| — Other HDCT | | | | | |
| Spontaneous / Structural | | | | | |
| — IIH | | | | | |
| — Bone spur | | | | | |
| — Tarlov/cyst | | | | | |
| Traumatic | | | | | |
| Unknown / Not disclosed | | | | | |

### Statistical test
Chi-square test of independence: is there a statistically significant association between cause group and leak type? Report chi-square statistic, degrees of freedom, and p-value. Note: this requires cells ≥ 5 for validity — suppress or flag cells where expected count < 5.

### Filters available
Diagnostic status (diagnosed only vs all sufferers), gender, age band, country, membership year range.

### Output format
Interactive matrix table (expandable rows). Heatmap overlay option. Statistical test results shown below the table with plain-language interpretation.

### Limitations
Multi-value cause and type fields require careful handling — a member with both EDS and lumbar puncture appears in both cause rows. Denominators must be clearly documented. The chi-square test assumes independence between observations — this assumption holds for between-member analysis but should be noted. Members with `unknown` leak type are included in the table but excluded from the chi-square test denominator.

---

## Report 8 — Referral Source Analysis

**Purpose:** How members heard about the charity.

**Clinical value:** Lower research value than the clinical reports, but operationally important for the charity. Referral source patterns may also indicate where in the healthcare pathway patients are becoming aware of CSF leaks (e.g. high GP referral rates vs patient community discovery).

### Breakdown
Count and % by referral source category. Cross-tabulated with membership year (has referral source mix changed over time?).

### Structured referral source values
(from `referral_source` field — structured array, free text excluded)
Values to be confirmed from membership system — expected categories include search engine, social media, GP/doctor, friend/family, news/media, other charity, hospital.

### Filters available
Membership year range, country.

### Output format
Horizontal bar chart ranked by volume. Year trend line chart for top 5 sources.

### Limitations
Lower priority report — referral source data quality may be lower than health fields. Missing/null values should be reported separately and not collapsed into "unknown".

---

## Summary Table

| # | Report | Primary research value | Key fields |
|---|---|---|---|
| 1 | Cohort Overview | Population characterisation | All |
| 2 | Diagnostic Status Profile | Diagnostic equity and delay | member_status, age_band, gender, country |
| 3 | CSF Leak Type Distribution | Clinical profile of cohort | csf_leak_type, member_status |
| 4 | Cause of Leak Analysis | Prevalence of cause categories | cause_of_leak, csf_leak_type |
| 5 | Geographic Distribution | Healthcare access and reach | country, region, outward_code |
| 6 | Membership Growth & Trends | Awareness and diagnostic trends over time | member_since_year, all fields |
| 7 | Cause × Type Cross-Analysis | Novel clinical research — cause/location relationship | cause_of_leak × csf_leak_type |
| 8 | Referral Source Analysis | Operational insight | referral_source |

---

## Future Data Collection Recommendations

The following additions to the membership form would significantly expand research value. These are recommendations for the charity to consider for future data collection — they do not affect the current build.

| Field | Research value |
|---|---|
| Year of symptom onset | Enable time-to-diagnosis calculation |
| Year of diagnosis (if applicable) | Directly measure diagnostic delay |
| Treatment types received | Treatment pattern analysis |
| Current symptom status | Outcome and recovery analysis |
| Diagnostic pathway (GP → specialist → etc.) | Healthcare journey mapping |

---

## Notes for Bolt

- Reports 1–8 should all respect the `MIN_COHORT_SIZE = 10` constant already defined in `reports.py`
- Report 4 and Report 7 involve multi-value fields (cause_of_leak, csf_leak_type) — queries must JOIN to child tables, not aggregate arrays. Denominators must be member counts, not row counts.
- Report 7 chi-square test: use `scipy.stats.chi2_contingency`. Suppress cells with expected count < 5 and note in output.
- Report 6 year trends: enforce minimum 3-year window before displaying trend lines.
- All percentage calculations: document the denominator clearly in the report output (e.g. "% of sufferers with known leak type", not just "%").

## Notes for Sketch

- Report 7 (Cause × Type matrix) is the most complex UI element — the expandable row matrix needs careful design. Consider a progressive disclosure pattern: show cause groups collapsed by default, expand to individual causes.
- Report 4 heatmap: use a colour-blind-safe sequential palette (not red/green).
- All charts need accessible data table alternatives.
- Geographic maps: consider members in smaller countries — a choropleth where one member = 100% of a country is misleading. Apply k≥10 suppression visually (grey out suppressed countries/regions).
