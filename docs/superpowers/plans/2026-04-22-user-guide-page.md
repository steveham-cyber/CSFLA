# User Guide Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/help` user guide page accessible to all authenticated roles, with a sticky table of contents and seven sections covering navigation, reports, import, user management, and data privacy.

**Architecture:** Three small, focused changes — a new route in `ui.py`, a new `help.html` Jinja2 template with all static content, and a nav item added to `base.html`. No backend data required; no new dependencies.

**Tech Stack:** FastAPI, Jinja2, plain HTML/CSS matching existing app design tokens (`var(--space-*)`, `var(--color-*)`, `.card`, `.label-small`, `.data-table`).

---

## File Structure

| File | Change |
|---|---|
| `app/api/routes/ui.py` | Add `GET /help` route |
| `app/templates/base.html` | Add "Help" nav item before sign-out |
| `app/templates/help.html` | New file — full static guide content |
| `app/tests/test_api/test_auth.py` | Add tests: all roles access `/help`, anon redirects |

---

### Task 1: Route and tests

**Files:**
- Modify: `app/api/routes/ui.py`
- Modify: `app/tests/test_api/test_auth.py`

- [ ] **Step 1: Write the failing tests**

Add to `app/tests/test_api/test_auth.py`, inside the existing `TestViewerRole` class and a new `TestHelpPage` class:

```python
# Inside class TestViewerRole:
    async def test_viewer_can_access_help_page(self, viewer_client) -> None:
        response = await viewer_client.get("/help")
        assert response.status_code == 200

# New class after TestViewerRole:
class TestHelpPage:
    """Help page is accessible to all authenticated roles and blocks anon."""

    async def test_researcher_can_access_help_page(self, researcher_client) -> None:
        response = await researcher_client.get("/help")
        assert response.status_code == 200

    async def test_admin_can_access_help_page(self, admin_client) -> None:
        response = await admin_client.get("/help")
        assert response.status_code == 200

    async def test_anon_is_redirected_from_help_page(self, anon_client) -> None:
        response = await anon_client.get("/help")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/stevehamilton/Documents/Claude/CSFLA\ Data/app
pytest tests/test_api/test_auth.py::TestViewerRole::test_viewer_can_access_help_page tests/test_api/test_auth.py::TestHelpPage -v
```

Expected: FAIL — `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Add the `/help` route to `ui.py`**

Add this block to `app/api/routes/ui.py` immediately before the `GET /admin` route (keep admin last):

```python
@router.get("/help", response_class=HTMLResponse, include_in_schema=False)
async def help_page(request: Request):
    user = _require_ui_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("help.html", {
        "request": request,
        "user": user,
        "active_nav": "help",
        "page_title": "User Guide",
    })
```

- [ ] **Step 4: Create a minimal `help.html` to make tests pass**

Create `app/templates/help.html`:

```html
{% extends "base.html" %}

{% block title %}User Guide — CSFLA Research{% endblock %}

{% block content %}
<div style="padding: var(--space-6);">
  <h2>User Guide</h2>
  <p>Coming soon.</p>
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/stevehamilton/Documents/Claude/CSFLA\ Data/app
pytest tests/test_api/test_auth.py::TestViewerRole::test_viewer_can_access_help_page tests/test_api/test_auth.py::TestHelpPage -v
```

Expected: All 4 tests PASS

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
cd /Users/stevehamilton/Documents/Claude/CSFLA\ Data/app
pytest --tb=short -q
```

Expected: All tests pass, 0 failures

- [ ] **Step 7: Commit**

```bash
cd "/Users/stevehamilton/Documents/Claude/CSFLA Data"
git add app/api/routes/ui.py app/templates/help.html app/tests/test_api/test_auth.py
git commit -m "feat(help): add /help route accessible to all authenticated roles"
```

---

### Task 2: Add Help nav item to base.html

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: Add the Help nav item**

In `app/templates/base.html`, find the `<!-- Spacer -->` comment and the sign-out link block:

