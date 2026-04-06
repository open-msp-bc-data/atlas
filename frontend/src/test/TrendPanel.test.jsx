import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import TrendPanel from '../components/TrendPanel';

const mockTrend = {
  pseudo_id: 'PHY-ABC123',
  specialty_group: 'General Practice',
  data: [
    { year: '2022-2023', billing_range: '220k\u2013230k' },
    { year: '2023-2024', billing_range: '270k\u2013280k' },
  ],
};

beforeEach(() => {
  vi.resetModules();
});

vi.mock('../api', () => ({
  fetchTrend: vi.fn(() => Promise.resolve(mockTrend)),
}));

describe('TrendPanel', () => {
  it('renders nothing when pseudoId is null', () => {
    const { container } = render(<TrendPanel pseudoId={null} onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the pseudo ID in the heading', async () => {
    render(<TrendPanel pseudoId="PHY-ABC123" onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/PHY-ABC123/)).toBeInTheDocument();
    });
  });

  it('renders close button', async () => {
    render(<TrendPanel pseudoId="PHY-ABC123" onClose={() => {}} />);
    expect(screen.getByLabelText('Close trend panel')).toBeInTheDocument();
  });

  it('shows specialty group', async () => {
    render(<TrendPanel pseudoId="PHY-ABC123" onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/General Practice/)).toBeInTheDocument();
    });
  });

  it('shows billing ranges for each year', async () => {
    render(<TrendPanel pseudoId="PHY-ABC123" onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/2022-2023/)).toBeInTheDocument();
      expect(screen.getByText(/2023-2024/)).toBeInTheDocument();
    });
  });
});
