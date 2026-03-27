export default function FilterPanel({
  filters,
  onFilterChange,
  specialties,
  cities,
  healthAuthorities,
  years,
}) {
  return (
    <div className="filter-panel">
      <h3>🔍 Filters</h3>

      <div className="filter-group">
        <label htmlFor="year-select">Fiscal Year</label>
        <select
          id="year-select"
          value={filters.year}
          onChange={(e) => onFilterChange('year', e.target.value)}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="specialty-select">Specialty Group</label>
        <select
          id="specialty-select"
          value={filters.specialty}
          onChange={(e) => onFilterChange('specialty', e.target.value)}
        >
          <option value="">All Specialties</option>
          {specialties.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="city-select">City</label>
        <select
          id="city-select"
          value={filters.city}
          onChange={(e) => onFilterChange('city', e.target.value)}
        >
          <option value="">All Cities</option>
          {cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="ha-select">Health Authority</label>
        <select
          id="ha-select"
          value={filters.health_authority}
          onChange={(e) => onFilterChange('health_authority', e.target.value)}
        >
          <option value="">All Health Authorities</option>
          {healthAuthorities.map((ha) => (
            <option key={ha} value={ha}>
              {ha}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label className="filter-toggle">
          <input
            type="checkbox"
            checked={filters.showHeatmap}
            onChange={(e) => onFilterChange('showHeatmap', e.target.checked)}
          />
          Show Billing Heatmap
        </label>
      </div>
    </div>
  );
}
