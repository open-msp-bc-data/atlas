import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchPhysicians, fetchAggregations, fetchHeatmap, fetchTrend } from '../api';

beforeEach(() => {
  vi.restoreAllMocks();
});

function mockFetch(data, ok = true, status = 200) {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(data),
    })
  );
}

describe('fetchPhysicians', () => {
  it('returns array of physicians', async () => {
    mockFetch([{ pseudo_id: 'PHY-ABC' }]);
    const result = await fetchPhysicians({ year: '2023-2024' });
    expect(result).toEqual([{ pseudo_id: 'PHY-ABC' }]);
    expect(fetch).toHaveBeenCalledWith('/physicians?year=2023-2024');
  });

  it('returns empty array for suppression response', async () => {
    mockFetch({ suppressed: true, reason: 'query_k_anonymity' });
    const result = await fetchPhysicians({ city: 'SmallTown' });
    expect(result).toEqual([]);
  });

  it('throws on non-array non-suppression response', async () => {
    mockFetch({ unexpected: true });
    await expect(fetchPhysicians()).rejects.toThrow('Unexpected response format');
  });

  it('throws on HTTP error', async () => {
    mockFetch(null, false, 500);
    await expect(fetchPhysicians()).rejects.toThrow('API error: 500');
  });
});

describe('fetchAggregations', () => {
  it('returns aggregation data', async () => {
    mockFetch([{ geo_name: 'Vancouver', total_payments: 1000000 }]);
    const result = await fetchAggregations({ fiscal_year: '2023-2024' });
    expect(result).toEqual([{ geo_name: 'Vancouver', total_payments: 1000000 }]);
  });

  it('throws on HTTP error', async () => {
    mockFetch(null, false, 404);
    await expect(fetchAggregations()).rejects.toThrow('API error: 404');
  });
});

describe('fetchHeatmap', () => {
  it('returns heatmap cells', async () => {
    mockFetch([{ lat: 49.28, lng: -123.12, intensity: 5000 }]);
    const result = await fetchHeatmap({ year: '2023-2024' });
    expect(result[0].lat).toBe(49.28);
  });

  it('throws on HTTP error', async () => {
    mockFetch(null, false, 422);
    await expect(fetchHeatmap({ year: 'invalid' })).rejects.toThrow('API error: 422');
  });
});

describe('fetchTrend', () => {
  it('returns trend data for a physician', async () => {
    mockFetch({ pseudo_id: 'PHY-ABC', data: [{ year: '2023-2024', billing_range: '200k-210k' }] });
    const result = await fetchTrend('PHY-ABC');
    expect(result.pseudo_id).toBe('PHY-ABC');
    expect(result.data).toHaveLength(1);
  });

  it('throws on 404 for unknown physician', async () => {
    mockFetch(null, false, 404);
    await expect(fetchTrend('PHY-UNKNOWN')).rejects.toThrow('API error: 404');
  });
});
