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
  Legend,
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
const INFO = '#2563EB';
const SUCCESS = '#1B7340';
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
    { key: 'methodology', label: 'Methodology' },
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
        {activeTab === 'methodology' && <MethodologyPanel data={data} />}
      </div>
    </div>
  );
}

function SpendingTrends({ data }) {
  const [showReal, setShowReal] = useState(false);

  const trends = data.billing_trends.map((t) => ({
    ...t,
    year_short: formatShortYear(t.year),
    total_b: (showReal ? t.total_billing_real : t.total_billing) / 1e9,
    median_k: (showReal ? t.median_billing_real : t.median_billing) / 1e3,
  }));

  const cagrLabel = showReal ? data.cagr_real_pct : data.cagr_nominal_pct;

  return (
    <div className="trends-panel-grid">
      <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
        <label className="filter-toggle" style={{ fontSize: '0.85rem' }}>
          <input type="checkbox" checked={showReal} onChange={(e) => setShowReal(e.target.checked)} />
          Adjust for inflation (constant {data.cpi_base_year} dollars)
        </label>
      </div>

      <div className="chart-card">
        <h4>Total MSP Spending {showReal ? '(Real)' : '(Nominal)'}</h4>
        <p className="chart-stat">
          {formatCurrency(trends[0][showReal ? 'total_billing_real' : 'total_billing'])}
          {' to '}
          {formatCurrency(trends[trends.length - 1][showReal ? 'total_billing_real' : 'total_billing'])}
          <span className="chart-stat-note"> ({cagrLabel}% CAGR)</span>
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={trends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => `$${v.toFixed(1)}B`} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => [`$${v.toFixed(2)}B`, 'Total']} />
            <Line type="monotone" dataKey="total_b" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Median Billing per Physician {showReal ? '(Real)' : '(Nominal)'}</h4>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={trends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => `$${v}k`} tick={{ fontSize: 12 }} />
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
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => v.toLocaleString()} />
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

  const bt = data.gini_bootstrap_test;
  const pareto = data.pareto_lifetime;
  const paretoNorm = data.pareto_normalized;

  // Per-year Pareto for top 10%
  const paretoYearly = (data.pareto_per_year || []).map((p) => ({
    ...p,
    year_short: formatShortYear(p.year),
  }));

  return (
    <div className="trends-panel-grid">
      <div className="chart-card">
        <h4>Gini Coefficient Over Time</h4>
        <p className="chart-stat-note">
          Higher = more unequal. {bt && bt.significant
            ? `Change from ${bt.gini_first} to ${bt.gini_last} is statistically significant (p < 0.05, bootstrap 95% CI).`
            : bt ? `Change from ${bt.gini_first} to ${bt.gini_last} is not statistically significant.` : ''}
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={giniData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis domain={[0.38, 0.46]} tick={{ fontSize: 12 }} tickFormatter={(v) => v.toFixed(2)} />
            <Tooltip formatter={(v) => [v.toFixed(4), 'Gini']} />
            <Line type="monotone" dataKey="gini" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
        {bt && (
          <p className="chart-stat-note" style={{ marginTop: 4 }}>
            {bt.first_year}: {bt.gini_first} [{bt.ci_95_first[0]}, {bt.ci_95_first[1]}] ...
            {bt.last_year}: {bt.gini_last} [{bt.ci_95_last[0]}, {bt.ci_95_last[1]}]
          </p>
        )}
      </div>

      <div className="chart-card">
        <h4>Pareto Distribution</h4>
        <p className="chart-stat-note">Lifetime totals vs. normalized (per year of activity)</p>
        <div className="pareto-table">
          <table className="data-table">
            <thead>
              <tr>
                <th className="data-th">Top %</th>
                <th className="data-th data-th-num">Lifetime %</th>
                <th className="data-th data-th-num">Normalized %</th>
              </tr>
            </thead>
            <tbody>
              {pareto.map((p, i) => (
                <tr key={p.top_pct} className="data-row">
                  <td className="data-td">{p.top_pct}%</td>
                  <td className="data-td data-td-num" style={{ fontWeight: 600 }}>{p.billing_share}%</td>
                  <td className="data-td data-td-num">{paretoNorm[i]?.billing_share}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {paretoYearly.length > 0 && (
        <div className="chart-card">
          <h4>Top 10% Billing Share Over Time</h4>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={paretoYearly}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
              <YAxis domain={[30, 45]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => [`${v}%`, 'Top 10% share']} />
              <Line type="monotone" dataKey="top_10_pct" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

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
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => `$${v}k`} tick={{ fontSize: 12 }} />
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

  // YoY stats with IQR
  const yoy = (data.yoy_stats || []).map((s) => ({
    ...s,
    year_short: formatShortYear(s.to_year),
  }));

  return (
    <div className="trends-panel-grid">
      <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
        <h4>Practitioner Turnover</h4>
        <p className="chart-stat-note">
          "New entrants" crossed the $25K reporting threshold. "Exits" dropped below it.
          This is not the same as starting or stopping practice.
        </p>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={turnover}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="new_entrants" fill={SUCCESS} name="New Entrants" radius={0} />
            <Bar dataKey="returnees" fill={INFO} name="Returnees" radius={0} />
            <Bar dataKey="exits" fill={ACCENT} name="Exits" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Retention Rate</h4>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={turnover.filter((t) => t.retention_pct != null)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis domain={[80, 100]} tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
            <Tooltip formatter={(v) => [`${v}%`, 'Retention']} />
            <Line type="monotone" dataKey="retention_pct" stroke={SUCCESS} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {yoy.length > 0 && (
        <div className="chart-card">
          <h4>Year-over-Year Billing Change</h4>
          <p className="chart-stat-note">Median change with IQR (Q1 to Q3)</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={yoy}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(v, name) => [`${v.toFixed(1)}%`, name === 'median_yoy' ? 'Median' : name]}
                labelFormatter={(l) => {
                  const item = yoy.find((y) => y.year_short === l);
                  return item ? `${item.from_year} to ${item.to_year} (n=${item.n_matched.toLocaleString()})` : l;
                }}
              />
              <Bar dataKey="median_yoy" fill={INFO} name="median_yoy" radius={0} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
            {yoy.length > 0 && (() => {
              const last = yoy[yoy.length - 1];
              return `Latest: median ${last.median_yoy}%, IQR [${last.q1}%, ${last.q3}%], spread ${last.iqr}pp`;
            })()}
          </div>
        </div>
      )}
    </div>
  );
}

function DistributionPanel({ data }) {
  const { year, brackets } = data.income_brackets;

  // Section drift data
  const drift = (data.section_drift || []).map((d) => ({
    ...d,
    year_short: formatShortYear(d.year),
    prac_b: d.practitioner_total / 1e9,
    org_b: d.organization_total / 1e9,
  }));

  return (
    <div className="trends-panel-grid">
      <div className="chart-card">
        <h4>Income Distribution ({year})</h4>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={brackets}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => [v.toLocaleString(), 'Physicians']} />
            <Bar dataKey="count" fill={ACCENT_LIGHT} name="Physicians" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Billing Share by Bracket ({year})</h4>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={brackets}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => [`${v}%`, '% of Total']} />
            <Bar dataKey="pct_of_billing" fill={ACCENT} name="% of Billing" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {drift.length > 0 && (
        <div className="chart-card">
          <h4>Practitioner vs Organization Billings</h4>
          <p className="chart-stat-note">
            Organization payments grew faster, reflecting methodology changes and payment model shifts.
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={drift} stackOffset="none">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year_short" tick={{ fontSize: 10 }} />
              <YAxis tickFormatter={(v) => `$${v.toFixed(1)}B`} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => [`$${v.toFixed(2)}B`]} />
              <Legend />
              <Bar dataKey="prac_b" stackId="a" fill={ACCENT_LIGHT} name="Practitioners" radius={0} />
              <Bar dataKey="org_b" stackId="a" fill="#6B7280" name="Organizations" radius={0} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function MethodologyPanel({ data }) {
  const m = data.methodology || {};
  const caveats = data.caveats || [];

  return (
    <div className="trends-panel-grid">
      <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
        <h4>Data Caveats</h4>
        <ul style={{ fontSize: '0.85rem', lineHeight: 1.6, paddingLeft: '1.2em' }}>
          {caveats.map((c, i) => (
            <li key={i} style={{ marginBottom: 8 }}>{c}</li>
          ))}
        </ul>
      </div>
      <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
        <h4>Statistical Methodology</h4>
        <div className="stats-grid">
          {Object.entries(m).map(([key, val]) => (
            <div key={key} className="stat-row">
              <span className="stat-label">{key.replace(/_/g, ' ')}</span>
              <span className="stat-value">{val}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
