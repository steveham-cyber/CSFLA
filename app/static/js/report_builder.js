'use strict';

// ── State ─────────────────────────────────────────────────────────────────────

const S = {
    reportId:     null,
    reportName:   '',
    dimensions:   [],
    filters:      {},
    catalogue:    [],
    savedReports: [],
};

// ── DOM refs ──────────────────────────────────────────────────────────────────

const ROOT       = document.getElementById('builder-root');
const nameInput  = document.getElementById('report-name-input');
const savedBar   = document.getElementById('saved-bar');
const leftPanel  = document.getElementById('left-panel');
const resultArea = document.getElementById('result-area');

// ── Security helper ───────────────────────────────────────────────────────────

function _esc(s) {
    return String(s)
        .replace(/&/g,  '&amp;')
        .replace(/</g,  '&lt;')
        .replace(/>/g,  '&gt;')
        .replace(/"/g,  '&quot;')
        .replace(/'/g,  '&#39;');
}

// ── Catalogue helpers ─────────────────────────────────────────────────────────

function fieldMeta(key) {
    return S.catalogue.find(f => f.key === key) || { key, label: key, values: [] };
}

const ORDINALS = ['1st', '2nd', '3rd', '4th', '5th', '6th'];

// ── Render: left panel ────────────────────────────────────────────────────────

function renderLeft() {
    const dimIndex = Object.fromEntries(S.dimensions.map((k, i) => [k, i]));

    let html = '<div style="margin-bottom:var(--space-5)">';
    html += '<div style="font-size:11px;font-weight:700;color:var(--color-text-muted);'
          + 'text-transform:uppercase;letter-spacing:1px;margin-bottom:var(--space-2)">Group By</div>';

    for (const field of S.catalogue) {
        const isActive = field.key in dimIndex;
        const isIndividualCause = field.key === 'individual_cause';
        const ordinal = isActive ? ORDINALS[dimIndex[field.key]] : null;
        html += `<div class="dim-pill" data-field="${_esc(field.key)}" style="
            display:flex;align-items:center;justify-content:space-between;
            padding:8px 10px;border-radius:var(--radius-md);
            border:1.5px solid ${isActive ? 'var(--color-primary)' : 'var(--color-border)'};
            margin-bottom:6px;cursor:pointer;
            font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);
            color:${isActive ? '#fff' : 'var(--color-primary)'};
            background:${isActive ? 'var(--color-primary)' : 'var(--color-bg-white)'};
            opacity:${!isActive && isIndividualCause ? '0.65' : '1'};
        ">
            <span>${_esc(field.label)}</span>
            ${isActive
                ? `<span style="font-size:11px;font-weight:700;background:rgba(255,255,255,0.25);
                     color:#fff;border-radius:99px;padding:1px 7px;">${ordinal}</span>`
                : `<span style="font-size:11px;color:var(--color-text-muted)">+ add</span>`
            }
        </div>`;
    }
    html += '</div>';

    const filterFields = [...new Set([...S.dimensions, ...Object.keys(S.filters)])];

    html += '<div>';
    html += '<div style="font-size:11px;font-weight:700;color:var(--color-text-muted);'
          + 'text-transform:uppercase;letter-spacing:1px;margin-bottom:var(--space-2)">Filters</div>';

    for (const key of filterFields) {
        const field    = fieldMeta(key);
        const isFilterOnly = !S.dimensions.includes(key);
        const active   = S.filters[key] || [];
        const available = field.values.filter(v => !active.includes(v));

        html += `<div style="margin-bottom:var(--space-3)">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;font-weight:var(--font-weight-medium);color:var(--color-primary)">
                    ${_esc(field.label)}
                </span>
                ${isFilterOnly
                    ? `<button class="remove-filter-field" data-field="${_esc(key)}"
                         style="background:none;border:none;cursor:pointer;
                                color:var(--color-text-muted);font-size:16px;line-height:1;padding:0;">×</button>`
                    : ''}
            </div>`;

        if (available.length > 0) {
            html += `<select class="filter-add-select" data-field="${_esc(key)}"
                style="width:100%;border:1px solid var(--color-border);
                       border-radius:var(--radius-md);padding:6px var(--space-2);
                       font-size:12px;font-family:inherit;
                       background:var(--color-bg-card);color:var(--color-text-body);">
                <option value="">Add value…</option>`;
            for (const v of available) {
                html += `<option value="${_esc(v)}">${_esc(v)}</option>`;
            }
            html += `</select>`;
        }

        if (active.length > 0) {
            html += `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:5px;">`;
            for (const v of active) {
                html += `<span style="background:var(--color-bg-shape);color:var(--color-primary);
                    font-size:11px;font-weight:var(--font-weight-medium);border-radius:99px;
                    padding:2px 8px;display:inline-flex;align-items:center;gap:4px;">
                    ${_esc(v)}
                    <button class="remove-filter-val"
                        data-field="${_esc(key)}" data-value="${_esc(v)}"
                        style="background:none;border:none;cursor:pointer;
                               color:var(--color-text-muted);font-size:13px;line-height:1;padding:0;">×</button>
                </span>`;
            }
            html += `</div>`;
        }
        html += `</div>`;
    }

    const nonFilterFields = S.catalogue.filter(f => !filterFields.includes(f.key));
    if (nonFilterFields.length > 0) {
        html += `<select id="add-filter-field"
            style="width:100%;border:1px solid var(--color-border);
                   border-radius:var(--radius-md);padding:6px var(--space-2);
                   font-size:12px;font-family:inherit;
                   background:var(--color-bg-white);color:var(--color-text-muted);
                   margin-top:var(--space-2);">
            <option value="">Filter on another field…</option>`;
        for (const f of nonFilterFields) {
            html += `<option value="${_esc(f.key)}">${_esc(f.label)}</option>`;
        }
        html += `</select>`;
    }

    html += '</div>';
    leftPanel.innerHTML = html;
    _attachLeftEvents();
}

