import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FilterPanel from '../components/FilterPanel';

const defaultProps = {
  filters: {
    specialty: [],
    city: [],
    health_authority: [],
    year: '2023-2024',
    fromYear: '2011-2012',
    toYear: '2023-2024',
    showHeatmap: false,
  },
  onFilterChange: vi.fn(),
  specialties: ['General Practice', 'Surgery', 'Psychiatry'],
  cities: ['Vancouver', 'Victoria', 'Kelowna'],
  healthAuthorities: ['Fraser Health', 'Vancouver Coastal Health'],
  years: ['2021-2022', '2022-2023', '2023-2024'],
};

describe('FilterPanel', () => {
  it('renders all filter sections', () => {
    render(<FilterPanel {...defaultProps} />);
    expect(screen.getByText('Filters')).toBeInTheDocument();
    expect(screen.getByText(/Fiscal Year Range/i)).toBeInTheDocument();
    expect(screen.getByText(/Specialty Group/i)).toBeInTheDocument();
    expect(screen.getByText(/City/i)).toBeInTheDocument();
    expect(screen.getByText(/Health Authority/i)).toBeInTheDocument();
  });

  it('renders year range dropdowns with all years', () => {
    render(<FilterPanel {...defaultProps} />);
    const selects = screen.getAllByRole('combobox');
    // FROM and TO year dropdowns
    expect(selects.length).toBeGreaterThanOrEqual(2);
  });

  it('calls onFilterChange when TO year changes', () => {
    const onChange = vi.fn();
    render(<FilterPanel {...defaultProps} onFilterChange={onChange} />);
    const selects = screen.getAllByRole('combobox');
    // TO year is the second select
    fireEvent.change(selects[1], { target: { value: '2022-2023' } });
    expect(onChange).toHaveBeenCalled();
  });

  it('renders heatmap toggle checkbox', () => {
    render(<FilterPanel {...defaultProps} />);
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).not.toBeChecked();
  });

  it('calls onFilterChange when heatmap is toggled', () => {
    const onChange = vi.fn();
    render(<FilterPanel {...defaultProps} onFilterChange={onChange} />);
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith('showHeatmap', true);
  });
});
