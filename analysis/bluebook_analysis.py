"""
Blue Book Billing Analysis
==========================
Pure analysis from raw Blue Book PDFs only — no CPSBC or other linked data.
Covers: billing trends, top billers, YoY changes, entrants/exits, inequality.
"""

import sys
from pathlib import Path

# Add project root so we can import the existing parser
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.pipeline.ingest_bluebook import parse_bluebook_pdf
from collections import defaultdict
import statistics
import json

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


PARSED_DIR = Path(__file__).resolve().parent / "parsed"


def load_all_bluebooks():
    """Load pre-parsed JSON files (from parallel subagent parsing)."""
    all_records = []
    for jf in sorted(PARSED_DIR.glob("*.json")):
        with open(jf) as f:
            rows = json.load(f)
        print(f"  Loaded {jf.name}: {len(rows)} entries")
        all_records.extend(rows)
    return all_records


def filter_practitioners(records):
    """Keep only 'practitioners' section (individual doctors, not orgs)."""
    return [r for r in records if r["section"] == "practitioners"]


def sort_fiscal_years(years):
    """Sort fiscal years like '2011-2012' chronologically."""
    return sorted(years, key=lambda y: int(y.split("-")[0]))


# ─── Analysis functions ───────────────────────────────────────────────

def billing_trends(records):
    """Aggregate billing stats per fiscal year."""
    by_year = defaultdict(list)
    for r in records:
        by_year[r["fiscal_year"]].append(r["amount_gross"])

    print("\n" + "=" * 70)
    print("1. BILLING TRENDS OVER TIME (Practitioners Only)")
    print("=" * 70)
    print(f"{'Year':<14} {'Count':>7} {'Total ($M)':>12} {'Mean ($K)':>11} {'Median ($K)':>12} {'Max ($K)':>10}")
    print("-" * 70)

    yearly_totals = {}
    for year in sort_fiscal_years(by_year.keys()):
        amounts = by_year[year]
        total = sum(amounts)
        mean = statistics.mean(amounts)
        median = statistics.median(amounts)
        mx = max(amounts)
        yearly_totals[year] = total
        print(f"{year:<14} {len(amounts):>7,} {total/1e6:>12.1f} {mean/1e3:>11.1f} {median/1e3:>12.1f} {mx/1e3:>10.1f}")

    # Growth rate
    years_sorted = sort_fiscal_years(yearly_totals.keys())
    if len(years_sorted) >= 2:
        first_year, last_year = years_sorted[0], years_sorted[-1]
        first_total, last_total = yearly_totals[first_year], yearly_totals[last_year]
        n_years = int(last_year.split("-")[0]) - int(first_year.split("-")[0])
        cagr = (last_total / first_total) ** (1 / n_years) - 1 if n_years > 0 else 0
        print(f"\nTotal spending grew from ${first_total/1e9:.2f}B to ${last_total/1e9:.2f}B")
        print(f"CAGR: {cagr*100:.1f}% over {n_years} years")

    return yearly_totals


def top_billers(records):
    """Show top billers across all years and per-year."""
    # Lifetime totals
    lifetime = defaultdict(float)
    for r in records:
        lifetime[r["payee_name"]] += r["amount_gross"]

    ranked = sorted(lifetime.items(), key=lambda x: -x[1])

    print("\n" + "=" * 70)
    print("2. TOP BILLERS — LIFETIME (All Years Combined)")
    print("=" * 70)
    total_all = sum(lifetime.values())
    cumulative = 0
    print(f"{'Rank':<6} {'Name':<40} {'Total ($M)':>12} {'Cum %':>7}")
    print("-" * 70)
    for i, (name, total) in enumerate(ranked[:25], 1):
        cumulative += total
        print(f"{i:<6} {name[:39]:<40} {total/1e6:>12.2f} {cumulative/total_all*100:>6.1f}%")

    # Pareto analysis
    print("\n--- Pareto Analysis ---")
    n_total = len(ranked)
    running = 0
    for pct in [1, 5, 10, 20, 50]:
        n = max(1, int(n_total * pct / 100))
        top_sum = sum(v for _, v in ranked[:n])
        print(f"Top {pct:>2}% of billers ({n:>5} practitioners) account for {top_sum/total_all*100:.1f}% of total billings")

    # Highest single-year billing
    print("\n--- Highest Single-Year Billings ---")
    by_year_name = defaultdict(float)
    for r in records:
        by_year_name[(r["fiscal_year"], r["payee_name"])] += r["amount_gross"]
    top_single = sorted(by_year_name.items(), key=lambda x: -x[1])[:10]
    print(f"{'Rank':<6} {'Year':<14} {'Name':<35} {'Amount ($M)':>12}")
    print("-" * 70)
    for i, ((year, name), amt) in enumerate(top_single, 1):
        print(f"{i:<6} {year:<14} {name[:34]:<35} {amt/1e6:>12.2f}")


