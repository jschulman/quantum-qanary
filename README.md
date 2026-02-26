# The Quantum Qanary

Real-time dashboard tracking quantum computing's approach to breaking cryptography.

**Live dashboard:** [jschulman.github.io/quantum-qanary](https://jschulman.github.io/quantum-qanary)

## What This Tracks

| Signal | Source | Update Frequency |
|--------|--------|-----------------|
| Alert Level | Milestone triggers + manual override | On change |
| RSA Factoring Ladder | Academic papers, vendor publications | On event |
| ECDLP Ladder | Academic papers, vendor publications | On event |
| Hardware Progress | Vendor announcements, press releases | On event |
| PQC Adoption Matrix | Product changelogs, security advisories | Weekly |
| Blockchain PQC Status | Chain governance, dev forums, GitHub | Weekly |
| Government Funding | CRS, RAND, CSIS, government reports | Monthly |
| Research Velocity | arXiv API (quant-ph, cs.CR) | Daily |
| Q-Day Distance Estimate | Weighted composite of above signals | Weekly |

## Alert Levels

The dashboard uses a traffic-light system based on observable milestones:

- **GREEN** — No quantum computer has factored anything beyond 21 bits using Shor's algorithm
- **YELLOW** — Credible hardware demonstrations or government commitments signal accelerating timelines
- **ORANGE** — Quantum factoring reaches ~100 bits, or insurance carriers begin requiring PQC readiness
- **RED** — RSA-512 or 128-bit ECDLP broken by quantum computer (the canary is dead)

## The Canary Ladders

Two parallel ladders track quantum progress toward breaking cryptography:

**RSA Ladder** — Tracks quantum factoring from 15-bit (achieved 2001) through RSA-2048 (Q-Day).
The canary rung is RSA-512: once quantum computers reach this level, breaking RSA-2048 becomes an engineering problem, not a physics problem.

**ECDLP Ladder** — Tracks quantum attacks on elliptic curve cryptography.
The canary rung is 128-bit ECDLP: this triggers the blockchain migration race, as Bitcoin and Ethereum keys use secp256k1 (256-bit).

## Mosca's Theorem

The interactive calculator implements Mosca's inequality: if your data needs to stay secret for **X years**, and migrating to PQC takes **Y years**, and quantum computers break current encryption in **Z years**, start **now** if X + Y > Z.

## Architecture

```
collectors/           Python scripts fetching live data
  arxiv_quantum.py      arXiv paper counts (daily)
  github_pqc.py         PQC library activity (weekly)
  alert_checker.py      Alert level computation (weekly)
normalizers/
  qday_distance.py      Weighted Q-Day distance estimate
data/                 Curated JSON data files (trigger files)
  alerts/               Alert status and triggered milestones
  factoring/            RSA and ECDLP canary ladders
  hardware/             Qubit records and roadmap targets
  adoption/             PQC deployment matrix
  blockchain/           Chain PQC readiness
  funding/              Government and private investment
  milestones/           Historical timeline
docs/                 Static dashboard (GitHub Pages)
  index.html            Single-page dashboard
  style.css             Dark mode styles
  dashboard.js          Chart.js visualizations + Mosca calculator
  data/                 Copy of data/ served to browser
.github/workflows/    Automated collection schedules
```

## How It Updates

**Automated:** GitHub Actions run collectors on schedule (daily/weekly/monthly) and commit results.

**Manual (trigger files):** Edit any JSON file in `data/`, push, and the dashboard rebuilds automatically. Key trigger files:

- `data/alerts/status.json` — Set `override` field to manually change alert level
- `data/factoring/records.json` — Add new factoring milestones
- `data/hardware/qubit_records.json` — Add hardware announcements
- `data/adoption/pqc_deployments.json` — Update PQC deployment status
- `data/blockchain/pqc_status.json` — Update chain readiness

## Methodology

See [METHODOLOGY.md](METHODOLOGY.md) for detailed documentation of how alert levels, Q-Day distance estimates, and risk components are calculated.

## License

MIT
