# Azure Test Environment — Design Spec

**Date:** 22 April 2026
**Status:** Implemented
**Author:** Goose / Bolt (CSFLA AI Team)

---

## Goal

Provision a persistent test environment in Azure that:
- Runs the full CSFLA Research Application stack
- Uses real pseudonymised member data
- Is accessible to a small named group (admins, researchers, viewers)
- Serves as a staging environment for all future releases before production

---

## Architecture

```
Browser (HTTPS)
    │
    ▼
Azure App Service (csfla-test-app)
│   FastAPI / Python 3.12 / uvicorn
│   Deployed via GitHub Actions on push to main
│
├── Azure Database for PostgreSQL Flexible Server (csfla-test-db)
│       Database: csfla_research
│       Auth: PostgreSQL user (csfla_app) with password
│       SSL: required
│
├── Azure Key Vault (csfla-test-kv)
│       Key: pseudonymisation-key (RSA 2048)
│       Access: App Service Managed Identity (Key Vault Crypto User + Secrets User)
│
├── Azure Storage Account (csflateststorage)
│       Container: imports (private)
│       Access: App Service Managed Identity (Storage Blob Data Contributor)
│
└── Microsoft Entra ID (existing tenant)
        App Registration: CSFLA Research App (Test)
        Auth flow: OIDC / MSAL authorisation code
        Roles: admin | researcher | viewer
```

---

## Azure Resources

| Resource | Name | Tier | Est. monthly cost |
|---|---|---|---|
| Resource Group | `csfla-test` | — | — |
| App Service Plan | (within csfla-test-app) | B1 | ~£12 |
| App Service | `csfla-test-app` | B1 Linux | included |
| PostgreSQL Flexible Server | `csfla-test-db` | Development (Burstable) | ~£12 |
| Key Vault | `csfla-test-kv` | Standard | ~£1 |
| Storage Account | `csflateststorage` | Standard LRS | ~£1 |
| **Total** | | | **~£26/month** |

All resources are in region **UK South** to keep data within the UK.

---

## Application Configuration

The app runs with `APP_ENV=development` in this test environment. This was chosen to avoid the complexity of Managed Identity token auth for PostgreSQL during initial setup. It has the following implications:

| Setting | Test behaviour | Production behaviour |
|---|---|---|
| Database auth | Password (`csfla_app` user) | Managed Identity token |
| Pseudonymisation key source | `TEST_PSEUDONYMISATION_KEY` env var | Azure Key Vault |
| HTTPS redirect enforcement | Off (App Service enforces HTTPS natively) | On (FastAPI middleware) |
| Swagger `/docs` endpoint | **Enabled** — restrict access or disable when not needed | Disabled |
| Session cookie `Secure` flag | Off | On |

### Environment variables (App Service Application Settings)

| Variable | Notes |
|---|---|
| `APP_ENV` | `development` |
| `AZURE_TENANT_ID` | Entra ID tenant |
| `AZURE_CLIENT_ID` | App Registration client ID |
| `AZURE_CLIENT_SECRET` | App Registration client secret (expires 12 months from setup) |
| `AZURE_KEY_VAULT_URL` | `https://csfla-test-kv.vault.azure.net/` |
| `AZURE_KEY_VAULT_KEY_NAME` | `pseudonymisation-key` |
| `DB_HOST` | `csfla-test-db.postgres.database.azure.com` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `csfla_research` |
| `DB_USER` | `csfla_app` |
| `DB_PASSWORD` | PostgreSQL password (stored in App Service settings) |
| `SECRET_KEY` | Session signing key (64-char hex) |
| `ALLOWED_ORIGINS` | `https://csfla-test-app.azurewebsites.net` |
| `TEST_PSEUDONYMISATION_KEY` | 64-char hex HMAC key — **store in password manager** |

---

## Deployment Pipeline

GitHub Actions workflow: `.github/workflows/main_csfla-test-app.yml`

**Trigger:** Push to `main` branch (or manual dispatch)

**Steps:**
1. Check out repository
2. Set up Python 3.12
3. Install dependencies from `app/requirements.txt`
4. Upload `app/` directory as deployment artifact (only the app subdirectory — not the repo root)
5. Deploy to App Service using publish profile secret

**Startup command:** `uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*`

**Database initialisation:** On first boot, `main.py`'s lifespan event calls `Base.metadata.create_all()` — tables are created automatically if they don't exist. This is idempotent and safe on every restart.

---

## Access Control

### Who can log in

Access is controlled via Entra ID App Role assignments on the `CSFLA Research App (Test)` enterprise application. Users must be explicitly assigned a role — no role = no access.

| Role | Permissions |
|---|---|
| `admin` | Full access including data imports and export |
| `researcher` | All reports, custom report builder, data export |
| `viewer` | Standard reports only (read-only) |

To add a user: Entra ID → Enterprise applications → `CSFLA Research App (Test)` → Users and groups → Add user/group.

### Network access

- **App Service:** Public HTTPS (`https://csfla-test-app.azurewebsites.net`)
- **PostgreSQL:** Public access with Azure services firewall rule (required for initial setup and Cloud Shell admin access)
- **Key Vault:** Public endpoint, access restricted by RBAC (Managed Identity only + Key Vault Administrator for the setup account)
- **Storage:** Public endpoint, access restricted by RBAC (Managed Identity only)

---

## Known Differences from Production

These items must be addressed before a production deployment:

1. **Database auth:** Switch from password to Managed Identity token auth. Requires:
   - Setting `APP_ENV=production`
   - Enabling the `pgaadauth` extension on PostgreSQL
   - Creating an Entra ID user for the App Service Managed Identity via `pgaadauth_create_principal_with_oid()`
   - Removing `DB_PASSWORD` and `TEST_PSEUDONYMISATION_KEY` from App Settings

2. **PostgreSQL network:** Lock down to Private access (VNet integration) rather than public access with firewall rules. Requires a VNet and private DNS zone.

3. **Client secret rotation:** The Entra ID client secret expires in 12 months. Set a calendar reminder to rotate it. Long-term: replace with a certificate or Managed Identity for MSAL.

4. **Swagger docs:** `/docs` is enabled because `APP_ENV=development`. Either disable access to that path or switch to `APP_ENV=production` once database auth is resolved.

5. **DPIA:** This environment processes real member data. A DPIA update is required before production deployment (deferred — agreed with Steve Hamilton, 22 April 2026).

---

## Runbook: Common Admin Tasks

**Add a new user:**
Entra ID → Enterprise applications → `CSFLA Research App (Test)` → Users and groups → Add

**Rotate the client secret:**
Entra ID → App registrations → `CSFLA Research App (Test)` → Certificates & secrets → delete old → create new → update `AZURE_CLIENT_SECRET` in App Service env vars

**Connect to the database (Cloud Shell):**
```bash
psql "host=csfla-test-db.postgres.database.azure.com port=5432 dbname=csfla_research user=SteveHamilton sslmode=require"
```

**Check application logs:**
App Service → Log stream

**Force a redeploy:**
GitHub → Actions → latest workflow → Re-run all jobs

**Estimated monthly cost:** ~£26. Budget alert configured at £50/month.
