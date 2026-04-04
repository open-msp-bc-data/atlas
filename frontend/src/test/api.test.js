import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockData = {
  physicians: [
    {
      pseudo_id: 'PHY-ABC', specialty_group: 'General Practice',
      lat_approx: 49.28, lng_approx: -123.12, city: 'Vancouver',
      health_authority: 'Vancouver Coastal Health',
      latest_billing_range: '230k\u2013240k', yoy_change: 0.05,
      billing_years: [
        { year: '2023-2024', billing_range: '230k\u2013240k' },
        { year: '2022-2023', billing_range: '220k\u2013230k' },
      ],
    },
    {
      pseudo_id: 'PHY-DEF', specialty_group: 'Surgery',
      lat_approx: 49.88, lng_approx: -119.50, city: 'Kelowna',
      health_authority: 'Interior Health',
      latest_billing_range: '500k\u2013510k', yoy_change: -0.02,
      billing_years: [{ year: '2023-2024', billing_range: '500k\u2013510k' }],
    },
  ],
  aggregations: {
    '2023-2024': [{ geo_name: 'Vancouver', n_physicians: 500, total_payments: 150000000 }],
  },
  years: ['2022-2023', '2023-2024'],
};

beforeEach(() => {
  vi.resetModules();
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(JSON.stringify(mockData))) })
  );
});

describe('fetchPhysicians', () => {
  it('returns physicians from static data', async () => {
    const { fetchPhysicians } = await import('../api');
    const result = await fetchPhysicians({});
    expect(result).toHaveLength(2);
    expect(result[0].pseudo_id).toBe('PHY-ABC');
  });

  it('filters by year', async () => {
    const { fetchPhysicians } = await import('../api');
    const result = await fetchPhysicians({ year: '2022-2023' });
    expect(result).toHaveLength(1);
    expect(result[0].pseudo_id).toBe('PHY-ABC');
  });

  it('respects limit', async () => {
    const { fetchPhysicians } = await import('../api');
    const result = await fetchPhysicians({ limit: 1 });
    expect(result).toHaveLength(1);
  });
});

describe('fetchAggregations', () => {
  it('returns aggregations for a year', async () => {
    const { fetchAggregations } = await import('../api');
    const result = await fetchAggregations({ fiscal_year: '2023-2024' });
    expect(result).toHaveLength(1);
    expect(result[0].geo_name).toBe('Vancouver');
  });

  it('returns empty for unknown year', async () => {
    const { fetchAggregations } = await import('../api');
    const result = await fetchAggregations({ fiscal_year: '1999-2000' });
    expect(result).toEqual([]);
  });
});

describe('fetchHeatmap', () => {
  it('returns empty in static mode', async () => {
    const { fetchHeatmap } = await import('../api');
    expect(await fetchHeatmap()).toEqual([]);
  });
});

describe('fetchTrend', () => {
  it('returns trend for known physician', async () => {
    const { fetchTrend } = await import('../api');
    const result = await fetchTrend('PHY-ABC');
    expect(result.pseudo_id).toBe('PHY-ABC');
    expect(result.data).toHaveLength(2);
  });

  it('throws for unknown physician', async () => {
    const { fetchTrend } = await import('../api');
    await expect(fetchTrend('PHY-UNKNOWN')).rejects.toThrow('Physician not found');
  });
});
