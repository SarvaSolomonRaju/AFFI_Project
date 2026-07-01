from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import generate_api_key, hash_api_key


class TestAPIKeyGeneration:
    def test_generate_produces_key_and_record(self):
        result = generate_api_key("test_user", "readonly")
        assert "raw_key" in result
        assert "record" in result
        assert result["raw_key"].startswith("affi_")
        assert result["record"]["owner"] == "test_user"
        assert result["record"]["role"] == "readonly"
        assert result["record"]["active"] is True

    def test_hash_is_deterministic(self):
        key = "affi_test_key_123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2

    def test_different_keys_produce_different_hashes(self):
        h1 = hash_api_key("key_a")
        h2 = hash_api_key("key_b")
        assert h1 != h2

    def test_generate_unique_keys(self):
        k1 = generate_api_key("user1")
        k2 = generate_api_key("user2")
        assert k1["raw_key"] != k2["raw_key"]
        assert k1["record"]["key_hash"] != k2["record"]["key_hash"]
