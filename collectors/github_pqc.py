#!/usr/bin/env python3
"""
Quantum Qanary - GitHub PQC Activity Collector

Tracks GitHub activity for post-quantum cryptography libraries and repositories.

Tracked repos:
  - open-quantum-safe/liboqs
  - pq-crystals/kyber
  - pq-crystals/dilithium
  - Topic search: "post-quantum-cryptography"

Usage:
  python collectors/github_pqc.py                          # Live (needs GITHUB_TOKEN)
  python collectors/github_pqc.py --mock                   # Mock data
  python collectors/github_pqc.py --token ghp_xxx          # Explicit token
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "github_pqc", "processed")
RAW_DIR = os.path.join(BASE_DIR, "data", "github_pqc", "raw")

GITHUB_API_BASE = "https://api.github.com"

TRACKED_REPOS = [
    "open-quantum-safe/liboqs",
    "pq-crystals/kyber",
    "pq-crystals/dilithium",
]

TOPIC_QUERY = "post-quantum-cryptography"


def github_request(path, token=None, params=None):
    """Make an authenticated request to the GitHub API."""
    if params:
        query_string = urllib.parse.urlencode(params)
        url = f"{GITHUB_API_BASE}{path}?{query_string}"
    else:
        url = f"{GITHUB_API_BASE}{path}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "QuantumQanary/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            remaining = response.headers.get("X-RateLimit-Remaining", "?")
            reset_time = response.headers.get("X-RateLimit-Reset", "")
            data = json.loads(response.read().decode("utf-8"))

            # Rate limit awareness
            if remaining != "?" and int(remaining) < 10:
                if reset_time:
                    wait_until = int(reset_time)
                    wait_seconds = max(0, wait_until - int(time.time())) + 1
                    print(
                        f"  [RATE LIMIT] Only {remaining} requests remaining. "
                        f"Waiting {wait_seconds}s for reset...",
                        file=sys.stderr,
                    )
                    time.sleep(wait_seconds)

            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"  [ERROR] GitHub API {e.code}: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [ERROR] Request failed: {e}", file=sys.stderr)
        return None


def fetch_repo_info(repo_full_name, token=None):
    """Fetch detailed info for a specific repository."""
    data = github_request(f"/repos/{repo_full_name}", token=token)
    if not data:
        return None

    return {
        "name": data.get("full_name", repo_full_name),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0),
        "last_push": (data.get("pushed_at", "")[:10] if data.get("pushed_at") else ""),
    }


def fetch_topic_stats(token=None):
    """Fetch aggregate stats for the post-quantum-cryptography topic."""
    data = github_request(
        "/search/repositories",
        token=token,
        params={"q": f"topic:{TOPIC_QUERY}", "per_page": 1, "sort": "stars"},
    )
    if not data:
        return {"total_repos": 0, "total_stars": 0}

    total_repos = data.get("total_count", 0)

    # Fetch top repos to estimate total stars
    top_data = github_request(
        "/search/repositories",
        token=token,
        params={
            "q": f"topic:{TOPIC_QUERY}",
            "per_page": 100,
            "sort": "stars",
            "order": "desc",
        },
    )
    time.sleep(2)  # Respect search rate limit

    total_stars = 0
    if top_data and "items" in top_data:
        total_stars = sum(
            item.get("stargazers_count", 0) for item in top_data["items"]
        )

    return {"total_repos": total_repos, "total_stars": total_stars}


def fetch_monthly_activity(token=None, years_back=3):
    """Estimate monthly new repo creation for the PQC topic."""
    monthly = []
    today = datetime.now()

    for i in range(years_back * 12):
        dt = today - timedelta(days=(years_back * 12 - 1 - i) * 30.44)
        year = dt.year
        month = dt.month
        month_str = f"{year:04d}-{month:02d}"

        # Calculate date range
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"

        # Search for repos created in this month
        query = f"topic:{TOPIC_QUERY} created:{start_date}..{end_date}"
        data = github_request(
            "/search/repositories",
            token=token,
            params={"q": query, "per_page": 1},
        )
        time.sleep(2)  # Search API has stricter rate limits

        new_repos = data.get("total_count", 0) if data else 0
        monthly.append({
            "date": month_str,
            "new_repos": new_repos,
            "total_stars_delta": 0,  # Would need historical data to compute
        })

        print(f"  {month_str}: {new_repos} new repos")

    return monthly


def fetch_live_data(token):
    """Fetch all live data from GitHub API."""
    repos = []
    for repo_name in TRACKED_REPOS:
        print(f"Fetching repo: {repo_name}")
        info = fetch_repo_info(repo_name, token=token)
        if info:
            repos.append(info)
        else:
            repos.append({
                "name": repo_name,
                "stars": 0,
                "forks": 0,
                "open_issues": 0,
                "last_push": "",
            })
        time.sleep(1)

    print("Fetching topic stats...")
    topic_stats = fetch_topic_stats(token=token)
    time.sleep(1)

    print("Fetching monthly activity...")
    monthly_activity = fetch_monthly_activity(token=token)

    return repos, topic_stats, monthly_activity


def generate_mock_data():
    """Generate realistic mock data for testing."""
    random.seed(42)
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    repos = [
        {
            "name": "open-quantum-safe/liboqs",
            "stars": 1850 + random.randint(-50, 50),
            "forks": 450 + random.randint(-20, 20),
            "open_issues": 120 + random.randint(-10, 10),
            "last_push": (today - timedelta(days=random.randint(0, 3))).strftime(
                "%Y-%m-%d"
            ),
        },
        {
            "name": "pq-crystals/kyber",
            "stars": 820 + random.randint(-30, 30),
            "forks": 280 + random.randint(-15, 15),
            "open_issues": 35 + random.randint(-5, 5),
            "last_push": (today - timedelta(days=random.randint(0, 7))).strftime(
                "%Y-%m-%d"
            ),
        },
        {
            "name": "pq-crystals/dilithium",
            "stars": 640 + random.randint(-25, 25),
            "forks": 195 + random.randint(-10, 10),
            "open_issues": 22 + random.randint(-5, 5),
            "last_push": (today - timedelta(days=random.randint(0, 10))).strftime(
                "%Y-%m-%d"
            ),
        },
    ]

    topic_stats = {
        "total_repos": 350 + random.randint(-20, 20),
        "total_stars": 25000 + random.randint(-500, 500),
    }

    # Monthly activity with growth trend
    monthly_activity = []
    base_new_repos = 8
    for i in range(36):
        dt = today - timedelta(days=(35 - i) * 30.44)
        month_str = f"{dt.year:04d}-{dt.month:02d}"

        growth = 1 + (i * 0.03)
        seasonal = 1.0
        if dt.month in (6, 7, 8):
            seasonal = 0.75
        elif dt.month == 12:
            seasonal = 0.85

        new_repos = max(
            1, round(base_new_repos * growth * seasonal * random.gauss(1.0, 0.25))
        )
        stars_delta = max(
            0, round(new_repos * random.uniform(20, 50) + random.gauss(200, 80))
        )

        monthly_activity.append({
            "date": month_str,
            "new_repos": new_repos,
            "total_stars_delta": stars_delta,
        })

    return repos, topic_stats, monthly_activity


def save_raw_response(filename, data):
    """Save raw API response with timestamp."""
    os.makedirs(RAW_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(RAW_DIR, f"{filename}_{timestamp}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def build_output(repos, topic_stats, monthly_activity, is_mock):
    """Build the output JSON structure."""
    today = datetime.now().strftime("%Y-%m-%d")

    return {
        "metadata": {
            "source": "GitHub API",
            "last_updated": today,
            "mock": is_mock,
        },
        "repos": repos,
        "topic_stats": topic_stats,
        "monthly_activity": monthly_activity,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Track GitHub activity for PQC libraries"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate realistic mock data instead of calling GitHub API",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    if args.mock:
        print("Running in MOCK mode -- generating realistic test data")
        repos, topic_stats, monthly_activity = generate_mock_data()
    else:
        token = args.token or os.environ.get("GITHUB_TOKEN")
        if not token:
            print(
                "[WARN] No GitHub token provided. API rate limits will be very low.",
                file=sys.stderr,
            )
            print(
                "  Set GITHUB_TOKEN env var or use --token flag.",
                file=sys.stderr,
            )

        print("Running in LIVE mode -- fetching from GitHub API")
        repos, topic_stats, monthly_activity = fetch_live_data(token)

        # Save raw data
        save_raw_response("repos", repos)
        save_raw_response("topic_stats", topic_stats)
        save_raw_response("monthly_activity", monthly_activity)

    output = build_output(repos, topic_stats, monthly_activity, is_mock=args.mock)

    output_path = os.path.join(OUTPUT_DIR, "activity.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nOutput written to {output_path}")

    # Print summary
    for repo in repos:
        print(f"  {repo['name']}: {repo['stars']} stars, {repo['forks']} forks")
    print(f"  Topic repos: {topic_stats['total_repos']}, stars: {topic_stats['total_stars']}")


if __name__ == "__main__":
    main()
