// Anonymous per-browser id so each visitor sees their own history (no login needed).
function getClientId() {
  let id = null;
  try { id = localStorage.getItem('ecoscan-client-id'); } catch (e) {}
  if (!id) {
    id = (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2, 12));
    try { localStorage.setItem('ecoscan-client-id', id); } catch (e) {}
  }
  return id;
}

async function api(url, options = {}) {
  const headers = Object.assign({ 'X-Client-Id': getClientId() }, options.headers || {});
  const res = await fetch(url, Object.assign({}, options, { headers }));
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function formatDate(iso) {
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); }
  catch (e) { return iso; }
}
