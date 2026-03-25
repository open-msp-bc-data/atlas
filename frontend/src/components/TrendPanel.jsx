import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { fetchTrend } from '../api';

export default function TrendPanel({ pseudoId, onClose }) {
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!pseudoId) return;
    setLoading(true);
    setError(null);
    fetchTrend(pseudoId)
      .then(setTrend)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [pseudoId]);

  if (!pseudoId) return null;

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

      {trend && trend.data && trend.data.length > 0 && (
        <>
          <p style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem' }}>
            Specialty: {trend.specialty_group || 'Unknown'}
          </p>
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={trend.data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="billing_range"
                stroke="#1a73e8"
                strokeWidth={2}
                dot={{ r: 4 }}
                name="Billing Range"
              />
            </LineChart>
          </ResponsiveContainer>

          <div style={{ fontSize: '0.8rem', marginTop: '0.5rem' }}>
            {trend.data.map((d) => (
              <div key={d.year}>
                <strong>{d.year}:</strong> {d.billing_range || 'Suppressed'}
              </div>
            ))}
          </div>
        </>
      )}

      {trend && (!trend.data || trend.data.length === 0) && (
        <p style={{ fontSize: '0.85rem', color: '#666' }}>No trend data available.</p>
      )}
    </div>
  );
}