```html
      <!-- Spacer -->
      <div style="flex:1;" aria-hidden="true"></div>

      <!-- Sign out -->
      <a href="/auth/logout"
```

Replace with:

```html
      <!-- Spacer -->
      <div style="flex:1;" aria-hidden="true"></div>

      <!-- Help -->
      <a href="/help"
         class="nav-item {% if active_nav == 'help' %}active{% endif %}"
         aria-current="{% if active_nav == 'help' %}page{% endif %}">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1.5"/>
          <path d="M9 13v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          <path d="M9 10c0-1.5 2-2 2-3.5a2 2 0 10-4 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span>Help</span>
      </a>

      <!-- Sign out -->
      <a href="/auth/logout"
```

- [ ] **Step 2: Verify visually**

Start the dev server and check that the Help item appears in the nav for all roles:

```bash
cd "/Users/stevehamilton/Documents/Claude/CSFLA Data/app"
.venv/bin/uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/help` — confirm the nav item is visible and highlighted.

- [ ] **Step 3: Commit**

```bash
cd "/Users/stevehamilton/Documents/Claude/CSFLA Data"
git add app/templates/base.html
git commit -m "feat(help): add Help nav item to sidebar"
```

---

### Task 3: Full help.html content

**Files:**
- Modify: `app/templates/help.html`

This task replaces the stub `help.html` with the full guide content.

- [ ] **Step 1: Replace `app/templates/help.html` with the full content below**

