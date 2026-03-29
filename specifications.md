# MSP-BC Open Atlas — Software Specification (v0.1)

A fully open-source pipeline and web map that aggregates B.C. MSP payments into privacy-safe geographic and attribute groupings.

## 1) Goals & Non-Goals
### Goals
- Aggregate annual MSP gross payments into **k-anonymous** cells at **facility, city, and health authority** levels.
- Provide a public **web map + downloads API** with reproducible ETL.
- Enable rich filtering (specialty, training, geography, time) and **year-over-year** comparisons.
- Comply with **Open Government Licence – BC** and site ToS of upstream data providers.
- Serve **privacy-protected individual data** (pseudo IDs, jittered coordinates, billing ranges, generalized specialties) alongside aggregate views, with query-level k-anonymity safeguards.

### Non-Goals
- No publication of **real names** or **exact payment amounts**. Individual data is served only through privacy-protected fields (pseudo IDs, billing ranges, jittered coordinates, generalized specialties).
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
- PII posture: Process person-level data **in transient staging only**. Publish **privacy-protected individual records** (pseudo IDs, billing ranges, jittered coordinates) and **aggregates**. No real names, exact amounts, or precise locations in published output.

## 4) Privacy Model

### 4.1 Individual-Level Protections
Individual physician records are published with these protections applied:
- **Pseudo IDs:** Let `entity_key_hash = SHA256(salt + normalized_name + city)` (see §7.3). The published pseudo ID is `PHY-{entity_key_hash[:16]}` and replaces real names. Not reversible without the salt.
- **Jittered coordinates:** Uniform random offset up to 1.5 km, applied to each physician's base location. Jitter is deterministic per physician by seeding the random number generator from the physician's pseudo ID.
- **Billing ranges:** Exact amounts replaced with bucketed ranges (e.g., "$100k–$200k").
- **Generalized specialties:** Subspecialties mapped to broad groups (e.g., "Cardiology" → "Internal Medicine").

### 4.2 Query-Level K-Anonymity
When the `/physicians` endpoint receives filter parameters, the result set must contain at least `K_MIN_UNIQUE_PHYS` distinct physicians. If a filter combination (e.g., specialty=Cardiology AND city=Prince George) returns fewer than `K_MIN_UNIQUE_PHYS` individuals, the endpoint returns a suppression notice instead of individual records. This prevents narrowing to a single identifiable person via filter combinations.

**Admin bypass:** Authenticated admin requests (valid `X-Admin-Token` header) may pass `?k_anonymity=off` to disable query-level suppression. This is for pipeline validation, debugging, and quality checks. The default is always `on`. The frontend "Include suppressed cells" toggle (Section 9.2) sends the admin token when enabled. Non-admin requests with `k_anonymity=off` are ignored (parameter silently treated as `on`).

### 4.3 Aggregate-Level Suppression
*K-anonymity rules (configurable):*
- `K_MIN_UNIQUE_PHYS = 5`  → suppress aggregate cell if contributors < 5.
- `DOMINANCE_THRESHOLD = 0.60` → suppress if one contributor ≥ 60% of cell total.
- `PERCENTILE_TOPCODE = 0.99` → display top-coded values as `"≥ value_99p"` for outliers.
- Differencing protection: publish YoY deltas *only for cells* that meet k-safety in both years.
- Suppression labelling: field `suppression_reason ∈ {k_min, dominance, topcode, dual_year_fail}`.

