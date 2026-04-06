# BC MSP Map — Roadmap

## Completed

- **Core API**: Physicians, heatmap, aggregations, trends, admin endpoints
- **Privacy module**: Pseudo-IDs (128-bit), k-anonymity, dominance suppression, location jitter, billing ranges
- **Privacy hardening**: Query-level k-anonymity, heatmap grid-cell aggregation, CSP headers, rate limiting
- **Security hardening**: SHA-pinned CI actions, CODEOWNERS, CORS restrictions, env-var-only secrets
- **Frontend**: Leaflet map with clustering, filter panel, aggregation tables, per-capita table
- **Pipeline**: Blue Book PDF parser, entity resolution (RapidFuzz), geocoding (Nominatim + fallback), aggregation, seed data
- **CPSBC scraper**: Full Playwright-based scraper with pagination, rate-limit backoff, resume support, UA rotation (`scrape_cpsbc.py`)
- **CPSBC enrichment**: Fuzzy-matching of Blue Book names to CPSBC registrants (`enrich_cpsbc.py`)
- **Blue Book analysis**: Billing trends, Pareto, Gini, entrants/exits across 11 years (`analysis/bluebook_analysis.py`)
- **Tests**: 132 tests across API, privacy, pipeline, and PDF parser integration
- **CI/CD**: GitHub Pages deployment via GitHub Actions
- **Static deployment**: Frontend builds to static site served via GitHub Pages (no backend in prod)

## In Progress

### 1. CPSBC Directory Scrape
- `scrape_cpsbc.py` is fully implemented and running
- `ingest_cpsbc.py` currently loads from cached JSON snapshot
- Once scrape completes, enrichment pipeline will link Blue Book names to CPSBC specialties/cities

## Up Next

### 2. Pipeline Integration
- Wire `scrape_cpsbc.py` → `enrich_cpsbc.py` → `run_pipeline.py` into a single orchestrated flow
- Single command to run: parse PDFs → resolve entities → enrich from CPSBC → geocode → aggregate → export

### 3. Entity Resolution Manual Overrides
- Config references `overrides/entity_links.yml` but no code consumes it
- Implement loading and applying manual name-matching overrides

### 4. Blue Book Analysis on Website
- Incorporate billing trends, inequality metrics, and aggregate statistics into the frontend
- Add visualizations for Gini coefficient trends, Pareto distribution, entrant/exit analysis

### 5. Frontend Tests
- Add component tests (React Testing Library)
- Add Playwright e2e tests against the deployed site

### 6. Containerized Deployment (if backend needed)
- Currently static-only deployment; backend runs locally
- Add Dockerfile if backend API deployment is needed
