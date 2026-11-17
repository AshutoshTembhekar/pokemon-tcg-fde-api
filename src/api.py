import json
import os
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from src.connector import fetch_set_cards
from src.validator import validate_and_quarantine

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
QUARANTINE_FILE = PROCESSED_DIR / "quarantine_log.json"

EXPECTED_API_KEY = os.getenv("FDE_API_KEY", "fde-tcg-dev-key-2026")

app = FastAPI(
    title="Pokémon TCG Forward-Deployed Ingestion & Analytics API",
    version="1.0.0",
    description="FDE microservice ingesting live TCGdex data, enforcing schema quarantine, and serving Parquet-backed analytics.",
)


def verify_api_key(x_api_key: str | None = Header(default=None)):
    if x_api_key != EXPECTED_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
    return x_api_key


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "pokemon-tcg-fde-api"}


@app.post("/v1/sync/set/{set_id}", dependencies=[Depends(verify_api_key)])
async def sync_set(set_id: str, limit: int = Query(default=50, ge=1, le=200)):
    try:
        raw_payload = await fetch_set_cards(set_id=set_id, max_cards=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    df_clean, quarantine_log = validate_and_quarantine(raw_payload)
    parquet_path = PROCESSED_DIR / f"{set_id}.parquet"

    if not df_clean.empty:
        df_clean.to_parquet(parquet_path, index=False)

    QUARANTINE_FILE.write_text(json.dumps(quarantine_log, indent=2), encoding="utf-8")

    return {
        "set_id": set_id,
        "set_name": raw_payload.get("set_name"),
        "ingested_clean_count": len(df_clean),
        "quarantined_count": len(quarantine_log),
        "parquet_artifact": str(parquet_path),
    }


@app.get("/v1/cards", dependencies=[Depends(verify_api_key)])
def query_cards(
    set_id: str = Query(default="base1"),
    primary_type: str | None = Query(default=None),
    min_hp: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    parquet_path = PROCESSED_DIR / f"{set_id}.parquet"
    if not parquet_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Set '{set_id}' has not been synced yet. Call POST /v1/sync/set/{set_id} first.",
        )

    df = pd.read_parquet(parquet_path)
    if primary_type:
        df = df[df["primary_type"].str.lower() == primary_type.lower()]
    if min_hp is not None:
        df = df[df["hp"].fillna(0) >= min_hp]

    records = df.head(limit).where(pd.notnull(df), None).to_dict(orient="records")
    return {
        "set_id": set_id,
        "total_matched": len(df),
        "returned": len(records),
        "data": records,
    }


@app.get("/v1/sets/{set_id}/analytics", dependencies=[Depends(verify_api_key)])
def set_analytics(set_id: str):
    parquet_path = PROCESSED_DIR / f"{set_id}.parquet"
    if not parquet_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Set '{set_id}' not found in Parquet store.",
        )

    df = pd.read_parquet(parquet_path)
    pokemon_df = df[df["category"] == "Pokemon"]

    rarity_breakdown = df["rarity"].value_counts().to_dict()
    avg_hp_by_type = (
        pokemon_df.groupby("primary_type")["hp"].mean().round(2).to_dict()
        if not pokemon_df.empty
        else {}
    )
    top_efficiency = (
        pokemon_df.sort_values(by="damage_per_hp_ratio", ascending=False)
        .head(3)[["card_id", "name", "hp", "max_attack_damage", "damage_per_hp_ratio"]]
        .to_dict(orient="records")
        if not pokemon_df.empty
        else []
    )

    return {
        "set_id": set_id,
        "total_clean_cards": len(df),
        "rarity_distribution": rarity_breakdown,
        "mean_hp_by_type": avg_hp_by_type,
        "top_damage_efficiency_cards": top_efficiency,
    }


@app.get("/v1/quarantine", dependencies=[Depends(verify_api_key)])
def get_quarantine_audit():
    if not QUARANTINE_FILE.exists():
        return {"quarantined_count": 0, "records": []}
    records = json.loads(QUARANTINE_FILE.read_text(encoding="utf-8"))
    return {"quarantined_count": len(records), "records": records}