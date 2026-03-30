import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

const COLORS = [
  '#C4122F', '#8B0D21', '#E86060', '#1B7340', '#2563EB',
  '#B45309', '#5C0816', '#6B7280', '#F5A3A3', '#D1D1CC',
];

function formatCurrency(value) {
  if (value == null) return 'N/A';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

export default function AggregationCharts({ aggregations, year }) {
  if (!aggregations || aggregations.length === 0) {
    return null;
  }

  // Top regions by total billings
  const topRegions = [...aggregations]
    .filter((a) => a.total_payments != null && !a.suppressed)
    .sort((a, b) => (b.total_payments || 0) - (a.total_payments || 0))
    .slice(0, 10)
    .map((a) => ({
      name: a.geo_name,
      total: a.total_payments,
      physicians: a.n_physicians,
      median: a.median_payments,
    }));

  // Distribution by region for pie chart
  const totalAll = topRegions.reduce((s, r) => s + (r.total || 0), 0);
  const pieData = topRegions.slice(0, 6).map((r) => ({
    name: r.name,
    value: r.total,
    pct: totalAll > 0 ? ((r.total / totalAll) * 100).toFixed(1) : 0,
  }));

  return (
    <div className="charts-area">
      <h3>Regional Aggregations — {year}</h3>
      <div className="charts-grid">
        {/* Bar chart: Top regions by total billings */}
        <div className="chart-card">
          <h4>Top Regions by Total Billings</h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={topRegions} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tickFormatter={formatCurrency} />
              <YAxis type="category" dataKey="name" width={75} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => formatCurrency(v)} />
              <Bar dataKey="total" fill="#C4122F" radius={0} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie chart: Distribution */}
        <div className="chart-card">
          <h4>Billing Distribution</h4>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ name, pct }) => `${name} (${pct}%)`}
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => formatCurrency(v)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
