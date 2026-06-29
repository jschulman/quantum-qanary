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
- First non-trivial quantum ECDLP attack demonstrated (occurred April 2026 — 15-bit elliptic-curve key recovered via Shor's variant on a public quantum cloud, Project Eleven Q-Day Prize)

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

### Manual Override
The `data/alerts/status.json` file has an `override` field. Setting it to a level (e.g., "ORANGE") forces the dashboard to that level regardless of computed triggers. Set to `null` to return to computed level.

## Q-Day Distance Estimate

The Q-Day distance is a weighted composite of five signals, expressed as a range in years:

| Component | Weight | What It Measures | Current Progress |
|-----------|--------|-----------------|-----------------|
| **Factoring Progress** | 30% | Largest number factored by quantum Shor's (bits) relative to 2048-bit target | log₂ scale progress |
| **Logical Qubits** | 25% | Demonstrated logical qubits vs. ~4,000 needed for RSA-2048 | log₂ scale progress |
| **Roadmap Consensus** | 20% | Average target year for fault-tolerant quantum from major vendors/governments | Years from now |
| **Error Correction** | 15% | Whether below-threshold error correction has been demonstrated | Binary + quality score |
| **Investment Trend** | 10% | Year-over-year growth in global quantum computing investment | Growth rate signal |

### Calculation

Each component produces a progress percentage (0-100). The weighted sum maps to a year range:

```
weighted_progress = Σ (component_progress × component_weight)
```

The low/high year range is derived from:
- **Roadmap consensus** provides the baseline center estimate
- **Factoring + logical qubits** (the two largest weights) indicate how much engineering progress has been made
- **Error correction** and **investment** serve as acceleration/deceleration signals

The output is a range (e.g., "2-4 years") with a midpoint used as the default for Mosca's Theorem calculator.

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
