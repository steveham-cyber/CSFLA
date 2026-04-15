/**
 * report_builder.js — Custom Report Builder
 *
 * Manages the palette, canvas (SortableJS), config modal, save, and run.
 * All API calls go to /api/custom-reports/*.
 *
 * State is held in `builderState`:
 *   blocks:             array of { instanceId, reportId, title, filters }
 *   catalogue:          array of block metadata from /api/custom-reports/blocks
 *   reportId:           null | string (UUID of the saved report being edited)
 *   editingInstanceId:  null | string (which block's config modal is open)
 */

// ── State ─────────────────────────────────────────────────────────────────────

const builderState = {
  blocks: [],
  catalogue: [],
  reportId: null,
  editingInstanceId: null,
};

const FILTER_LABELS = {
  country: 'Country',
  gender: 'Gender',
  age_band: 'Age band',
  year_from: 'Year from',
  year_to: 'Year to',
  diagnostic_status: 'Diagnostic status',
  cause_group: 'Cause group',
  individual_cause: 'Individual cause',
  leak_type: 'Leak type',
  country_group: 'Country group',
};

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('builder-root');
  if (!root) return;

  const mode = root.dataset.mode;
  const reportId = root.dataset.reportId || null;
  builderState.reportId = reportId;

  if (mode === 'list') {
    builderInitList();
  } else if (mode === 'new') {
    builderInitNew();
  } else if (mode === 'edit') {
    builderInitEdit(reportId);
  }
});

// ── List mode ─────────────────────────────────────────────────────────────────

async function builderInitList() {
  const listEl = document.getElementById('saved-reports-list');
  try {
    const resp = await fetch('/api/custom-reports/');
    if (!resp.ok) throw new Error('Failed to load reports');
    const data = await resp.json();
    builderRenderList(listEl, data.reports);
  } catch (err) {
    listEl.innerHTML = `<p style="color:var(--color-danger); padding:var(--space-4);">Error loading reports: ${_esc(err.message)}</p>`;
  }
}

function builderRenderList(container, reports) {
  if (reports.length === 0) {
    container.innerHTML = `
      <p style="color:var(--color-text-muted); text-align:center; padding:var(--space-6);">
        No custom reports yet. <a href="/reports/builder/new">Create your first report</a>.
      </p>`;
    return;
  }

  const rows = reports.map(r => `
    <div style="display:flex; align-items:center; justify-content:space-between; padding:var(--space-3) 0; border-bottom:1px solid var(--color-border);">
      <div>
        <a href="/reports/builder/${_esc(r.id)}" style="font-weight:600; text-decoration:none; color:var(--color-text);">${_esc(r.name)}</a>
        ${r.description ? `<p style="font-size:var(--font-size-sm); color:var(--color-text-muted); margin:var(--space-1) 0 0;">${_esc(r.description)}</p>` : ''}
        <p style="font-size:var(--font-size-sm); color:var(--color-text-muted); margin:var(--space-1) 0 0;">
          ${_esc(String(r.block_count))} block${r.block_count !== 1 ? 's' : ''} · Last updated ${_esc(_fmtDate(r.updated_at))}
        </p>
      </div>
      <div style="display:flex; gap:var(--space-2);">
        <a href="/reports/builder/${_esc(r.id)}" class="btn btn-ghost" style="font-size:var(--font-size-sm);">Edit</a>
        <button class="btn btn-ghost" style="font-size:var(--font-size-sm); color:var(--color-danger);"
                data-delete-id="${_esc(r.id)}" data-delete-name="${_esc(r.name)}">Delete</button>
      </div>
    </div>
  `).join('');

  container.innerHTML = `<div style="padding:0 var(--space-4);">${rows}</div>`;

  // Attach delete handlers via event listeners — never inline onclick with user data
  container.querySelectorAll('[data-delete-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      builderDeleteReport(btn.dataset.deleteId, btn.dataset.deleteName);
    });
  });
}

async function builderDeleteReport(reportId, name) {
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
  try {
    const resp = await fetch(`/api/custom-reports/${reportId}/delete`, { method: 'POST' });
    if (!resp.ok) throw new Error('Delete failed');
    builderInitList();
  } catch (err) {
    alert(`Failed to delete: ${_esc(err.message)}`);
  }
}

// ── Builder init ──────────────────────────────────────────────────────────────

async function builderInitNew() {
  await builderLoadCatalogue();
  builderRenderPalette();
  builderInitCanvas();
}

