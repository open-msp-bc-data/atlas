# MSP-BC Open Atlas — Software Specification (v0.1)

A fully open-source pipeline and web map that aggregates B.C. MSP payments into privacy-safe geographic and attribute groupings.

## 1) Goals & Non-Goals
### Goals
- Aggregate annual MSP gross payments into **k-anonymous** cells at **facility, city, and health authority** levels.
- Provide a public **web map + downloads API** with reproducible ETL.
- Enable rich filtering (specialty, training, geography, time) and **year-over-year** comparisons.
- Comply with **Open Government Licence – BC** and site ToS of upstream data providers; publish only aggregate, non-identifying data.

### Non-Goals
- No publication of per-physician values or re-identifiable small cells.
- No real-time updates; cadence is **annual** (optionally quarterly in future).
- No inference of physician income after expenses; values reflect gross payments reported.

## 2) System Architecture
- ETL: Python 3.11+, pandas/duckdb, geopandas/shapely, pdfplumber, rapidfuzz, pyogrio.
- Storage: GeoParquet on disk + DuckDB; optional PostGIS.
- API: FastAPI + Uvicorn, static CDN for tiles (tileserver-gl).
- Frontend: React + Vite + MapLibre GL; vector tiles via Tippecanoe.
- CI/CD: GitHub Actions (lint, tests, data build, release).
- Infra: GitHub Pages/Cloudflare Pages for web; object store for data (GitHub Releases or Cloudflare R2).

### Layered Architecture

| Layer | Purpose | Key Technologies | Outputs |
|-------|----------|------------------|----------|
| **Data Ingestion** | Collect raw MSP Blue Book PDFs/CSVs, CPSBC directory snapshots, and geographic boundaries. | `pdfplumber`, `pandas`, `duckdb`, `geopandas` | Cleaned staging tables (`payments_raw`, `cpsbc_practitioner`) |
| **Geocoding** | Standardize and geolocate addresses (city/facility/HA). | `Nominatim`, `Pelias`, `shapely`, `pyogrio` | Geo-coded address table (`geo_addresses`) |
| **Entity Resolution** | Match payee names to CPSBC registrants using deterministic + fuzzy methods. | `rapidfuzz`, custom matching rules | Unique `entity_key_hash` linking records |
| **Feature Store** | Integrate geocoded payments and physician attributes. | `duckdb`, `GeoParquet` | `payments_geo`, `physician_attributes` tables |
| **Aggregation & Privacy Enforcement** | Aggregate to safe cells, apply k-anonymity and dominance suppression. | `pandas`, `numpy`, custom privacy module | Aggregated data (`agg_facility`, `agg_city`, `agg_ha`) |
| **API Layer** | Serve processed data via REST endpoints. | `FastAPI`, `Uvicorn` | `/aggregates`, `/timeseries`, `/tiles` endpoints |
| **Web Visualization** | Provide interactive mapping and filtering interface. | `React`, `Vite`, `MapLibre GL`, `deck.gl`, `Tippecanoe` | Public web app and downloadable datasets |
| **CI/CD & Infrastructure** | Automate builds, testing, and releases. | GitHub Actions, Cloudflare Pages, R2 storage | Versioned artifacts, reproducible builds |

### Data Flow Diagram

       ┌──────────────────-──────┐
       │    Raw Data Sources     │
       │  (MSP Blue Book, CPSBC) │
       └────────────---──────────┘
                    ▼
         ┌──────────────────────┐
         │    Ingestion/ETL     │
         │ Clean + Normalize CSV│
         └────────────--────────┘
                    ▼
         ┌──────────────────────┐
         │     Geocoding        │
         │ lat/lon + facility ID│
         └────────────-─────────┘
                    ▼
         ┌─────────────────-─────┐
         │  Entity Resolution    │
         │  Match Names to CPSBC │
         └────────────-─────-────┘
                    ▼
         ┌─────────────────-─────┐
         │  Aggregation + K-Safe │
         │  Apply privacy filters│
         └────────────-────-─────┘
                    ▼
         ┌──────────────-────────┐
         │       API Layer       │
         │   (FastAPI + CDN)     │
         └────────────-───-──────┘
                    ▼
         ┌──────────────-────────┐
         │   Web Visualization   │
         │ React + MapLibre map  │
         └──────────────────-────┘

