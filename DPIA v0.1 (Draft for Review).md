# Data Protection Impact Assessment (DPIA)
## CSF Leak Association — Research Data Application

**Document status:** Draft v0.1 — for review and approval  
**Prepared by:** Lex (Compliance Specialist)  
**Date drafted:** 2026-04-11  
**Owner:** CSF Leak Association (Charity No. SC046319)  
**ICO Registration:** ZB804603  
**Applicable legislation:** UK GDPR, UK Data Protection Act 2018, EU GDPR (Regulation 2016/679)  

> **Note on dual compliance:** The CSF Leak Association is a UK data controller regulated by the ICO under UK GDPR. It also processes personal data of EU residents, meaning EU GDPR applies to that processing under Article 3(2). Both regimes are addressed throughout this document. They are substantially parallel; where material differences exist, both positions are stated.

---

## 1. Overview and Purpose of this DPIA

This DPIA covers the design, build, and operation of the **CSF Leak Association Research Data Application** — a new internal system that will:

- Ingest regular exports of membership data from the charity's membership platform
- Pseudonymise all personal and special category data at the point of import
- Store only the data of European (UK and EU) members in a research database
- Enable standard and custom medical statistical analysis reports
- Enable AI-assisted analysis of pseudonymised, aggregated data via the Claude API (Anthropic)

A DPIA is mandatory for this processing activity under UK GDPR Article 35 and EU GDPR Article 35, as it involves large-scale processing of special category health data.

This document must be completed, reviewed by the Data Protection Officer or equivalent, and approved by the Board (or delegated authority) **before any personal data is imported into the research system.**

---

## 2. Description of the Processing

### 2.1 Data Controller

**CSF Leak Association**  
Registered charity: SC046319 (Scotland)  
ICO registration: ZB804603  
Data protection contact: dataprotection@csfleak.uk

### 2.2 Data Subjects

Members of the CSF Leak Association who are resident in the United Kingdom or European Economic Area (EEA) and who have provided health information as part of their membership registration.

Members resident outside the UK and EEA are **excluded from this system entirely** at the point of import.

### 2.3 Categories of Personal Data Processed

**Special category data (Article 9 UK/EU GDPR — health data):**

| Data field | Description |
|---|---|
| CSF leak type | Spinal, cranial, spinal and cranial, or unknown |
| CSF leak cause | Trauma, unknown, or other categorised cause |
| Member status | Diagnosed, suspected, or other categorised status |

**Personal data retained in pseudonymised form:**

| Data field | Form retained |
|---|---|
| Member identity | Pseudonymous ID only (HMAC-derived — see Section 4) |
| Age | Age band only (e.g. 30–39). Full date of birth never stored. |
| Gender | As provided by member |
| Geographic location | Country + region + outward postcode only. Full address never stored. |
| Membership dates | Year only. Full timestamps never stored. |
| How member heard about the charity | Structured category only. Free text never stored. |
| Volunteer status | Yes/no flag |

### 2.4 Data Fields Excluded from the Research System

The following fields are present in the membership export but are **never imported** into the research system:

- Full name (first name, last name, all name variants)
- Email address and username
- Password (any form)
- Phone number
- Full postal address (street, town, full postcode)
- Full date of birth
- Admin URLs and internal system identifiers
- Authentication and security fields (verification codes, login IPs, lockout data)
- CMS system fields with no research value
- NHS research participation flag (relates to a separate programme)
- Gift Aid status
- Corporate/organisational fields
- Free-text fields (howDidYouHearAboutUsOther)

### 2.5 Purpose of Processing

The personal data is processed for the following purposes:

1. **Medical statistical research** — to generate insights into the prevalence, presentation, causes, and treatment of CSF leaks and associated conditions across the charity's membership cohort
2. **Longitudinal tracking** — to enable analysis of how the membership cohort changes over time across successive data imports
3. **AI-assisted research analysis** — to use the Claude API (Anthropic) to interpret statistical findings and assist with research queries, using aggregated or summary data only

### 2.6 Legal Basis for Processing

**For special category health data:**

| Regime | Legal basis |
|---|---|
| UK GDPR | Article 9(2)(j) — processing necessary for scientific research purposes, in accordance with Article 89(1), subject to appropriate safeguards. Supplemented by UK DPA 2018, Schedule 1, Part 2 (substantial public interest — research, statistics, and archiving). |
| EU GDPR | Article 9(2)(j) — processing necessary for scientific research purposes, subject to Article 89(1) safeguards and applicable Member State law. |