function _attachLeftEvents() {
    leftPanel.querySelectorAll('.dim-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const key = pill.dataset.field;
            if (S.dimensions.includes(key)) {
                S.dimensions = S.dimensions.filter(k => k !== key);
                delete S.filters[key];
            } else if (S.dimensions.length < 6) {
                S.dimensions.push(key);
            }
            renderLeft();
        });
    });

    leftPanel.querySelectorAll('.filter-add-select').forEach(sel => {
        sel.addEventListener('change', () => {
            const key = sel.dataset.field;
            const val = sel.value;
            if (!val) return;
            if (!S.filters[key]) S.filters[key] = [];
            if (!S.filters[key].includes(val)) S.filters[key].push(val);
            renderLeft();
        });
    });

    leftPanel.querySelectorAll('.remove-filter-val').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            const key = btn.dataset.field;
            const val = btn.dataset.value;
            S.filters[key] = (S.filters[key] || []).filter(v => v !== val);
            if (S.filters[key].length === 0) delete S.filters[key];
            renderLeft();
        });
    });

    leftPanel.querySelectorAll('.remove-filter-field').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            delete S.filters[btn.dataset.field];
            renderLeft();
        });
    });

    const addSel = document.getElementById('add-filter-field');
    if (addSel) {
        addSel.addEventListener('change', () => {
            const key = addSel.value;
            if (!key) return;
            if (!S.filters[key]) S.filters[key] = [];
            renderLeft();
        });
    }
}

// ── Render: saved bar ─────────────────────────────────────────────────────────