def yoy_analysis(records):
    """Year-over-year changes per practitioner."""
    by_name_year = defaultdict(dict)
    for r in records:
        by_name_year[r["payee_name"]][r["fiscal_year"]] = \
            by_name_year[r["payee_name"]].get(r["fiscal_year"], 0) + r["amount_gross"]

    all_years = sort_fiscal_years({r["fiscal_year"] for r in records})

    print("\n" + "=" * 70)
    print("3. YEAR-OVER-YEAR ANALYSIS")
    print("=" * 70)

    # Aggregate YoY changes
    print(f"\n{'Year Pair':<30} {'Median YoY%':>12} {'Mean YoY%':>11} {'Practitioners':>14}")
    print("-" * 70)

    for i in range(1, len(all_years)):
        prev_year, curr_year = all_years[i-1], all_years[i]
        changes = []
        for name, years in by_name_year.items():
            if prev_year in years and curr_year in years and years[prev_year] > 0:
                pct = (years[curr_year] - years[prev_year]) / years[prev_year] * 100
                changes.append(pct)
        if changes:
            med = statistics.median(changes)
            mean = statistics.mean(changes)
            print(f"{prev_year} → {curr_year:<14} {med:>11.1f}% {mean:>10.1f}% {len(changes):>14,}")

    # Biggest gainers and biggest drops (latest year pair)
    if len(all_years) >= 2:
        prev_year, curr_year = all_years[-2], all_years[-1]
        changes_detail = []
        for name, years in by_name_year.items():
            if prev_year in years and curr_year in years and years[prev_year] > 10000:
                pct = (years[curr_year] - years[prev_year]) / years[prev_year] * 100
                delta = years[curr_year] - years[prev_year]
                changes_detail.append((name, years[prev_year], years[curr_year], pct, delta))

        print(f"\n--- Biggest $ Increases: {prev_year} → {curr_year} ---")
        by_delta = sorted(changes_detail, key=lambda x: -x[4])[:10]
        print(f"{'Name':<35} {'Previous ($K)':>14} {'Current ($K)':>14} {'Change ($K)':>12} {'%':>8}")
        print("-" * 85)
        for name, prev, curr, pct, delta in by_delta:
            print(f"{name[:34]:<35} {prev/1e3:>14.1f} {curr/1e3:>14.1f} {delta/1e3:>12.1f} {pct:>7.1f}%")

        print(f"\n--- Biggest $ Decreases: {prev_year} → {curr_year} ---")
        by_delta_down = sorted(changes_detail, key=lambda x: x[4])[:10]
        print(f"{'Name':<35} {'Previous ($K)':>14} {'Current ($K)':>14} {'Change ($K)':>12} {'%':>8}")
        print("-" * 85)
        for name, prev, curr, pct, delta in by_delta_down:
            print(f"{name[:34]:<35} {prev/1e3:>14.1f} {curr/1e3:>14.1f} {delta/1e3:>12.1f} {pct:>7.1f}%")


def entrants_exits(records):
    """Track new entrants and exits across years."""
    by_name_year = defaultdict(set)
    for r in records:
        by_name_year[r["payee_name"]].add(r["fiscal_year"])

    all_years = sort_fiscal_years({r["fiscal_year"] for r in records})
    names_by_year = defaultdict(set)
    for name, years in by_name_year.items():
        for y in years:
            names_by_year[y].add(name)

    print("\n" + "=" * 70)
    print("4. NEW ENTRANTS & EXITS")
    print("=" * 70)
    print(f"{'Year':<14} {'Total':>7} {'New':>7} {'Exited':>7} {'Retained':>9} {'Retention%':>11}")
    print("-" * 70)

    cumulative_ever = set()
    for i, year in enumerate(all_years):
        current = names_by_year[year]
        if i == 0:
            new = len(current)
            exited = 0
            retained = 0
            ret_pct = "-"
        else:
            prev = names_by_year[all_years[i-1]]
            retained_set = current & prev
            new_set = current - cumulative_ever
            exited_set = prev - current
            new = len(new_set)
            exited = len(exited_set)
            retained = len(retained_set)
            ret_pct = f"{retained/len(prev)*100:.1f}%"

        cumulative_ever |= current
        print(f"{year:<14} {len(current):>7,} {new:>7,} {exited:>7,} {retained:>9,} {ret_pct:>11}")

    print(f"\nTotal unique practitioners across all years: {len(cumulative_ever):,}")

    # Longitudinal presence
    print("\n--- Longitudinal Presence ---")
    presence_counts = defaultdict(int)
    for name, years in by_name_year.items():
        presence_counts[len(years)] += 1
    print(f"{'Years Present':<15} {'Practitioners':>14} {'%':>7}")
    print("-" * 38)
    total_unique = len(by_name_year)
    for n_years in sorted(presence_counts.keys()):
        count = presence_counts[n_years]
        print(f"{n_years:<15} {count:>14,} {count/total_unique*100:>6.1f}%")


