#!/usr/bin/env python3
"""
Quantum Qanary - Q-Day Distance Estimator

Computes the Q-Day distance estimate from all signal files using a weighted
multi-factor model. This is the core analytical engine of the dashboard.

Signal weights:
  - Factoring record progress: 25% (log scale)
  - Logical qubit progress: 25% (log scale)
  - Vendor roadmap consensus: 20% (weighted avg of credible vendor target years)
  - Error correction trajectory: 10% (tier on the curated fault-tolerance ladder)
  - Investment acceleration: 10% (YoY growth rate of global funding)
  - DiVincenzo completeness: 10% (leading vendor's core criteria fulfillment)

Usage:
  python normalizers/qday_distance.py
"""

import json
import math
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "composite")


def load_json(relative_path):
    """Load a JSON file relative to the project base directory."""
    full_path = os.path.join(BASE_DIR, relative_path)
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  [WARN] File not found: {full_path}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON parse error in {full_path}: {e}", file=sys.stderr)
        return None


def compute_factoring_component(factoring_data):
    """
    Compute the factoring record progress component.

    Weight: 25%
    Uses log scale: current record bits vs 2048-bit target.
    The gap is enormous (21 bits vs 2048 bits), but progress on a log scale
    is what matters for estimating trajectory.
    """
    if not factoring_data:
        return {"weight": 0.25, "current_bits": 0, "target_bits": 2048, "progress_pct": 0.0}

    # Find the highest achieved factoring record
    current_bits = 0
    rsa_ladder = factoring_data.get("rsa_ladder", [])
    for record in rsa_ladder:
        if record.get("status") == "achieved":
            current_bits = max(current_bits, record.get("bits", 0))

    target_bits = 2048

    # Log-scale progress: log2(current) / log2(target)
    if current_bits > 0:
        progress_pct = round(
            (math.log2(current_bits) / math.log2(target_bits)) * 100, 1
        )
    else:
        progress_pct = 0.0

    return {
        "weight": 0.25,
        "current_bits": current_bits,
        "target_bits": target_bits,
        "progress_pct": progress_pct,
    }


def compute_logical_qubits_component(hardware_data):
    """
    Compute the logical qubit progress component.

    Weight: 25%
    Uses log scale: current logical qubits vs ~4000 needed for RSA-2048.
    """
    if not hardware_data:
        return {"weight": 0.25, "current": 0, "target": 4000, "progress_pct": 0.0}

    target = hardware_data.get("target_logical_qubits_for_rsa2048", 4000)

    # Find the highest demonstrated logical qubit count
    current_logical = 0
    for milestone in hardware_data.get("milestones", []):
        lq = milestone.get("logical_qubits")
        if lq is not None and lq > current_logical:
            current_logical = lq

    # Log-scale progress
    if current_logical > 0:
        progress_pct = round(
            (math.log2(current_logical + 1) / math.log2(target)) * 100, 1
        )
    else:
        progress_pct = 0.0

    return {
        "weight": 0.25,
        "current": current_logical,
        "target": target,
        "progress_pct": progress_pct,
    }


def compute_roadmap_consensus_component(roadmap_data):
    """
    Compute the vendor roadmap consensus component.

    Weight: 20%
    Weighted average of credible vendor/government target years for
    fault-tolerant quantum computing.
    """
    if not roadmap_data:
        current_year = datetime.now().year
        return {
            "weight": 0.20,
            "avg_target_year": current_year + 10,
            "years_out": 10,
        }

    current_year = datetime.now().year
    commitments = roadmap_data.get("commitments", [])

    # Weight by status: in_progress > active > announced > roadmap
    status_weights = {
        "in_progress": 3.0,
        "active": 2.5,
        "announced": 2.0,
        "roadmap": 1.0,
    }

    weighted_sum = 0.0
    total_weight = 0.0

    for commitment in commitments:
        target_year = commitment.get("target_year")
        status = commitment.get("status", "roadmap")
        if target_year is None:
            continue

        # Only include commitments related to fault-tolerant quantum or
        # large-scale systems (not migration deadlines like NIST 2035)
        entity = commitment.get("entity", "")
        comm_text = commitment.get("commitment", "").lower()
        if "migration" in comm_text or "federal" in comm_text:
            continue  # Skip migration deadlines, they are policy not capability

        w = status_weights.get(status, 1.0)
        weighted_sum += target_year * w
        total_weight += w

    if total_weight > 0:
        avg_target_year = round(weighted_sum / total_weight)
    else:
        avg_target_year = current_year + 10

    years_out = max(0, avg_target_year - current_year)

    return {
        "weight": 0.20,
        "avg_target_year": avg_target_year,
        "years_out": years_out,
    }


RUNG_POINTS = {"achieved": 1.0, "partial": 0.5, "not_yet": 0.0}

