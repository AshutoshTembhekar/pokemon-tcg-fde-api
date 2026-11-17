# Pokémon TCG Forward-Deployed Ingestion & Analytics API

A production-grade FastAPI data engineering microservice that ingests live Pokémon TCG expansion data from the **TCGdex REST API**, enforces Pydantic schema contracts with automated data quarantine, persists clean datasets to **Apache Parquet**, and exposes SLA-monitored analytics endpoints.

## Architecture & Key Capabilities
* **Resilient Upstream Ingestion (`src/connector.py`):** Async `httpx` client pulling set metadata and card payloads from `api.tcgdex.net/v2/en` with automatic local raw JSON snapshotting (`data/raw/`) for deterministic offline fallback.
* **Schema Validation & Quarantine (`src/validator.py`):** Pydantic v2 domain validation isolating malformed records (e.g., Pokémon cards missing positive HP or elemental typing) into a queryable quarantine audit log while calculating `damage_per_hp_ratio` efficiency metrics.
* **Parquet-Backed Analytics (`src/api.py`):** API-key protected (`X-API-Key`) FastAPI endpoints serving filtered card queries, rarity distributions, and mean HP aggregations directly from columnar Parquet storage.
* **Automated Testing & CI:** Includes a `pytest` suite (`tests/test_api.py`), Ruff linting, GitHub Actions CI workflow (`.github/workflows/ci.yaml`), and a portable Postman v2.1 collection + environment (`postman/`).

## Quickstart

```powershell
# 1. Install dependencies
py -m pip install -r requirements.txt

# 2. Run automated tests
py -m pytest tests/ -v

# 3. Start the FastAPI server
py -m uvicorn src.api:app --reload --port 8000