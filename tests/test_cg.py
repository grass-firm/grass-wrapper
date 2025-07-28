import os
import json
import pytest

from grass_wrapper.CoinGlass.client import CoinGlass


@pytest.mark.skipif(
    "CG_API_KEY" not in os.environ,
    reason="環境変数 CG_API_KEY が無いと実 API コールできません",
)
def test_get_exchange_and_pairs_live():
    """
    CoinGlass API に実際にリクエストして
    レスポンス形式だけ簡易チェックするライブテスト。
    """
    client = CoinGlass(api_key=os.environ["CG_API_KEY"])
    res = client.get_supported_exchange_pairs()

    print("=== exchange_and_pairs_live ===")
    print(json.dumps(res["data"]["Binance"][0], indent=2, ensure_ascii=False))

    assert isinstance(res, dict)
    assert res.get("code") == "0" or res.get("success") is True
    assert "data" in res


def test_get_exchange_and_pairs_mock(monkeypatch):
    """
    requests.Session.get をモックしてオフラインで動作確認するテスト。
    """
    dummy_json = {
        "code": "0",
        "data": {
            "Binance": [
                {"instrument_id": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT"}
            ]
        },
    }

    class DummyResp:  # 最低限の stub
        def raise_for_status(self):
            return None

        def json(self):
            return dummy_json

    def dummy_get(*args, **kwargs):
        return DummyResp()

    client = CoinGlass(api_key="dummy")

    # monkeypatch で _session.get を差し替え
    monkeypatch.setattr(client._session, "get", dummy_get)

    res = client.get_supported_exchange_pairs()
    assert res == dummy_json


# Funding‑Rate OHLC データ取得
@pytest.mark.skipif(
    "CG_API_KEY" not in os.environ,
    reason="環境変数 CG_API_KEY が無いと実 API コールできません",
)
def test_get_fr_ohlc_history_live():
    """
    Bybit の BTCUSDT 1h Funding‑Rate OHLC データを取得して
    レスポンス構造をざっくり確認するライブテスト。
    """
    client = CoinGlass(api_key=os.environ["CG_API_KEY"])
    res = client.get_fr_ohlc_history(
        exchange="Binance",
        symbol="COMPUSDT",
        interval="1h",
        limit=1,
    )

    print("=== fr_ohlc_history_live ===")
    print(json.dumps(res, indent=2, ensure_ascii=False))

    assert isinstance(res, dict)
    assert res.get("code") == "0" or res.get("success") is True
    assert "data" in res and isinstance(res["data"], list)