# Used when fault_tolerance.json omits tier_modifiers. Tier 1 keeps the
# 0.85 the binary model applied once below-threshold QEC was shown.
DEFAULT_TIER_MODIFIERS = {0: 1.10, 1: 0.85, 2: 0.80, 3: 0.75, 4: 0.70, 5: 0.60, 6: 0.50}


def compute_error_correction_component(hardware_data, fault_tolerance_data):
    """
    Compute the error correction trajectory component.

    Weight: 10%
    Climbs the curated fault-tolerance ladder in data/hardware/fault_tolerance.json.
    Tier = consecutive "achieved" rungs counted from rung 1; a "partial" or
    "not_yet" rung stops the count. Score (0-100) gives achieved rungs 1 point
    and partial rungs 0.5, so partial progress is visible without moving the
    tier. The tier selects the timeline modifier.

    Falls back to the old binary check (any hardware milestone flagged
    error_correction) when the ladder file is missing.
    """
    below_threshold = any(
        m.get("error_correction", False)
        for m in (hardware_data or {}).get("milestones", [])
    )

    rungs = (fault_tolerance_data or {}).get("rungs", [])
    if not rungs:
        tier = 1 if below_threshold else 0
        return {
            "weight": 0.10,
            "below_threshold_demonstrated": below_threshold,
            "tier": tier,
            "max_tier": 1,
            "tier_label": "Below-threshold error correction" if tier else "None demonstrated",
            "score": 50 if below_threshold else 0,
            "modifier": DEFAULT_TIER_MODIFIERS[tier],
            "rungs": [],
        }

    for i, rung in enumerate(rungs, 1):
        if rung.get("status") not in RUNG_POINTS or not rung.get("id") or not rung.get("label"):
            raise ValueError(
                f"fault_tolerance.json rung {i}: needs id, label, and status in "
                f"{sorted(RUNG_POINTS)} (got status={rung.get('status')!r})"
            )

    tier = 0
    for rung in rungs:
        if rung.get("status") != "achieved":
            break
        tier += 1

    points = sum(RUNG_POINTS[r["status"]] for r in rungs)
    score = round(points / len(rungs) * 100, 1)

    modifiers = {
        int(k): v for k, v in (fault_tolerance_data.get("tier_modifiers") or {}).items()
    } or DEFAULT_TIER_MODIFIERS
    modifier = modifiers.get(tier, DEFAULT_TIER_MODIFIERS.get(tier, 1.0))

    # The ladder is authoritative once it exists.
    below_threshold = any(
        r.get("id") == "below_threshold" and r.get("status") == "achieved" for r in rungs
    )

    return {
        "weight": 0.10,
        "below_threshold_demonstrated": below_threshold,
        "tier": tier,
        "max_tier": len(rungs),
        "tier_label": rungs[tier - 1].get("label") if tier else "None demonstrated",
        "score": score,
        "modifier": modifier,
        "rungs": [
            {
                "id": r.get("id"),
                "label": r.get("label"),
                "criterion": r.get("criterion"),
                "status": r.get("status", "not_yet"),
                "date": r.get("date"),
                "evidence": r.get("evidence"),
                "source": r.get("source"),
                "sources": r.get("sources") or ([r["source"]] if r.get("source") else []),
            }
            for r in rungs
        ],
    }


def compute_investment_component(funding_data):
    """
    Compute the investment acceleration component.

    Weight: 10%
    Year-over-year growth rate of global quantum computing funding.
    """
    if not funding_data:
        return {
            "weight": 0.10,
            "yoy_growth_pct": 0.0,
            "accelerating": False,
        }

    annual = funding_data.get("annual", [])
    if len(annual) < 2:
        return {
            "weight": 0.10,
            "yoy_growth_pct": 0.0,
            "accelerating": False,
        }

    # Sort by year and get the last two years
    annual_sorted = sorted(annual, key=lambda x: x.get("year", 0))
    latest = annual_sorted[-1]
    previous = annual_sorted[-2]

    latest_total = latest.get("total", 0)
    previous_total = previous.get("total", 0)

    if previous_total > 0:
        yoy_growth_pct = round(
            ((latest_total - previous_total) / previous_total) * 100, 1
        )
    else:
        yoy_growth_pct = 0.0

    # Check if acceleration is increasing (compare last 2 YoY rates)
    accelerating = False
    if len(annual_sorted) >= 3:
        prev_prev = annual_sorted[-3]
        prev_prev_total = prev_prev.get("total", 0)
        if prev_prev_total > 0:
            prev_yoy = ((previous_total - prev_prev_total) / prev_prev_total) * 100
            accelerating = yoy_growth_pct > prev_yoy

    return {
        "weight": 0.10,
        "yoy_growth_pct": yoy_growth_pct,
        "accelerating": accelerating,
    }


