"""
Generate trends.json for the frontend — scientifically rigorous version.

Fixes applied (from adversarial review):
  1. Same-name practitioners disambiguated (kept as separate individuals)
  2. Cross-year matching uses normalized names (fuzzy-safe)
  3. Percentiles use linear interpolation (not nearest-rank)
  4. Pareto analysis added per-year + normalized by years-present
  5. YoY reports IQR alongside median
  6. $25K floor caveat included
  7. CPI-adjusted (real) billing series included
  8. Section classification drift tracked (org billings alongside)
  9. Bootstrap confidence interval on Gini trend
"""

import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from pipeline.entity_resolution import normalize_name

PARSED_DIR = Path(__file__).parent / "parsed"
OUTPUT = Path(__file__).parent.parent / "frontend" / "public" / "trends.json"

# ── BC CPI (March values, StatsCan Table 18-10-0005-01, 2002=100) ────
# Each key is the fiscal year end (e.g., "2011-2012" ended March 2012).
BC_CPI = {
    "2011-2012": 121.0,
    "2012-2013": 122.2,
    "2013-2014": 123.5,
    "2014-2015": 124.5,
    "2015-2016": 125.8,
    "2016-2017": 128.0,
    "2017-2018": 131.0,
    "2018-2019": 134.0,
    "2019-2020": 135.5,
    "2020-2021": 139.0,
    "2021-2022": 147.0,
    "2022-2023": 154.0,
    "2023-2024": 158.5,
}


def cpi_deflator(year: str, base_year: str = "2023-2024") -> float:
    """Return multiplier to convert nominal dollars in `year` to `base_year` dollars."""
    return BC_CPI[base_year] / BC_CPI.get(year, BC_CPI[base_year])


def sort_fy(years):
    return sorted(years, key=lambda y: int(y.split("-")[0]))


def interpolated_percentile(sorted_vals: list[float], p: float) -> float:
    """Linear interpolation percentile (matches numpy's default method)."""
    n = len(sorted_vals)
    if n == 0:
        return 0
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def gini(values: list[float]) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 0 or sum(sorted_vals) == 0:
        return 0
    cumsum = 0
    for i, v in enumerate(sorted_vals):
        cumsum += (2 * (i + 1) - n - 1) * v
    return cumsum / (n * sum(sorted_vals))


def bootstrap_gini_ci(values: list[float], n_boot: int = 2000, ci: float = 95) -> tuple[float, float]:
    """Bootstrap confidence interval for Gini coefficient."""
    rng = random.Random(42)
    n = len(values)
    ginis = []
    for _ in range(n_boot):
        sample = [values[rng.randint(0, n - 1)] for _ in range(n)]
        ginis.append(gini(sample))
    ginis.sort()
    lo = (100 - ci) / 2 / 100
    hi = 1 - lo
    return ginis[int(n_boot * lo)], ginis[int(n_boot * hi)]


def load_all():
    all_records = []
    for jf in sorted(PARSED_DIR.glob("*.json")):
        with open(jf) as f:
            all_records.extend(json.load(f))
    return all_records


def disambiguate_duplicates(records: list[dict]) -> list[dict]:
    """When the same payee_name appears multiple times in the same fiscal year,
    they are different practitioners (common names like 'Lee, Susan').
    Append a disambiguator so they aren't merged during aggregation."""
    # Group by (fiscal_year, payee_name)
    groups = defaultdict(list)
    for r in records:
        groups[(r["fiscal_year"], r["payee_name"])].append(r)

    result = []
    for (fy, name), recs in groups.items():
        if len(recs) == 1:
            result.append(recs[0])
        else:
            # Multiple entries for same name in same year — disambiguate
            for i, r in enumerate(recs):
                r_copy = dict(r)
                r_copy["payee_name"] = f"{name} [{i+1}]"
                r_copy["_disambiguated"] = True
                result.append(r_copy)
    return result


def build_normalized_id(name: str) -> str:
    """Create a stable cross-year identifier from a name.
    Uses normalized form (lowercase, no titles, collapsed whitespace)."""
    norm = normalize_name(name)
    # Strip disambiguator if present
    if norm.endswith("]"):
        bracket = norm.rfind("[")
        if bracket > 0:
            norm = norm[:bracket].strip()
    return norm