### Key Design Principles
1. Reproducibility: All transformations are scripted, version-controlled, and automated through CI.
2. Privacy by Design: Aggregation and suppression occur *before* publication; no personal identifiers leave the ETL boundary
3. Modularity: Each pipeline stage is an independent function or Make target for incremental rebuilds
4. Openness: Every component is built using open data, open formats (CSV/Parquet/GeoJSON), and open-source tools.

### Deployment Summary

| Component | Deployment | Hosting |
|------------|-------------|---------|
| ETL + Data Build | GitHub Actions workflow (`build.yml`) | GitHub Runners |
| API | Containerized (FastAPI + Uvicorn) | Cloudflare Workers / Fly.io |
| Web Map | Static site (React + MapLibre) | GitHub Pages / Cloudflare Pages |
| Data Artifacts | Versioned Parquet/CSV files | GitHub Releases / R2 Bucket |
| CI/CD | Lint → Test → Build → Release | GitHub Actions |

### Scalability Notes
- Expected dataset: ~100k–150k records/year (manageable in-memory).
- DuckDB and GeoParquet ensure fast local joins.
- Vector tiles pre-generated (Tippecanoe) → zero dynamic load on map.
- API endpoints cached via CDN for <300 ms response time.

## 3) Licensing & Compliance
- Output license: **Open Government Licence – British Columbia** attribution in README, data package metadata, and site footer.
- Input terms: Respect robots/ToS; cache minimal, non-sensitive CPSBC fields. No scraping of restricted pages; backoff + user agent.
- PII posture: Process person-level data **in transient staging only**; publish only **aggregates**.

## 4) Privacy Model
*K-anonymity rules (configurable):*
- `K_MIN_UNIQUE_PHYS = 5`  → suppress cell if contributors < 5.
- `DOMINANCE_THRESHOLD = 0.60` → suppress if one contributor ≥ 60% of cell total.
- `PERCENTILE_TOPCODE = 0.99` → display top-coded values as `"≥ value_99p"` for outliers.
- Differencing protection: publish YoY deltas *only for cells* that meet k-safety in both years.
- Suppression labelling: field `suppression_reason ∈ {k_min, dominance, topcode, dual_year_fail}`.

## 5) Data Sources (abstracted interfaces)
- `msp_bluebook(year) -> payments_raw`  
- `cpsbc_directory(snapshot_date) -> practitioners`  
- `boundaries() -> {has, cities, hospitals}`  
- `rurality_index() -> communities` *(optional)*

## 6) Data Model (Canonical Schemas)
### 6.1 Staging Tables
**`payments_raw`**
```json
{
  "fields": {
    "fiscal_year": "string (YYYY-YYYY)",
    "payee_name": "string",
    "payee_address": "string",
    "category": "string",
    "amount_gross": "decimal(14,2)",
    "source_row_id": "string",
    "ingested_at": "timestamp"
  },
  "primary_key": ["source_row_id"]
}
```

***`cpsbc_practitioner`***
```json
{
  "fields": {
    "cpsbc_id": "string",
    "full_name": "string",
    "status": "string",
    "scope": "string",
    "specialty": "string",
    "city": "string",
    "md_school_country": "string",
    "residency_country": "string",
    "licence_year": "int",
    "snapshot_date": "date"
  },
  "primary_key": ["cpsbc_id"]
}
```

***`geo_addresses`***
```json
{
  "fields": {
    "address_raw": "string",
    "address_std": "string",
    "lat": "float",
    "lon": "float",
    "geocode_provider": "string",
    "confidence": "float"
  },
  "primary_key": ["address_raw"]
}
```

## 6.2 Feature Store
***`entity_resolution`***
```json
{
  "fields": {
    "entity_key_hash": "string",       // salted hash of (normalized_name, city)
    "canonical_name": "string",
    "cpsbc_id": "string|null",
    "match_score": "float",
    "match_method": "enum{block,fuzzy,manual}",
    "notes": "string|null"
  },
  "primary_key": ["entity_key_hash"]
}
```

***`payments_geo`***
```json
{
  "fields": {
    "fiscal_year": "string",
    "entity_key_hash": "string",
    "amount_gross": "decimal(14,2)",
    "address_std": "string",
    "lat": "float",
    "lon": "float",
    "city": "string",
    "ha_id": "string",
    "facility_id": "string|null",
    "geo_method": "enum{address_point,city_centroid,facility_snap}"
  },
  "primary_key": ["fiscal_year","entity_key_hash","address_std"]
}
```

