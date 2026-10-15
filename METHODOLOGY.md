# Methodology

How The Quantum Qanary computes alert levels, Q-Day distance estimates, and risk assessments.

## Alert Level System

The alert level is determined by observable milestones, not predictions. Each level has specific trigger conditions:

### GREEN — Business as Usual
No quantum computer has factored anything beyond 21 bits using Shor's algorithm. PQC standards are published but adoption is voluntary. No urgency signals.

### YELLOW — Early Warning
**Triggered when any of these occur:**
- NIST publishes final PQC standards (occurred August 2024)
- A major vendor demonstrates below-threshold quantum error correction (occurred December 2024)
- A government announces a funded fault-tolerant quantum program (occurred November 2024)
- A major blockchain forms a dedicated PQC team (occurred January 2026)
- First non-trivial quantum ECDLP attack demonstrated (not yet occurred — the April 2026 Project Eleven Q-Day Prize 15-bit claim was refuted: random bits in place of the quantum output still recover the key)
- First verified AI-discovered break of a standardization-track cryptographic scheme (occurred July 2026 — Anthropic's Claude Mythos Preview cut HAWK-256 key recovery from ~2^64 to ~2^38; HAWK withdrawn from NIST). Classical/AI axis — see below.

**Current status: YELLOW** — Multiple YELLOW triggers have fired.

### ORANGE — Elevated Concern
**Triggered when any of these occur:**
- Quantum factoring reaches ~100-bit semiprimes
- Insurance carriers begin requiring PQC readiness on applications
- A government mandates PQC migration with enforcement deadlines (occurred June 2026 — US EO 14412 + OMB M-26-15: HVA key establishment by 2030, digital signatures by 2031, full federal migration by 2035) — code-backed by `data/policy/mandates.json` via `check_government_milestones()` in `alert_checker.py`
- Logical qubit counts exceed 100 on a single platform

**Current status: ORANGE** — A government (US federal) has mandated PQC migration with enforceable deadlines (June 22, 2026). This is a policy/ecosystem indicator: the Q-Day hardware-distance estimate is deliberately left unchanged, because these orders contain no new qubit count, factoring result, or cryptographically-relevant-quantum-computer timeline. Threat-capability and policy-response are tracked on separate axes.

### RED — Critical
**Triggered when any of these occur:**
- RSA-512 broken by quantum computer (the canary)
- 128-bit ECDLP solved by quantum computer (blockchain canary)
- Any currently-deployed encryption scheme broken by quantum attack
- Practical key recovery against a deployed primitive (e.g. secp256k1 ECDSA) by a classical or AI-found attack — watch item, applied via manual override (see below)

### Classical & AI Cryptanalysis Axis
The canary's ladders count quantum results only. But the keys the canary protects fail the same way whether a quantum computer or a classical algorithm breaks them, and AI-driven mathematics made the classical path a live concern in 2026. This axis tracks it separately, in `ai_cryptanalysis` in `data/factoring/records.json`:

- Entries carry a status of `context`, `claimed`, `unverified`, or `verified`, plus `deployed_target` (whether the attacked scheme protects real assets today).
- Entries never advance the quantum ladders and never feed the Q-Day distance estimate.
- No code path computes an alert from this axis yet. A verified break of a standardization-track scheme was recorded as a YELLOW trigger by hand. Public cryptanalytic progress against a deployed primitive is an ORANGE watch item. Practical key recovery against a deployed primitive is a RED watch item. Apply both through `override` when they occur.

### Manual Override
The `data/alerts/status.json` file has an `override` field. Setting it to a level (e.g., "ORANGE") forces the dashboard to that level regardless of computed triggers. Set to `null` to return to computed level.

## Q-Day Distance Estimate

The Q-Day distance is a weighted composite of six signals, expressed as a range in years (`normalizers/qday_distance.py`):

| Component | Weight | What It Measures | Modifier Input |
|-----------|--------|-----------------|-----------------|
| **Factoring Progress** | 25% | Largest number factored by quantum Shor's (bits) relative to 2048-bit target | log₂ scale progress |
| **Logical Qubits** | 25% | Demonstrated logical qubits vs. ~4,000 needed for RSA-2048 | log₂ scale progress |
| **Roadmap Consensus** | 20% | Status-weighted average target year for fault-tolerant quantum from major vendors/governments | Sets the base, in years from now |
| **Fault Tolerance** | 10% | Tier reached on the fault-tolerance ladder (below) | Ladder tier |
| **Investment Trend** | 10% | Year-over-year growth in global quantum computing investment | Growth rate signal |
| **DiVincenzo Completeness** | 10% | Leading vendor's score on the five core DiVincenzo criteria | Completeness % |

### Calculation

Roadmap consensus sets the base estimate in years. Each other component maps to a timeline modifier: below 1.0 compresses the estimate and above 1.0 pushes it out. Roadmap consensus contributes a fixed 1.0. The composite modifier is the weight-averaged modifier:

```
composite = Σ (modifier × weight) / Σ weight
midpoint  = roadmap_years_out × composite
range     = midpoint ± max(2, 0.3 × midpoint) / 2
```

The midpoint is the default for Mosca's Theorem calculator.

### Fault-Tolerance Ladder

Until October 2026 this component was binary: had below-threshold error correction been demonstrated? That flag was set by Willow in December 2024 and could not register later progress. The component now climbs a curated, sourced ladder in `data/hardware/fault_tolerance.json`:

| Tier | Rung | Criterion |
|------|------|-----------|
| 1 | Below-threshold error correction | Logical error falls as code distance grows |
| 2 | Fault-tolerant logical magic states | Magic (T) states prepared in an error-correcting code with error below the physical gate error |
| 3 | Break-even logical non-Clifford gate in a circuit | A magic-state-fed logical non-Clifford gate beats the physical gate inside a fault-tolerant circuit |
| 4 | Algorithm-grade magic states | T states at or below 1e-6 error, at a usable acceptance rate |
| 5 | Magic-state-fed logical computation | At least 100 logical non-Clifford gates in one error-corrected circuit with real-time decoding |
| 6 | CRQC-class fault tolerance | About 1,000+ logical qubits with T-state throughput sufficient for ECDLP-256 or RSA-2048 |

Each rung is `achieved`, `partial`, or `not_yet`, with a date, evidence, and source.

- **Tier** is the number of consecutive `achieved` rungs counted from rung 1. A `partial` rung stops the count.
- **Score** (0-100, shown on the dashboard) gives achieved rungs 1 point and partial rungs 0.5, so partial progress is visible without moving the estimate.
- **Modifier** comes from the tier: 0 → 1.10, 1 → 0.85, 2 → 0.80, 3 → 0.75, 4 → 0.70, 5 → 0.60, 6 → 0.50. Tier 1 keeps the 0.85 the binary model applied, so the historical meaning of below-threshold QEC is unchanged.

As of October 2026 the ladder sits at tier 2. Rung 3 is `partial`: Quantinuum's June 2025 break-even non-Clifford gate ran in a small error-detecting code with post-selection, not a scalable error-correcting code.

Because this component carries 10% of the weight, its pull is small. Replacing the binary flag (tier 1 equivalent, 0.85) with tier 2 (0.80) moved the unrounded midpoint from 2.655 to 2.640 years — 0.015 years, which happens to cross the rounding boundary and changes the displayed midpoint from 2.7 to 2.6. Climbing from tier 2 to tier 6 would move it a further 0.09 years. The ladder exists to make fault-tolerance progress visible and auditable; changing its pull on the estimate is a reweighting decision.

### Important Caveat

Quantum progress is nonlinear. Breakthroughs can compress timelines rapidly. The estimate reflects current trajectory only and should not be used as a precise prediction.

## Canary Ladder Methodology

The RSA and ECDLP ladders are ordered by bit size. Each rung has a status:

- **achieved** — Demonstrated on quantum hardware using a genuine quantum algorithm (not classical shortcuts)
- **current** — Current frontier (for ECDLP: no quantum break has occurred at any bit size)
- **pending** — Not yet achieved
- **canary** — The critical inflection point where breaking larger keys becomes an engineering sprint
- **qday** — Full cryptographic break of production keys

Records are sourced from peer-reviewed papers, IACR ePrint archive, and vendor publications. Only genuine quantum algorithmic results count — classical factoring records and hybrid classical-quantum approaches are noted as context but do not advance the ladder.

## Data Sources

- **Hardware milestones:** Vendor press releases, academic publications, independent verification
- **PQC adoption:** Product changelogs, security advisories, IETF drafts, browser release notes
- **Blockchain status:** Chain governance proposals, developer forums, GitHub repositories
- **Funding:** Congressional Research Service, RAND Corporation, CSIS, government budget documents
- **Research velocity:** arXiv API queries across quant-ph and cs.CR categories
- **Factoring records:** Nature, Physical Review Letters, IACR ePrint, vendor publications

All data is public. No proprietary or classified sources are used.