function renderSavedBar() {
    savedBar.querySelectorAll('button.saved-chip').forEach(c => c.remove());

    for (const r of S.savedReports) {
        const chip = document.createElement('button');
        chip.className = 'saved-chip';
        chip.textContent = r.name;
        chip.dataset.id  = r.id;
        const isActive = r.id === S.reportId;
        chip.style.cssText = `
            background:${isActive ? 'var(--color-primary)' : 'var(--color-bg-white)'};
            color:${isActive ? '#fff' : 'var(--color-primary)'};
            border:1px solid ${isActive ? 'var(--color-primary)' : 'var(--color-border)'};
            border-radius:99px;padding:3px 12px;font-size:12px;
            font-family:inherit;font-weight:var(--font-weight-medium);
            cursor:pointer;white-space:nowrap;
        `;
        chip.addEventListener('click', () => {
            loadReport(r.id).catch(err => {
                alert(`Could not load report: ${err.message}`);
            });
        });
        savedBar.appendChild(chip);
    }
}

// ── Render: results ───────────────────────────────────────────────────────────

function renderEmptyResult() {
    resultArea.innerHTML = `
        <div style="text-align:center;padding:64px var(--space-6);color:var(--color-text-muted);">
            <div style="font-size:32px;margin-bottom:var(--space-3);">&#8862;</div>
            <p style="font-size:var(--font-size-sm);">Select fields and press Run</p>
        </div>`;
}

