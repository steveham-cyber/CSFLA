# Security Threat Model & Requirements v0.1
## CSF Leak Association — Research Data Application

**Document status:** Draft v0.1 — for Lex review and owner approval  
**Prepared by:** Cipher (Security Specialist)  
**Date drafted:** 2026-04-11  
**Stack:** Azure (App Service / Container Apps, PostgreSQL Flexible Server, Key Vault Premium, Entra ID, Blob Storage, Log Analytics)  

---

## 1. Assets

These are what we are protecting, in priority order:

| Asset | Description | Impact if compromised |
|---|---|---|
| **Pseudonymisation key** | HMAC-SHA256 key in Azure Key Vault | Critical — all research records become re-identifiable |
| **Research database** | Azure PostgreSQL — pseudonymised health data | High — health data of all members exposed |
| **Staged CSV uploads** | Temporary Blob Storage — raw membership export including PII | Critical — full PII and health data exposed |
| **Audit logs** | Log Analytics — record of all data access | High — tampered logs mask breaches and access |
| **Application** | Azure App Service — the running system | Medium — service disruption or pivot to other assets |
| **User sessions** | Entra ID tokens — authenticated researcher sessions | Medium — unauthorised data access |

---

## 2. Threat Actors

| Actor | Motivation | Capability |
|---|---|---|
| External attacker | Data theft, ransomware, reputational damage | Low–medium. Opportunistic scanning, credential stuffing. |
| Compromised user account | Depends on attacker behind it | Medium. Has valid session, bypasses perimeter controls. |
| Malicious insider | Data exfiltration, sabotage | High. Legitimate access, knows the system. |
| Supply chain | Malicious dependency, compromised build | Medium. Hard to detect, wide blast radius. |

---

## 3. Threat Model (STRIDE)

### 3.1 Spoofing

| Threat | Target | Mitigation |
|---|---|---|
| Account takeover via credential stuffing | Researcher/admin accounts | Entra ID handles auth — no passwords in the app. Entra ID MFA enforced via Conditional Access policy. |
| Session token theft | Active researcher session | Short-lived tokens (1 hour max). HTTPS only. `HttpOnly`, `Secure`, `SameSite=Strict` on session cookies. |
| Forged import file | Pipeline — pretend to be a valid membership export | File upload validates schema strictly. Pipeline halts on unexpected schema. Source access controlled to admin role only. |

### 3.2 Tampering

| Threat | Target | Mitigation |
|---|---|---|
| Direct database modification | Research DB records | No public endpoint on PostgreSQL. Private endpoint only. No direct SQL access for any user role in production — all access via application layer. |
| Pipeline manipulation | Import pipeline — inject PII or modify transformation logic | PII check runs on every transformed record before DB write. Pipeline halts hard on failure. |
| Key Vault key modification | Pseudonymisation key | Azure RBAC: pipeline Managed Identity has `Key/Sign` only. No `Key/Update` or `Key/Delete`. Purge protection enabled. |
| Dependency tampering | Application code | Dependency pinning (locked requirements). Dependabot or equivalent for vulnerability alerts. |

### 3.3 Repudiation

| Threat | Target | Mitigation |
|---|---|---|
| Denial of data access | User claims they didn't run a report or trigger an import | All data access events logged to Log Analytics with user ID, timestamp, action, data scope. Logs are append-only — no application write access to modify them. |
| Denial of import | Admin claims an import didn't happen | Import batch records written to DB on completion. Log Analytics diagnostic logs provide independent record. |

### 3.4 Information Disclosure

