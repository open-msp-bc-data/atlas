# TODOS

## Database Migration (PostgreSQL)
- Add composite index on `(specialty_group, city, health_authority)` for `/physicians` COUNT query performance
- `func.round` uses banker's rounding in SQLite but round-half-away-from-zero in PostgreSQL — heatmap grid cell assignments will shift on migration. Consider `FLOOR(x / grid) * grid` for consistent behavior across databases.

## PDF Parser Validation
- Validate `_ENTRY_RE` regex against real Blue Book PDFs for false positives (page headers, footnotes, running text)
- The `$50M` sanity check only catches extreme outliers, not in-range false positives
- Test with all 5 fiscal years of real PDFs before publishing any data
