let _cache = null;

async function loadData() {
  if (_cache) return _cache;
  const resp = await fetch(`${import.meta.env.BASE_URL}data.json`);
  if (!resp.ok) throw new Error(`Failed to load data: ${resp.status}`);
  _cache = await resp.json();
  return _cache;
}

export async function fetchPhysicians(params = {}) {
  const data = await loadData();
  let physicians = data.physicians;

  // Client-side filtering
  if (params.year) {
    physicians = physicians.filter((p) =>
      p.billing_years?.some((b) => b.year === params.year)
    );
  }

  const limit = params.limit ? parseInt(params.limit, 10) : 500;
  return physicians.slice(0, limit);
}

export async function fetchAggregations(params = {}) {
  const data = await loadData();
  const year = params.fiscal_year || data.years[data.years.length - 1];
  return data.aggregations[year] || [];
}

export async function fetchHeatmap() {
  // Heatmap not available in static mode (needs server-side grid computation)
  return [];
}

export async function fetchTrend(pseudoId) {
  const data = await loadData();
  const phys = data.physicians.find((p) => p.pseudo_id === pseudoId);
  if (!phys) throw new Error('Physician not found');
  return {
    pseudo_id: phys.pseudo_id,
    specialty_group: phys.specialty_group,
    data: phys.billing_years || [],
  };
}

export async function getYears() {
  const data = await loadData();
  return data.years;
}