async function builderInitEdit(reportId) {
  await builderLoadCatalogue();
  try {
    const resp = await fetch(`/api/custom-reports/${reportId}`);
    if (!resp.ok) throw new Error('Report not found');
    const data = await resp.json();

    document.getElementById('report-name').value = data.name;
    document.getElementById('report-description').value = data.description || '';

    builderState.blocks = (data.definition.blocks || []).map(b => ({
      instanceId: b.instance_id,
      reportId: b.report_id,
      title: b.title || '',
      filters: b.filters || {},
    }));
  } catch (err) {
    alert(`Failed to load report: ${_esc(err.message)}`);
    return;
  }
  builderRenderPalette();
  builderInitCanvas();
  builderRenderCanvas();
  builderUpdateSaveState();
}

async function builderLoadCatalogue() {
  const resp = await fetch('/api/custom-reports/blocks');
  const data = await resp.json();
  builderState.catalogue = data.blocks;
}

// ── Palette ───────────────────────────────────────────────────────────────────

function builderRenderPalette() {
  const palette = document.getElementById('block-palette');
  if (!palette) return;

  palette.innerHTML = builderState.catalogue.map(block => `
    <div class="palette-block"
         draggable="true"
         data-report-id="${_esc(block.id)}"
         style="background:var(--color-surface); border:1px solid var(--color-border); border-radius:var(--radius-sm); padding:var(--space-3); cursor:grab; user-select:none;"
         ondragstart="builderPaletteDragStart(event, '${_esc(block.id)}')">
      <div style="font-weight:600; font-size:var(--font-size-sm);">${_esc(block.title)}</div>
      <div style="font-size:var(--font-size-xs); color:var(--color-text-muted); margin-top:var(--space-1);">${_esc(block.description)}</div>
    </div>
  `).join('');
}

function builderPaletteDragStart(event, reportId) {
  event.dataTransfer.setData('text/plain', reportId);
  event.dataTransfer.effectAllowed = 'copy';
}

// ── Canvas ────────────────────────────────────────────────────────────────────

function builderInitCanvas() {
  const canvas = document.getElementById('block-canvas');
  if (!canvas) return;

  canvas.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    canvas.style.borderColor = 'var(--color-primary)';
  });

  canvas.addEventListener('dragleave', () => {
    canvas.style.borderColor = 'var(--color-border)';
  });

  canvas.addEventListener('drop', e => {
    e.preventDefault();
    canvas.style.borderColor = 'var(--color-border)';
    const reportId = e.dataTransfer.getData('text/plain');
    if (!reportId) return;
    if (builderState.blocks.length >= 8) {
      alert('Maximum 8 blocks per report.');
      return;
    }
    builderAddBlock(reportId);
  });

  Sortable.create(canvas, {
    animation: 150,
    handle: '.drag-handle',
    filter: '.canvas-empty-hint',
    onEnd: () => {
      const newOrder = [];
      canvas.querySelectorAll('[data-instance-id]').forEach(el => {
        const found = builderState.blocks.find(b => b.instanceId === el.dataset.instanceId);
        if (found) newOrder.push(found);
      });
      builderState.blocks = newOrder;
    },
  });
}

function builderAddBlock(reportId) {
  const instanceId = 'b' + Date.now();
  builderState.blocks.push({ instanceId, reportId, title: '', filters: {} });
  builderRenderCanvas();
  builderUpdateSaveState();
}

function builderRemoveBlock(instanceId) {
  builderState.blocks = builderState.blocks.filter(b => b.instanceId !== instanceId);
  builderRenderCanvas();
  builderUpdateSaveState();
}