**For standard personal data:**

| Regime | Legal basis |
|---|---|
| UK GDPR | Article 6(1)(e) — processing necessary for a task carried out in the public interest, or Article 6(1)(f) — legitimate interests of the charity in conducting medical research for charitable purposes. |
| EU GDPR | Article 6(1)(e) or Article 6(1)(f) as above. |

**Data retention under the research exemption:**

The charity has received professional legal advice that pseudonymised data retained for research and statistical purposes may be retained indefinitely under the research exemption in UK GDPR Article 89 and UK DPA 2018 Section 26. This applies provided the data is genuinely pseudonymised and appropriate safeguards are maintained. This position is consistent with ICO guidance on research exemptions.

### 2.7 Data Recipients

| Recipient | Purpose | Basis |
|---|---|---|
| Charity staff with `researcher` or `admin` role | Running reports and analysis | Employment / role-based access control |
| Anthropic (Claude API) | AI-assisted analysis of aggregated/summary data only | Data Processing Agreement required. No individual records or pseudo_ids transmitted. |

No other third parties receive access to the research database or its contents.

### 2.8 International Transfers

**UK → EU/EEA:** The UK has an EU adequacy decision in place. Transfers of pseudonymised research data to EU-based staff or partners are permissible without additional safeguards.

**UK → USA (Anthropic/Claude API):** Anthropic is a US-based processor. Transfer is permissible under the UK Extension to the EU-US Data Privacy Framework or via ICO-approved International Data Transfer Agreements (IDTAs). A Data Processing Agreement must be in place with Anthropic before the Claude API integration is used in production. **Only aggregated or summary data is ever transmitted — no individual records, no pseudo_ids.**

---

## 3. Necessity and Proportionality

### 3.1 Is the processing necessary?

Yes. The charity's core mission is to improve understanding and treatment of CSF leaks. Its membership represents one of the largest cohorts of CSF leak patients in the UK and Europe. This data, properly pseudonymised and analysed, enables the charity to generate and publish meaningful medical research that would not otherwise be possible. The processing is directly necessary to fulfil this charitable purpose.

### 3.2 Is the processing proportionate?

Yes, subject to the safeguards described in this document. Key proportionality measures:

- **Data minimisation:** Only health-relevant fields are retained. The full membership record is not imported. Fields with no research value are discarded at the pipeline boundary.
- **Pseudonymisation:** All retained data is pseudonymised before storage. The pseudonymisation key is held separately from the research database.
- **Geographic scope:** Only UK and EEA member data is processed. Non-European records are excluded before any health data is read.
- **Purpose limitation:** The research database is used only for statistical analysis and research. It is not used for member communications, fundraising, or any other purpose.
- **Minimum cohort threshold:** No report or query may return results for a cohort of fewer than 10 members, preventing indirect re-identification through small group analysis.
- **Access controls:** Role-based access limits who can run queries and view data.

### 3.3 Could the purpose be achieved with less data or lower-risk processing?

The level of pseudonymisation proposed represents the minimum necessary for longitudinal research. Further anonymisation (e.g. removing stable pseudo_ids) would prevent tracking members across imports, limiting the research value to cross-sectional analysis only. The decision to retain pseudonymous (rather than fully anonymous) data is justified by the research purpose and is consistent with Article 89 safeguards.

---

## 4. Technical and Organisational Safeguards (Article 89)

These are the safeguards required under Article 89(1) UK/EU GDPR as conditions for processing health data for research purposes.

### 4.1 Pseudonymisation

The pseudonymisation algorithm uses HMAC-SHA256 with a secret key:

```
pseudo_id = HMAC-SHA256(secret_key, member_id)
```

Properties:
- **Stable:** The same member always receives the same pseudo_id across successive imports
- **Irreversible** without the secret key
- The secret key is stored in a dedicated key store, separate from the research database, with distinct access credentials

Re-identification from the research database alone is not possible without the key.

### 4.2 Data Separation

The research database contains no direct identifiers. The pseudonymisation key store contains no health data. These two systems are kept on separate credentials and, where technically feasible, separate hosts.

### 4.3 Authentication and Access Control

- OAuth 2.0 authentication via an approved identity provider (Microsoft Entra ID preferred). No passwords stored in the application.
- Role-based access: `admin`, `researcher`, `viewer`
- No role has direct SQL access to the production research database
- Multi-factor authentication enforced at the identity provider level

