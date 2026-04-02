# Changelog

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