function builderRenderCanvas() {
  const canvas = document.getElementById('block-canvas');
  const badge = document.getElementById('block-count-badge');
  if (!canvas) return;

  const count = builderState.blocks.length;
  if (badge) badge.textContent = `(${count} / 8 blocks)`;

  if (count === 0) {
    canvas.innerHTML = `
      <p id="canvas-empty-hint" class="canvas-empty-hint"
         style="color:var(--color-text-muted); font-size:var(--font-size-sm); text-align:center; padding:var(--space-6) 0; margin:0;">
        Drag blocks from the palette to build your report
      </p>`;
    return;
  }

  canvas.innerHTML = builderState.blocks.map(block => {
    const meta = builderState.catalogue.find(b => b.id === block.reportId);
    const displayTitle = block.title || (meta ? meta.title : block.reportId);
    const filterSummary = _filterSummary(block.filters);

    return `
      <div class="canvas-block" data-instance-id="${_esc(block.instanceId)}"
           style="background:var(--color-surface); border:1px solid var(--color-border); border-radius:var(--radius-sm); padding:var(--space-3); display:flex; align-items:center; gap:var(--space-3);">
        <span class="drag-handle" style="color:var(--color-text-muted); cursor:grab; font-size:18px; flex-shrink:0;" title="Drag to reorder">⠿</span>
        <div style="flex:1; min-width:0;">
          <div style="font-weight:600; font-size:var(--font-size-sm);">${_esc(displayTitle)}</div>
          <div style="font-size:var(--font-size-xs); color:var(--color-text-muted); margin-top:2px;">
            ${filterSummary || '<em>No filters applied</em>'}
          </div>
        </div>
        <button class="btn btn-ghost" style="font-size:var(--font-size-sm); flex-shrink:0;"
                onclick="builderOpenConfigModal('${_esc(block.instanceId)}')" type="button">⚙ Configure</button>
        <button class="btn btn-ghost" style="font-size:var(--font-size-sm); color:var(--color-danger); flex-shrink:0;"
                onclick="builderRemoveBlock('${_esc(block.instanceId)}')" type="button">✕</button>
      </div>`;
  }).join('');
}

// ── Config modal ──────────────────────────────────────────────────────────────

function builderOpenConfigModal(instanceId) {
  const block = builderState.blocks.find(b => b.instanceId === instanceId);
  if (!block) return;

  const meta = builderState.catalogue.find(b => b.id === block.reportId);
  builderState.editingInstanceId = instanceId;

  document.getElementById('config-modal-title').textContent =
    'Configure: ' + (meta ? meta.title : block.reportId);

  const body = document.getElementById('config-modal-body');
  const availableFilters = meta ? meta.filters : [];

  if (availableFilters.length === 0) {
    body.innerHTML = `<p style="color:var(--color-text-muted); font-size:var(--font-size-sm);">This block has no configurable filters.</p>`;
  } else {
    body.innerHTML = `
      <div style="margin-bottom:var(--space-3);">
        <label style="display:block; font-size:var(--font-size-sm); font-weight:600; margin-bottom:var(--space-1);">Custom title (optional)</label>
        <input type="text" id="cfg-title" class="input" style="width:100%;" maxlength="100"
               value="${_esc(block.title || '')}" placeholder="Leave blank to use default">
      </div>
      ${availableFilters.map(key => `
        <div style="margin-bottom:var(--space-3);">
          <label for="cfg-${_esc(key)}" style="display:block; font-size:var(--font-size-sm); font-weight:600; margin-bottom:var(--space-1);">
            ${_esc(FILTER_LABELS[key] || key)}
          </label>
          <input type="${key.startsWith('year') ? 'number' : 'text'}"
                 id="cfg-${_esc(key)}" class="input" style="width:100%;"
                 value="${_esc(String(block.filters[key] ?? ''))}"
                 placeholder="Leave blank for no filter"
                 ${key.startsWith('year') ? 'min="2000" max="2100"' : ''}>
        </div>
      `).join('')}
    `;
  }

  const modal = document.getElementById('config-modal');
  modal.style.display = 'flex';
}

function builderCloseConfigModal() {
  document.getElementById('config-modal').style.display = 'none';
  builderState.editingInstanceId = null;
}

function builderSaveBlockConfig() {
  const instanceId = builderState.editingInstanceId;
  if (!instanceId) return;

  const block = builderState.blocks.find(b => b.instanceId === instanceId);
  const meta = builderState.catalogue.find(b => b.id === block.reportId);
  const availableFilters = meta ? meta.filters : [];

  const titleInput = document.getElementById('cfg-title');
  if (titleInput) block.title = titleInput.value.trim();

  block.filters = {};
  availableFilters.forEach(key => {
    const el = document.getElementById(`cfg-${key}`);
    if (!el) return;
    const val = el.value.trim();
    if (!val) return;
    block.filters[key] = key.startsWith('year') ? parseInt(val, 10) : val;
  });

  builderCloseConfigModal();
  builderRenderCanvas();
}

// ── Save / Run ────────────────────────────────────────────────────────────────

