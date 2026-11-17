# Pokémon TCG Forward-Deployed Ingestion & Analytics API

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![Parquet](https://img.shields.io/badge/Storage-Apache%20Parquet-50ABF1?logo=apache&logoColor=white)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions%20%7C%20Pytest%20%7C%20Ruff-2088FF?logo=githubactions&logoColor=white)

A production-grade **Forward-Deployed Data Engineering (FDE)** microservice built with **FastAPI**, **Pydantic v2**, and **Apache Parquet**. The service ingests live Pokémon Trading Card Game (TCG) expansion data from the **TCGdex REST API**, enforces strict domain schema contracts with automated bad-record quarantine, persists normalized datasets to columnar Parquet storage, and serves SLA-monitored analytics endpoints.

---

## System Architecture

```mermaid
flowchart TD
    A["🌐 TCGdex REST API<br/>(api.tcgdex.net/v2/en)"] -->|"Async HTTPX Ingestion"| B["⚙️ Ingestion Connector<br/>(src/connector.py)"]
    B -.->|"Offline Fallback Snapshot"| C["📄 Raw JSON Cache<br/>(data/raw/*.json)"]
    C -.-> B
    B -->|"Raw Card Payloads"| D{"🛡️ Pydantic v2 Validator<br/>& Quarantine Gate<br/>(src/validator.py)"}
    D -->|"Valid Schema & Derived Metrics"| E["📦 Apache Parquet Store<br/>(data/processed/*.parquet)"]
    D -->|"Corrupt / Missing HP, Type, Rarity"| F["🚨 Quarantine Audit Log<br/>(quarantine_log.json)"]
    E -->|"Sub-250ms Columnar Queries"| G["🚀 FastAPI REST Layer<br/>(X-API-Key Protected)<br/>(src/api.py)"]
    F -->|"Audit Inspection"| G
    G -->|"JSON Responses"| H["🧪 Postman Suite & Client Apps"]

    style A fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
    style B fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#f8fafc
    style D fill:#31102f,stroke:#f43f5e,stroke-width:2px,color:#f8fafc
    style E fill:#0c4a6e,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
    style F fill:#450a0a,stroke:#ef4444,stroke-width:2px,color:#f8fafc
    style G fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#f8fafc
```

---

## Engineering Highlights

* **Resilient Upstream Ingestion (`src/connector.py`):** Asynchronous `httpx` client fetching expansion metadata and granular card payloads with automatic raw JSON snapshotting (`data/raw/{set_id}.json`) to guarantee deterministic offline fallback if upstream APIs rate-limit or degrade.
* **Domain Schema Enforcement & Quarantine (`src/validator.py`):** Pydantic v2 validation pipeline enforcing business rules (e.g., `Pokemon`-category cards must possess positive integer HP, elemental typing, and valid rarity tiers). Malformed records are isolated into an auditable quarantine log rather than crashing batch runs.
* **Derived Analytical Features:** Automatically extracts numeric attack ceilings across multi-attack movesets and computes `damage_per_hp_ratio` combat efficiency metrics during ingestion.
* **Columnar Parquet Persistence (`src/api.py`):** Stores validated expansion datasets in compressed Apache Parquet (`pyarrow`), enabling sub-250ms filtered queries and analytical aggregations without external database overhead.
* **API Security & Automated Verification:** Protected via `X-API-Key` header dependency injection, validated by a `pytest` unit/integration suite (`tests/test_api.py`), Ruff static linting, GitHub Actions CI (`.github/workflows/ci.yaml`), and a portable Postman v2.1 collection (`postman/`).

---

## Repository Structure

```text
pokemon-tcg-fde-api/
├── .github/workflows/ci.yaml      # Ruff lint & Pytest CI
├── data/
│   ├── raw/                       # Upstream JSON snapshots
│   └── processed/                 # Clean Parquet & quarantine log
├── postman/
│   ├── Local_Dev.postman_environment.json
│   └── Pokemon_TCG_FDE.postman_collection.json
├── src/
│   ├── api.py                     # FastAPI routes & X-API-Key auth
│   ├── connector.py               # Async TCGdex REST client
│   └── validator.py               # Pydantic v2 validation & quarantine
├── tests/
│   └── test_api.py                # Unit & integration test suite
├── .gitignore
├── README.md
└── requirements.txt
```

---

## API Reference

All `/v1/*` endpoints require the header: `X-API-Key: fde-tcg-dev-key-2026` (configurable via `FDE_API_KEY` environment variable).

| Method | Endpoint | Auth | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/health` | Public | Liveness and service health check |
| `POST` | `/v1/sync/set/{set_id}?limit=50` | Required | Ingests expansion cards from TCGdex, quarantines invalid records, and writes `{set_id}.parquet` |
| `GET` | `/v1/cards?set_id=base1&min_hp=50` | Required | Queries Parquet store with optional `primary_type`, `min_hp`, and `limit` filters |
| `GET` | `/v1/sets/{set_id}/analytics` | Required | Computes rarity distribution, mean HP by elemental type, and top damage-efficiency cards |
| `GET` | `/v1/quarantine` | Required | Returns rejected card payloads alongside exact Pydantic/domain failure reasons |

### Sample Analytics Response (`GET /v1/sets/base1/analytics`)

```json
{
  "set_id": "base1",
  "total_clean_cards": 15,
  "rarity_distribution": {
    "Rare": 15
  },
  "mean_hp_by_type": {
    "Fire": 120.0,
    "Water": 100.0,
    "Psychic": 80.0
  },
  "top_damage_efficiency_cards": [
    {
      "card_id": "base1-4",
      "name": "Charizard",
      "hp": 120,
      "max_attack_damage": 100,
      "damage_per_hp_ratio": 0.8333
    }
  ]
}
```

---

## Local Setup & Execution

```powershell
# 1. Install dependencies
py -m pip install -r requirements.txt

# 2. Run static linter and automated test suite
py -m ruff check src/ tests/
py -m pytest tests/ -v

# 3. Launch the FastAPI server (Swagger UI available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs))
py -m uvicorn src.api:app --reload --port 8000
```

### Triggering an Ingestion & Analytics Workflow

```powershell
# Sync 40 cards from Base Set (base1) into Apache Parquet
curl -X POST "http://127.0.0.1:8000/v1/sync/set/base1?limit=40" -H "X-API-Key: fde-tcg-dev-key-2026"

# Query aggregated set KPIs
curl -X GET "http://127.0.0.1:8000/v1/sets/base1/analytics" -H "X-API-Key: fde-tcg-dev-key-2026"
```

Author
Ashutosh Tembhekar

Data Analytics & Forward-Deployed Data Engineering

GitHub: @AshutoshTembhekar