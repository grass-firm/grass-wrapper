from __future__ import annotations

import os
import sys
# Make the package under ../src importable when running tests from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
from typing import Any, Dict

import types
import requests

from grass_wrapper.Bybit import Bybit, BybitConfig


class DummyResp:
    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_private_get_signature_monkeypatch(monkeypatch):
    """
    Private GET should sign the queryString (sorted) with
    HMAC(secret, f"{ts}{apiKey}{recvWindow}{queryString}")
    We intercept the outgoing request to verify headers exist and return success.
    """
    cfg = BybitConfig(api_key="KEY", api_secret="SECRET", testnet=True)
    client = Bybit(cfg)

    captured = {}

    def fake_request(self, method, url, data=None, headers=None, timeout=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        # emulate bybit success envelope
        return DummyResp(200, {"retCode": 0, "retMsg": "OK", "result": {"rows": []}})

    monkeypatch.setattr(requests.Session, "request", fake_request)

    out = client.positions(category="linear", symbol="BTCUSDT")
    assert out["retCode"] == 0
    assert "X-BAPI-API-KEY" in captured["headers"]
    assert "X-BAPI-SIGN" in captured["headers"]
    assert captured["method"] == "GET"
    assert "/v5/position/list" in captured["url"]


def test_public_get_ok(monkeypatch):
    cfg = BybitConfig(testnet=True)
    client = Bybit(cfg)

    def fake_request(self, method, url, data=None, headers=None, timeout=None, **kwargs):
        return DummyResp(200, {"retCode": 0, "retMsg": "OK", "time": 1234567890})

    monkeypatch.setattr(requests.Session, "request", fake_request)
    res = client.server_time()
    assert res["retCode"] == 0