def inequality_analysis(records):
    """Gini coefficient and distribution analysis per year."""

    def gini(values):
        """Compute Gini coefficient."""
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n == 0:
            return 0
        cumsum = 0
        for i, v in enumerate(sorted_vals):
            cumsum += (2 * (i + 1) - n - 1) * v
        return cumsum / (n * sum(sorted_vals)) if sum(sorted_vals) > 0 else 0

    by_year = defaultdict(list)
    for r in records:
        # Aggregate per practitioner per year first
        pass

    by_name_year = defaultdict(lambda: defaultdict(float))
    for r in records:
        by_name_year[r["fiscal_year"]][r["payee_name"]] += r["amount_gross"]

    print("\n" + "=" * 70)
    print("5. INEQUALITY ANALYSIS (Gini Coefficient)")
    print("=" * 70)
    print(f"{'Year':<14} {'Gini':>7} {'P10 ($K)':>10} {'P25 ($K)':>10} {'P50 ($K)':>10} {'P75 ($K)':>10} {'P90 ($K)':>10} {'P99 ($K)':>10}")
    print("-" * 85)

    for year in sort_fiscal_years(by_name_year.keys()):
        amounts = list(by_name_year[year].values())
        g = gini(amounts)
        percentiles = [10, 25, 50, 75, 90, 99]
        pcts = []
        sorted_amounts = sorted(amounts)
        n = len(sorted_amounts)
        for p in percentiles:
            idx = min(int(n * p / 100), n - 1)
            pcts.append(sorted_amounts[idx])
        print(f"{year:<14} {g:>7.3f} {pcts[0]/1e3:>10.1f} {pcts[1]/1e3:>10.1f} {pcts[2]/1e3:>10.1f} {pcts[3]/1e3:>10.1f} {pcts[4]/1e3:>10.1f} {pcts[5]/1e3:>10.1f}")

    # Income brackets
    print("\n--- Income Brackets (Latest Year) ---")
    latest_year = sort_fiscal_years(by_name_year.keys())[-1]
    amounts = list(by_name_year[latest_year].values())
    brackets = [
        (0, 50_000, "Under $50K"),
        (50_000, 100_000, "$50K - $100K"),
        (100_000, 200_000, "$100K - $200K"),
        (200_000, 300_000, "$200K - $300K"),
        (300_000, 500_000, "$300K - $500K"),
        (500_000, 750_000, "$500K - $750K"),
        (750_000, 1_000_000, "$750K - $1M"),
        (1_000_000, 2_000_000, "$1M - $2M"),
        (2_000_000, 50_000_000, "$2M+"),
    ]
    total_n = len(amounts)
    total_billing = sum(amounts)
    print(f"\n{latest_year}:")
    print(f"{'Bracket':<20} {'Count':>7} {'% of MDs':>9} {'Total ($M)':>12} {'% of $':>8}")
    print("-" * 58)
    for lo, hi, label in brackets:
        in_bracket = [a for a in amounts if lo <= a < hi]
        count = len(in_bracket)
        bracket_total = sum(in_bracket)
        print(f"{label:<20} {count:>7,} {count/total_n*100:>8.1f}% {bracket_total/1e6:>12.1f} {bracket_total/total_billing*100:>7.1f}%")


def main():
    print("Loading Blue Book PDFs (raw extraction only, no CPSBC data)...")
    print("-" * 50)
    all_records = load_all_bluebooks()
    print(f"\nTotal raw records: {len(all_records):,}")

    practitioners = filter_practitioners(all_records)
    print(f"Practitioner records: {len(practitioners):,}")

    orgs = [r for r in all_records if r["section"] == "organizations"]
    print(f"Organization records: {len(orgs):,}")

    other = [r for r in all_records if r["section"] == "other"]
    print(f"Other records: {len(other):,}")

    # Run all analyses on practitioners only
    billing_trends(practitioners)
    top_billers(practitioners)
    yoy_analysis(practitioners)
    entrants_exits(practitioners)
    inequality_analysis(practitioners)

    # Also save raw extracted data as CSV for further exploration
    output_path = Path(__file__).parent / "bluebook_raw_data.csv"
    import csv
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["fiscal_year", "payee_name", "amount_gross", "section"])
        writer.writeheader()
        for r in all_records:
            writer.writerow({k: r[k] for k in ["fiscal_year", "payee_name", "amount_gross", "section"]})
    print(f"\n\nRaw data saved to: {output_path}")


if __name__ == "__main__":
    main()
