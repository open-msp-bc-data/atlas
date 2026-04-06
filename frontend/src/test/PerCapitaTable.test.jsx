import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PerCapitaTable from '../components/PerCapitaTable';

const mockAggregations = [
  { geo_name: 'Vancouver', n_physicians: 500, total_payments: 150000000, suppressed: false },
  { geo_name: 'Kelowna', n_physicians: 200, total_payments: 50000000, suppressed: false },
  { geo_name: 'Victoria', n_physicians: 300, total_payments: 90000000, suppressed: false },
];

describe('PerCapitaTable', () => {
  it('renders nothing when aggregations is empty', () => {
    const { container } = render(<PerCapitaTable aggregations={[]} year="2023-2024" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when aggregations is null', () => {
    const { container } = render(<PerCapitaTable aggregations={null} year="2023-2024" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders table with all regions', () => {
    render(<PerCapitaTable aggregations={mockAggregations} year="2023-2024" />);
    expect(screen.getByText('Vancouver')).toBeInTheDocument();
    expect(screen.getByText('Kelowna')).toBeInTheDocument();
    expect(screen.getByText('Victoria')).toBeInTheDocument();
  });

  it('shows per-physician billing heading', () => {
    render(<PerCapitaTable aggregations={mockAggregations} year="2023-2024" />);
    expect(screen.getByText('Per-Physician Billing')).toBeInTheDocument();
  });

  it('computes average billing per physician', () => {
    render(<PerCapitaTable aggregations={mockAggregations} year="2023-2024" />);
    // Kelowna: 50M / 200 = $250k (unique value in the table)
    expect(screen.getByText('$250k')).toBeInTheDocument();
  });

  it('sorts by average billing descending by default', () => {
    render(<PerCapitaTable aggregations={mockAggregations} year="2023-2024" />);
    const rows = screen.getAllByRole('row');
    // Victoria has highest avg (300k), then Kelowna (250k), then Vancouver (300k)
    // Actually Vancouver 150M/500=300k, Victoria 90M/300=300k, Kelowna 50M/200=250k
    // Tie between Vancouver and Victoria, Kelowna last
    expect(rows[rows.length - 1]).toHaveTextContent('Kelowna');
  });

  it('toggles sort direction on header click', () => {
    render(<PerCapitaTable aggregations={mockAggregations} year="2023-2024" />);
    const regionHeader = screen.getByText('Region');
    fireEvent.click(regionHeader);
    const rows = screen.getAllByRole('row');
    // Descending alphabetical: Victoria first
    expect(rows[1]).toHaveTextContent('Victoria');
  });

  it('filters out suppressed aggregations', () => {
    const withSuppressed = [
      ...mockAggregations,
      { geo_name: 'SmallTown', n_physicians: 2, total_payments: 0, suppressed: true },
    ];
    render(<PerCapitaTable aggregations={withSuppressed} year="2023-2024" />);
    expect(screen.queryByText('SmallTown')).not.toBeInTheDocument();
  });
});
