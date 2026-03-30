# BC MSP Map — Roadmap

## Completed

- **Core API**: Physicians, heatmap, aggregations, trends, admin endpoints
- **Privacy module**: Pseudo-IDs, k-anonymity, dominance suppression, location jitter, billing ranges
- **Privacy hardening**: Query-level k-anonymity, heatmap grid-cell aggregation, improved pseudo-IDs
- **Frontend**: Leaflet map with clustering, filter panel, aggregation charts, trend panel
- **Pipeline**: Blue Book PDF parser, entity resolution (RapidFuzz), geocoding (Nominatim + fallback), aggregation, seed data
- **Tests**: API, privacy, pipeline modules

## Up Next

### 1. CPSBC Live Scraper
- `ingest_cpsbc.py` is currently a stub — only loads from cached JSON snapshot
- Implement live scraping of https://www.cpsbc.ca/public/registrant-directory with pagination
- Respect robots.txt and rate-limiting
- Cache results locally to avoid repeated scraping

### 2. Entity Resolution Manual Overrides
- Config references `overrides/entity_links.yml` but no code consumes it
- Implement loading and applying manual name-matching overrides for edge cases fuzzy matching misses

### 3. Percentile Top-coding
- `percentile_topcode: 0.99` is in config.yaml but unused
- Implement top-coding to cap extreme billing values at the 99th percentile

### 4. End-to-End Pipeline Orchestration
- No single command to run "download PDFs → parse → resolve → geocode → aggregate → load DB"
- Build a CLI or script that orchestrates the full pipeline with year parameters

### 5. CI/CD
- No GitHub Actions or equivalent
- Add test runner, linting, and basic checks on PR

### 6. Deployment Configuration
- No Dockerfile, fly.toml, or similar
- Add containerization and deployment config for production hosting

### 7. Frontend Tests
- No frontend test coverage currently
- Add basic component tests (React Testing Library or similar)
