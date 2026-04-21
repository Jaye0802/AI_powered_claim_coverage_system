# AI agents Claims Coverage System — Technical Documentation

## Overview

This document provides a comprehensive, implementation-oriented overview of the Claims Coverage System. It is intended for developers, ML engineers, analysts, and operators. It explains system responsibilities, architecture, data flow, configuration, AI integration, data model, runtime behaviors, validation, testing, and operational playbooks.

## 1. Executive Summary

The Claims Coverage System ingests structured policy, claim, and coverage data from an Excel workbook (for test only: **BklSQL_valid.xlsx, BklSQL_invalid.xlsx**), normalizes it into an embedded **SQLite** database, and uses a structured-output LLM (OpenAI) to produce coverage determinations and estimated payouts for claims.

The system enforces schema conformity via Pydantic (strict JSON schemas) and exposes ergonomic entry points to process individual claims or batches. It includes preflight data validation and lightweight performance diagnostics.

### Key Strengths

- Clear separation of concerns:
    - **Data Adapter** (I/O + DB)
    - **Coverage Agent** (LLM + validation)
    - **System Orchestrator** (end-to-end flow)
- Deterministic, schema-constrained AI outputs
- Idempotent Excel import with change detection
- Portable SQLite-based architecture

### Key Risks

- Non-atomic imports (risk of empty DB)
- OpenAI JSON schema compatibility issues
- Missing FK enforcement in SQLite
- Lack of persisted audit trail

## 2. Repository Layout

```python
claims_system_clean.py # Core runtime (data + LLM + orchestration)
config.py # Configuration
data_validator.py # Data validation
performance_monitor.py # Performance tracking
test_claims_system.py # Tests
requirements.txt # Dependencies
README.md # Developer guide
BklSQL.xlsx # Input data
```

## 3. Architecture

### Core Components

### 1. BCDataAdapter

- Handles SQLite schema + connections
- Imports Excel → normalized tables:
    - `policies`
    - `claims`
    - `coverages`
    - `import_log`
- Provides typed data access

### 2. ClaimsCoverageAgent

- Handles LLM interaction
- Enforces structured JSON output
- Uses Pydantic schemas:
    - `CoverageAnalysis`
    - `ClaimAssessment`

### 3. ClaimsCoverageSystem

- Orchestrates full pipeline:
    1. Ensure data loaded
    2. Select claims
    3. Query policy + coverages
    4. Call LLM
    5. Compute payout
    6. Return structured results

### Data Flow

```
Excel → DataAdapter → SQLite → Orchestrator → LLM → Output
```

## 4. Data Model (SQLite)

### Tables

- **policies**
- **claims**
- **coverages**
- **import_log**

### Key Relationship

```
claims.policy_id → policies.policy_id
```

### Notes

- Add `PRAGMA foreign_keys=ON`
- Add indexes for performance
- Consider `policy_terms` table for multi-term policies

## 5. Import Pipeline

1. Check if import is needed (via file mtime)
2. If needed:
    - Read Excel
    - Preprocess data
    - Load into DB

### Recommended Improvement

Use transactional import:

```
BEGIN → temp tables → validate → swap → COMMIT
```

## 6. AI Inference

### Prompting

- Input: policy + claim + coverages
- Output: structured JSON

### Output Enforcement

- Primary: `json_schema`
- Fallback: `json_object`

### Determinism

- `temperature = 0`
- optional `seed`

## 7. Configuration

Located in `config.py`

```python
AI_SEED = 42
AI_TEMPERATURE = 0
DATABASE_PATH = "bc_real.db"
DEFAULT_MODEL = "gpt-4o"
EXCEL_PATH = "BklSQL.xlsx"
EXCEL_SHEET = "PoliciesNClaims"
```

### Secrets

- `OPENAI_API_KEY` via environment variable

## 8. Usage

### Single Claim

```python
sys = ClaimsCoverageSystem()
result = sys.process_claim("CLM-001234")
```

### Batch

```python
df = sys.process_claims(50)
```

### All Claims

```python
df = sys.process_claims("all")
```

## 9. Validation & Testing

### Data Validation

- Schema checks
- Referential integrity
- Date validation

### Tests

- Single claim
- Batch processing
- Determinism

## 10. Performance

Tracked via `performance_monitor.py`

Metrics:

- latency per claim
- batch throughput
- import time

## 11. Security

- Use env variables for API keys
- Avoid hardcoding secrets
- Consider encryption
- Add audit trail

## 12. Roadmap

- Atomic imports
- Better JSON fallback
- Persist results to DB
- Add caching
- CLI improvements

## 13. Limitations

- LLM dependency
- Excel schema drift
- No atomic import (currently)
- FK not enforced by default

## 14. Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
python claims_system_clean.py
```

## 15. Code Structure

### Main Classes

- `BCDataAdapter`
- `ClaimsCoverageAgent`
- `ClaimsCoverageSystem`

### Supporting Modules

- `data_validator.py`
- `performance_monitor.py`
- `test_claims_system.py`