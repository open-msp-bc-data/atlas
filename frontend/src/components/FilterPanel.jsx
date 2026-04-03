import { useState, useRef, useEffect } from 'react';

// ── MultiSelect ─────────────────────────────────────────────────────────────
// A searchable multi-select with tag chips. No external dependencies.
function MultiSelect({ id, label, options, selected, onChange, placeholder }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const filtered = options.filter((opt) =>
    opt.toLowerCase().includes(search.toLowerCase())
  );

  function toggle(value) {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  }

  function removeTag(value, e) {
    e.stopPropagation();
    onChange(selected.filter((v) => v !== value));
  }

  return (
    <div className="filter-group" ref={containerRef}>
      <label htmlFor={id}>{label}</label>

      {/* Selected tags */}
      {selected.length > 0 && (
        <div className="multiselect-tags">
          {selected.map((v) => (
            <span key={v} className="multiselect-tag">
              {v}
              <button
                type="button"
                className="multiselect-tag-remove"
                onClick={(e) => removeTag(v, e)}
                aria-label={`Remove ${v}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search input that opens dropdown */}
      <input
        id={id}
        type="text"
        className="multiselect-input"
        placeholder={selected.length === 0 ? placeholder || `All — click to filter` : `Add more…`}
        value={search}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setSearch(e.target.value);
          setOpen(true);
        }}
        autoComplete="off"
      />

      {/* Dropdown */}
      {open && (
        <div className="multiselect-dropdown">
          {filtered.length === 0 && (
            <div className="multiselect-empty">No matches</div>
          )}
          {filtered.map((opt) => (
            <label key={opt} className="multiselect-option">
              <input
                type="checkbox"
                checked={selected.includes(opt)}
                onChange={() => toggle(opt)}
              />
              <span>{opt}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ── FilterPanel ──────────────────────────────────────────────────────────────
export default function FilterPanel({
  filters,
  onFilterChange,
  specialties,
  cities,
  healthAuthorities,
  years,
}) {
  // Year range: fromYear / toYear stored separately in filters
  const fromYear = filters.fromYear || years[0] || '';
  const toYear = filters.toYear || years[years.length - 1] || '';

  function handleFromYear(e) {
    const val = e.target.value;
    onFilterChange('fromYear', val);
    // If toYear is now before fromYear, push toYear forward
    if (toYear && val && years.indexOf(val) > years.indexOf(toYear)) {
      onFilterChange('toYear', val);
    }
    // Pass toYear (or fromYear if toYear unset) as the active `year`
    const active = toYear && years.indexOf(toYear) >= years.indexOf(val) ? toYear : val;
    onFilterChange('year', active);
  }

  function handleToYear(e) {
    const val = e.target.value;
    onFilterChange('toYear', val);
    onFilterChange('year', val);
  }

  return (
    <div className="filter-panel">
      <h3>Filters</h3>

      {/* Year range */}
      <div className="filter-group">
        <label>Fiscal Year Range</label>
        <div className="year-range-row">
          <div className="year-range-col">
            <span className="year-range-label">From</span>
            <select value={fromYear} onChange={handleFromYear}>
              {years.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="year-range-col">
            <span className="year-range-label">To</span>
            <select value={toYear} onChange={handleToYear}>
              {years
                .filter((y) => !fromYear || years.indexOf(y) >= years.indexOf(fromYear))
                .map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
            </select>
          </div>
        </div>
        <p className="year-range-note">Showing data for {toYear}</p>
      </div>

      <MultiSelect
        id="specialty-select"
        label="Specialty Group"
        options={specialties}
        selected={filters.specialty}
        onChange={(val) => onFilterChange('specialty', val)}
        placeholder="All Specialties"
      />

      <MultiSelect
        id="city-select"
        label="City"
        options={cities}
        selected={filters.city}
        onChange={(val) => onFilterChange('city', val)}
        placeholder="All Cities"
      />

      <MultiSelect
        id="ha-select"
        label="Health Authority"
        options={healthAuthorities}
        selected={filters.health_authority}
        onChange={(val) => onFilterChange('health_authority', val)}
        placeholder="All Health Authorities"
      />

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
