import { useState, useEffect, useCallback } from 'react';
import PhysicianMap from './components/PhysicianMap';
import FilterPanel from './components/FilterPanel';
import DataPanel from './components/DataPanel';
import TrendPanel from './components/TrendPanel';
import { fetchPhysicians, fetchAggregations, fetchHeatmap } from './api';
import './App.css';

const YEARS = [
  '2011-2012', '2013-2014', '2014-2015', '2016-2017', '2017-2018',
  '2018-2019', '2019-2020', '2020-2021', '2021-2022', '2022-2023', '2023-2024',
];

// Specialty color map (must match PhysicianMap.jsx)
const SPECIALTY_COLORS = {
  'General Practice': '#1B7340',
  'Internal Medicine': '#2563EB',
  Surgery: '#C4122F',
  Pediatrics: '#B45309',
  Psychiatry: '#7C3AED',
  'Emergency Medicine': '#DC2626',
  Anesthesiology: '#0891B2',
  Radiology: '#6B7280',
  'Obstetrics & Gynecology': '#BE185D',
  Dermatology: '#92400E',
  Ophthalmology: '#1D4ED8',
  Neurology: '#0F766E',
  Pathology: '#4D7C0F',
  'Physical Medicine': '#A16207',
  'Other Specialty': '#9CA3AF',
};

// Billing gradient swatches for the legend
const BILLING_SWATCHES = [
  { color: '#FDE8E8', label: '< $100k' },
  { color: '#F5A3A3', label: '$100k–$200k' },
  { color: '#E86060', label: '$200k–$300k' },
  { color: '#C4122F', label: '$300k–$500k' },
  { color: '#5C0816', label: '$500k+' },
];

function InfoPanel({ open, onToggle }) {
  return (
    <div className="info-panel">
      <button
        type="button"
        className="info-panel-toggle"
        onClick={onToggle}
        aria-expanded={open}
      >
        How to Read This Map
        <span className="info-panel-chevron">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="info-panel-body">
          <p className="info-section-label">Specialty Colors</p>
          <div className="legend-list">
            {Object.entries(SPECIALTY_COLORS).map(([name, color]) => (
              <div key={name} className="legend-item">
                <span className="legend-dot" style={{ background: color }} />
                <span>{name}</span>
              </div>
            ))}
          </div>

          <p className="info-section-label" style={{ marginTop: '12px' }}>
            Billing Intensity (Unknown specialty)
          </p>
          <div className="legend-billing">
            {BILLING_SWATCHES.map((s) => (
              <div key={s.label} className="legend-item">
                <span className="legend-dot" style={{ background: s.color }} />
                <span>{s.label}</span>
              </div>
            ))}
          </div>

          <p className="info-note">Locations are approximate (±1.5 km)</p>
          <p className="info-note">Data from BC MSP Blue Book (public government data)</p>
        </div>
      )}
    </div>
  );
}

function App() {
  const [physicians, setPhysicians] = useState([]);
  const [aggregations, setAggregations] = useState([]);
  const [heatmapData, setHeatmapData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPhysician, setSelectedPhysician] = useState(null);
  const [infoOpen, setInfoOpen] = useState(false);

  // Filters — specialty/city/health_authority are now arrays (multi-select)
  const [filters, setFilters] = useState({
    specialty: [],        // array
    city: [],             // array
    health_authority: [], // array
    year: '2023-2024',
    fromYear: '2011-2012',
    toYear: '2023-2024',
    showHeatmap: false,
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch with no server-side specialty/city/ha filters (we filter client-side)
      const params = { limit: 500 };
      if (filters.year) params.year = filters.year;

      const [physData, aggData, heatData] = await Promise.all([
        fetchPhysicians(params),
        fetchAggregations({ fiscal_year: filters.year, geo_level: 'city' }),
        filters.showHeatmap ? fetchHeatmap({ year: filters.year }) : Promise.resolve([]),
      ]);

      setPhysicians(physData);
      setAggregations(aggData);
      setHeatmapData(heatData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filters.year, filters.showHeatmap]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  // Derive filter options from full dataset (before client-side filtering)
  const specialties = [...new Set(physicians.map((p) => p.specialty_group).filter(Boolean))].sort();
  const cities = [...new Set(physicians.map((p) => p.city).filter(Boolean))].sort();
  const healthAuthorities = [
    ...new Set(physicians.map((p) => p.health_authority).filter(Boolean)),
  ].sort();

  // Client-side filter application
  const filteredPhysicians = physicians.filter((p) => {
    if (filters.specialty.length > 0 && !filters.specialty.includes(p.specialty_group)) return false;
    if (filters.city.length > 0 && !filters.city.includes(p.city)) return false;
    if (filters.health_authority.length > 0 && !filters.health_authority.includes(p.health_authority)) return false;
    return true;
  });

  return (
    <div className="app">
      <header className="app-header">
        <h1>MSP-BC Open Atlas<span className="accent-bar" /></h1>
        <p className="subtitle">
          Privacy-safe physician billing data for British Columbia
        </p>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <FilterPanel
            filters={filters}
            onFilterChange={updateFilter}
            specialties={specialties}
            cities={cities}
            healthAuthorities={healthAuthorities}
            years={YEARS}
          />

          <InfoPanel open={infoOpen} onToggle={() => setInfoOpen((v) => !v)} />

          <div className="sidebar-section">
            <h3>Summary</h3>
            <p>
              <strong>{filteredPhysicians.length}</strong> physicians displayed
            </p>
            <p>
              <strong>{aggregations.length}</strong> aggregated regions
            </p>
          </div>

          {selectedPhysician && (
            <TrendPanel
              pseudoId={selectedPhysician}
              onClose={() => setSelectedPhysician(null)}
            />
          )}

          <div className="sidebar-section privacy-notice">
            <h2 className="sidebar-heading">Privacy Notice</h2>
            <p>
              All data is anonymised. Locations are approximate (±1.5 km jitter).
              Physician names are replaced with pseudonymous IDs. Groups with fewer
              than 5 physicians are suppressed.
            </p>
          </div>
        </aside>

        <main className="main-content">
          {error && <div className="error-banner">Error: {error}</div>}
          {loading && <div className="loading-overlay">Loading data…</div>}

          <PhysicianMap
            physicians={filteredPhysicians}
            heatmapData={heatmapData}
            showHeatmap={filters.showHeatmap}
            onSelectPhysician={setSelectedPhysician}
          />

          <DataPanel aggregations={aggregations} year={filters.year} />
        </main>
      </div>

      <footer className="app-footer">
        <p>
          Data source:{' '}
          <a
            href="https://www2.gov.bc.ca/gov/content/health/practitioner-professional-resources/msp/publications"
            target="_blank"
            rel="noopener noreferrer"
          >
            BC MSP Blue Book
          </a>{' '}
          | Open Government Licence – British Columbia | All values are approximate
        </p>
      </footer>
    </div>
  );
}

export default App;
