#!/usr/bin/env python3
"""
Quantum Qanary - Alert Level Checker

Reads all data files and recalculates the alert level based on triggered
milestones. Compares against data/alerts/status.json.

If 'override' is set in status.json, the override level is preserved.
Otherwise, the alert level is computed from triggered milestones.

This is a safety check -- it validates the alert level but does not
override manual curation without the override field being explicitly set.

Usage:
  python collectors/alert_checker.py
  python collectors/alert_checker.py --dry-run   # Print result without writing
"""

import argparse
import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Alert level hierarchy (ascending severity)
ALERT_LEVELS = ["GREEN", "YELLOW", "ORANGE", "RED"]


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


def level_index(level):
    """Get the numeric index for an alert level (higher = more severe)."""
    try:
        return ALERT_LEVELS.index(level.upper())
    except ValueError:
        return 0


def check_factoring_milestones(factoring_data):
    """Check factoring records for alert-triggering milestones."""
    triggers = []
    if not factoring_data:
        return triggers

    for record in factoring_data.get("rsa_ladder", []):
        if record.get("status") == "achieved" and record.get("canary"):
            triggers.append({
                "source": "factoring",
                "event": f"RSA-{record['bits']} factored via quantum (canary milestone)",
                "level": "RED",
                "bits": record.get("bits"),
            })
        elif record.get("status") == "achieved" and record.get("bits", 0) >= 100:
            triggers.append({
                "source": "factoring",
                "event": f"{record['bits']}-bit quantum factoring achieved",
                "level": "ORANGE",
                "bits": record.get("bits"),
            })

    max_ecdlp_bits = 0
    for record in factoring_data.get("ecdlp_ladder", []):
        if record.get("status") == "achieved":
            bits = record.get("bits", 0)
            if bits > max_ecdlp_bits:
                max_ecdlp_bits = bits
        if record.get("status") == "achieved" and record.get("canary"):
            triggers.append({
                "source": "factoring",
                "event": f"{record['bits']}-bit ECDLP solved via quantum (canary milestone)",
                "level": "RED",
                "bits": record.get("bits"),
            })

    if max_ecdlp_bits >= 1:
        triggers.append({
            "source": "factoring",
            "event": f"First non-trivial quantum ECDLP attack demonstrated ({max_ecdlp_bits}-bit)",
            "level": "YELLOW",
            "bits": max_ecdlp_bits,
        })

    return triggers


def check_hardware_milestones(hardware_data):
    """Check hardware milestones for alert-triggering events."""
    triggers = []
    if not hardware_data:
        return triggers

    # Check for error correction breakthroughs
    for milestone in hardware_data.get("milestones", []):
        if milestone.get("error_correction"):
            triggers.append({
                "source": "hardware",
                "event": (
                    f"{milestone.get('vendor', 'Unknown')} demonstrates "
                    f"below-threshold error correction ({milestone.get('event', '')})"
                ),
                "level": "YELLOW",
                "date": milestone.get("date"),
            })

    # Check logical qubit counts
    max_logical = 0
    for milestone in hardware_data.get("milestones", []):
        lq = milestone.get("logical_qubits")
        if lq is not None and lq > max_logical:
            max_logical = lq

    target = hardware_data.get("target_logical_qubits_for_rsa2048", 4000)
    if max_logical >= target:
        triggers.append({
            "source": "hardware",
            "event": f"Logical qubit count ({max_logical}) reaches RSA-2048 target ({target})",
            "level": "RED",
        })
    elif max_logical >= target * 0.1:
        triggers.append({
            "source": "hardware",
            "event": f"Logical qubit count ({max_logical}) reaches 10% of RSA-2048 target",
            "level": "ORANGE",
        })
    elif max_logical >= 1:
        triggers.append({
            "source": "hardware",
            "event": f"First logical qubit demonstrated ({max_logical} logical qubits)",
            "level": "YELLOW",
        })

    return triggers


def check_roadmap_milestones(roadmap_data):
    """Check vendor roadmap commitments for timeline compression."""
    triggers = []
    if not roadmap_data:
        return triggers

    current_year = datetime.now().year

    for commitment in roadmap_data.get("commitments", []):
        target_year = commitment.get("target_year")
        status = commitment.get("status")
        entity = commitment.get("entity", "Unknown")
        comm_text = commitment.get("commitment", "")

        if target_year is None:
            continue

        # Skip migration deadlines (policy, not capability)
        if "migration" in comm_text.lower() or "federal" in comm_text.lower():
            continue

        years_out = target_year - current_year
        if years_out <= 0 and status in ("in_progress", "active"):
            triggers.append({
                "source": "roadmap",
                "event": f"{entity} target year {target_year} has arrived for: {comm_text}",
                "level": "ORANGE",
            })
        elif years_out <= 2 and status in ("in_progress", "active"):
            triggers.append({
                "source": "roadmap",
                "event": (
                    f"{entity} fault-tolerant target ({target_year}) is "
                    f"{years_out} years away, status: {status}"
                ),
                "level": "YELLOW",
            })

    return triggers


def check_insurance_signals(insurance_data):
    """Check insurance signals for PQC requirements (ORANGE trigger)."""
    triggers = []
    if not insurance_data:
        return triggers

    status = insurance_data.get("status", "no_requirements")
    if status != "no_requirements":
        triggers.append({
            "source": "insurance",
            "event": f"Insurance carriers detecting PQC requirements: {insurance_data.get('status_label', status)}",
            "level": "ORANGE",
        })

    events = insurance_data.get("events", [])
    for event in events:
        triggers.append({
            "source": "insurance",
            "event": event.get("description", "Insurance signal detected"),
            "level": "ORANGE",
        })

    return triggers


