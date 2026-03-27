const API_BASE = '';

export async function fetchPhysicians(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`${API_BASE}/physicians?${qs}`);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function fetchAggregations(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`${API_BASE}/aggregations?${qs}`);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function fetchHeatmap(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`${API_BASE}/heatmap?${qs}`);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function fetchTrend(pseudoId) {
  const resp = await fetch(`${API_BASE}/trends/${pseudoId}`);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}
