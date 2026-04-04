import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DataPanel from '../components/DataPanel';

const mockAggregations = [
  { geo_name: 'Vancouver', n_physicians: 500, total_payments: 150000000, median_payments: 300000, pct_change_yoy: 0.05, suppressed: false },
  { geo_name: 'Kelowna', n_physicians: 200, total_payments: 50000000, median_payments: 250000, pct_change_yoy: -0.03, suppressed: false },
  { geo_name: 'Victoria', n_physicians: 300, total_payments: 80000000, median_payments: 266000, pct_change_yoy: 0.12, suppressed: false },
];

describe('DataPanel', () => {
  it('renders nothing when aggregations is empty', () => {
    const { container } = render(<DataPanel aggregations={[]} year="2023-2024" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a table with all regions', () => {
    render(<DataPanel aggregations={mockAggregations} year="2023-2024" />);
    expect(screen.getByText('Vancouver')).toBeInTheDocument();
    expect(screen.getByText('Kelowna')).toBeInTheDocument();
    expect(screen.getByText('Victoria')).toBeInTheDocument();
  });

  it('shows region count in caption', () => {
    render(<DataPanel aggregations={mockAggregations} year="2023-2024" />);
    expect(screen.getByText(/3 regions/i)).toBeInTheDocument();
  });

  it('sorts by total billing descending by default', () => {
    render(<DataPanel aggregations={mockAggregations} year="2023-2024" />);
    const rows = screen.getAllByRole('row');
    // First data row (after header) should be Vancouver (highest total)
    expect(rows[1]).toHaveTextContent('Vancouver');
  });

  it('toggles sort direction when clicking a column header', () => {
    render(<DataPanel aggregations={mockAggregations} year="2023-2024" />);
    const regionHeader = screen.getByText('Region');
    fireEvent.click(regionHeader);
    // First click on a new column sorts descending
    // V > V > K alphabetically descending
    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Victoria');
    // Click again to toggle to ascending
    fireEvent.click(regionHeader);
    const rows2 = screen.getAllByRole('row');
    expect(rows2[1]).toHaveTextContent('Kelowna');
  });

  it('filters out suppressed aggregations', () => {
    const withSuppressed = [
      ...mockAggregations,
      { geo_name: 'SmallTown', n_physicians: 2, total_payments: 0, suppressed: true },
    ];
    render(<DataPanel aggregations={withSuppressed} year="2023-2024" />);
    expect(screen.queryByText('SmallTown')).not.toBeInTheDocument();
  });

  it('formats currency values correctly', () => {
    render(<DataPanel aggregations={mockAggregations} year="2023-2024" />);
    // Vancouver total is $150M
    expect(screen.getByText('$150.0M')).toBeInTheDocument();
    // Kelowna total is $50M
    expect(screen.getByText('$50.0M')).toBeInTheDocument();
  });
});
