import { useState } from 'react';

function formatCurrency(value) {
  if (value == null) return '\u2014';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

const COLUMNS = [
  { key: 'rank',          label: '#',                   sortKey: 'rank',          numeric: true  },
  { key: 'geo_name',      label: 'Region',              sortKey: 'geo_name',      numeric: false },
  { key: 'n_physicians',  label: 'Physicians',          sortKey: 'n_physicians',  numeric: true  },
  { key: 'avg_billing',   label: 'Avg Billing/Physician', sortKey: 'avg_billing', numeric: true  },
  { key: 'total_payments', label: 'Total Billing',      sortKey: 'total_payments', numeric: true  },
];

export default function PerCapitaTable({ aggregations, year }) {
  const [sortKey, setSortKey] = useState('avg_billing');
  const [sortDir, setSortDir] = useState('desc');

  if (!aggregations || aggregations.length === 0) return null;

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  const rows = aggregations
    .filter((a) => !a.suppressed && a.n_physicians > 0)
    .map((a) => ({
      ...a,
      avg_billing: a.total_payments / a.n_physicians,
    }))
    .sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === 'asc' ? av - bv : bv - av;
    })
    .map((a, i) => ({ ...a, rank: i + 1 }));

  function sortIndicator(key) {
    if (sortKey !== key) return <span className="sort-indicator sort-inactive">{'\u2195'}</span>;
    return (
      <span className="sort-indicator sort-active">
        {sortDir === 'asc' ? '\u2191' : '\u2193'}
      </span>
    );
  }

  return (
    <div className="data-panel">
      <div className="data-panel-header">
        <h3>Per-Physician Billing</h3>
        <p className="data-panel-caption">
          Average billing per physician by region for fiscal year {year}.
          Normalizes for population size so small and large regions can be compared fairly.
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
                <td className="data-td data-td-num">{row.n_physicians?.toLocaleString() ?? '\u2014'}</td>
                <td className="data-td data-td-num" style={{ fontWeight: 600 }}>{formatCurrency(row.avg_billing)}</td>
                <td className="data-td data-td-num">{formatCurrency(row.total_payments)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
