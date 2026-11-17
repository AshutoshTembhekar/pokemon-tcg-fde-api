from fastapi.testclient import TestClient

from src.api import EXPECTED_API_KEY, app
from src.validator import validate_and_quarantine

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": EXPECTED_API_KEY}


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_unauthorized_request_blocked():
    resp = client.get("/v1/cards?set_id=base1")
    assert resp.status_code == 401


def test_validator_quarantines_corrupt_pokemon_cards():
    mock_payload = {
        "set_id": "test_set",
        "set_name": "Test Expansion",
        "cards": [
            {
                "id": "test-1",
                "name": "Charizard",
                "category": "Pokemon",
                "rarity": "Rare Holo",
                "hp": 120,
                "types": ["Fire"],
                "attacks": [{"name": "Fire Spin", "damage": "100"}],
                "illustrator": "Mitsuhiro Arita",
            },
            {
                "id": "test-bad-hp",
                "name": "Corrupt Missing HP Mon",
                "category": "Pokemon",
                "rarity": "Common",
                "hp": None,
                "types": ["Water"],
            },
            {
                "id": "test-bad-rarity",
                "name": "Missing Rarity Trainer",
                "category": "Trainer",
                "rarity": "",
            },
        ],
    }

    df_clean, quarantine = validate_and_quarantine(mock_payload)
    assert len(df_clean) == 1
    assert df_clean.iloc[0]["name"] == "Charizard"
    assert df_clean.iloc[0]["damage_per_hp_ratio"] == round(100 / 120, 4)
    assert len(quarantine) == 2