def compute_divincenzo_component(divincenzo_data):
    """
    Compute the DiVincenzo Criteria completeness component.

    Weight: 10% (taken from investment, which drops to 5%)
    Measures how close the leading vendor is to satisfying all 5 core criteria.
    Status scores: not_demonstrated=0, partial=1, demonstrated=2, scalable=3.
    Max possible = 15 (5 criteria x 3 points each).
    """
    if not divincenzo_data:
        return {
            "weight": 0.10,
            "leading_vendor": "Unknown",
            "core_score": 0,
            "max_score": 15,
            "progress_pct": 0.0,
        }

    status_scores = {
        "not_demonstrated": 0,
        "partial": 1,
        "demonstrated": 2,
        "scalable": 3,
    }
    core_ids = ["C1", "C2", "C3", "C4", "C5"]

    best_vendor = "Unknown"
    best_score = 0

    for vendor in divincenzo_data.get("vendors", []):
        assessments = vendor.get("assessments", {})
        score = 0
        for cid in core_ids:
            a = assessments.get(cid, {})
            score += status_scores.get(a.get("status", "not_demonstrated"), 0)
        if score > best_score:
            best_score = score
            best_vendor = vendor.get("name", "Unknown")

    max_score = 15
    progress_pct = round((best_score / max_score) * 100, 1) if max_score > 0 else 0.0

    return {
        "weight": 0.10,
        "leading_vendor": best_vendor,
        "core_score": best_score,
        "max_score": max_score,
        "progress_pct": progress_pct,
    }


def compute_qday_estimate(components):
    """
    Compute the Q-Day distance estimate from all components.

    The estimate is a range in years. The model works as follows:

    For factoring and qubits: the log-scale progress percentage tells us
    how far along the exponential curve we are. The remaining distance
    maps to a timeline based on historical rate of progress.

    For roadmaps: vendor target years provide direct timeline data.

    For error correction: the fault-tolerance ladder tier selects a modifier.

    For investment: accelerating investment compresses timelines.
    """
    factoring = components["factoring"]
    qubits = components["logical_qubits"]
    roadmap = components["roadmap_consensus"]
    error_corr = components["error_correction"]
    investment = components["investment"]
    divincenzo = components.get("divincenzo", {"weight": 0.10, "progress_pct": 0.0})

    # Base estimate from roadmap consensus (most direct signal)
    base_years = roadmap["years_out"]

    # Factoring progress modifier
    # Very low progress (< 5%) suggests we are far from cryptographic relevance
    # This pushes the estimate outward
    factoring_progress = factoring["progress_pct"] / 100.0
    if factoring_progress < 0.05:
        factoring_modifier = 1.5  # Push estimate out
    elif factoring_progress < 0.20:
        factoring_modifier = 1.2
    elif factoring_progress < 0.50:
        factoring_modifier = 1.0
    else:
        factoring_modifier = 0.7  # Compress estimate

    # Qubit progress modifier
    qubit_progress = qubits["progress_pct"] / 100.0
    if qubit_progress < 0.05:
        qubit_modifier = 1.4
    elif qubit_progress < 0.15:
        qubit_modifier = 1.1
    elif qubit_progress < 0.40:
        qubit_modifier = 0.9
    else:
        qubit_modifier = 0.7

    # Error correction modifier (from the fault-tolerance ladder tier)
    ec_modifier = error_corr["modifier"]

    # Investment modifier
    if investment["accelerating"] and investment["yoy_growth_pct"] > 15:
        inv_modifier = 0.9
    elif investment["yoy_growth_pct"] > 10:
        inv_modifier = 0.95
    else:
        inv_modifier = 1.0

    # DiVincenzo completeness modifier
    # High completeness (>80%) means hardware is nearly viable, compresses timeline
    dv_progress = divincenzo["progress_pct"] / 100.0
    if dv_progress > 0.80:
        dv_modifier = 0.8
    elif dv_progress > 0.60:
        dv_modifier = 0.9
    elif dv_progress > 0.40:
        dv_modifier = 1.0
    else:
        dv_modifier = 1.2

    # Weighted composite modifier
    composite_modifier = (
        factoring_modifier * factoring["weight"]
        + qubit_modifier * qubits["weight"]
        + 1.0 * roadmap["weight"]  # Roadmap is the base, modifier is 1.0
        + ec_modifier * error_corr["weight"]
        + inv_modifier * investment["weight"]
        + dv_modifier * divincenzo["weight"]
    ) / (
        factoring["weight"]
        + qubits["weight"]
        + roadmap["weight"]
        + error_corr["weight"]
        + investment["weight"]
        + divincenzo["weight"]
    )

    # Apply modifier to base
    midpoint = round(base_years * composite_modifier, 1)

    # Uncertainty range: +/- 30% of midpoint, minimum 2 years spread
    spread = max(2.0, midpoint * 0.3)
    low_years = max(1, round(midpoint - spread / 2))
    high_years = round(midpoint + spread / 2)

    return {
        "low_years": low_years,
        "high_years": high_years,
        "midpoint_years": midpoint,
    }