### 4.4 Encryption

- Data at rest: PostgreSQL with encrypted tablespace and/or column-level encryption for health fields
- Data in transit: TLS 1.2 minimum for all connections
- Full disk encryption on the hosting server

### 4.5 Audit Logging

All data access events (imports, queries, report generation, AI analysis requests) are logged with timestamp, user ID, action, and data scope. Logs are append-only and stored separately from application data. No personal data or pseudo_ids are written to logs.

### 4.6 Minimum Cohort Size

No report, query, or AI analysis request may return or expose data for a group of fewer than 10 members. This constraint is enforced at the application query layer, not only in the UI.

### 4.7 AI Analysis Constraints

The Claude API integration transmits only:
- Aggregated statistical summaries
- Report outputs and computed findings
- Researcher questions about patterns in the data

Individual records, pseudo_ids, and any data that could relate to a cohort smaller than 10 members are **never transmitted** to any external API.

### 4.8 Incident Response

The charity's existing data breach response procedures apply. Any breach involving the research database must be assessed for notification obligations to the ICO (within 72 hours if risk to individuals) and, for EU residents' data, to the relevant EU supervisory authority.

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Residual risk after mitigations |
|---|---|---|---|
| Re-identification of members via research database | Low | High | Low — pseudonymisation + data minimisation + k≥10 threshold |
| Compromise of pseudonymisation key | Low | Very high | Low — key held separately, restricted access, secrets management |
| Unauthorised access to research database | Low | High | Low — OAuth MFA, RBAC, no direct SQL access |
| PII leaking into research database via pipeline failure | Low | High | Low — field allowlist, automated PII detection tests, Probe sign-off |
| Non-European member data entering research database | Low | Medium | Low — EU/UK filter is first pipeline step, tested independently |
| Individual data exposed via small-cohort query | Low | Medium | Low — k≥10 enforced at query layer |
| Personal data transmitted to Claude API | Low | High | Low — aggregated data only, DPA with Anthropic in place |
| Data breach / ransomware on hosting server | Low | High | Medium — internal hosting; mitigated by encryption at rest, backups, incident response. Residual risk accepted. |

**Overall risk rating: LOW** — subject to all mitigations being implemented before go-live.

---

## 6. Consultation

### 6.1 Internal consultation

- [ ] Data Protection Officer (or equivalent responsible person) — review and approval required
- [ ] Board of Trustees — approval required before go-live
- [ ] IT/system administrator — review of hosting and infrastructure sections

### 6.2 ICO consultation

ICO prior consultation (Article 36 UK GDPR) is **not required** — the residual risk after mitigations is assessed as Low. This assessment should be reviewed if the scope of the system changes materially (e.g. linking to external datasets, adding new special category fields, sharing data with research partners).

### 6.3 EU supervisory authority

EU prior consultation is similarly **not required** on the same basis. If the system is extended to share EU residents' data with EU-based research partners, this assessment should be revisited.

---

## 7. Action Items Before Go-Live

| # | Action | Owner | Status |
|---|---|---|---|
| 1 | Complete and approve this DPIA | Data protection lead / Board | Open |
| 2 | Update Privacy Policy to v1.1 referencing this system | Lex | Pending DPIA approval |
| 3 | Obtain Data Processing Agreement with Anthropic (Claude API) | Data protection lead | Open |
| 4 | Confirm identity provider for OAuth (Entra ID / other) | IT lead | Open |
| 5 | Confirm internal hosting environment details for infrastructure security review | IT lead | Open |
| 6 | Confirm no EU representative obligation under EU GDPR Article 27 | Lex | Open — see note below |

> **Note on EU GDPR Article 27 (EU representative):** Article 27 requires non-EU controllers processing EU residents' data to appoint an EU representative, unless the processing is occasional or poses low risk to individuals. Given that this processing is systematic (regular imports) and involves special category data, the charity should take legal advice on whether an EU representative appointment is required. This is a relatively low administrative burden if needed.

---

## 8. Sign-Off

| Role | Name | Date | Signature |
|---|---|---|---|
| Data protection lead | | | |
| Board representative | | | |
| IT / infrastructure lead | | | |

---

*This DPIA should be reviewed annually and whenever there is a material change to the processing described — including changes to the data fields imported, new data recipients, changes to the hosting environment, or extension of the system's purpose.*