def main():
    print("Loading parsed Blue Book data...")
    all_records = load_all()
    practitioners_raw = [r for r in all_records if r["section"] == "practitioners"]
    orgs = [r for r in all_records if r["section"] == "organizations"]

    # Issue 1: disambiguate same-name practitioners
    practitioners = disambiguate_duplicates(practitioners_raw)
    n_disambiguated = sum(1 for r in practitioners if r.get("_disambiguated"))
    print(f"  Disambiguated {n_disambiguated} same-name entries across all years")

    all_years = sort_fy(set(r["fiscal_year"] for r in practitioners))

    # Aggregate per practitioner per year (using disambiguated names)
    by_year = defaultdict(lambda: defaultdict(float))
    for r in practitioners:
        by_year[r["fiscal_year"]][r["payee_name"]] += r["amount_gross"]

    # Issue 2: build normalized IDs for cross-year matching
    name_to_norm = {}
    for r in practitioners:
        name_to_norm[r["payee_name"]] = build_normalized_id(r["payee_name"])

    norm_by_year = defaultdict(set)
    for year in all_years:
        for name in by_year[year]:
            norm_by_year[year].add(name_to_norm[name])

    # ── 1. Billing trends (nominal + real) ───────────────────────────
    trends = []
    for year in all_years:
        amounts = list(by_year[year].values())
        deflator = cpi_deflator(year)
        real_amounts = [a * deflator for a in amounts]
        trends.append({
            "year": year,
            "n_practitioners": len(amounts),
            "total_billing": round(sum(amounts)),
            "total_billing_real": round(sum(real_amounts)),
            "mean_billing": round(statistics.mean(amounts)),
            "mean_billing_real": round(statistics.mean(real_amounts)),
            "median_billing": round(statistics.median(amounts)),
            "median_billing_real": round(statistics.median(real_amounts)),
            "max_billing": round(max(amounts)),
        })

    first, last = trends[0], trends[-1]
    n_span = int(last["year"].split("-")[0]) - int(first["year"].split("-")[0])
    cagr_nominal = ((last["total_billing"] / first["total_billing"]) ** (1 / n_span) - 1) * 100 if n_span > 0 else 0
    cagr_real = ((last["total_billing_real"] / first["total_billing_real"]) ** (1 / n_span) - 1) * 100 if n_span > 0 else 0

    # ── 2. Inequality (Gini + percentiles with interpolation) ────────
    inequality = []
    for year in all_years:
        amounts = sorted(by_year[year].values())
        g = round(gini(amounts), 4)
        pcts = {}
        for p in [10, 25, 50, 75, 90, 99]:
            pcts[f"p{p}"] = round(interpolated_percentile(amounts, p))
        inequality.append({"year": year, "gini": g, **pcts})

    # Issue 10: bootstrap test on Gini difference (first vs last year)
    first_amounts = list(by_year[all_years[0]].values())
    last_amounts = list(by_year[all_years[-1]].values())
    g_first = gini(first_amounts)
    g_last = gini(last_amounts)
    ci_first = bootstrap_gini_ci(first_amounts)
    ci_last = bootstrap_gini_ci(last_amounts)
    gini_test = {
        "first_year": all_years[0],
        "last_year": all_years[-1],
        "gini_first": round(g_first, 4),
        "gini_last": round(g_last, 4),
        "ci_95_first": [round(ci_first[0], 4), round(ci_first[1], 4)],
        "ci_95_last": [round(ci_last[0], 4), round(ci_last[1], 4)],
        "significant": ci_first[1] < ci_last[0] or ci_last[1] < ci_first[0],
    }
    print(f"  Gini bootstrap: {all_years[0]}={g_first:.4f} CI{ci_first}, "
          f"{all_years[-1]}={g_last:.4f} CI{ci_last}, significant={gini_test['significant']}")

    # ── 3. Turnover (using normalized IDs for cross-year matching) ────
    cumulative_ever = set()
    turnover = []
    for i, year in enumerate(all_years):
        current = norm_by_year[year]
        if i == 0:
            new, exited, retained, returnees, retention_pct = len(current), 0, 0, 0, None
        else:
            prev = norm_by_year[all_years[i - 1]]
            retained = len(current & prev)
            exited = len(prev - current)
            new_to_system = current - cumulative_ever
            returned = (current - prev) & cumulative_ever  # were seen before but not last year
            new = len(new_to_system)
            returnees = len(returned)
            retention_pct = round(retained / len(prev) * 100, 1)
        cumulative_ever |= current
        turnover.append({
            "year": year,
            "total": len(current),
            "new_entrants": new,
            "returnees": returnees,
            "exits": exited,
            "retained": retained,
            "retention_pct": retention_pct,
        })

    # ── 4. Income brackets ───────────────────────────────────────────
    latest = all_years[-1]
    amounts = list(by_year[latest].values())
    brackets_def = [
        (0, 100_000, "Under $100K"),
        (100_000, 200_000, "$100K-$200K"),
        (200_000, 300_000, "$200K-$300K"),
        (300_000, 500_000, "$300K-$500K"),
        (500_000, 1_000_000, "$500K-$1M"),
        (1_000_000, 50_000_000, "$1M+"),
    ]
    total_n, total_billing = len(amounts), sum(amounts)
    brackets = []
    for lo, hi, label in brackets_def:
        ib = [a for a in amounts if lo <= a < hi]
        brackets.append({
            "label": label,
            "count": len(ib),
            "pct_of_physicians": round(len(ib) / total_n * 100, 1),
            "total_billing": round(sum(ib)),
            "pct_of_billing": round(sum(ib) / total_billing * 100, 1),
        })

    # ── 5. Pareto — lifetime, per-year, and normalized ───────────────
    # Lifetime (raw)
    lifetime = defaultdict(float)
    years_present = defaultdict(int)
    for r in practitioners:
        lifetime[r["payee_name"]] += r["amount_gross"]
        # Count unique years per name (using normalized ID to avoid double-counting disambiguated)
    norm_years = defaultdict(set)
    for r in practitioners:
        nid = name_to_norm[r["payee_name"]]
        norm_years[nid].add(r["fiscal_year"])
    for nid, yrs in norm_years.items():
        years_present[nid] = len(yrs)

    ranked = sorted(lifetime.values(), reverse=True)
    total_all = sum(ranked)
    n_total = len(ranked)
    pareto_lifetime = []
    for pct in [1, 5, 10, 20, 50]:
        n = max(1, int(n_total * pct / 100))
        pareto_lifetime.append({
            "top_pct": pct,
            "n_practitioners": n,
            "billing_share": round(sum(ranked[:n]) / total_all * 100, 1),
        })

    # Per-year Pareto (issue 5)
    pareto_per_year = []
    for year in all_years:
        amounts_sorted = sorted(by_year[year].values(), reverse=True)
        yr_total = sum(amounts_sorted)
        yr_n = len(amounts_sorted)
        yr_pareto = {}
        for pct in [1, 5, 10, 20]:
            n = max(1, int(yr_n * pct / 100))
            yr_pareto[f"top_{pct}_pct"] = round(sum(amounts_sorted[:n]) / yr_total * 100, 1)
        pareto_per_year.append({"year": year, **yr_pareto})

    # Normalized Pareto (lifetime / years_present)
    # Map disambiguated names back to normalized IDs for averaging
    norm_lifetime = defaultdict(float)
    for name, total in lifetime.items():
        nid = name_to_norm[name]
        norm_lifetime[nid] += total  # sum in case of disambiguated
    normalized_annual = {}
    for nid, total in norm_lifetime.items():
        yp = years_present.get(nid, 1)
        normalized_annual[nid] = total / yp

    ranked_norm = sorted(normalized_annual.values(), reverse=True)
    total_norm = sum(ranked_norm)
    n_norm = len(ranked_norm)
    pareto_normalized = []
    for pct in [1, 5, 10, 20, 50]:
        n = max(1, int(n_norm * pct / 100))
        pareto_normalized.append({
            "top_pct": pct,
            "n_practitioners": n,
            "billing_share": round(sum(ranked_norm[:n]) / total_norm * 100, 1),
        })

    # ── 6. YoY with IQR ─────────────────────────────────────────────
    # Build per-normalized-ID billing by year
    norm_billing_by_year = defaultdict(lambda: defaultdict(float))
    for r in practitioners:
        nid = name_to_norm[r["payee_name"]]
        norm_billing_by_year[nid][r["fiscal_year"]] += r["amount_gross"]

    yoy_stats = []
    for i in range(1, len(all_years)):
        prev_y, curr_y = all_years[i - 1], all_years[i]
        changes = []
        for nid, years_data in norm_billing_by_year.items():
            if prev_y in years_data and curr_y in years_data and years_data[prev_y] > 0:
                pct = (years_data[curr_y] - years_data[prev_y]) / years_data[prev_y] * 100
                changes.append(pct)
        if changes:
            sorted_changes = sorted(changes)
            q1 = interpolated_percentile(sorted_changes, 25)
            q3 = interpolated_percentile(sorted_changes, 75)
            yoy_stats.append({
                "from_year": prev_y,
                "to_year": curr_y,
                "n_matched": len(changes),
                "median_yoy": round(statistics.median(changes), 1),
                "mean_yoy": round(statistics.mean(changes), 1),
                "q1": round(q1, 1),
                "q3": round(q3, 1),
                "iqr": round(q3 - q1, 1),
            })

    # ── 8. Section classification drift (org billings) ───────────────
    org_by_year = defaultdict(float)
    org_count_by_year = defaultdict(int)
    for r in orgs:
        org_by_year[r["fiscal_year"]] += r["amount_gross"]
        org_count_by_year[r["fiscal_year"]] += 1

    section_drift = []
    for year in all_years:
        prac_total = sum(by_year[year].values())
        org_total = org_by_year.get(year, 0)
        combined = prac_total + org_total
        section_drift.append({
            "year": year,
            "practitioner_total": round(prac_total),
            "organization_total": round(org_total),
            "combined_total": round(combined),
            "practitioner_share_pct": round(prac_total / combined * 100, 1) if combined > 0 else None,
            "n_orgs": org_count_by_year.get(year, 0),
        })

    # ── Build output ─────────────────────────────────────────────────
    output = {
        "generated": "2026-04-06",
        "source": "BC MSP Blue Book PDFs (2011-2024)",
        "n_fiscal_years": len(all_years),
        "years": all_years,
        "total_unique_practitioners": len(cumulative_ever),
        "cagr_nominal_pct": round(cagr_nominal, 1),
        "cagr_real_pct": round(cagr_real, 1),
        "cpi_base_year": "2023-2024",
        "billing_trends": trends,
        "inequality": inequality,
        "gini_bootstrap_test": gini_test,
        "turnover": turnover,
        "income_brackets": {"year": latest, "brackets": brackets},
        "pareto_lifetime": pareto_lifetime,
        "pareto_per_year": pareto_per_year,
        "pareto_normalized": pareto_normalized,
        "yoy_stats": yoy_stats,
        "section_drift": section_drift,
        "caveats": [
            "All amounts are gross billings. Practitioners pay practice expenses (overhead, staff, equipment) from these amounts. Net income cannot be determined.",
            "Only practitioners billing $25,000+ are individually listed. 'New entrants' may include physicians who crossed this threshold, not just those starting practice. 'Exits' may include physicians who dipped below, not just those stopping practice.",
            "Cross-year practitioner matching uses normalized names. Name changes (marriage, legal) cause false exits/entries. Approximately 3-6 same-name duplicates per year are disambiguated.",
            "Section classification methodology changed over time: lab, radiology, and FPSC payments shifted from 'Practitioners' to 'Organizations' in later years, affecting practitioner counts and totals.",
            "Amounts are not adjusted for changes in fee schedule or scope of practice. The 2023-24 spike reflects the new Physician Master Agreement fee increases and LFP model payments.",
            "Alternative Payment Plans (APP), salaried positions, MOCAP on-call payments, and LFP panel/time payments are NOT included. This data covers fee-for-service only.",
            "Real (inflation-adjusted) values use BC CPI (March values, StatsCan 18-10-0005-01), base year 2023-2024.",
        ],
        "methodology": {
            "duplicate_handling": "Same-name practitioners in the same fiscal year are treated as separate individuals (disambiguated with index suffixes).",
            "cross_year_matching": "Names are normalized (lowercase, titles removed, whitespace collapsed) for cross-year matching. This reduces but does not eliminate false matches/misses.",
            "percentiles": "Linear interpolation method (equivalent to numpy default).",
            "gini": "Standard discrete Gini formula. 95% CI via 2000-iteration bootstrap (seed=42).",
            "pareto_normalized": "Lifetime billing divided by number of years present, to control for longevity bias.",
            "inflation": f"BC CPI deflators applied to convert to {all_years[-1]} constant dollars.",
        },
    }

    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