```html
{% extends "base.html" %}

{% block title %}User Guide — CSFLA Research{% endblock %}

{% block content %}
<div style="padding: var(--space-6);">

  <div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom: var(--space-6);">
    <div>
      <h2 style="margin-bottom: var(--space-1);">User Guide</h2>
      <p style="color: var(--color-text-muted); font-size: var(--font-size-sm);">
        How to use the CSFLA Research Application.
      </p>
    </div>
  </div>

  <div style="display:grid; grid-template-columns: 220px 1fr; gap: var(--space-8); align-items:start;">

    <!-- Table of contents -->
    <nav aria-label="Guide sections" style="position:sticky; top: var(--space-6);">
      <div class="card" style="padding: var(--space-4);">
        <div class="label-small" style="margin-bottom: var(--space-3);">Contents</div>
        <ol style="list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap: var(--space-2);">
          <li><a href="#getting-started" class="toc-link">1. Getting started</a></li>
          <li><a href="#dashboard" class="toc-link">2. The dashboard</a></li>
          <li><a href="#standard-reports" class="toc-link">3. Standard reports</a></li>
          <li><a href="#custom-reports" class="toc-link">4. Custom report builder</a></li>
          <li><a href="#importing-data" class="toc-link">5. Importing data</a></li>
          <li><a href="#managing-users" class="toc-link">6. Managing users</a></li>
          <li><a href="#data-privacy" class="toc-link">7. Data privacy</a></li>
        </ol>
      </div>
    </nav>

    <!-- Main content -->
    <div>

      <!-- 1. Getting started -->
      <section id="getting-started" style="margin-bottom: var(--space-8);">
        <h3 style="margin-bottom: var(--space-4);">1. Getting started</h3>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Logging in</h4>
          <p style="margin-bottom: var(--space-3);">Go to the application URL and click <strong>Sign in</strong>. You will be redirected to Microsoft's sign-in page. Use your Microsoft account — the same account used for your charity email or Microsoft 365.</p>
          <p style="margin-bottom: var(--space-3);">If you see an error saying you are not authorised, your account has not been assigned a role yet. Contact your system administrator to be added.</p>
          <p>To sign out, click <strong>Sign out</strong> at the bottom of the left navigation sidebar.</p>
        </div>
        <div class="card">
          <h4 style="margin-bottom: var(--space-3);">Navigation</h4>
          <p style="margin-bottom: var(--space-3);">The left sidebar contains all navigation links. What you see depends on your role:</p>
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr><th>Item</th><th>Description</th><th>Who can see it</th></tr>
              </thead>
              <tbody>
                <tr><td>Dashboard</td><td>Summary metrics and charts for the whole cohort</td><td>All roles</td></tr>
                <tr><td>Reports</td><td>Seven standard research reports</td><td>All roles</td></tr>
                <tr><td>Custom Reports</td><td>Build and run your own queries</td><td>Researcher, Admin</td></tr>
                <tr><td>AI Analysis</td><td>AI-assisted data analysis (coming soon)</td><td>All roles</td></tr>
                <tr><td>Import</td><td>Upload new membership data exports</td><td>Admin only</td></tr>
                <tr><td>Admin</td><td>Audit logs, export, and system settings</td><td>Admin only</td></tr>
                <tr><td>Help</td><td>This guide</td><td>All roles</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- 2. Dashboard -->
      <section id="dashboard" style="margin-bottom: var(--space-8);">
        <h3 style="margin-bottom: var(--space-4);">2. The dashboard</h3>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Metric cards</h4>
          <div class="table-scroll">
            <table class="data-table">
              <thead><tr><th>Metric</th><th>What it means</th></tr></thead>
              <tbody>
                <tr><td>Total Cohort</td><td>All members in the database — includes sufferers, former sufferers, family members, medical professionals, and others.</td></tr>
                <tr><td>Diagnosed</td><td>Members with a confirmed CSF leak diagnosis. Shown as a count and a percentage of all sufferers (diagnosed + suspected).</td></tr>
                <tr><td>Suspected</td><td>Members who believe they have a CSF leak but do not yet have a formal diagnosis.</td></tr>
                <tr><td>Countries</td><td>The number of distinct UK and European countries represented in the cohort.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Charts</h4>
          <div class="table-scroll">
            <table class="data-table">
              <thead><tr><th>Chart</th><th>What it shows</th></tr></thead>
              <tbody>
                <tr><td>Member Status</td><td>A breakdown of all members by their status (Diagnosed, Suspected, Former, Family / Friend, Medical Professional, Other). Click <em>View full report</em> for the detailed Report 2.</td></tr>
                <tr><td>CSF Leak Type</td><td>Distribution of spinal, cranial, and combined leak types among sufferers with a known type. Click <em>View full report</em> for Report 3.</td></tr>
                <tr><td>Cohort Growth</td><td>New sufferers added per membership year. This reflects awareness of the charity, not the prevalence of the condition. Click <em>View full report</em> for Report 6.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card">
          <h4 style="margin-bottom: var(--space-3);">Last import badge</h4>
          <p>The top-right corner shows when data was last imported. If the badge turns amber with a warning symbol, the data is more than 90 days old and may not reflect the current membership.</p>
        </div>
      </section>

      <!-- 3. Standard reports -->
      <section id="standard-reports" style="margin-bottom: var(--space-8);">
        <h3 style="margin-bottom: var(--space-4);">3. Standard reports</h3>
        <div class="card" style="margin-bottom: var(--space-4);">
          <p style="margin-bottom: var(--space-3);">Standard reports are pre-built research summaries. Go to <strong>Reports</strong> in the sidebar to see all seven. Click <strong>Run report →</strong> on any card to open it.</p>
          <p style="margin-bottom: var(--space-3);"><strong>Filters:</strong> Each report has filters at the top. Use them to focus the data — for example, filter by diagnostic status or country. Changing a filter reloads the report automatically. Click <strong>Reset filters</strong> to return to the full cohort.</p>
          <p><strong>Suppressed cells:</strong> Any group with fewer than 10 members is shown as <code>—</code> to protect individual privacy. This is a legal requirement under UK GDPR for health data.</p>
        </div>

        <div class="card" style="margin-bottom: var(--space-3);">
          <h4 style="margin-bottom: var(--space-2);">Report 1 — Cohort Overview</h4>
          <p>A whole-cohort snapshot: total size, status composition (diagnosed / suspected / former / supporters), country breakdown, and data completeness. Use this report to understand the shape of the dataset before drilling into specific dimensions.</p>
        </div>

        <div class="card" style="margin-bottom: var(--space-3);">
          <h4 style="margin-bottom: var(--space-2);">Report 2 — Diagnostic Status Profile</h4>
          <p>Breaks down the sufferer cohort by diagnostic status with demographic cross-tabulations (gender, age band). The gender and age distributions help identify whether certain groups are under- or over-represented in the diagnosed population.</p>
        </div>

        <div class="card" style="margin-bottom: var(--space-3);">
          <h4 style="margin-bottom: var(--space-2);">Report 3 — CSF Leak Type Distribution</h4>
          <p>Shows the split between spinal, cranial, and spinal-and-cranial leak types. Filtered to sufferers with a known leak type — members without a recorded type are excluded from this report's denominator.</p>
        </div>

        <div class="card" style="margin-bottom: var(--space-3);">
          <h4 style="margin-bottom: var(--space-2);">Report 4 — Cause of Leak Analysis</h4>
          <p>Breaks causes of leak into groups (Iatrogenic, CTD, Spontaneous / Structural, IIH-Related, Traumatic, Other, Unknown). Use the cause group filter to drill into a specific group and see the individual causes within it.</p>
        </div>

        <div class="card" style="margin-bottom: var(--space-3);">
          <h4 style="margin-bottom: var(--space-2);">Report 5 — Geographic Distribution</h4>
          <p>UK breakdown by country (England, Scotland, Wales, Northern Ireland), by region, and by outward postcode. Also shows European member countries. Outward codes with fewer than 10 members are suppressed. Note: absolute counts only — no population rates, as a denominator is not available.</p>
        </div>

        <div class="card" style="margin-bottom: var(--space-3);">
          <h4 style="margin-bottom: var(--space-2);">Report 6 — Membership Growth &amp; Trends</h4>
          <p>New sufferers per membership year and cumulative cohort growth. <strong>Important:</strong> membership year reflects when someone joined the charity, not when they developed their condition. Growth trends show awareness of the charity, not incidence of the condition.</p>
        </div>

        <div class="card">
          <h4 style="margin-bottom: var(--space-2);">Report 7 — Cause × Type Cross-Analysis</h4>
          <p>A cross-tabulation of cause group against leak type, with a chi-square test of independence. A statistically significant result (p &lt; 0.05) suggests cause and leak type are not independent — but interpret with caution given the limitations of self-reported data and variable completeness.</p>
        </div>
      </section>

      <!-- 4. Custom report builder -->
      <section id="custom-reports" style="margin-bottom: var(--space-8);">
        <h3 style="margin-bottom: var(--space-4);">
          4. Custom report builder
          <span style="display:inline-block; margin-left: var(--space-2); padding: 2px 6px; font-size: var(--font-size-xs); font-weight: 600; background: rgba(76,152,198,0.12); color: var(--color-primary); border: 1px solid var(--color-primary); border-radius: 4px; vertical-align: middle;">RESEARCHER &amp; ADMIN</span>
        </h3>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Creating a custom report</h4>
          <ol style="margin:0; padding-left: var(--space-5); display:flex; flex-direction:column; gap: var(--space-2);">
            <li>Go to <strong>Custom Reports</strong> in the sidebar.</li>
            <li>Click <strong>New report</strong>.</li>
            <li>Give the report a name.</li>
            <li>Select the metrics and dimensions you want to include.</li>
            <li>Add any filters to scope the data.</li>
            <li>Click <strong>Run</strong> to preview the results.</li>
            <li>Click <strong>Save</strong> to save the report for future use.</li>
          </ol>
        </div>
        <div class="card">
          <h4 style="margin-bottom: var(--space-3);">Notes</h4>
          <ul style="margin:0; padding-left: var(--space-5); display:flex; flex-direction:column; gap: var(--space-2);">
            <li>Custom reports are personal — they are only visible to you, not shared with other users.</li>
            <li>The same k≥10 suppression rules apply as in standard reports.</li>
            <li>Saved reports can be edited or deleted from the Custom Reports list.</li>
          </ul>
        </div>
      </section>

      <!-- 5. Importing data -->
      <section id="importing-data" style="margin-bottom: var(--space-8);">
        <h3 style="margin-bottom: var(--space-4);">
          5. Importing data
          <span style="display:inline-block; margin-left: var(--space-2); padding: 2px 6px; font-size: var(--font-size-xs); font-weight: 600; background: rgba(245,200,66,0.15); color: #7a6000; border: 1px solid var(--color-warning); border-radius: 4px; vertical-align: middle;">ADMIN ONLY</span>
        </h3>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Expected file format</h4>
          <p style="margin-bottom: var(--space-3);">The import expects a CSV export from the membership management system. The following columns are required:</p>
          <div class="table-scroll">
            <table class="data-table">
              <thead><tr><th>Column</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td><code>id</code></td><td>Unique member identifier (used for pseudonymisation — never stored)</td></tr>
                <tr><td><code>dateOfBirth</code></td><td>ISO date (YYYY-MM-DD) — used to derive age band only</td></tr>
                <tr><td><code>gender</code></td><td><code>male</code> or <code>female</code></td></tr>
                <tr><td><code>country</code></td><td>Country name (e.g. England, Scotland, France)</td></tr>
                <tr><td><code>postcodeZipCode</code></td><td>Used to derive outward code only (e.g. EH1 from EH1 2AB)</td></tr>
                <tr><td><code>memberStatus</code></td><td>Membership status value</td></tr>
                <tr><td><code>csfLeakType</code></td><td>Leak type (spinal, cranial, spinalAndCranial, etc.)</td></tr>
                <tr><td><code>causeOfLeak</code></td><td>Cause value</td></tr>
                <tr><td><code>memberSince</code></td><td>ISO date — when member joined. Falls back to <code>manualStart</code> then <code>dateCreated</code> if blank.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Import steps</h4>
          <ol style="margin:0; padding-left: var(--space-5); display:flex; flex-direction:column; gap: var(--space-2);">
            <li>Export the latest data from the membership management system as a CSV.</li>
            <li>Go to <strong>Import</strong> in the sidebar.</li>
            <li>Click <strong>Choose file</strong> and select your CSV.</li>
            <li>Click <strong>Import</strong>. The pipeline will run automatically.</li>
            <li>Review the import summary — it shows how many records were imported, skipped, or flagged.</li>
            <li>If errors are listed, check the membership export and re-try.</li>
          </ol>
        </div>
        <div class="card">
          <h4 style="margin-bottom: var(--space-3);">What happens to the data</h4>
          <p>All personally identifiable information (name, email, raw date of birth, full postcode) is pseudonymised or discarded during the import pipeline — before any data is written to the database. The application never stores raw PII.</p>
        </div>
      </section>

      <!-- 6. Managing users -->
      <section id="managing-users" style="margin-bottom: var(--space-8);">
        <h3 style="margin-bottom: var(--space-4);">
          6. Managing users
          <span style="display:inline-block; margin-left: var(--space-2); padding: 2px 6px; font-size: var(--font-size-xs); font-weight: 600; background: rgba(245,200,66,0.15); color: #7a6000; border: 1px solid var(--color-warning); border-radius: 4px; vertical-align: middle;">ADMIN ONLY</span>
        </h3>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Roles</h4>
          <div class="table-scroll">
            <table class="data-table">
              <thead><tr><th>Role</th><th>What they can do</th></tr></thead>
              <tbody>
                <tr><td>Viewer</td><td>View standard reports only. Cannot use the custom report builder, import data, or access admin functions.</td></tr>
                <tr><td>Researcher</td><td>View all standard reports and use the custom report builder. Cannot import data or access admin functions.</td></tr>
                <tr><td>Admin</td><td>Full access — all reports, custom reports, data import, export, and admin functions.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Adding a user</h4>
          <p style="margin-bottom: var(--space-3);">Users are managed in <strong>Microsoft Entra ID</strong> (Azure), not within this application. To add someone:</p>
          <ol style="margin:0; padding-left: var(--space-5); display:flex; flex-direction:column; gap: var(--space-2);">
            <li>Go to <a href="https://portal.azure.com" target="_blank" rel="noopener noreferrer">portal.azure.com</a> and sign in.</li>
            <li>Search for <strong>Microsoft Entra ID</strong> and open it.</li>
            <li>Click <strong>Enterprise applications</strong> → find and open <strong>CSFLA Research App</strong>.</li>
            <li>Click <strong>Users and groups</strong> → <strong>+ Add user/group</strong>.</li>
            <li>Select the person's name, then select their role (Admin, Researcher, or Viewer).</li>
            <li>Click <strong>Assign</strong>.</li>
          </ol>
          <p style="margin-top: var(--space-3);">The user can log in immediately. Role changes take effect at their next login.</p>
        </div>
        <div class="card">
          <h4 style="margin-bottom: var(--space-3);">Removing a user</h4>
          <p>In <strong>Enterprise applications → Users and groups</strong>, find the user, tick their row, and click <strong>Remove</strong>. Their access is revoked at their next login attempt.</p>
        </div>
      </section>

      <!-- 7. Data privacy -->
      <section id="data-privacy" style="margin-bottom: var(--space-8);">
        <h3 style="margin-bottom: var(--space-4);">7. Data privacy</h3>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">What is stored</h4>
          <p style="margin-bottom: var(--space-3);">The application stores <strong>pseudonymised</strong> health and demographic data only. No names, email addresses, or other direct identifiers are ever written to the research database.</p>
          <p>Each member is represented by a pseudonymous ID — a one-way cryptographic token derived from their original membership ID. It is not possible to reverse this token to identify an individual.</p>
        </div>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Legal basis</h4>
          <p>Processing is carried out under UK GDPR and EU GDPR on the basis of the charity's legitimate research interests and public task. A Data Protection Impact Assessment (DPIA) covers the processing activities in this application.</p>
        </div>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Data location</h4>
          <p>All data is stored in Microsoft Azure's UK South region. Data does not leave the UK or EEA.</p>
        </div>
        <div class="card" style="margin-bottom: var(--space-4);">
          <h4 style="margin-bottom: var(--space-3);">Access</h4>
          <p>Only users with an explicitly assigned role can access this application. All access is logged. There is no public or anonymous access.</p>
        </div>
        <div class="card">
          <h4 style="margin-bottom: var(--space-3);">Questions</h4>
          <p>For questions about data protection, contact the charity's Data Protection Officer.</p>
        </div>
      </section>

    </div><!-- /main content -->
  </div><!-- /grid -->
</div>

<style>
.toc-link {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  text-decoration: none;
  padding: var(--space-1) 0;
  transition: color 150ms ease;
}
.toc-link:hover {
  color: var(--color-primary);
}
</style>

{% endblock %}
```

- [ ] **Step 2: Verify visually**

With the dev server running, open `http://localhost:8000/help` and check:
- Two-column layout renders correctly (TOC left, content right)
- TOC links jump to the correct sections
- All seven sections are present
- Role badges appear on sections 4, 5, and 6
- Page looks consistent with the rest of the app

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/stevehamilton/Documents/Claude/CSFLA\ Data/app
pytest --tb=short -q
```

Expected: All tests pass, 0 failures

- [ ] **Step 4: Commit**

```bash
cd "/Users/stevehamilton/Documents/Claude/CSFLA Data"
git add app/templates/help.html
git commit -m "feat(help): add full user guide content — 7 sections with role badges and TOC"
git push origin main
```