***`physician_attributes`***
```json
{
  "fields": {
    "entity_key_hash": "string",
    "physician_type": "enum{GP,Specialist,Unknown}",
    "specialty_group": "string",
    "md_country": "string",
    "residency_country": "string",
    "tenure_bucket": "enum{0-5,6-10,11-20,20+,'Unknown'}"
  },
  "primary_key": ["entity_key_hash"]
}
```

## 6.3 Published Aggregates
***`agg_facility / agg_city / agg_ha`***

```json
{
  "fields": {
    "fiscal_year": "string",
    "geo_level": "enum{facility,city,ha}",
    "geo_id": "string",
    "geo_name": "string",
    "specialty_group": "string",
    "physician_type": "string",
    "n_physicians": "int",
    "total_payments": "decimal(14,2)",
    "median_payments": "decimal(14,2)",
    "pct_change_yoy": "float|null",
    "suppressed": "bool",
    "suppression_reason": "string|null"
  },
  "primary_key": ["fiscal_year","geo_level","geo_id","specialty_group","physician_type"]
}
```

## 7) ETL Pipeline

### 7.1 Ingestion
- Parse MSP PDFs/CSVs with robust table extraction; include unit tests for header/footnote variations.  
- Standardize fiscal-year field; normalize all currency values.  
- Perform address standardization: convert to lowercase, strip punctuation, and expand common abbreviations.

### 7.2 Geocoding
- Use open geocoder (e.g., **Pelias** or **Nominatim**) as the primary service; allow optional paid fallback.  
- Record geocoding confidence; if `< 0.6` or address is a **P.O. Box**, substitute with CPSBC city centroid.  
- Implement **facility snapping**: map to nearest facility within ≤ 500 m; otherwise, leave facility as null.

### 7.3 Entity Resolution (Name → Practitioner)
- **Blocking:** match by last name + first initial + city.  
- **Fuzzy matching:** use `RapidFuzz` with `token_set_ratio ≥ 90`, tie-breaking by city match.  
- **CPSBC ID join:** if a single unambiguous match exists, assign that ID.  
- Maintain manual override file: `overrides/entity_links.yml`.  
- Generate hashed key:  
  `entity_key_hash = SHA256(salt + normalized_name + city)`.

### 7.4 Enrichment
- Apply **specialty grouping taxonomy (CSV)** to canonicalize subspecialties into major specialty groups.  
- Compute **tenure** as `current_year - licence_year` and assign to bucketed ranges (e.g., 0–5, 6–10, 11–20, 20+).

### 7.5 Aggregation & Suppression
- Group records by `geo_level × geo_id × year × filters`.  
- Compute aggregate metrics: `n_physicians`, `total`, `median`, and `p90`.  
- Apply k-anonymity and dominance suppression; annotate suppression reasons.  
- Compute **year-over-year (YoY)** changes on k-safe pairs only.

### 7.6 Validation
- Reconcile annual totals against source MSP data within ±0.5%.  
- Spot-check geocoding results on 100 randomly selected records.  
- Evaluate entity-matching precision/recall using a 500-record manually labeled gold set.



## 9) Frontend Specification
### 9.1 Pages
- Map View (default)
-- Left panel: filters and controls.
-- Center: MapLibre choropleth (toggle between facility, city, or HA).
-- Right drawer: summary stats and small multiple sparkline for YoY trends.

- Data Explorer
-- Tabular data view with identical filters.
-- Export buttons for CSV and Parquet.

- About & Methodology
-- Displays privacy policy, suppression methods, data caveats, and data dictionary.

### 9.2 Filters (UI)
- Physician type: GP / Specialist
- Specialty group (multiselect)
- Training: MD country, Residency country
- Geography: Health Authority, City, Facility
- Year slider (range selection)
- Rurality toggle (if dataset includes)
- “Show YoY change” toggle
- “Include suppressed cells” toggle (admin/debug only)

## 9.3 Map Interactions
- Hover tooltip: { name, year, total $, n_phys, median, YoY, suppression badge }
- Click: pins location and displays detailed breakdown by specialty.

## 9.4 Accessibility & UX
- Conforms to WCAG AA accessibility standards.
- High-contrast color palette, focus indicators, full keyboard navigation.
- Persistent download buttons.
- Descriptive alt text for all charts and images.

