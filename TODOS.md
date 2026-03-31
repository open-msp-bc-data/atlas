# TODOS

## Bugs Fixed (see PR for implementation)

### Bug: aggregate.py unique physician count used Python id() as fallback
- `backend/pipeline/aggregate.py` line 37 used `id(m)` (memory address) as a fallback when
  a record had no `entity_key_hash`. Because every dict gets a unique `id()`, two billing rows
  for the same physician were counted as two separate physicians, breaking k-anonymity enforcement.
- **Fixed:** count only distinct `entity_key_hash` values; records without a hash are excluded.

### Bug: k-anonymity suppression message leaked the exact k_min threshold
- The `/physicians` suppression response included the literal k_min value in the message:
  `"fewer than 5 individuals"` — revealing the threshold enables targeted enumeration attacks.
- **Fixed:** message now reads `"Filter combination matches too few individuals."` with no number.

### Bug: Year query parameter accepted any string (no format validation)
- `/physicians?year=invalid` and `/heatmap?year=2023` were accepted silently; string-based
  `<=` comparisons on the `year` column produce wrong results with arbitrary strings.
- **Fixed:** added `pattern=r"^\d{4}-\d{4}$"` validation on both endpoints; invalid formats
  now return HTTP 422.

### Bug: Frontend crashes when /physicians returns a suppression object instead of an array
- `App.jsx` called `.map()` directly on the API response. When the server returns a suppression
  notice `{suppressed: true, ...}` (an object, not an array), calling `.map()` on it throws a
  `TypeError` and crashes the UI.
- **Fixed:** `fetchPhysicians()` in `api.js` now checks `Array.isArray(data)` and returns `[]`
  for suppression responses, allowing the UI to render correctly.

### Bug: Aggregation table had no UNIQUE constraint, allowing duplicate rows
- `models.py` had no composite unique constraint on the `Aggregation` table. Running the
  pipeline twice would insert duplicate `(fiscal_year, geo_level, geo_id, specialty_group)` rows,
  causing double-counting in charts.
- **Fixed:** added `UniqueConstraint("fiscal_year", "geo_level", "geo_id", "specialty_group")`.

### Code quality: SQLAlchemy `== False` anti-pattern in aggregations router
- `aggregations.py` used `.filter(Aggregation.suppressed == False)` which triggers a SQLAlchemy
  `SAWarning` and is flagged by linters.
- **Fixed:** changed to `.filter(Aggregation.suppressed.is_(False))`.

## Database Migration (PostgreSQL)
- Add composite index on `(specialty_group, city, health_authority)` for `/physicians` COUNT query performance
- `func.round` uses banker's rounding in SQLite but round-half-away-from-zero in PostgreSQL — heatmap grid cell assignments will shift on migration. Consider `FLOOR(x / grid) * grid` for consistent behavior across databases.

## PDF Parser Validation
- Validate `_ENTRY_RE` regex against real Blue Book PDFs for false positives (page headers, footnotes, running text)
- The `$50M` sanity check only catches extreme outliers, not in-range false positives
- Test with all 5 fiscal years of real PDFs before publishing any data

