import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BillingTrends from '../components/BillingTrends';

const mockTrends = {
  generated: '2026-04-06',
  source: 'BC MSP Blue Book PDFs (2011-2024)',
  n_fiscal_years: 3,
  years: ['2021-2022', '2022-2023', '2023-2024'],
  total_unique_practitioners: 15000,
  cagr_nominal_pct: 4.6,
  cagr_real_pct: 2.1,
  cpi_base_year: '2023-2024',
  billing_trends: [
    { year: '2021-2022', n_practitioners: 12500, total_billing: 3554000000, total_billing_real: 3830000000, mean_billing: 284000, mean_billing_real: 306000, median_billing: 222000, median_billing_real: 239000, max_billing: 3977000 },
    { year: '2022-2023', n_practitioners: 12020, total_billing: 3391000000, total_billing_real: 3490000000, mean_billing: 282000, mean_billing_real: 290000, median_billing: 223000, median_billing_real: 229000, max_billing: 4403000 },
    { year: '2023-2024', n_practitioners: 12496, total_billing: 4148000000, total_billing_real: 4148000000, mean_billing: 332000, mean_billing_real: 332000, median_billing: 273000, median_billing_real: 273000, max_billing: 5030000 },
  ],
  inequality: [
    { year: '2021-2022', gini: 0.447, p10: 50000, p25: 100000, p50: 222000, p75: 384000, p90: 578000, p99: 1230000 },
    { year: '2022-2023', gini: 0.440, p10: 53000, p25: 99000, p50: 223000, p75: 382000, p90: 562000, p99: 1194000 },
    { year: '2023-2024', gini: 0.435, p10: 57000, p25: 114000, p50: 273000, p75: 466000, p90: 660000, p99: 1313000 },
  ],
  gini_bootstrap_test: {
    first_year: '2021-2022', last_year: '2023-2024',
    gini_first: 0.447, gini_last: 0.435,
    ci_95_first: [0.440, 0.454], ci_95_last: [0.429, 0.441],
    significant: true,
  },
  turnover: [
    { year: '2021-2022', total: 12500, new_entrants: 991, exits: 792, retained: 11215, retention_pct: 93.4 },
    { year: '2022-2023', total: 12020, new_entrants: 825, exits: 1515, retained: 10985, retention_pct: 87.9 },
    { year: '2023-2024', total: 12496, new_entrants: 841, exits: 773, retained: 11247, retention_pct: 93.6 },
  ],
  yoy_stats: [
    { from_year: '2021-2022', to_year: '2022-2023', n_matched: 10985, median_yoy: -3.4, mean_yoy: 4.1, q1: -15.2, q3: 12.1, iqr: 27.3 },
    { from_year: '2022-2023', to_year: '2023-2024', n_matched: 11247, median_yoy: 17.1, mean_yoy: 34.7, q1: 5.2, q3: 30.8, iqr: 25.6 },
  ],
  income_brackets: {
    year: '2023-2024',
    brackets: [
      { label: 'Under $100K', count: 2690, pct_of_physicians: 21.5, total_billing: 35900000, pct_of_billing: 3.9 },
      { label: '$100K-$200K', count: 2314, pct_of_physicians: 18.5, total_billing: 335100000, pct_of_billing: 8.1 },
      { label: '$200K-$300K', count: 1702, pct_of_physicians: 13.6, total_billing: 425900000, pct_of_billing: 10.3 },
    ],
  },
  pareto_lifetime: [
    { top_pct: 1, n_practitioners: 205, billing_share: 8.0 },
    { top_pct: 5, n_practitioners: 1029, billing_share: 24.3 },
    { top_pct: 10, n_practitioners: 2058, billing_share: 38.5 },
  ],
  pareto_normalized: [
    { top_pct: 1, n_practitioners: 205, billing_share: 7.5 },
    { top_pct: 5, n_practitioners: 1029, billing_share: 23.1 },
    { top_pct: 10, n_practitioners: 2058, billing_share: 37.0 },
  ],
  pareto_per_year: [
    { year: '2021-2022', top_1_pct: 8.2, top_5_pct: 25.0, top_10_pct: 39.5, top_20_pct: 60.0 },
    { year: '2022-2023', top_1_pct: 8.5, top_5_pct: 25.5, top_10_pct: 39.8, top_20_pct: 60.2 },
    { year: '2023-2024', top_1_pct: 8.0, top_5_pct: 24.3, top_10_pct: 38.5, top_20_pct: 59.0 },
  ],
  section_drift: [
    { year: '2021-2022', practitioner_total: 3554000000, organization_total: 267000000, combined_total: 3821000000, practitioner_share_pct: 93.0, n_orgs: 178 },
    { year: '2022-2023', practitioner_total: 3391000000, organization_total: 565000000, combined_total: 3956000000, practitioner_share_pct: 85.7, n_orgs: 326 },
    { year: '2023-2024', practitioner_total: 4148000000, organization_total: 615000000, combined_total: 4763000000, practitioner_share_pct: 87.1, n_orgs: 358 },
  ],
  caveats: ['All amounts are gross billings.', 'Only practitioners billing $25,000+ are listed.'],
  methodology: { percentiles: 'Linear interpolation', gini: 'Bootstrap 95% CI' },
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
      expect(screen.getByText(/Total MSP Spending/)).toBeInTheDocument();
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
    expect(screen.getByText('Pareto Distribution')).toBeInTheDocument();
    expect(screen.getByText('Gini Coefficient Over Time')).toBeInTheDocument();
  });

  it('shows methodology tab with caveats', async () => {
    render(<BillingTrends />);
    await waitFor(() => screen.getByText('Methodology'));
    fireEvent.click(screen.getByText('Methodology'));
    expect(screen.getByText('Data Caveats')).toBeInTheDocument();
    expect(screen.getByText('Statistical Methodology')).toBeInTheDocument();
  });

  it('renders nothing when fetch fails', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('fail')));
    const { container } = render(<BillingTrends />);
    await waitFor(() => {
      expect(container.querySelector('.billing-trends')).toBeNull();
    });
  });
});