| Threat | Target | Mitigation |
|---|---|---|
| Key Vault key extraction | Pseudonymisation key | HSM-backed key (Premium tier). `Sign` operation only — raw key never leaves vault. Private endpoint — not accessible from internet. |
| Database exfiltration | Research DB | Private endpoint. TLS enforced. Managed Identity auth — no connection string with password. Defender for PostgreSQL enabled. |
| PII in staged CSV exposed | Blob Storage staging area | Blob container private (no public access). Staging files deleted immediately after pipeline completes. Access via Managed Identity only. No SAS tokens. |
| PII in logs | Log Analytics | Audit logging captures user IDs and actions only — no health data, no pseudo_ids, no field values written to logs. |
| Small-cohort re-identification | Report outputs | k≥10 minimum cohort enforced at query layer. Reports suppressed, not just hidden in UI, when threshold not met. |
| PII in API responses | Application API | API returns aggregate/pseudonymised data only. No endpoint returns individual records. Enforced at service layer, not just UI. |
| Secrets in code/config | GitHub repository | Managed Identity used throughout — no secrets in config files. `.gitignore` covers all credential file patterns. GitHub secret scanning enabled. |
| PII transmitted to Claude API | AI analysis feature | Only aggregate statistics and summary outputs sent to Claude API. No individual records, no pseudo_ids. Minimum cohort check runs before any AI query. |

### 3.5 Denial of Service

| Threat | Target | Mitigation |
|---|---|---|
| Large malicious file upload | Pipeline — exhaust memory/compute | File size limit enforced at upload endpoint (recommend 50MB max — adjust based on expected export size). File type validation before processing begins. |
| Query bombing | Report engine — expensive queries | Role-based rate limiting on report endpoints. Query timeout enforced at DB level. |
| Key Vault throttling | Pipeline — too many HMAC requests | Single Key Vault call per import batch at pipeline start (key fetched once, used in memory, cleared on completion) — not per-record. |

### 3.6 Elevation of Privilege

| Threat | Target | Mitigation |
|---|---|---|
| Researcher escalates to admin | User role escalation | Role assignments managed in Entra ID, not in the application database. Roles cannot be self-assigned. Admin role changes require a second admin to approve (enforce in Entra ID). |
| Viewer accesses raw report data | Accessing endpoints above their role | All API endpoints enforce role check via dependency injection — not optional middleware. Viewer role gets read-only access to published reports only. |
| Pipeline service account misuse | Managed Identity used beyond its scope | Pipeline Managed Identity scoped to: Key Vault `Sign` only, Blob Storage `read/delete` on staging container only, PostgreSQL write on research DB only. Principle of least privilege — no subscription-level permissions. |

---

## 4. Azure-Specific Security Requirements

These are requirements for Bolt to implement and for the infrastructure configuration. Each must be in place before go-live.

### 4.1 Network

| Requirement | Implementation |
|---|---|
| No public internet access to PostgreSQL | Private endpoint on Azure PostgreSQL. Public network access: disabled. |
| No public internet access to Key Vault | Private endpoint on Azure Key Vault. Public network access: disabled. |
| Application accessible internally only | Azure App Service on VNet integration or Container Apps with internal ingress. If external access is needed, restrict via Entra ID App Proxy or private DNS. |
| All inter-service traffic over VNet | VNet integration for App Service. All outbound connections to PostgreSQL, Key Vault, Blob Storage use private endpoints. |

### 4.2 Identity and Access

| Requirement | Implementation |
|---|---|
| MFA enforced for all users | Entra ID Conditional Access policy — require MFA for all sign-ins to this application. No exceptions. |
| Compliant device recommended | Conditional Access — require compliant or Entra ID joined device where feasible. |
| Sign-in risk policy | Entra ID Identity Protection — block high-risk sign-ins automatically. |
| Managed Identity for all service-to-service auth | App Service system-assigned Managed Identity. No client secrets, no certificates, no passwords in config. |
| Least privilege RBAC | Key Vault: `Key Vault Crypto User` (Sign only) for pipeline MI. PostgreSQL: application DB user with SELECT/INSERT/UPDATE on research tables only — no DDL, no superuser. Blob: `Storage Blob Data Contributor` on staging container only. |
| Admin role change approval | Require second admin approval for role assignment changes. Document in runbook. |

### 4.3 Data Protection