function renderResult(result) {
    let html = `
        <div style="display:flex;align-items:center;justify-content:space-between;
                    margin-bottom:var(--space-3);">
            <span style="font-size:var(--font-size-sm);font-weight:var(--font-weight-bold);
                         color:var(--color-primary);">Results</span>
            <span style="font-size:var(--font-size-xs);color:var(--color-text-muted);">
                ${_esc(result.total_shown.toLocaleString())} members shown
            </span>
        </div>`;

    if (result.suppressed_count > 0) {
        const n = result.suppressed_count;
        html += `
            <div style="background:#FFF8E8;border:1px solid var(--color-warning);
                        border-radius:var(--radius-md);padding:10px var(--space-4);
                        font-size:var(--font-size-xs);color:var(--color-text-body);
                        margin-bottom:var(--space-3);display:flex;
                        align-items:flex-start;gap:var(--space-2);">
                <span>&#9888;</span>
                <span><strong>${_esc(n)} combination${n === 1 ? '' : 's'} hidden</strong>
                    — fewer than 10 members each. These are not shown to protect member privacy.</span>
            </div>`;
    }

    if (result.rows.length === 0) {
        html += `
            <div style="text-align:center;padding:var(--space-7) var(--space-6);
                        color:var(--color-text-muted);">
                <p style="font-size:var(--font-size-sm);">
                    No combinations with 10 or more members match the current filters.
                </p>
            </div>`;
    } else {
        html += `<div style="background:var(--color-bg-white);border:1px solid var(--color-border);
                              border-radius:var(--radius-md);overflow:hidden;
                              box-shadow:var(--shadow-card);">
            <table style="width:100%;border-collapse:collapse;">
                <thead><tr style="background:var(--color-bg-card);">`;

        for (const col of result.columns) {
            html += `<th style="padding:10px var(--space-4);font-size:11px;font-weight:700;
                text-transform:uppercase;letter-spacing:0.8px;color:var(--color-primary);
                text-align:left;border-bottom:1px solid var(--color-border);">
                ${_esc(fieldMeta(col).label)}</th>`;
        }
        html += `<th style="padding:10px var(--space-4);font-size:11px;font-weight:700;
            text-transform:uppercase;letter-spacing:0.8px;color:var(--color-primary);
            text-align:right;border-bottom:1px solid var(--color-border);">Members</th>
                </tr></thead><tbody>`;

        for (const row of result.rows) {
            html += `<tr style="border-bottom:1px solid var(--color-border);">`;
            for (const col of result.columns) {
                html += `<td style="padding:9px var(--space-4);font-size:var(--font-size-sm);
                    color:var(--color-text-body);">${_esc(row[col] ?? '—')}</td>`;
            }
            html += `<td style="padding:9px var(--space-4);font-size:var(--font-size-sm);
                font-weight:var(--font-weight-bold);color:var(--color-primary);
                text-align:right;">${_esc(row.member_count.toLocaleString())}</td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
    }

    resultArea.innerHTML = html;
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiFetch(url, opts = {}) {
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function loadCatalogue() {
    const data = await apiFetch('/api/custom-reports/fields');
    S.catalogue = data.fields;
}

async function loadSavedReports() {
    const data = await apiFetch('/api/custom-reports/');
    S.savedReports = data.reports;
    renderSavedBar();
}

async function loadReport(id) {
    const data = await apiFetch(`/api/custom-reports/${id}`);
    S.reportId   = data.id;
    S.reportName = data.name;
    S.dimensions = data.definition.dimensions;
    S.filters    = data.definition.filters || {};
    nameInput.value = S.reportName;
    history.replaceState(null, '', `/reports/builder/${id}`);
    renderLeft();
    renderSavedBar();
    renderEmptyResult();
}

function resetState() {
    S.reportId   = null;
    S.reportName = '';
    S.dimensions = [];
    S.filters    = {};
    nameInput.value = '';
    history.replaceState(null, '', '/reports/builder/new');
    renderLeft();
    renderSavedBar();
    renderEmptyResult();
}

async function saveReport() {
    const name = nameInput.value.trim();
    if (!name) {
        nameInput.focus();
        nameInput.style.borderColor = 'var(--color-error)';
        setTimeout(() => { nameInput.style.borderColor = ''; }, 2000);
        return;
    }
    if (S.dimensions.length === 0) {
        alert('Please select at least one field to group by.');
        return;
    }
    const body = {
        name,
        definition: { dimensions: S.dimensions, filters: S.filters },
    };
    try {
        let data;
        if (S.reportId) {
            data = await apiFetch(`/api/custom-reports/${S.reportId}`, {
                method: 'POST',
                body: JSON.stringify(body),
            });
        } else {
            data = await apiFetch('/api/custom-reports/', {
                method: 'POST',
                body: JSON.stringify(body),
            });
            S.reportId = data.id;
            history.replaceState(null, '', `/reports/builder/${S.reportId}`);
        }
        S.reportName = data.name;
        await loadSavedReports();
    } catch (err) {
        alert(`Save failed: ${err.message}`);
    }
}

async function runReport() {
    if (S.dimensions.length === 0) {
        alert('Please select at least one field to group by.');
        return;
    }
    const btnRun = document.getElementById('btn-run');
    btnRun.disabled  = true;
    btnRun.textContent = 'Running…';
    try {
        let result;
        if (S.reportId) {
            result = await apiFetch(`/api/custom-reports/${S.reportId}/run`, {
                method: 'POST',
            });
        } else {
            result = await apiFetch('/api/custom-reports/run', {
                method: 'POST',
                body: JSON.stringify({
                    dimensions: S.dimensions,
                    filters: S.filters,
                }),
            });
        }
        renderResult(result);
    } catch (err) {
        resultArea.innerHTML = `
            <div style="color:var(--color-error);padding:var(--space-4);">
                Error: ${_esc(err.message)}
            </div>`;
    } finally {
        btnRun.disabled = false;
        btnRun.textContent = '▶ Run';
    }
}

// ── Initialisation ────────────────────────────────────────────────────────────

async function init() {
    try {
        await loadCatalogue();
        await loadSavedReports();
    } catch (err) {
        leftPanel.innerHTML = `
            <div style="color:var(--color-error);font-size:var(--font-size-sm);
                        padding:var(--space-4);">
                Failed to load fields: ${_esc(err.message)}
            </div>`;
        return;
    }

    const initialReportId = ROOT.dataset.reportId;
    if (initialReportId) {
        try {
            await loadReport(initialReportId);
        } catch {
            resetState();
        }
    } else {
        renderLeft();
        renderEmptyResult();
    }

    document.getElementById('btn-new').addEventListener('click', resetState);
    document.getElementById('btn-save').addEventListener('click', saveReport);
    document.getElementById('btn-run').addEventListener('click', runReport);
}

document.addEventListener('DOMContentLoaded', init);
