import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

function formatCurrency(value) {
  if (value == null) return 'N/A';
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

function formatShortYear(year) {
  if (!year) return '';
  const parts = year.split('-');
  return `${parts[0].slice(2)}/${parts[1].slice(2)}`;
}

const ACCENT = '#C4122F';
const ACCENT_LIGHT = '#E86060';
const DATA_COLORS = ['#FDE8E8', '#F5A3A3', '#E86060', '#C4122F', '#8B0D21', '#5C0816'];

export default function BillingTrends() {
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState('trends');

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}trends.json`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null));
  }, []);

  if (!data) return null;

  const tabs = [
    { key: 'trends', label: 'Spending Trends' },
    { key: 'inequality', label: 'Inequality' },
    { key: 'turnover', label: 'Entrants & Exits' },
    { key: 'distribution', label: 'Distribution' },
  ];

  return (
    <div className="billing-trends">
      <div className="billing-trends-header">
        <h3>Blue Book Analysis</h3>
        <p className="data-panel-caption">
          {data.n_fiscal_years} fiscal years of MSP fee-for-service data
          ({data.years[0]} to {data.years[data.years.length - 1]}).
          {' '}{data.total_unique_practitioners.toLocaleString()} unique practitioners.
        </p>
      </div>

      <div className="trends-tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`trends-tab ${activeTab === t.key ? 'trends-tab-active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="trends-content">
        {activeTab === 'trends' && <SpendingTrends data={data} />}
        {activeTab === 'inequality' && <InequalityPanel data={data} />}
        {activeTab === 'turnover' && <TurnoverPanel data={data} />}
        {activeTab === 'distribution' && <DistributionPanel data={data} />}
      </div>
    </div>
  );
}

function SpendingTrends({ data }) {
  const trends = data.billing_trends.map((t) => ({
    ...t,
    year_short: formatShortYear(t.year),
    total_b: t.total_billing / 1e9,
    median_k: t.median_billing / 1e3,
  }));

  const first = trends[0];
  const last = trends[trends.length - 1];
  const n_years = parseInt(last.year.split('-')[0]) - parseInt(first.year.split('-')[0]);
  const cagr = n_years > 0 ? ((last.total_billing / first.total_billing) ** (1 / n_years) - 1) * 100 : 0;

  return (
    <div className="trends-panel-grid">
      <div className="chart-card">
        <h4>Total MSP Spending</h4>
        <p className="chart-stat">
          {formatCurrency(first.total_billing)} to {formatCurrency(last.total_billing)}
          <span className="chart-stat-note"> ({cagr.toFixed(1)}% CAGR)</span>
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={trends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => `$${v.toFixed(1)}B`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [`$${v.toFixed(2)}B`, 'Total']} />
            <Line type="monotone" dataKey="total_b" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Median Billing per Physician</h4>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={trends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => `$${v}k`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [`$${v.toFixed(0)}k`, 'Median']} />
            <Bar dataKey="median_k" fill={ACCENT_LIGHT} radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Practitioner Count</h4>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={trends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
            <Tooltip formatter={(v) => [v.toLocaleString(), 'Practitioners']} />
            <Bar dataKey="n_practitioners" fill="#6B7280" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function InequalityPanel({ data }) {
  const giniData = data.inequality.map((d) => ({
    ...d,
    year_short: formatShortYear(d.year),
  }));

  const pareto = data.pareto;

  return (
    <div className="trends-panel-grid">
      <div className="chart-card">
        <h4>Gini Coefficient Over Time</h4>
        <p className="chart-stat-note">Higher = more unequal (0 = perfect equality, 1 = one person gets all)</p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={giniData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
            <YAxis domain={[0.35, 0.50]} tick={{ fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} />
            <Tooltip formatter={(v) => [v.toFixed(3), 'Gini']} />
            <Line type="monotone" dataKey="gini" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Pareto Distribution (All Years)</h4>
        <p className="chart-stat-note">What share of total billing do the top X% of physicians account for?</p>
        <div className="pareto-table">
          <table className="data-table">
            <thead>
              <tr>
                <th className="data-th">Top %</th>
                <th className="data-th data-th-num">Practitioners</th>
                <th className="data-th data-th-num">% of Total Billing</th>
              </tr>
            </thead>
            <tbody>
              {pareto.map((p) => (
                <tr key={p.top_pct} className="data-row">
                  <td className="data-td">{p.top_pct}%</td>
                  <td className="data-td data-td-num">{p.n_practitioners.toLocaleString()}</td>
                  <td className="data-td data-td-num" style={{ fontWeight: 600 }}>{p.billing_share}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="chart-card">
        <h4>Percentile Ranges ({data.inequality[data.inequality.length - 1].year})</h4>
        {(() => {
          const latest = data.inequality[data.inequality.length - 1];
          const pctData = [
            { label: 'P10', value: latest.p10 / 1000 },
            { label: 'P25', value: latest.p25 / 1000 },
            { label: 'P50', value: latest.p50 / 1000 },
            { label: 'P75', value: latest.p75 / 1000 },
            { label: 'P90', value: latest.p90 / 1000 },
            { label: 'P99', value: latest.p99 / 1000 },
          ];
          return (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={pctData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `$${v}k`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`$${v.toFixed(0)}k`, 'Billing']} />
                <Bar dataKey="value" radius={0}>
                  {pctData.map((_, i) => (
                    <Cell key={i} fill={DATA_COLORS[i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          );
        })()}
      </div>
    </div>
  );
}

function TurnoverPanel({ data }) {
  const turnover = data.turnover.map((t) => ({
    ...t,
    year_short: formatShortYear(t.year),
  }));

  return (
    <div className="trends-panel-grid">
      <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
        <h4>Practitioner Turnover</h4>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={turnover}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="new_entrants" fill="#1B7340" name="New Entrants" radius={0} />
            <Bar dataKey="exits" fill={ACCENT} name="Exits" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Retention Rate</h4>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={turnover.filter((t) => t.retention_pct != null)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
            <YAxis domain={[80, 100]} tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
            <Tooltip formatter={(v) => [`${v}%`, 'Retention']} />
            <Line type="monotone" dataKey="retention_pct" stroke="#1B7340" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Total Practitioners</h4>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={turnover}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => v.toLocaleString()} />
            <Tooltip formatter={(v) => [v.toLocaleString(), 'Total']} />
            <Line type="monotone" dataKey="total" stroke="#2563EB" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function DistributionPanel({ data }) {
  const { year, brackets } = data.income_brackets;

  return (
    <div className="trends-panel-grid">
      <div className="chart-card">
        <h4>Income Distribution ({year})</h4>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={brackets}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v, name) => [name === 'count' ? v.toLocaleString() : `${v}%`, name === 'count' ? 'Physicians' : '% of Physicians']} />
            <Bar dataKey="count" fill={ACCENT_LIGHT} name="count" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Billing Share by Bracket ({year})</h4>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={brackets}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [`${v}%`, '% of Total Billing']} />
            <Bar dataKey="pct_of_billing" fill={ACCENT} name="pct_of_billing" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Key Stats</h4>
        <div className="stats-grid">
          {brackets.map((b) => (
            <div key={b.label} className="stat-row">
              <span className="stat-label">{b.label}</span>
              <span className="stat-value">{b.count.toLocaleString()} physicians ({b.pct_of_physicians}%)</span>
              <span className="stat-share">{b.pct_of_billing}% of billing</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
