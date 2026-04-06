import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BillingTrends from '../components/BillingTrends';

const mockTrends = {
  generated: '2026-04-06',
  source: 'BC MSP Blue Book PDFs (2011-2024)',
  n_fiscal_years: 3,
  years: ['2021-2022', '2022-2023', '2023-2024'],
  total_unique_practitioners: 15000,
  billing_trends: [
    { year: '2021-2022', n_practitioners: 12500, total_billing: 3554000000, mean_billing: 284000, median_billing: 222000, max_billing: 3977000 },
    { year: '2022-2023', n_practitioners: 12020, total_billing: 3391000000, mean_billing: 282000, median_billing: 223000, max_billing: 4403000 },
    { year: '2023-2024', n_practitioners: 12496, total_billing: 4148000000, mean_billing: 332000, median_billing: 273000, max_billing: 5030000 },
  ],
  inequality: [
    { year: '2021-2022', gini: 0.447, p10: 50000, p25: 100000, p50: 222000, p75: 384000, p90: 578000, p99: 1230000 },
    { year: '2022-2023', gini: 0.440, p10: 53000, p25: 99000, p50: 223000, p75: 382000, p90: 562000, p99: 1194000 },
    { year: '2023-2024', gini: 0.435, p10: 57000, p25: 114000, p50: 273000, p75: 466000, p90: 660000, p99: 1313000 },
  ],
  turnover: [
    { year: '2021-2022', total: 12500, new_entrants: 991, exits: 792, retained: 11215, retention_pct: 93.4 },
    { year: '2022-2023', total: 12020, new_entrants: 825, exits: 1515, retained: 10985, retention_pct: 87.9 },
    { year: '2023-2024', total: 12496, new_entrants: 841, exits: 773, retained: 11247, retention_pct: 93.6 },
  ],
  income_brackets: {
    year: '2023-2024',
    brackets: [
      { label: 'Under $100K', count: 2690, pct_of_physicians: 21.5, total_billing: 35900000, pct_of_billing: 3.9 },
      { label: '$100K-$200K', count: 2314, pct_of_physicians: 18.5, total_billing: 335100000, pct_of_billing: 8.1 },
      { label: '$200K-$300K', count: 1702, pct_of_physicians: 13.6, total_billing: 425900000, pct_of_billing: 10.3 },
    ],
  },
  pareto: [
    { top_pct: 1, n_practitioners: 205, billing_share: 8.0 },
    { top_pct: 5, n_practitioners: 1029, billing_share: 24.3 },
    { top_pct: 10, n_practitioners: 2058, billing_share: 38.5 },
  ],
};

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(mockTrends) })
  );
});

describe('BillingTrends', () => {
  it('renders the component with heading', async () => {
    render(<BillingTrends />);
    await waitFor(() => {
      expect(screen.getByText('Blue Book Analysis')).toBeInTheDocument();
    });
  });

  it('shows fiscal year count and practitioner total', async () => {
    render(<BillingTrends />);
    await waitFor(() => {
      expect(screen.getByText(/3 fiscal years/)).toBeInTheDocument();
      expect(screen.getByText(/15,000 unique practitioners/)).toBeInTheDocument();
    });
  });

  it('renders all four tabs', async () => {
    render(<BillingTrends />);
    await waitFor(() => {
      expect(screen.getByText('Spending Trends')).toBeInTheDocument();
      expect(screen.getByText('Inequality')).toBeInTheDocument();
      expect(screen.getByText('Entrants & Exits')).toBeInTheDocument();
      expect(screen.getByText('Distribution')).toBeInTheDocument();
    });
  });

  it('defaults to Spending Trends tab', async () => {
    render(<BillingTrends />);
    await waitFor(() => {
      expect(screen.getByText('Total MSP Spending')).toBeInTheDocument();
    });
  });

  it('switches to Inequality tab on click', async () => {
    render(<BillingTrends />);
    await waitFor(() => screen.getByText('Inequality'));
    fireEvent.click(screen.getByText('Inequality'));
    expect(screen.getByText('Gini Coefficient Over Time')).toBeInTheDocument();
  });

  it('switches to Entrants & Exits tab on click', async () => {
    render(<BillingTrends />);
    await waitFor(() => screen.getByText('Entrants & Exits'));
    fireEvent.click(screen.getByText('Entrants & Exits'));
    expect(screen.getByText('Practitioner Turnover')).toBeInTheDocument();
  });

  it('switches to Distribution tab on click', async () => {
    render(<BillingTrends />);
    await waitFor(() => screen.getByText('Distribution'));
    fireEvent.click(screen.getByText('Distribution'));
    expect(screen.getByText(/Income Distribution/)).toBeInTheDocument();
  });

  it('shows Pareto table in Inequality tab', async () => {
    render(<BillingTrends />);
    await waitFor(() => screen.getByText('Inequality'));
    fireEvent.click(screen.getByText('Inequality'));
    expect(screen.getByText('Pareto Distribution (All Years)')).toBeInTheDocument();
    expect(screen.getByText('Pareto Distribution (All Years)')).toBeInTheDocument();
    // Pareto data renders in table cells
    expect(screen.getByText('205')).toBeInTheDocument();
  });

  it('renders nothing when fetch fails', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('fail')));
    const { container } = render(<BillingTrends />);
    await waitFor(() => {
      expect(container.querySelector('.billing-trends')).toBeNull();
    });
  });
});
