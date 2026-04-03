# Changelog

## [0.3.0.0] - 2026-04-03

UI overhaul, real data pipeline, and CPSBC physician directory integration.

### Added
- Multi-select filters with search for Specialty, City, and Health Authority. Select multiple values, search within options, remove with tag chips.
- Year range selector (FROM/TO) covering all 11 fiscal years from 2011 to 2024.
- Sortable data table replacing the old bar chart and pie chart. Shows all regions with physician count, total billing, median billing, and YoY change.
- "How to Read This Map" collapsible info panel with specialty color legend, billing gradient explanation, and data source attribution.
- Blue Book PDF pipeline (`run_pipeline.py`): parses all 11 Blue Book PDFs, deduplicates 20,167 physicians across years, and loads billing records into the database.
- CPSBC registrant directory scraper (`scrape_cpsbc.py`): Playwright-based headless browser scraper with pagination, polite delays, rate limit detection, and resume support.
- CPSBC enrichment pipeline (`enrich_cpsbc.py`): fuzzy-matches Blue Book names to CPSBC registrants, populating real specialties and practice cities.
- Admin audit logging on `/admin/raw` endpoint with IP, token fingerprint, and timestamp.

### Changed
- Map takes 65% of viewport height (was ~50%). Data panel is scrollable below.
- Billing ranges use 10k precision ("230k-240k") instead of 50k ("200k-250k").
- Physician dots colored by billing amount when specialty is unknown (gradient from pink to dark red). Specialty colors used when CPSBC data provides real specialties.
- Heatmap radius increased (25→40, blur 15→25) so it's visible at province-wide zoom.
- Privacy config frozen after first load to prevent worker divergence in multi-process deployments.
- Startup migration skips when the unique index already exists (avoids table locks on every restart).
- Fiscal year validator rejects years outside 1900-2100 range.

### Fixed
- `billing_range()` returns None for negative/zero amounts instead of nonsense ranges.
- Removed 6 duplicate test methods in TestYearParameterValidation that Python silently shadowed.
- CPSBC scraper pagination: clicks NEXT PAGE in-page instead of navigating to URL (fixes lost session state).

## [0.2.1.0] - 2026-04-01

QA pass: mobile responsive layout, accessibility fix, and FastAPI deprecation cleanup.

### Fixed
- Mobile layout was completely broken. Sidebar was 280px fixed on all viewports, leaving ~95px for the map on phones. Added responsive breakpoint at 768px that stacks sidebar above map.
- Heading hierarchy skipped H2 (H1 → H3), breaking screen reader navigation. Sidebar headings are now H2.
- FastAPI `@app.on_event("startup")` replaced with lifespan context manager, eliminating deprecation warnings.

### Changed
- Added gstack skill routing rules to CLAUDE.md.

## [0.2.0.0] - 2026-03-29

Privacy hardening, editorial design system, and comprehensive test coverage.

### Added
- Query-level k-anonymity on `/physicians` endpoint. Filter combinations returning fewer than 5 individuals now return a suppression notice instead of individual records.
- Heatmap grid-cell aggregation. Individual physician locations aggregated into ~5 km cells with per-cell k-anonymity suppression.
- Shared admin token validation (`auth.py`) using `hmac.compare_digest` for constant-time comparison.
- Salt fail-fast validation on app startup. Refuses to start with default placeholder salt.
- Rate limiting on `/trends/{pseudo_id}` endpoint (30 req/min per pseudo_id) to prevent enumeration.
- Admin bypass for k-anonymity via `X-Admin-Token` header and `k_anonymity=off` query parameter.
- Editorial design system (DESIGN.md): Instrument Serif + Source Sans 3 typography, institutional red (#C4122F) accent, zero border-radius, warm neutral palette.
- CLAUDE.md with testing and design system instructions.
- ROADMAP.md with development roadmap.
- TODOS.md tracking database migration notes and PDF parser validation.
- 18 new tests covering k-anonymity suppression, admin bypass, heatmap grid cells, parser regex, fiscal year formats, dominance priority, and pseudo-ID normalization.

### Changed
- Pseudo-ID hash now includes city and uses 16 hex characters (64 bits) for collision resistance. Breaking change from 8-char format.
- Blue Book PDF parser rewritten from table-based to regex-based dot-leader extraction.
- Fiscal year extraction handles more filename conventions (4+2 digit, single year).
- Dominance suppression no longer overwrites prior k-min suppression.
- Frontend colors from Google Blue to institutional red accent throughout.
- Heatmap gradient uses sequential red data palette.
- All emojis removed from UI.
- Suppression response no longer leaks exact physician count.

### Fixed
- HeatmapPoint renamed to HeatmapCell to match router import.
- Admin token validation in `admin.py` now uses shared helper with 16-char minimum.
- Broken test imports (`_parse_row` removed, pseudo-ID length assertion updated).

## v1.0.0

### Added or Changed
- Added this changelog :)
- Fixed typos in both templates
- Back to top links
- Added more "Built With" frameworks/libraries
- Changed table of contents to start collapsed
- Added checkboxes for major features on roadmap

### Removed
- Some packages/libraries from acknowledgements I no longer use
