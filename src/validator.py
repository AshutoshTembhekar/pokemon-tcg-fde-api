from typing import Any, List, Optional, Tuple
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator


class CleanCardRecord(BaseModel):
    card_id: str
    set_id: str
    set_name: str
    name: str
    category: str
    rarity: str
    hp: Optional[int] = None
    primary_type: str
    attack_count: int = Field(ge=0)
    max_attack_damage: int = Field(ge=0)
    damage_per_hp_ratio: float = Field(ge=0.0)
    illustrator: str

    @field_validator("rarity")
    @classmethod
    def validate_rarity(cls, v: str) -> str:
        if not v or v.strip().lower() in {"none", "unknown", ""}:
            raise ValueError("Missing or invalid card rarity")
        return v.strip()


def _extract_numeric_damage(attacks: List[dict]) -> int:
    max_dmg = 0
    for atk in attacks or []:
        raw_dmg = str(atk.get("damage", "0"))
        digits = "".join(ch for ch in raw_dmg if ch.isdigit())
        if digits:
            max_dmg = max(max_dmg, int(digits))
    return max_dmg


def validate_and_quarantine(raw_payload: dict) -> Tuple[pd.DataFrame, List[dict]]:
    """
    Validates raw TCGdex card objects, returning (clean_dataframe, quarantined_records).
    """
    set_id = raw_payload.get("set_id", "unknown")
    set_name = raw_payload.get("set_name", "Unknown")
    clean_rows: List[dict] = []
    quarantine_log: List[dict] = []

    for raw in raw_payload.get("cards", []):
        card_id = raw.get("id", "MISSING_ID")
        category = raw.get("category", "Unknown")
        hp_val = raw.get("hp")
        types_list = raw.get("types") or []

        # Domain rule: Pokemon category cards must have positive HP and at least one elemental type
        if category == "Pokemon":
            if hp_val is None or not isinstance(hp_val, int) or hp_val <= 0:
                quarantine_log.append({
                    "card_id": card_id,
                    "name": raw.get("name"),
                    "reason": "Pokemon card missing valid positive HP",
                })
                continue
            if not types_list:
                quarantine_log.append({
                    "card_id": card_id,
                    "name": raw.get("name"),
                    "reason": "Pokemon card missing elemental typing",
                })
                continue

        attacks = raw.get("attacks") or []
        max_dmg = _extract_numeric_damage(attacks)
        dmg_ratio = round(max_dmg / hp_val, 4) if (hp_val and hp_val > 0) else 0.0

        candidate = {
            "card_id": card_id,
            "set_id": set_id,
            "set_name": set_name,
            "name": raw.get("name", ""),
            "category": category,
            "rarity": raw.get("rarity", ""),
            "hp": hp_val if isinstance(hp_val, int) else None,
            "primary_type": types_list[0] if types_list else "Trainer/Energy",
            "attack_count": len(attacks),
            "max_attack_damage": max_dmg,
            "damage_per_hp_ratio": dmg_ratio,
            "illustrator": raw.get("illustrator") or "Uncredited",
        }

        try:
            validated = CleanCardRecord(**candidate)
            clean_rows.append(validated.model_dump())
        except ValidationError as err:
            quarantine_log.append({
                "card_id": card_id,
                "name": raw.get("name"),
                "reason": str(err.errors()[0]["msg"]),
            })

    df_clean = pd.DataFrame(clean_rows)
    return df_clean, quarantine_log