| Requirement | Implementation |
|---|---|
| Encryption at rest — database | Azure PostgreSQL: encryption at rest enabled by default (AES-256). Consider customer-managed key (CMK) for additional control — assess operational overhead. |
| Encryption at rest — Key Vault | HSM-backed keys (Premium tier). Keys never exported. |
| Encryption at rest — Blob Storage | Azure Storage: encryption at rest enabled by default. |
| Encryption in transit | TLS 1.2 minimum enforced across all services. Disable TLS 1.0 and 1.1. PostgreSQL: `ssl=require` in connection parameters. |
| Staging file deletion | Pipeline deletes staging blob immediately on completion (success or failure). Blob soft-delete disabled on staging container (so deletions are immediate and permanent). |
| Database backup | Azure PostgreSQL automated backups enabled. Geo-redundant backup recommended. Restore tested before go-live. |

### 4.4 Monitoring and Alerting

| Requirement | Implementation |
|---|---|
| Centralised logging | All services send diagnostic logs to Log Analytics Workspace. |
| Key Vault access logging | Key Vault audit logs → Log Analytics. Alert on: any access by unexpected principal, any failed access, any key management operation. |
| PostgreSQL audit logging | `pgaudit` extension enabled. Log all DML on health data tables. Logs → Log Analytics. |
| Application access logging | All import, query, report, and AI analysis events logged with user ID and timestamp. No PII in logs. |
| Failed login alerting | Entra ID sign-in logs → alert on unusual sign-in patterns, multiple failures, impossible travel. |
| Defender for Cloud | Enable Defender for Databases (PostgreSQL) and Defender for Key Vault on the subscription. |
| Security alert notifications | Alerts route to a monitored email address (not a single person — use a shared mailbox or distribution list). |

### 4.5 Application Security

| Requirement | Implementation |
|---|---|
| Dependency vulnerability scanning | GitHub Dependabot alerts enabled. No deployment with known high/critical CVEs in dependencies. |
| Secret scanning | GitHub secret scanning enabled. Pre-commit hook to catch accidental credential commits. |
| Security headers | Application returns: `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`. |
| Input validation | All API inputs validated via Pydantic models. File upload: type, size, and encoding validated before pipeline starts. |
| Error handling | Application never returns stack traces or internal error details to the client. Log internally, return generic error to user. |
| k≥10 enforcement | Minimum cohort check enforced at the database query layer (SQL-level), not only in application logic or UI. |

---

## 5. Pre-Go-Live Security Checklist

These must all be confirmed complete before the system processes real member data:

- [ ] All private endpoints configured — PostgreSQL and Key Vault not publicly accessible
- [ ] Managed Identity auth in use — no passwords or secrets in application config
- [ ] MFA Conditional Access policy active and tested
- [ ] Key Vault purge protection and soft-delete enabled
- [ ] HSM-backed key in use (Premium Key Vault tier)
- [ ] Staging blob deletion confirmed working (test with a file)
- [ ] Audit logging flowing to Log Analytics and verified
- [ ] Defender for Cloud enabled and showing no critical findings
- [ ] Dependency scan clean — no high/critical CVEs
- [ ] Secret scanning enabled on GitHub repo
- [ ] PII check in pipeline tested — confirm it halts correctly on failure
- [ ] k≥10 enforcement tested at query layer
- [ ] Security headers present on all API responses
- [ ] Backup and restore tested
- [ ] Lex sign-off on data architecture spec
- [ ] DPIA approved

---

## 6. Items for Review

| # | Item | For |
|---|---|---|
| S-01 | Confirm whether external access is needed (internet-facing) or internal VNet only. Determines App Service ingress configuration. | Owner |
| S-02 | Confirm Azure subscription tier — determines Key Vault Premium (HSM) availability and Defender for Cloud options. | Owner / IT |
| S-03 | Confirm whether customer-managed key (CMK) for PostgreSQL encryption at rest is required, or Azure-managed key is acceptable. | Owner / Lex |
| S-04 | Confirm shared security alert mailbox or distribution list for monitoring alerts. | Owner |
