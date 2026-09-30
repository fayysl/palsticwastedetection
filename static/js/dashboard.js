const PALETTE = ['#16a34a', '#2563eb', '#d97706', '#9333ea', '#dc2626', '#0891b2', '#65a30d', '#6b7280'];

function setText(id, value) { document.getElementById(id).textContent = value; }

function chart(id, type, labels, values, colors) {
  if (!window.Chart) return;
  const el = document.getElementById(id);
  if (!labels.length) {
    el.parentElement.innerHTML = '<p class="muted empty-chart">No data yet — scan something!</p>';
    return;
  }
  new Chart(el, {
    type,
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: type === 'bar' ? 6 : 0, borderWidth: 0, maxBarThickness: 56 }] },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: type === 'doughnut', position: 'bottom' } },
      scales: type === 'bar' ? { y: { beginAtZero: true, ticks: { precision: 0 } } } : {},
    },
  });
}

async function load() {
  try {
    const { mine, community, category_labels } = await api('/api/stats');
    setText('k-level', mine.eco_level.name);
    setText('k-next', mine.eco_level.next_at ? `${mine.eco_level.next_at - mine.points} pts to next level` : 'Top level!');
    setText('k-points', mine.points);
    setText('k-items', mine.items);
    setText('k-recyclable', `${mine.recyclable_items} recyclable`);
    setText('k-co2', mine.co2_saved_kg);
    setText('cm-scans', community.scans);
    setText('cm-items', community.items);
    setText('cm-co2', community.co2_saved_kg);

    const cats = Object.keys(mine.by_category);
    chart('c-category', 'doughnut', cats.map(c => category_labels[c] || c), cats.map(c => mine.by_category[c]), PALETTE);
    const bins = Object.keys(mine.by_bin);
    const binColors = { 'Recycle': '#2563eb', 'Drop-off point': '#d97706', 'General waste': '#6b7280' };
    chart('c-bin', 'doughnut', bins, bins.map(b => mine.by_bin[b]), bins.map(b => binColors[b] || '#16a34a'));
    const days = Object.keys(mine.daily);
    chart('c-daily', 'bar', days, days.map(d => mine.daily[d]), '#16a34a');
  } catch (e) {
    setText('k-level', '—');
  }

  const box = document.getElementById('history');
  try {
    const { scans } = await api('/api/history');
    if (!scans.length) {
      box.innerHTML = '<div class="card"><p>No scans yet. <a href="/scan">Scan your first waste item →</a></p></div>';
      return;
    }
    box.innerHTML = scans.map(s => `
      <a class="card history-item" href="/scan/${encodeURIComponent(s.id)}">
        <img src="${esc(s.thumbnail)}" alt="">
        <div>
          <strong>${s.total_items} item${s.total_items === 1 ? '' : 's'} · <span class="lvl-text-${esc(s.level)}">${esc(s.level)}</span>${s.demo ? ' · demo' : ''}</strong>
          <p class="muted small">${esc(s.summary)}</p>
          <span class="muted small">${formatDate(s.created_at)} · +${s.points} pts · ${s.co2_saved_kg} kg CO₂</span>
        </div>
      </a>`).join('');
  } catch (e) {
    box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

load();