def main():
    print("Computing Q-Day distance estimate...")
    print(f"Base directory: {BASE_DIR}")

    # Load all signal files
    print("\nLoading signal files:")

    factoring_data = load_json("data/factoring/records.json")
    print(f"  factoring/records.json: {'loaded' if factoring_data else 'MISSING'}")

    hardware_data = load_json("data/hardware/qubit_records.json")
    print(f"  hardware/qubit_records.json: {'loaded' if hardware_data else 'MISSING'}")

    roadmap_data = load_json("data/roadmaps/commitments.json")
    print(f"  roadmaps/commitments.json: {'loaded' if roadmap_data else 'MISSING'}")

    funding_data = load_json("data/funding/investments.json")
    print(f"  funding/investments.json: {'loaded' if funding_data else 'MISSING'}")

    divincenzo_data = load_json("data/hardware/divincenzo.json")
    print(f"  hardware/divincenzo.json: {'loaded' if divincenzo_data else 'MISSING'}")

    fault_tolerance_data = load_json("data/hardware/fault_tolerance.json")
    print(f"  hardware/fault_tolerance.json: {'loaded' if fault_tolerance_data else 'MISSING'}")
    # The ladder is authoritative: only a genuinely absent file may fall back.
    if os.path.exists(os.path.join(BASE_DIR, "data", "hardware", "fault_tolerance.json")):
        rungs = (fault_tolerance_data or {}).get("rungs") if isinstance(fault_tolerance_data, dict) else None
        if not isinstance(rungs, list) or not rungs:
            sys.exit("ERROR: data/hardware/fault_tolerance.json is unreadable or has no rungs")

    # Compute each component
    print("\nComputing components:")

    factoring_component = compute_factoring_component(factoring_data)
    print(
        f"  Factoring: {factoring_component['current_bits']} bits / "
        f"{factoring_component['target_bits']} target = "
        f"{factoring_component['progress_pct']}% (log scale)"
    )

    qubits_component = compute_logical_qubits_component(hardware_data)
    print(
        f"  Logical qubits: {qubits_component['current']} / "
        f"{qubits_component['target']} target = "
        f"{qubits_component['progress_pct']}% (log scale)"
    )

    roadmap_component = compute_roadmap_consensus_component(roadmap_data)
    print(
        f"  Roadmap consensus: avg target year {roadmap_component['avg_target_year']}, "
        f"{roadmap_component['years_out']} years out"
    )

    error_corr_component = compute_error_correction_component(hardware_data, fault_tolerance_data)
    print(
        f"  Error correction: tier {error_corr_component['tier']}/"
        f"{error_corr_component['max_tier']} ({error_corr_component['tier_label']}), "
        f"score = {error_corr_component['score']}, "
        f"modifier = {error_corr_component['modifier']}"
    )

    investment_component = compute_investment_component(funding_data)
    print(
        f"  Investment: {investment_component['yoy_growth_pct']}% YoY, "
        f"accelerating = {investment_component['accelerating']}"
    )

    divincenzo_component = compute_divincenzo_component(divincenzo_data)
    print(
        f"  DiVincenzo: {divincenzo_component['leading_vendor']} leads "
        f"{divincenzo_component['core_score']}/{divincenzo_component['max_score']} = "
        f"{divincenzo_component['progress_pct']}%"
    )

    # Assemble components
    components = {
        "factoring": factoring_component,
        "logical_qubits": qubits_component,
        "roadmap_consensus": roadmap_component,
        "error_correction": error_corr_component,
        "investment": investment_component,
        "divincenzo": divincenzo_component,
    }

    # Compute estimate
    estimate = compute_qday_estimate(components)

    print(f"\nQ-Day Estimate:")
    print(f"  Low:      {estimate['low_years']} years")
    print(f"  Midpoint: {estimate['midpoint_years']} years")
    print(f"  High:     {estimate['high_years']} years")

    # Build output
    today = datetime.now().strftime("%Y-%m-%d")
    output = {
        "metadata": {"last_updated": today},
        "estimate": estimate,
        "components": components,
        "caveat": (
            "This estimate reflects current trajectory. Quantum progress is "
            "nonlinear -- breakthroughs can compress timelines rapidly."
        ),
    }

    # Write output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "qday_distance.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nOutput written to {output_path}")


if __name__ == "__main__":
    main()