function builderUpdateSaveState() {
  const nameEl = document.getElementById('report-name');
  const saveBtn = document.getElementById('btn-save');
  const runBtn = document.getElementById('btn-run');
  if (!saveBtn || !runBtn) return;

  const hasName = nameEl && nameEl.value.trim().length > 0;
  const hasBlocks = builderState.blocks.length > 0;
  saveBtn.disabled = !(hasName && hasBlocks);
  runBtn.disabled = !hasBlocks;
}

document.addEventListener('DOMContentLoaded', () => {
  const saveBtn = document.getElementById('btn-save');
  const runBtn = document.getElementById('btn-run');

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving\u2026';
      try {
        await builderSaveReport();
        saveBtn.textContent = 'Saved \u2713';
        setTimeout(() => { saveBtn.textContent = 'Save'; builderUpdateSaveState(); }, 2000);
      } catch (err) {
        alert(`Save failed: ${_esc(err.message)}`);
        saveBtn.textContent = 'Save';
        builderUpdateSaveState();
      }
    });
  }

  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      runBtn.disabled = true;
      runBtn.textContent = 'Running\u2026';
      try {
        await builderRunReport();
      } catch (err) {
        alert(`Run failed: ${_esc(err.message)}`);
      } finally {
        runBtn.textContent = 'Run';
        builderUpdateSaveState();
      }
    });
  }
});

function _buildDefinition() {
  return {
    blocks: builderState.blocks.map(b => ({
      instance_id: b.instanceId,
      report_id: b.reportId,
      title: b.title || null,
      filters: b.filters,
    })),
  };
}

async function builderSaveReport() {
  const name = document.getElementById('report-name').value.trim();
  const description = document.getElementById('report-description').value.trim();
  const definition = _buildDefinition();
  const body = { name, description: description || null, definition };
  const isEdit = !!builderState.reportId;
  const url = isEdit
    ? `/api/custom-reports/${builderState.reportId}`
    : '/api/custom-reports/';

  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }

  const data = await resp.json();
  if (!isEdit) {
    window.history.replaceState({}, '', `/reports/builder/${data.id}`);
    builderState.reportId = data.id;
    document.getElementById('builder-root').dataset.reportId = data.id;
  }
}

async function builderRunReport() {
  const definition = _buildDefinition();
  const resultsArea = document.getElementById('results-area');
  const resultsContent = document.getElementById('results-content');

  resultsContent.innerHTML = `<div class="loading-state" style="text-align:center; padding:var(--space-6); color:var(--color-text-muted);">Running report\u2026</div>`;
  resultsArea.style.display = 'block';
  resultsArea.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const url = builderState.reportId
    ? `/api/custom-reports/${builderState.reportId}/run`
    : '/api/custom-reports/preview';

  const fetchBody = builderState.reportId ? undefined : JSON.stringify({ definition });
  const resp = await fetch(url, {
    method: 'POST',
    headers: fetchBody ? { 'Content-Type': 'application/json' } : {},
    body: fetchBody,
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }

  const data = await resp.json();
  builderRenderResults(data);
}

function builderRenderResults(data) {
  const content = document.getElementById('results-content');
  const blockResults = data.blocks || {};

  const sections = builderState.blocks.map(block => {
    const meta = builderState.catalogue.find(b => b.id === block.reportId);
    const title = block.title || (meta ? meta.title : block.reportId);
    const result = blockResults[block.instanceId];

    if (!result) {
      return `<div class="card" style="margin-bottom:var(--space-4);">
        <h4>${_esc(title)}</h4>
        <p style="color:var(--color-text-muted);">No result returned.</p>
      </div>`;
    }
    if (!result.ok) {
      return `<div class="card" style="margin-bottom:var(--space-4);">
        <h4>${_esc(title)}</h4>
        <p style="color:var(--color-danger);">Error: ${_esc(result.error)}</p>
      </div>`;
    }
    return `<div class="card" style="margin-bottom:var(--space-4);">
      <h4>${_esc(title)}</h4>
      <pre style="font-size:var(--font-size-xs); overflow-x:auto; background:var(--color-bg); padding:var(--space-3); border-radius:var(--radius-sm); color:var(--color-text);">${_esc(JSON.stringify(result.data, null, 2))}</pre>
    </div>`;
  });

  content.innerHTML = sections.join('');
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function _esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function _filterSummary(filters) {
  const parts = Object.entries(filters)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${_esc(FILTER_LABELS[k] || k)}: ${_esc(String(v))}`);
  return parts.join(' \u00b7 ');
}

function _fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
