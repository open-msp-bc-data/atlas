import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { fetchTrend } from '../api';

/**
 * Parse a billing_range string like "200k–250k" into its midpoint value in thousands.
 * Returns null if the string cannot be parsed.
 */
function parseBillingMidpoint(rangeStr) {
  if (!rangeStr) return null;
  // Normalize all Unicode dash variants (en-dash, em-dash, etc.) to a standard hyphen
  const normalized = rangeStr.replace(/[\u2013\u2014\u2015\u2212]/g, '-');
  const match = normalized.match(/(\d+)k\s*-\s*(\d+)k/);
  if (!match) return null;
  const low = parseInt(match[1], 10);
  const high = parseInt(match[2], 10);
  return (low + high) / 2;
}

export default function TrendPanel({ pseudoId, onClose }) {
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!pseudoId) return;
    setLoading(true);
    setError(null);
    setTrend(null);
    fetchTrend(pseudoId)
      .then(setTrend)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [pseudoId]);

  if (!pseudoId) return null;

  // Transform trend data to include a numeric midpoint for charting
  const chartData =
    trend?.data?.map((d) => ({
      year: d.year,
      billing_range: d.billing_range,
      midpoint: parseBillingMidpoint(d.billing_range),
    })) || [];

  return (
    <div className="trend-panel">
      <h3>
        📈 Trend: {pseudoId}
        <button className="close-btn" onClick={onClose} aria-label="Close trend panel">
          ✕
        </button>
      </h3>

      {loading && <p>Loading trend data…</p>}
      {error && <p style={{ color: '#d93025' }}>Error: {error}</p>}

      {trend && chartData.length > 0 && (
        <>
          <p style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem' }}>
            Specialty: {trend.specialty_group || 'Unknown'}
          </p>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year" tick={{ fontSize: 10 }} />
              <YAxis
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => `${v}k`}
                label={{ value: '$ (thousands)', angle: -90, position: 'insideLeft', fontSize: 9 }}
              />
              <Tooltip
                formatter={(value, name, props) => [
                  props.payload.billing_range || (value != null ? `${value}k` : 'N/A'),
                  'Billing',
                ]}
              />
              <Bar dataKey="midpoint" fill="#1a73e8" radius={[4, 4, 0, 0]} name="Billing" />
            </BarChart>
          </ResponsiveContainer>

          <div style={{ fontSize: '0.8rem', marginTop: '0.5rem' }}>
            {chartData.map((d) => (
              <div key={d.year}>
                <strong>{d.year}:</strong> {d.billing_range || 'Suppressed'}
              </div>
            ))}
          </div>
        </>
      )}

      {trend && chartData.length === 0 && (
        <p style={{ fontSize: '0.85rem', color: '#666' }}>No trend data available.</p>
      )}
    </div>
  );
}
