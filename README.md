# MSP-BC Open Atlas

Privacy-safe geospatial analysis of physician billing in British Columbia, using publicly available MSP Blue Book data.

![MSP-BC Open Atlas UI](https://github.com/user-attachments/assets/69d719e1-3c76-4913-9a65-f7e429847b30)

## Overview

MSP-BC Open Atlas is an end-to-end pipeline and web application that:

1. **Ingests** BC MSP Blue Book PDFs and CPSBC registrant directory data
2. **Geocodes** physician practice addresses to lat/lng coordinates
3. **Matches** payee names to registrants using fuzzy matching (RapidFuzz)
4. **Anonymises** data with deterministic hashing, location jitter, and k-anonymity
5. **Serves** privacy-safe aggregations via a FastAPI REST API
6. **Visualises** results on an interactive Leaflet map with filters and charts

## Privacy Model

All public-facing data is protected by multiple privacy layers:

| Mechanism | Description |
|-----------|-------------|
| **Pseudonymous IDs** | Physician names replaced with deterministic hashed IDs (e.g., `PHY-A1B2C3D4E5F6G7H8`) |
| **Location Jitter** | Coordinates offset by ±1.5 km random noise |
| **k-Anonymity** | Groups with fewer than 5 physicians are suppressed |
| **Query-level k-Anonymity** | Filter combinations returning fewer than 5 individuals return a suppression notice |
| **Heatmap Grid Cells** | Individual locations aggregated into ~5 km grid cells |
| **Dominance Suppression** | Groups where one contributor >=60% of total are suppressed |
| **Billing Ranges** | Exact values replaced with ranges (e.g., "200k-250k") |
| **Rate Limiting** | Trend endpoint rate-limited to prevent pseudo-ID enumeration |
| **Salt Validation** | App refuses to start with default placeholder salt |
| **Admin Separation** | Raw data only accessible via token-protected admin endpoint with constant-time comparison |

## Design

The frontend uses an editorial design system inspired by data journalism sites like ProPublica and The Markup. See [DESIGN.md](DESIGN.md) for the full specification.

- **Typography:** Instrument Serif (display), Source Sans 3 (body), JetBrains Mono (code)
- **Color:** Institutional red (#C4122F) accent with warm neutrals
- **Aesthetic:** Sharp edges, minimal decoration, typography-driven hierarchy

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React 19, Vite, Leaflet, Recharts
- **Pipeline**: pdfplumber, RapidFuzz, Nominatim geocoding
- **Privacy**: SHA-256 hashing, configurable k-anonymity, location jitter, rate limiting
- **Design**: Instrument Serif + Source Sans 3, editorial aesthetic

## Project Structure

```
bc_msp_map/
├── backend/
│   ├── app/                    # FastAPI application
│   │   ├── main.py             # App entry point (salt validation on startup)
│   │   ├── auth.py             # Shared admin token validation (hmac)
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── privacy.py          # Privacy module (hashing, jitter, k-anonymity)
│   │   ├── schemas.py          # Pydantic response schemas
│   │   ├── config.py           # YAML configuration loader
│   │   ├── database.py         # Database setup
│   │   └── routers/
│   │       ├── physicians.py   # /physicians, /heatmap, /trends endpoints
│   │       ├── aggregations.py # /aggregations endpoint
│   │       └── admin.py        # /admin/raw (protected) endpoint
│   ├── pipeline/               # ETL pipeline modules
│   │   ├── ingest_bluebook.py  # MSP Blue Book PDF parser (regex-based)
│   │   ├── ingest_cpsbc.py     # CPSBC directory scraper (stub)
│   │   ├── geocode.py          # Address geocoding + city centroids
│   │   ├── entity_resolution.py# Fuzzy name matching
│   │   ├── aggregate.py        # Aggregation with privacy enforcement
│   │   └── seed_data.py        # Demo data generator
│   ├── tests/                  # pytest test suite
│   ├── config.yaml             # Application configuration
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Main application
│   │   ├── App.css             # Design system CSS (tokens from DESIGN.md)
│   │   ├── api.js              # API client
│   │   └── components/
│   │       ├── PhysicianMap.jsx      # Leaflet map with clustering
│   │       ├── FilterPanel.jsx       # Filter controls
│   │       ├── AggregationCharts.jsx # Bar/pie charts
│   │       └── TrendPanel.jsx        # Per-physician YoY trends
│   ├── package.json
│   └── vite.config.js
├── DESIGN.md                   # Design system specification
├── ROADMAP.md                  # Development roadmap
├── TODOS.md                    # Tracked technical debt
└── specifications.md           # Detailed software specification
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export PRIVACY_SALT="your-long-random-secret-here"
export ADMIN_TOKEN="your-admin-token-at-least-16-chars"

# Generate demo data
python -m pipeline.seed_data

# Start API server
python -m uvicorn app.main:app --reload --port 8000
```

The app will refuse to start if `PRIVACY_SALT` is not set or is the default placeholder.

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies API to :8000)
npm run dev

# Or build for production
npm run build
```

When the frontend is built (`npm run build`), the backend automatically serves the static files from `frontend/dist/`.

### Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

## API Endpoints

### Public Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /physicians` | Anonymised physician records with approximate locations |
| `GET /aggregations` | Pre-computed regional aggregations (city/HA level) |
| `GET /heatmap` | Grid-cell aggregated billing intensity (cells with <5 physicians suppressed) |
| `GET /trends/{pseudo_id}` | Year-over-year billing trend for an anonymised physician (rate-limited) |
| `GET /health` | Health check |

### Query Parameters

- `specialty` - Filter by specialty group
- `city` - Filter by city
- `health_authority` - Filter by health authority
- `year` / `fiscal_year` - Filter by fiscal year
- `k_anonymity` - Set to `off` with admin token to bypass query-level k-anonymity
- `limit` / `offset` - Pagination

### Admin Endpoints (Token Required)

| Endpoint | Description |
|----------|-------------|
| `GET /admin/raw` | Raw physician records (requires `X-Admin-Token` header, minimum 16 characters) |

Admin token is validated using constant-time comparison (`hmac.compare_digest`).

## Configuration

Privacy and geocoding settings are in `backend/config.yaml`:

```yaml
privacy:
  k_min_unique_phys: 5          # Minimum group size for k-anonymity
  dominance_threshold: 0.60     # Suppress if one contributor >=60%
  location_jitter_km: 1.5       # Random coordinate offset (km)
  salt: "CHANGE_ME_IN_PRODUCTION"  # Placeholder - override via PRIVACY_SALT env var
```

The `salt` value in committed config is a placeholder. The app will not start with this default. Override it via `PRIVACY_SALT` environment variable in production.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `PRIVACY_SALT` | **Required.** Override the privacy salt for pseudo-ID generation. Must not be the default placeholder. |
| `ADMIN_TOKEN` | **Required** for admin API access. Must be at least 16 characters. |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins (default: `http://localhost:5173,http://localhost:4173`). |

## Data Sources

- **MSP Blue Book**: [BC MSP Publications](https://www2.gov.bc.ca/gov/content/health/practitioner-professional-resources/msp/publications)
- **CPSBC Directory**: [Registrant Directory](https://www.cpsbc.ca/public/registrant-directory)
- **Geographic Boundaries**: BC Health Authority regions mapped via city lookup tables

## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

Data published under the [Open Government Licence - British Columbia](https://www2.gov.bc.ca/gov/content/data/open-data/open-government-licence-bc).
