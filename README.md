# Atlas-MH Rater
**Self-hosted insurance rate extraction and premium generation engine.**

Monitors a local directory for SERFF filings, parses rate tables into PostgreSQL, and exposes an API for bulk premium calculations across American Modern, Foremost, Tower Hill, Assurant, and Aegis.

## Architecture Overview

```
data/inbox/       ← SERFF filings land here (PDF/XLSX)
       ↓
  [Parser Agent]   ← Camelot-py / PyMuPDF extraction
       ↓
 PostgreSQL       ← Normalized rate tables + territory mapping
       ↓
PremiumEngine     ← Multiplicative factor model:
                   Base × Territory × Tier × Variables = Final Premium
       ↓
  [API Layer]      ← Bulk calculation endpoints
```

## Quick Start

```bash
# Clone & enter
git clone https://github.com/sgrouplabs/atlas-mh-rater.git
cd atlas-mh-rater

# Docker Compose (PostgreSQL + App)
docker compose up -d

# Manual setup
pip install -r requirements.txt
cp .env.template .env
python main.py
```

## Carriers Supported

| Carrier | Form Complexity | Status |
|---|---|---|
| Foremost | High | 🔨 In Progress |
| American Modern | Standard | 🔨 In Progress |
| Assurant | Medium | 🔨 In Progress |
| Tower Hill | Medium | 🔨 In Progress |
| Aegis | Low | 🔨 In Progress |

## Project Structure

```
atlas-mh-rater/
├── schema/           # SQL initialization scripts
│   └── init.sql      # Normalized schema
├── models/           # Carrier-specific logic
├── tests/           # QA smoke tests
├── data/
│   ├── inbox/       # SERFF filing drop zone
│   └── logs/        # Processing logs
├── main.py          # Entry point
├── premium_engine.py
├── requirements.txt
├── .env.template
└── progress.json
```

## Premium Calculation Model

```
Final Premium = Base Rate × Territory Factor × Tier Factor × [Variable Factors]
```

All variable factors are carrier-specific multipliers stored in the `rate_variables` table.

## Agent Protocol

This project is built by a rotating multi-agent team:
- `[ARCH]` — Schema design, JSON mapping, cross-carrier compatibility
- `[DEV]` — PDF extraction, premium calculation engine
- `[QA]` — Validation suite, actuarial target verification
- `[DOC]` — README, API docs, `.env` templates

Every commit is prefixed with the agent tag that completed the work.