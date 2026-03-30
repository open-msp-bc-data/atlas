import { useState, useEffect, useCallback } from 'react';
import PhysicianMap from './components/PhysicianMap';
import FilterPanel from './components/FilterPanel';
import AggregationCharts from './components/AggregationCharts';
import TrendPanel from './components/TrendPanel';
import { fetchPhysicians, fetchAggregations, fetchHeatmap } from './api';
import './App.css';

const YEARS = ['2021-2022', '2022-2023', '2023-2024'];

function App() {
  const [physicians, setPhysicians] = useState([]);
  const [aggregations, setAggregations] = useState([]);
  const [heatmapData, setHeatmapData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPhysician, setSelectedPhysician] = useState(null);

  // Filters
  const [filters, setFilters] = useState({
    specialty: '',
    city: '',
    health_authority: '',
    year: '2023-2024',
    showHeatmap: false,
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filters.specialty) params.specialty = filters.specialty;
      if (filters.city) params.city = filters.city;
      if (filters.health_authority) params.health_authority = filters.health_authority;
      if (filters.year) params.year = filters.year;

      const [physData, aggData, heatData] = await Promise.all([
        fetchPhysicians({ ...params, limit: 500 }),
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
  }, [filters]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  // Derive unique values for filter dropdowns
  const specialties = [...new Set(physicians.map((p) => p.specialty_group).filter(Boolean))].sort();
  const cities = [...new Set(physicians.map((p) => p.city).filter(Boolean))].sort();
  const healthAuthorities = [
    ...new Set(physicians.map((p) => p.health_authority).filter(Boolean)),
  ].sort();

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

          {selectedPhysician && (
            <TrendPanel
              pseudoId={selectedPhysician}
              onClose={() => setSelectedPhysician(null)}
            />
          )}

          <div className="sidebar-section">
            <h3>Summary</h3>
            <p>
              <strong>{physicians.length}</strong> physicians displayed
            </p>
            <p>
              <strong>{aggregations.length}</strong> aggregated regions
            </p>
          </div>

          <div className="sidebar-section privacy-notice">
            <h3>Privacy Notice</h3>
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
            physicians={physicians}
            heatmapData={heatmapData}
            showHeatmap={filters.showHeatmap}
            onSelectPhysician={setSelectedPhysician}
          />

          <AggregationCharts aggregations={aggregations} year={filters.year} />
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
