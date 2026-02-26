#!/usr/bin/env python3
"""
Quantum Qanary - arXiv Quantum Paper Collector

Fetches quantum computing paper counts from the arXiv Atom API.
Tracks three search categories over the last 3 years, counting papers per month.

Categories:
  - shor_implementation: Shor's algorithm AND (implementation OR factoring) in quant-ph
  - pqc_deployment: post-quantum AND (migration OR deployment) in cs.CR
  - error_correction: quantum error correction AND logical qubit in quant-ph

Usage:
  python collectors/arxiv_quantum.py          # Live API fetch
  python collectors/arxiv_quantum.py --mock   # Generate realistic mock data
"""

import argparse
import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "arxiv", "processed")
RAW_DIR = os.path.join(BASE_DIR, "data", "arxiv", "raw")

ARXIV_API_URL = "http://export.arxiv.org/api/query"
RATE_LIMIT_SECONDS = 3

# Atom XML namespace
ATOM_NS = "{http://www.w3.org/2005/Atom}"
OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"

CATEGORIES = {
    "shor_implementation": {
        "label": "Shor's Algorithm Implementation",
        "query": 'all:"Shor\'s algorithm" AND (all:implementation OR all:factoring)',
        "arxiv_cat": "quant-ph",
    },
    "pqc_deployment": {
        "label": "PQC Migration & Deployment",
        "query": "all:post-quantum AND (all:migration OR all:deployment)",
        "arxiv_cat": "cs.CR",
    },
    "error_correction": {
        "label": "Quantum Error Correction",
        "query": 'all:"quantum error correction" AND all:"logical qubit"',
        "arxiv_cat": "quant-ph",
    },
}


def generate_month_range(years_back=3):
    """Generate a list of (year, month) tuples for the last N years."""
    today = datetime.now()
    months = []
    for i in range(years_back * 12):
        dt = today - timedelta(days=i * 30.44)
        ym = (dt.year, dt.month)
        if ym not in [m for m in months]:
            months.append(ym)
    months.sort()
    return months


def format_month(year, month):
    """Format year/month as YYYY-MM string."""
    return f"{year:04d}-{month:02d}"


def build_arxiv_query(category_key, year, month):
    """Build an arXiv API query URL for a specific category and month."""
    cat_info = CATEGORIES[category_key]
    search_query = cat_info["query"]
    arxiv_cat = cat_info["arxiv_cat"]

    # Calculate date range for the month
    start_date = f"{year:04d}{month:02d}01"
    if month == 12:
        end_year = year + 1
        end_month = 1
    else:
        end_year = year
        end_month = month + 1
    end_date = f"{end_year:04d}{end_month:02d}01"

    # arXiv uses submittedDate for date range filtering
    date_filter = f" AND submittedDate:[{start_date}0000 TO {end_date}0000]"
    full_query = f"cat:{arxiv_cat} AND {search_query}{date_filter}"

    params = urllib.parse.urlencode({
        "search_query": full_query,
        "start": 0,
        "max_results": 0,  # We only need the total count
    })
    return f"{ARXIV_API_URL}?{params}"