def check_existing_triggers(status_data):
    """Extract existing manually curated triggers."""
    triggers = []
    if not status_data:
        return triggers

    for triggered in status_data.get("triggered", []):
        triggers.append({
            "source": "curated",
            "event": triggered.get("event", ""),
            "level": triggered.get("level", "YELLOW"),
            "date": triggered.get("date"),
        })

    return triggers


def compute_alert_level(all_triggers):
    """Compute the overall alert level from all triggers."""
    if not all_triggers:
        return "GREEN"

    max_level = "GREEN"
    for trigger in all_triggers:
        trigger_level = trigger.get("level", "GREEN")
        if level_index(trigger_level) > level_index(max_level):
            max_level = trigger_level

    return max_level


def main():
    parser = argparse.ArgumentParser(
        description="Check and recalculate alert level from all data signals"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without writing to status.json",
    )
    args = parser.parse_args()

    print("Alert Checker -- scanning all data signals")
    print(f"Base directory: {BASE_DIR}")

    # Load all data files
    print("\nLoading data files:")

    status_data = load_json("data/alerts/status.json")
    print(f"  alerts/status.json: {'loaded' if status_data else 'MISSING'}")

    factoring_data = load_json("data/factoring/records.json")
    print(f"  factoring/records.json: {'loaded' if factoring_data else 'MISSING'}")

    hardware_data = load_json("data/hardware/qubit_records.json")
    print(f"  hardware/qubit_records.json: {'loaded' if hardware_data else 'MISSING'}")

    roadmap_data = load_json("data/roadmaps/commitments.json")
    print(f"  roadmaps/commitments.json: {'loaded' if roadmap_data else 'MISSING'}")

    insurance_data = load_json("data/insurance/signals.json")
    print(f"  insurance/signals.json: {'loaded' if insurance_data else 'MISSING'}")

    # Check for override
    if status_data and status_data.get("override"):
        override_level = status_data["override"]
        print(f"\n*** OVERRIDE SET: {override_level} ***")
        print("  Manual override is in effect. Computed level will be logged but not applied.")
        print("  Remove 'override' from status.json to use computed level.")

    # Collect triggers from all sources
    print("\nScanning for triggers:")

    all_triggers = []

    # Include existing curated triggers
    curated = check_existing_triggers(status_data)
    print(f"  Curated triggers: {len(curated)}")
    all_triggers.extend(curated)

    factoring_triggers = check_factoring_milestones(factoring_data)
    print(f"  Factoring triggers: {len(factoring_triggers)}")
    all_triggers.extend(factoring_triggers)

    hardware_triggers = check_hardware_milestones(hardware_data)
    print(f"  Hardware triggers: {len(hardware_triggers)}")
    all_triggers.extend(hardware_triggers)

    roadmap_triggers = check_roadmap_milestones(roadmap_data)
    print(f"  Roadmap triggers: {len(roadmap_triggers)}")
    all_triggers.extend(roadmap_triggers)

    insurance_triggers = check_insurance_signals(insurance_data)
    print(f"  Insurance triggers: {len(insurance_triggers)}")
    all_triggers.extend(insurance_triggers)

    # Compute alert level
    computed_level = compute_alert_level(all_triggers)
    print(f"\nComputed alert level: {computed_level}")

    # Determine effective level
    if status_data and status_data.get("override"):
        effective_level = status_data["override"]
        print(f"Effective level (override): {effective_level}")
    else:
        effective_level = computed_level
        print(f"Effective level (computed): {effective_level}")

    # Check if level changed
    current_level = status_data.get("current_level", "GREEN") if status_data else "GREEN"
    if effective_level != current_level:
        print(f"\n*** ALERT LEVEL CHANGE: {current_level} -> {effective_level} ***")
    else:
        print(f"\nAlert level unchanged: {effective_level}")

    # Print all triggers
    print(f"\nAll triggers ({len(all_triggers)}):")
    for trigger in all_triggers:
        print(f"  [{trigger['level']}] {trigger['event']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    # Update status.json
    if status_data is None:
        status_data = {
            "metadata": {
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "source": "manual curation + computed",
            },
            "current_level": effective_level,
            "override": None,
            "levels": {
                "GREEN": {
                    "label": "Monitoring",
                    "description": "No canary milestones triggered.",
                },
                "YELLOW": {
                    "label": "Milestones Triggered",
                    "description": "Significant milestones confirm quantum progress.",
                },
                "ORANGE": {
                    "label": "Watch Closely",
                    "description": "Timeline compressing. Conditions forming.",
                },
                "RED": {
                    "label": "Canary Down",
                    "description": "Cryptographically relevant quantum factoring demonstrated.",
                },
            },
            "triggered": [],
            "watch_items": [],
        }

    # Update fields
    status_data["current_level"] = effective_level
    status_data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    status_data["metadata"]["last_checked"] = datetime.now().strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    status_data["metadata"]["computed_level"] = computed_level

    # Write updated status
    output_path = os.path.join(BASE_DIR, "data", "alerts", "status.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)
    print(f"\nStatus written to {output_path}")


if __name__ == "__main__":
    main()
