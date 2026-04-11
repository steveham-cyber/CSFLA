# Future Enhancements

Tracked items that are out of scope for the initial build but agreed to revisit.  
Add to this list as new ideas arise. Review at each project milestone.

---

## UX / Frontend

| # | Enhancement | Raised by | Rationale |
|---|---|---|---|
| FE-01 | Interactive maps (Leaflet.js) for geographic reports | Sketch / Owner | Richer geographic exploration — zoom, hover tooltips, region drill-down. Deferred in favour of simpler SVG maps for v1. |

---

## Data & Research

| # | Enhancement | Raised by | Rationale |
|---|---|---|---|
| DR-01 | Year of symptom onset field in membership form | Nova | Enables time-to-diagnosis calculation — high research value. Requires membership form update. |
| DR-02 | Year of diagnosis field in membership form | Nova | Direct measurement of diagnostic delay. Requires membership form update. |
| DR-03 | Treatment types received field | Nova | Enables treatment pattern analysis — second generation of reports. |
| DR-04 | Current symptom status field | Nova | Enables outcome and recovery analysis. |
| DR-05 | Diagnostic pathway field | Nova | Maps healthcare journey (GP → specialist → diagnosis). |
| DR-06 | Scheduled automated export from membership system | Atlas | Replace manual CSV upload with automated pipeline once manual flow is stable. |

---

## Infrastructure & Security

| # | Enhancement | Raised by | Rationale |
|---|---|---|---|
| IS-01 | Customer-managed key (CMK) for PostgreSQL encryption at rest | Cipher | Additional control over encryption. Deferred pending assessment of operational overhead vs benefit. |
| IS-02 | Azure Defender for Cloud — full enablement | Cipher | Continuous posture assessment. Deferred until subscription tier confirmed. |

---

## AI Analysis

| # | Enhancement | Raised by | Rationale |
|---|---|---|---|
| AI-01 | Persist AI analysis session history across logins | Sketch / Owner | Currently browser-session only. Persistent history would allow researchers to revisit previous analyses. Requires Lex review of data retention implications before implementing. |
