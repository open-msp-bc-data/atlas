import { useState } from 'react';

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

export default function DataPanel({ aggregations, year }) {
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

  const rows = aggregations
    .filter((a) => !a.suppressed)
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
          Showing {rows.length} regions — {totalPhysicians.toLocaleString()} physicians — {formatCurrency(totalBilling)} total.
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