# 10) Configuration (YAML)
```yaml
privacy:
  k_min_unique_phys: 5
  dominance_threshold: 0.60
  percentile_topcode: 0.99
geocoding:
  provider_primary: "pelias"
  provider_fallback: "nominatim"
  min_confidence: 0.6
  facility_snap_meters: 500
entity_resolution:
  fuzzy_threshold: 90
  manual_overrides: "overrides/entity_links.yml"
tiles:
  max_zoom: 12
  min_zoom: 3
  attribute_fields: ["total_payments","n_physicians","pct_change_yoy","suppressed"]
build:
  years: ["2021-2022","2022-2023","2023-2024"]
  threads: 8
```


## 11) Performance, Security, Deployment & Roadmap Summary
### **Performance Targets**
- **ETL runtime:** < 30 min for 3 years of data (~100k rows/year) on 8 vCPU.  
- **API latency (P95):** < 300 ms for aggregate requests; < 150 ms when cached.  
- **Tile generation:** ≤ 5 min per map level, then served via CDN.

### **Security & Reliability**
- No PII in published data; all IDs are **hashed with salted SHA256**.  
- Private staging bucket and CI logs are masked; **SBOM** generated with `pip-audit`.  
- Enforce **CSP headers**, **SRI integrity checks**, and **read-only API**.  
- Secrets handled via GitHub OIDC; salts rotated per environment.

### **Testing, QA & Observability**
- **Unit tests:** parsers, geocoding, fuzzy match scoring.  
- **Golden tests:** 500 labeled entity pairs; require precision ≥ 0.95, recall ≥ 0.90.  
- **End-to-End tests:** run pipeline on sample year; include visual choropleth regression tests.  
- **Data validation:** Great Expectations on schema + reconciliation (±0.5%).  
- **Structured logs:** JSON with build IDs.  
- **Metrics:** `cells_published`, `cells_suppressed`, `dominance_hits`, `kmin_hits`, `api_qps`, `tile_hit_ratio`.  
- **Monitoring:** Error budgets and SLO dashboards for build and API performance.

### **Deployment & Documentation**
- **Build process:** GitHub Actions (`build.yml`) triggered on tag push.  
- **Artifacts:** CSV/Parquet data, metadata, and API container image.  
- **Infrastructure:** lightweight IaC (Terraform optional); hosted via GitHub + Cloudflare Pages/R2 bucket.  
- **Documentation folder `/docs`:**
  - Methodology (privacy rules, caveats)  
  - Data dictionary (field-level)  
  - API reference (OpenAPI JSON)  
  - Reproducibility guide (`make` targets)  
  - README quickstart, CONTRIBUTING, CODE_OF_CONDUCT  

### **Roadmap**
#### **Phase 1 – Conservative (≈ 3 months)**
- Parse last 3 years of MSP Blue Book.  
- Implement entity resolution and city/HA aggregates.  
- Apply k-safety & YoY computation.  
- Publish minimal web map (HA/city view).  
- API v1 + vector tiles + CI pipeline + docs.

#### **Phase 2 – Ambitious (6–9 months)**
- Full hospital/clinic registry integration; enhanced geocoder.  
- Payment model inference (fee-for-service vs other).  
- Quarterly refresh and rurality index integration.  
- Analytics: Lorenz curves, Gini coefficients, decomposition over time.

#### **Phase 3 – Exploratory**
- Probabilistic record linkage (EM / FastLink).  
- Differential Privacy (ε-testing) for small-cell noise.  
- Causal decomposition of YoY changes by composition vs intensity.

### **Expansion Ideas**
- **Recruitment lens:** visualize shifts by training origin + tenure.  
- **Service availability:** correlate payments with wait-time proxies (ED/OR).  
- **Mobility:** track city-level movement over years.  
- **Comparators:** replicate method for AB/ON datasets.  
- **Equity lens:** overlay with rurality or IMD indices, per-capita normalization.

### **Risks & Mitigations**
| Risk | Mitigation |
|------|-------------|
| Re-identification via differencing | Publish YoY only on k-safe pairs; pilot DP noise addition. |
| Entity mismatch (homonyms) | Conservative matcher; manual override ledger; audit trail. |
| Address quality (P.O. Boxes) | Fallback to CPSBC city centroid; flag low-confidence records. |
| Legal/ToS drift | Snapshot ToS versions; annual compliance review. |

### **Acceptance Criteria (MVP)**
✅ Aggregates for 3 years across HA & city with k-safety applied.  
✅ `/aggregates` and `/timeseries` APIs return validated totals (±0.5%).  
✅ Interactive map renders choropleth + tooltips; downloads available.  
✅ Documentation includes privacy model & data dictionary.  
✅ CI/CD pipeline fully reproducible from raw public sources.
