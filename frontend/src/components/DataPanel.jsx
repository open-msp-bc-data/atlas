import { useState, useMemo } from 'react';

// City centroids for viewport filtering (matches backend/pipeline/geocode.py)
const CITY_CENTROIDS = {
  'Vancouver': [49.2827, -123.1207], 'Victoria': [48.4284, -123.3656],
  'Surrey': [49.1913, -122.8490], 'Burnaby': [49.2488, -122.9805],
  'Richmond': [49.1666, -123.1336], 'Kelowna': [49.8880, -119.4960],
  'Kamloops': [50.6745, -120.3273], 'Nanaimo': [49.1659, -123.9401],
  'Prince George': [53.9171, -122.7497], 'Chilliwack': [49.1579, -121.9514],
  'Abbotsford': [49.0504, -122.3045], 'Langley': [49.1044, -122.6609],
  'Courtenay': [49.6878, -124.9936], 'Cranbrook': [49.5097, -115.7688],
  'Penticton': [49.4991, -119.5937], 'Vernon': [50.2671, -119.2720],
  'Campbell River': [50.0163, -125.2442], 'New Westminster': [49.2057, -122.9110],
  'North Vancouver': [49.3200, -123.0724], 'West Vancouver': [49.3280, -123.1607],
  'Coquitlam': [49.2838, -122.7932], 'Port Moody': [49.2783, -122.8602],
  'Maple Ridge': [49.2193, -122.5984], 'White Rock': [49.0253, -122.8026],
  'Trail': [49.0966, -117.7113], 'Nelson': [49.4928, -117.2948],
  'Terrace': [54.5162, -128.5969], 'Fort St John': [56.2465, -120.8476],
  'Dawson Creek': [55.7596, -120.2353], 'Williams Lake': [52.1417, -122.1417],
  'Quesnel': [52.9784, -122.4927], 'Powell River': [49.8352, -124.5247],
};

function isInBounds(geoName, bounds) {
  if (!bounds) return true;
  const coords = CITY_CENTROIDS[geoName];
  if (!coords) return true; // unknown city, show it
  const [lat, lng] = coords;
  return lat >= bounds.south && lat <= bounds.north && lng >= bounds.west && lng <= bounds.east;
}

function formatCurrency(value) {
  if (value == null) return '—';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

function formatYoY(value) {
  if (value == null) return '—';
  const pct = (value * 100).toFixed(1);
  if (value > 0) return `+${pct}%`;
  return `${pct}%`;
}

function yoyClass(value) {
  if (value == null) return '';
  if (value > 0.05) return 'yoy-up';
  if (value < -0.05) return 'yoy-down';
  return 'yoy-flat';
}

const COLUMNS = [
  { key: 'rank',        label: '#',              sortKey: 'rank',           numeric: true  },
  { key: 'geo_name',    label: 'Region',          sortKey: 'geo_name',       numeric: false },
  { key: 'n_physicians',label: 'Physicians',      sortKey: 'n_physicians',   numeric: true  },
  { key: 'total_payments',label: 'Total Billing', sortKey: 'total_payments', numeric: true  },
  { key: 'median_payments',label: 'Median Billing',sortKey:'median_payments', numeric: true  },
  { key: 'yoy_change',  label: 'YoY Change',      sortKey: 'yoy_change',     numeric: true  },
];

export default function DataPanel({ aggregations, year, mapBounds }) {
  const [sortKey, setSortKey] = useState('total_payments');
  const [sortDir, setSortDir] = useState('desc');

  if (!aggregations || aggregations.length === 0) {
    return null;
  }

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  const allRows = aggregations.filter((a) => !a.suppressed);
  const inView = mapBounds ? allRows.filter((a) => isInBounds(a.geo_name, mapBounds)) : allRows;
  const isFiltered = mapBounds && inView.length < allRows.length;

  const rows = inView
    .sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'string') {
        return sortDir === 'asc'
          ? av.localeCompare(bv)
          : bv.localeCompare(av);
      }
      return sortDir === 'asc' ? av - bv : bv - av;
    })
    .map((a, i) => ({ ...a, rank: i + 1 }));

  const totalPhysicians = rows.reduce((s, r) => s + (r.n_physicians || 0), 0);
  const totalBilling = rows.reduce((s, r) => s + (r.total_payments || 0), 0);

  function sortIndicator(key) {
    if (sortKey !== key) return <span className="sort-indicator sort-inactive">↕</span>;
    return (
      <span className="sort-indicator sort-active">
        {sortDir === 'asc' ? '↑' : '↓'}
      </span>
    );
  }

  return (
    <div className="data-panel">
      <div className="data-panel-header">
        <h3>Regional Aggregations</h3>
        <p className="data-panel-caption">
          Physician billing totals by city for fiscal year {year}.
          {isFiltered
            ? `Showing ${rows.length} of ${allRows.length} regions in view`
            : `Showing all ${rows.length} regions`}
          {' — '}{totalPhysicians.toLocaleString()} physicians — {formatCurrency(totalBilling)} total.
          Groups with fewer than 5 physicians are suppressed.
        </p>
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`data-th ${col.numeric ? 'data-th-num' : ''} ${sortKey === col.sortKey ? 'data-th-active' : ''}`}
                  onClick={() => handleSort(col.sortKey)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort(col.sortKey)}
                >
                  {col.label}
                  {sortIndicator(col.sortKey)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.geo_name} className="data-row">
                <td className="data-td data-td-num data-td-muted">{row.rank}</td>
                <td className="data-td data-td-name">{row.geo_name}</td>
                <td className="data-td data-td-num">{row.n_physicians?.toLocaleString() ?? '—'}</td>
                <td className="data-td data-td-num">{formatCurrency(row.total_payments)}</td>
                <td className="data-td data-td-num">{formatCurrency(row.median_payments)}</td>
                <td className={`data-td data-td-num ${yoyClass(row.yoy_change)}`}>
                  {formatYoY(row.yoy_change)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