### 4.4 Heatmap Privacy
Heatmap points are grouped into spatial grid cells (e.g., H3 hexagons or lat/lng rounded to 0.1 degrees). Grid cells with fewer than `K_MIN_UNIQUE_PHYS` physicians are suppressed. Individual physician coordinates are never exposed directly in heatmap output.

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

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | Add per-capita normalization to MVP | P2 (boil lakes) | Touches aggregate.py only, <1 day CC | — |
| 2 | CEO | Add /download endpoint to MVP | P2 (boil lakes) | ~50 lines FastAPI, in blast radius | — |
| 3 | CEO | Ship downloadable data artifact before map polish | P6 (action) | Validates demand early | — |
| 4 | CEO | Add privacy threat model doc | P1 (completeness) | 5 re-identification scenarios | — |
| 5 | CEO | Publish entity resolution gold set | P2 (boil lakes) | Already creating for eval | — |
| 6 | CEO | Mode: SELECTIVE EXPANSION | P1+P2 | Completeness without bloat | SCOPE EXPANSION, HOLD SCOPE, SCOPE REDUCTION |
| 7 | CEO | Add comparison mode (two-year side-by-side) | P2 (boil lakes) | YoY data exists, UI extension | — |
| 8 | CEO | Observability requirements adequate | P3 (pragmatic) | Spec already covers structured logs, metrics | Over-specifying monitoring |
| 9 | CEO | Security model sound | P3 (pragmatic) | SHA256, CSP, SRI, read-only API, SBOM | — |
| 10 | CEO | Test coverage plan adequate | P1 (completeness) | 30+ unit tests + golden test + E2E planned | — |
| 11 | Design | Map MUST be choropleth, not individual markers | P5 (explicit) + P1 | Individual markers expose locations, conflict with privacy model | Point markers |
| 12 | Design | Add /metadata endpoint for filter options | P5 (explicit) | Deriving from query results creates circular dependencies | Current approach |
| 13 | Design | Comparison mode: single map, toggle to YoY choropleth | P3 (pragmatic) | Simpler than side-by-side, works on mobile | Split-screen |
| 14 | Design | Promise.all → Promise.allSettled for API calls | P5 (explicit) | Partial failure should show partial data | — |
| 15 | Design | Add interaction state table to plan | P1 (completeness) | Empty, loading, error states all unspecified | — |
| 16 | Design | Add responsive breakpoints (768px) | P1 (completeness) | No mobile design specified | — |
| 17 | Design | Add ARIA landmarks and a11y basics | P1 (completeness) | WCAG AA claimed but not designed for | — |
| 18 | Design | Choropleth color scale: YlGnBu sequential, RdYlGn diverging | P3 (pragmatic) | Colorblind-safe, well-established scales | — |
| 19 | Design | Add onboarding banner for first-time users | P1 (completeness) | No orientation for new visitors | — |
| 20 | Design | Suppressed cells shown with hatched pattern + tooltip | P1 (completeness) | Silently hiding suppression undermines credibility | — |
| 21 | Eng | ~~Remove /physicians, /trends, /heatmap endpoints~~ **OVERRIDDEN:** Keep endpoints, add query-level k-anonymity + heatmap spatial grouping | User override | Privacy model updated: individual data served with protections (pseudo IDs, jitter, ranges) + query-level k-min safeguard | Aggregate-only model |
| 22 | Eng | Unify hashing: name+city, 16 hex chars minimum | P4 (DRY) + P5 | Two schemes, collision risk at 8 chars | — |
| 23 | Eng | Implement blocking: last name + first initial + city | P1 (completeness) | O(n*m) → O(n*b), spec already describes this | — |
| 24 | Eng | Admin token: whitespace strip + min 16 char check | P5 (explicit) | Whitespace token bypass | — |
| 25 | Eng | Startup check: refuse placeholder salt in production | P5 (explicit) | Comment is not a security control | — |
| 26 | Eng | Add response caching (in-memory TTL) | P3 (pragmatic) | Data changes annually, no per-request SQLite queries | — |
| 27 | Eng | Input validation on PDF parser | P5 (explicit) | Name length, amount ceiling, strip non-printable | — |
| 28 | Eng | Fix suppression reason clobbering | P5 (explicit) | k_min priority over dominance | — |
| 29 | Eng | Add 12 missing test cases (see test plan) | P1 (completeness) | 43% path coverage → target 90%+ | — |
| 30 | Eng | pipeline/app coupling acceptable for MVP | P3 (pragmatic) | aggregate.py imports from app.privacy | — |

## Cross-Phase Themes

**Theme: Privacy model vs. implementation gap** — flagged in CEO (premise #2), Design (choropleth vs markers), and Eng (per-physician endpoints). High-confidence signal. The v0.1 spec explicitly permits serving privacy-protected individual-level data alongside aggregates, but the current implementation of the three per-physician endpoints does not yet fully align with the documented privacy model and safeguards. This is the single most important fix.

**Theme: Data validation before publication** — flagged in CEO (reconciliation targets) and Eng (input validation, differencing attacks). The pipeline needs validation gates at every stage.

## NOT in scope (Eng phase)
- MapLibre GL migration (Phase 2)
- Vector tile generation with Tippecanoe (Phase 2)
- Differential privacy (Phase 3)
- Probabilistic record linkage (Phase 3)
- PostGIS / DuckDB migration (Phase 2)
- Multi-province expansion

## What already exists (Eng phase)
- 30+ unit tests covering core pipeline logic
- SQLAlchemy ORM with models for all entities
- FastAPI app with CORS, static serving, health endpoint
- Config system (YAML + env vars)
- Seed data generator (150 synthetic physicians)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | 3 unresolved (taste decisions), 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | issues_open | 3 critical (choropleth, filter sourcing, truncation), 7 high |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | issues_open | 2 critical (privacy endpoints, admin auth), 3 high, 11 total |
| CEO Voices | `autoplan-voices` | Independent CEO challenge | 1 | clean | subagent-only, 1/6 confirmed |
| Design Voices | `autoplan-voices` | Independent design review | 1 | clean | subagent-only, 2/7 confirmed |
| Eng Voices | `autoplan-voices` | Independent eng review | 1 | clean | subagent-only, 1/6 confirmed |

**VERDICT:** APPROVED with 30 auto-decisions, 4 taste decisions accepted as defaults. Critical fix: align per-physician API endpoints (`/physicians`, `/trends`, `/heatmap`) with the documented privacy model and safeguards (Decision #21). Test plan: see the project test plan document in this repository (for example, `docs/test-plan.md`). Design doc: see the project design document in this repository (for example, `docs/design.md`). Next step: `/ship` when ready.
