const LEVEL_CLASS = { none: 'lvl-none', low: 'lvl-low', medium: 'lvl-medium', high: 'lvl-high' };

function renderResult(scan) {
  const box = document.getElementById('result');
  const a = scan.analysis;
  const banner = scan.demo
    ? '<div class="notice">Demo result — add an OpenRouter API key to analyse real photos.</div>' : '';
  const saveErr = scan.save_error ? `<div class="notice">${esc(scan.save_error)}</div>` : '';

  if (!a.plastic_detected) {
    box.innerHTML = `${banner}<div class="card"><h2>No plastic detected 🎉</h2>
      <p>${esc(a.summary || 'The AI could not find plastic waste in this photo.')}</p>
      <p class="muted">Try a closer, well-lit photo if you expected plastic items.</p></div>`;
    return;
  }

  const items = a.items.map(i => `
    <div class="card item">
      <div class="item-head">
        <span class="item-icon">${esc(i.icon)}</span>
        <div>
          <h3>${esc(i.name)} ${i.count > 1 ? `<span class="muted">×${i.count}</span>` : ''}</h3>
          <div class="item-meta">
            <span class="tag">#${i.resin.number} ${esc(i.resin.code)}</span>
            <span class="bin-tag" style="background:${esc(i.bin.color)}">${esc(i.bin.label)}</span>
            <span class="muted">${Math.round(i.confidence * 100)}% confident · ${esc(i.condition)}</span>
          </div>
        </div>
      </div>
      <p class="seg"><strong>Segregation:</strong> ${esc(i.segregation)}</p>
      <ol class="actions">${i.actions.map(x => `<li>${esc(x)}</li>`).join('')}</ol>
      <p class="muted">♻ Reuse idea: ${esc(i.reuse)}</p>
    </div>`).join('');

  const tips = a.tips.length
    ? `<div class="card"><h3>💡 Tips for this photo</h3><ul>${a.tips.map(t => `<li>${esc(t)}</li>`).join('')}</ul></div>` : '';

  box.innerHTML = `${banner}${saveErr}
    <div class="card summary">
      <div class="summary-top">
        <span class="level ${LEVEL_CLASS[a.level.key] || ''}">Waste level: ${esc(a.level.key.toUpperCase())}</span>
        ${scan.model && scan.model !== 'demo' ? `<span class="muted small">AI: ${esc(scan.model)}</span>` : ''}
      </div>
      <p>${esc(a.summary)}</p>
      <p class="muted small">${esc(a.level.text)}</p>
      <div class="summary-stats">
        <div><strong>${a.total_items}</strong><span>items</span></div>
        <div><strong>${a.recyclable_items}</strong><span>recyclable</span></div>
        <div><strong>${a.co2_saved_kg}</strong><span>kg CO₂ saved*</span></div>
        <div><strong>+${a.points}</strong><span>eco points</span></div>
      </div>
      <p class="muted small">*if recycled correctly instead of landfilled</p>
    </div>
    <h2 class="section-title small-title">What to do</h2>
    ${items}
    ${tips}
    <div class="card act-card">
      <h3>📍 Take action nearby</h3>
      <a class="btn btn-ghost" target="_blank" rel="noopener"
         href="https://www.google.com/maps/search/plastic+recycling+centre+near+me">Find recycling centres</a>
      <a class="btn btn-primary" href="/dashboard">View my impact</a>
    </div>`;
}

(function initUpload() {
  const input = document.getElementById('file');
  if (!input) return; // detail page reuses renderResult only

  const dropzone = document.getElementById('dropzone');
  const preview = document.getElementById('preview');
  const empty = document.getElementById('dz-empty');
  const analyze = document.getElementById('analyze');
  const change = document.getElementById('change');
  const error = document.getElementById('error');
  let file = null;

  function showError(msg) { error.textContent = msg; error.hidden = !msg; }

  function setFile(f) {
    showError('');
    if (!f) return;
    if (!f.type.startsWith('image/')) { showError('Please choose an image file.'); return; }
    if (f.size > 10 * 1024 * 1024) { showError('Photo is too large (max 10 MB).'); return; }
    file = f;
    preview.src = URL.createObjectURL(f);
    preview.hidden = false; empty.hidden = true; change.hidden = false;
    analyze.disabled = false;
  }

  input.addEventListener('change', () => setFile(input.files[0]));
  change.addEventListener('click', () => input.click());
  ['dragover', 'dragenter'].forEach(e => dropzone.addEventListener(e, ev => {
    ev.preventDefault(); dropzone.classList.add('drag');
  }));
  ['dragleave', 'drop'].forEach(e => dropzone.addEventListener(e, ev => {
    ev.preventDefault(); dropzone.classList.remove('drag');
  }));
  dropzone.addEventListener('drop', ev => setFile(ev.dataTransfer.files[0]));

  analyze.addEventListener('click', async () => {
    if (!file) return;
    showError('');
    analyze.disabled = true;
    analyze.innerHTML = '<span class="spinner"></span> Analysing…';
    document.getElementById('result').innerHTML =
      '<div class="card placeholder"><span class="spinner dark"></span> AI is detecting plastic items… this can take 10–30 s on free models.</div>';
    const form = new FormData();
    form.append('image', file);
    try {
      const scan = await api('/api/scan', { method: 'POST', body: form });
      renderResult(scan);
      document.getElementById('result').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      showError(e.message);
      document.getElementById('result').innerHTML = '';
    } finally {
      analyze.disabled = false;
      analyze.innerHTML = '🔍 Analyse waste';
    }
  });
})();
