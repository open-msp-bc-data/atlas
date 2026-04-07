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
  ReferenceLine,
  ReferenceDot,
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

// Key MSP policy milestones for chart annotations
const POLICY_EVENTS = [
  { year_short: '20/21', label: 'COVID-19', color: '#DC2626' },
  { year_short: '22/23', label: 'LFP launched', color: '#7C3AED' },
];

const POLICY_LEGEND = (
  <p className="chart-stat-note" style={{ marginTop: 6 }}>
    Dashed lines mark key events:{' '}
    <span style={{ color: '#DC2626', fontWeight: 600 }}>COVID-19</span> (pandemic impact, 2020) and{' '}
    <span style={{ color: '#7C3AED', fontWeight: 600 }}>LFP</span> (Longitudinal Family Physician payment model, Feb 2023).
  </p>
);

export default function BillingTrends() {
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState('trends');
  const [selectedYear, setSelectedYear] = useState(null);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}trends.json`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        if (!selectedYear) setSelectedYear('all');
      })
      .catch(() => setData(null));
  }, []);

  if (!data) return null;

  const tabs = [
    { key: 'trends', label: 'Spending Trends' },
    { key: 'inequality', label: 'Inequality' },
    { key: 'turnover', label: 'Workforce Turnover' },
    { key: 'distribution', label: 'Distribution' },
    { key: 'methodology', label: 'Methodology' },
  ];

  return (
    <div className="billing-trends">
      <div className="billing-trends-header">
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
          <h3 style={{ margin: 0 }}>Blue Book Analysis</h3>
          <select
            value={selectedYear || 'all'}
            onChange={(e) => setSelectedYear(e.target.value)}
            style={{
              padding: '3px 8px', border: '1px solid var(--border-strong)',
              borderRadius: 0, fontFamily: 'var(--font-body)', fontSize: '0.82rem',
            }}
          >
            <option value="all">All Years</option>
            {data.years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <p className="data-panel-caption" style={{ marginTop: 4 }}>
          {selectedYear === 'all'
            ? `${data.n_fiscal_years} fiscal years of MSP fee-for-service data (${data.years[0]} to ${data.years[data.years.length - 1]}). ${data.total_unique_practitioners.toLocaleString()} unique practitioners across all years.`
            : (() => {
                const bt = data.billing_trends.find((t) => t.year === selectedYear);
                return bt
                  ? `Fiscal year ${selectedYear}. ${bt.n_practitioners.toLocaleString()} practitioners billed above the reporting threshold.`
                  : `Fiscal year ${selectedYear}.`;
              })()
          }
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
        {activeTab === 'inequality' && <InequalityPanel data={data} selectedYear={selectedYear} />}
        {activeTab === 'turnover' && <TurnoverPanel data={data} />}
        {activeTab === 'distribution' && <DistributionPanel data={data} selectedYear={selectedYear} />}
        {activeTab === 'methodology' && <MethodologyPanel data={data} />}
      </div>
    </div>
  );
}

function SpendingTrends({ data }) {
  const [showReal, setShowReal] = useState(true);

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
        {POLICY_LEGEND}
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
            {POLICY_EVENTS.map((e) => (
              <ReferenceLine key={e.label} x={e.year_short} stroke={e.color} strokeDasharray="4 3" label={{ value: e.label, position: 'top', fontSize: 10, fill: e.color }} />
            ))}
            <Line type="monotone" dataKey="total_b" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Median Gross Billing per Physician {showReal ? '(Real)' : '(Nominal)'}</h4>
        <p className="chart-stat-note">
          The midpoint billing — half of practitioners billed more, half billed less.
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={trends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v) => `$${v}k`} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => [`$${v.toFixed(0)}k`, 'Median']} />
            {POLICY_EVENTS.map((e) => (
              <ReferenceLine key={e.label} x={e.year_short} stroke={e.color} strokeDasharray="4 3" label={{ value: e.label, position: 'top', fontSize: 10, fill: e.color }} />
            ))}
            <Bar dataKey="median_k" fill={ACCENT_LIGHT} radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Practitioner Count</h4>
        <p className="chart-stat-note">
          Number of practitioners billing above the ~$25K Blue Book reporting threshold each year.
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={trends}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => v.toLocaleString()} />
            <Tooltip formatter={(v) => [v.toLocaleString(), 'Practitioners']} />
            {POLICY_EVENTS.map((e) => (
              <ReferenceLine key={e.label} x={e.year_short} stroke={e.color} strokeDasharray="4 3" label={{ value: e.label, position: 'top', fontSize: 10, fill: e.color }} />
            ))}
            <Bar dataKey="n_practitioners" fill="#6B7280" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function InequalityPanel({ data, selectedYear }) {
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
            <YAxis domain={[0, 'auto']} tick={{ fontSize: 12 }} tickFormatter={(v) => v.toFixed(2)} />
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
        <p className="chart-stat-note">
          Shows how concentrated gross MSP billings are among top earners.
          "Lifetime" sums all years a practitioner billed; "Normalized" divides by
          active years to control for career length. A classic 80/20 pattern means
          20% of practitioners receive 80% of total billings.
        </p>
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
          <p className="chart-stat-note">
            Share of total gross MSP billings captured by the top 10% of practitioners each year.
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={paretoYearly}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 'auto']} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => [`${v}%`, 'Top 10% share']} />
              <Line type="monotone" dataKey="top_10_pct" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="chart-card">
        {(() => {
          const effectiveYear = selectedYear === 'all' ? data.inequality[data.inequality.length - 1].year : selectedYear;
          const yearData = data.inequality.find((d) => d.year === effectiveYear) || data.inequality[data.inequality.length - 1];
          const bt = data.billing_trends.find((t) => t.year === effectiveYear);
          const nPractitioners = bt ? bt.n_practitioners : null;
          const pctData = [
            { label: 'Bottom 10%', value: yearData.p10 / 1000 },
            { label: 'Lower 25%', value: yearData.p25 / 1000 },
            { label: 'Median', value: yearData.p50 / 1000 },
            { label: 'Upper 25%', value: yearData.p75 / 1000 },
            { label: 'Top 10%', value: yearData.p90 / 1000 },
            { label: 'Top 1%', value: yearData.p99 / 1000 },
          ];
          return (
            <>
              <h4>Gross Billing Percentiles ({effectiveYear}{nPractitioners ? `, n=${nPractitioners.toLocaleString()}` : ''})</h4>
              <p className="chart-stat-note">
                Where practitioners fall in the billing distribution. "Middle 50%" earns
                between the 25th and 75th percentile.{selectedYear === 'all' ? ' Showing latest year — select a specific year above to compare.' : ''}
              </p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={pctData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                  <YAxis tickFormatter={(v) => `$${v}k`} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v) => [`$${v.toFixed(0)}k`, 'Gross Billing']} />
                  <Bar dataKey="value" radius={0}>
                    {pctData.map((_, i) => (
                      <Cell key={i} fill={DATA_COLORS[i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </>
          );
        })()}
      </div>
    </div>
  );
}

function TurnoverPanel({ data }) {
  // Skip the first year — all practitioners appear as "new entrants" since
  // there is no prior year to compare against, which distorts the chart.
  const turnover = data.turnover.slice(1).map((t) => ({
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
          The Blue Book only lists practitioners billing above ~$25K/year.
          "New" means a practitioner appeared above this threshold for the first time.
          "Exits" means they dropped below it (retired, moved, reduced hours, or shifted
          to non-fee-for-service models). "Returnees" re-appeared after a gap year.
          These are <strong>billing threshold crossings</strong>, not career starts/ends.
          The first year ({data.turnover[0]?.year}) is excluded as all {data.turnover[0]?.total.toLocaleString()} practitioners
          appear as "new" with no prior year for comparison.
        </p>
        {POLICY_LEGEND}
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={turnover}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {POLICY_EVENTS.map((e) => (
              <ReferenceLine key={e.label} x={e.year_short} stroke={e.color} strokeDasharray="4 3" label={{ value: e.label, position: 'top', fontSize: 10, fill: e.color }} />
            ))}
            <Bar dataKey="new_entrants" fill={SUCCESS} name="New (threshold)" radius={0} />
            <Bar dataKey="returnees" fill={INFO} name="Returnees" radius={0} />
            <Bar dataKey="exits" fill={ACCENT} name="Exits (threshold)" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Retention Rate</h4>
        <p className="chart-stat-note">
          Percentage of practitioners from the prior year who remain above the billing threshold.
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={turnover.filter((t) => t.retention_pct != null)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_short" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
            <Tooltip formatter={(v) => [`${v}%`, 'Retention']} />
            <Line type="monotone" dataKey="retention_pct" stroke={SUCCESS} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
        <p className="chart-stat-note" style={{ marginTop: 4 }}>
          Notable drops: <strong>2014–15</strong> (87.6% — 1,266 exits; coincides with MSP fee schedule
          restructuring) and <strong>2022–23</strong> (87.8% — 1,521 exits; post-pandemic
          workforce shifts and transition to new payment models like LFP).
        </p>
      </div>

      {yoy.length > 0 && (
        <div className="chart-card">
          <h4>Year-over-Year Gross Billing Change</h4>
          <p className="chart-stat-note">
            Median change per practitioner. Bars show median; whiskers show IQR
            (25th–75th percentile range).
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={yoy}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year_short" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(v, name) => {
                  if (name === 'Median') return [`${v.toFixed(1)}%`, name];
                  return [`${v.toFixed(1)}%`, name];
                }}
                labelFormatter={(l) => {
                  const item = yoy.find((y) => y.year_short === l);
                  if (!item) return l;
                  return `${item.from_year} → ${item.to_year} (n=${item.n_matched.toLocaleString()})\nQ1: ${item.q1}% | Median: ${item.median_yoy}% | Q3: ${item.q3}%\nIQR spread: ${item.iqr}pp`;
                }}
              />
              <ReferenceLine y={0} stroke="#999" strokeDasharray="3 3" />
              <Bar dataKey="median_yoy" fill={INFO} name="Median" radius={0} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
            <table style={{ width: '100%', fontSize: '0.78rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={{ textAlign: 'left', padding: '3px 6px', fontWeight: 600 }}>Period</th>
                  <th style={{ textAlign: 'right', padding: '3px 6px', fontWeight: 600 }}>Q1</th>
                  <th style={{ textAlign: 'right', padding: '3px 6px', fontWeight: 600 }}>Median</th>
                  <th style={{ textAlign: 'right', padding: '3px 6px', fontWeight: 600 }}>Q3</th>
                  <th style={{ textAlign: 'right', padding: '3px 6px', fontWeight: 600 }}>IQR</th>
                </tr>
              </thead>
              <tbody>
                {yoy.slice(-3).map((y) => (
                  <tr key={y.to_year} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '3px 6px' }}>{y.year_short}</td>
                    <td style={{ textAlign: 'right', padding: '3px 6px' }}>{y.q1}%</td>
                    <td style={{ textAlign: 'right', padding: '3px 6px', fontWeight: 600 }}>{y.median_yoy}%</td>
                    <td style={{ textAlign: 'right', padding: '3px 6px' }}>{y.q3}%</td>
                    <td style={{ textAlign: 'right', padding: '3px 6px' }}>{y.iqr}pp</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function DistributionPanel({ data, selectedYear }) {
  const effectiveYear = selectedYear === 'all' ? data.income_brackets.year : selectedYear;
  const yearBrackets = data.income_brackets_by_year?.[effectiveYear];
  const brackets = yearBrackets || data.income_brackets.brackets;
  const year = effectiveYear;

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
        <h4>Gross Billing Distribution ({year})</h4>
        <p className="chart-stat-note">
          Number of practitioners by gross MSP fee-for-service billing bracket.
          These are gross billings before overhead, staff costs, and expenses.
        </p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={brackets}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => [v.toLocaleString(), 'Practitioners']} />
            <Bar dataKey="count" fill={ACCENT_LIGHT} name="Practitioners" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h4>Billing Share by Bracket ({year})</h4>
        <p className="chart-stat-note">
          Share of total gross MSP billings captured by each bracket.
        </p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={brackets}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => [`${v}%`, '% of Total Gross Billings']} />
            <Bar dataKey="pct_of_billing" fill={ACCENT} name="% of Billing" radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {drift.length > 0 && (
        <div className="chart-card">
          <h4>Practitioner vs Organization Billings</h4>
          <p className="chart-stat-note">
            The Blue Book separates individual practitioner billings (fee-for-service)
            from organization billings (clinics, labs, diagnostic facilities billing
            under a group number). Organization share grew from{' '}
            {drift.length > 0 ? `${drift[0].practitioner_share_pct}%/${(100 - drift[0].practitioner_share_pct).toFixed(1)}%` : ''}{' '}
            to{' '}
            {drift.length > 0 ? `${drift[drift.length - 1].practitioner_share_pct}%/${(100 - drift[drift.length - 1].practitioner_share_pct).toFixed(1)}%` : ''}{' '}
            as more services shifted to group billing models.
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={drift} stackOffset="none">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year_short" tick={{ fontSize: 10 }} />
              <YAxis tickFormatter={(v) => `$${v.toFixed(1)}B`} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => [`$${v.toFixed(2)}B`]} />
              <Legend />
              {POLICY_EVENTS.map((e) => (
                <ReferenceLine key={e.label} x={e.year_short} stroke={e.color} strokeDasharray="4 3" label={{ value: e.label, position: 'top', fontSize: 10, fill: e.color }} />
              ))}
              <Bar dataKey="prac_b" stackId="a" fill={ACCENT_LIGHT} name="Practitioners" radius={0} />
              <Bar dataKey="org_b" stackId="a" fill="#6B7280" name="Organizations" radius={0} />
            </BarChart>
          </ResponsiveContainer>
          {POLICY_LEGEND}
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