def fetch_paper_count(url):
    """Fetch paper count from arXiv API for a given query URL."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "QuantumQanary/1.0 (research dashboard; https://github.com/quantum-qanary)"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            xml_data = response.read().decode("utf-8")
    except Exception as e:
        print(f"  [WARN] Request failed: {e}", file=sys.stderr)
        return 0, None

    # Parse total results from Atom feed
    try:
        root = ET.fromstring(xml_data)
        total_el = root.find(f"{OPENSEARCH_NS}totalResults")
        if total_el is not None:
            return int(total_el.text), xml_data
        # Fallback: count entry elements
        entries = root.findall(f"{ATOM_NS}entry")
        return len(entries), xml_data
    except ET.ParseError as e:
        print(f"  [WARN] XML parse error: {e}", file=sys.stderr)
        return 0, xml_data


def fetch_live_data(months):
    """Fetch live data from arXiv API for all categories and months."""
    results = {}
    for cat_key in CATEGORIES:
        results[cat_key] = {}
        print(f"Fetching category: {CATEGORIES[cat_key]['label']}")

        for year, month in months:
            month_str = format_month(year, month)
            url = build_arxiv_query(cat_key, year, month)
            count, raw_xml = fetch_paper_count(url)
            results[cat_key][month_str] = count
            print(f"  {month_str}: {count} papers")

            # Save raw response
            if raw_xml:
                raw_path = os.path.join(
                    RAW_DIR,
                    f"{cat_key}_{month_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                )
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(raw_xml)

            # Rate limit: 1 request per 3 seconds
            time.sleep(RATE_LIMIT_SECONDS)

    return results


def generate_mock_data(months):
    """Generate realistic mock data for testing without API calls."""
    random.seed(42)
    results = {}

    # Base rates and growth curves per category
    profiles = {
        "shor_implementation": {
            "base": 3,
            "growth": 0.02,
            "variance": 0.4,
            "seasonal": True,
        },
        "pqc_deployment": {
            "base": 8,
            "growth": 0.05,
            "variance": 0.3,
            "seasonal": True,
        },
        "error_correction": {
            "base": 5,
            "growth": 0.04,
            "variance": 0.35,
            "seasonal": True,
        },
    }

    for cat_key, profile in profiles.items():
        results[cat_key] = {}
        for idx, (year, month) in enumerate(months):
            month_str = format_month(year, month)

            # Growth trend (exponential-ish)
            trend = profile["base"] * (1 + profile["growth"]) ** idx

            # Seasonal dip in summer months and December
            seasonal = 1.0
            if profile["seasonal"]:
                if month in (6, 7, 8):
                    seasonal = 0.7
                elif month == 12:
                    seasonal = 0.8
                elif month in (1, 9, 10):
                    seasonal = 1.15

            # Random variance
            noise = random.gauss(1.0, profile["variance"])
            noise = max(0.3, noise)

            count = max(0, round(trend * seasonal * noise))
            results[cat_key][month_str] = count

    return results


def build_output(results, months, is_mock):
    """Build the output JSON structure from collected results."""
    today = datetime.now().strftime("%Y-%m-%d")

    categories = {}
    for cat_key, cat_info in CATEGORIES.items():
        monthly = []
        for year, month in months:
            month_str = format_month(year, month)
            count = results.get(cat_key, {}).get(month_str, 0)
            monthly.append({"date": month_str, "count": count})
        categories[cat_key] = {
            "label": cat_info["label"],
            "monthly": monthly,
        }

    # Aggregate across all categories
    aggregate = []
    for year, month in months:
        month_str = format_month(year, month)
        total = sum(
            results.get(cat_key, {}).get(month_str, 0)
            for cat_key in CATEGORIES
        )
        aggregate.append({"date": month_str, "total": total})

    return {
        "metadata": {
            "source": "arxiv API",
            "last_updated": today,
            "mock": is_mock,
        },
        "categories": categories,
        "aggregate": aggregate,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch quantum computing paper counts from arXiv"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate realistic mock data instead of calling the API",
    )
    args = parser.parse_args()

    # Ensure output directories exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    months = generate_month_range(years_back=3)

    if args.mock:
        print("Running in MOCK mode -- generating realistic test data")
        results = generate_mock_data(months)
    else:
        print("Running in LIVE mode -- fetching from arXiv API")
        print(f"Rate limit: {RATE_LIMIT_SECONDS}s between requests")
        print(f"Total requests: ~{len(months) * len(CATEGORIES)}")
        results = fetch_live_data(months)

    output = build_output(results, months, is_mock=args.mock)

    output_path = os.path.join(OUTPUT_DIR, "paper_counts.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nOutput written to {output_path}")

    # Print summary
    for cat_key, cat_data in output["categories"].items():
        total = sum(m["count"] for m in cat_data["monthly"])
        print(f"  {cat_data['label']}: {total} papers over {len(cat_data['monthly'])} months")

    agg_total = sum(m["total"] for m in output["aggregate"])
    print(f"  Aggregate total: {agg_total}")


if __name__ == "__main__":
    main()
