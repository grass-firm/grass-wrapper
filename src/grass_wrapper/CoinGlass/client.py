"""
CoinGlass REST API クライアント

- API キーは `CoinGlass(api_key="...")` で明示指定、  
  省略時は環境変数 **CG_API_KEY** を自動参照
- 主な公開メソッド
    * `get_exchange_and_pairs()`
    * `get_fr_history(exchange, symbol, interval="1h")`

外部からは `from wrapper import CoinGlass` でインポート。
"""

from __future__ import annotations

from typing import Any, Dict

import os
import requests

__all__ = ["CoinGlass"]


class CoinGlass:
    """
    CoinGlass 公開 API v4 をラップするクライアント。

    Parameters
    ----------
    api_key : str | None, optional
        CoinGlass の API キー。省略時は環境変数 `CG_API_KEY` を使用。
    timeout : int, default 300
        単一リクエストのタイムアウト秒数。
    """

    BASE_URL = "https://open-api-v4.coinglass.com/api"

    def __init__(self, api_key: str | None = None, *, timeout: int = 300) -> None:
        # API キーは引数優先、無ければ環境変数 CG_API_KEY を参照
        self._api_key: str | None = api_key or os.getenv("CG_API_KEY")
        if not self._api_key:
            raise ValueError(
                "CoinGlass API キーが見つかりません。"
                "api_key 引数を指定するか、環境変数 CG_API_KEY を設定してください。"
            )

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "CG-API-KEY": self._api_key,
            }
        )
        self._timeout = timeout

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        """
        GET リクエスト共通処理。

        Returns
        -------
        dict
            レスポンス JSON を辞書で返す。

        Raises
        ------
        requests.HTTPError
            ステータスコード 4xx/5xx の場合。
        requests.RequestException
            ネットワーク関連のエラーが発生した場合。
        """
        url = f"{self.BASE_URL}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise exc


    def _get_timeseries(
        self,
        endpoint: str,
        *,
        symbol: str,
        interval: str = "1h",
        exchange: str | None = None,
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        unit: str | None = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
        }
        if exchange is not None:
            params["exchange"] = exchange
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if limit is not None:
            params["limit"] = limit
        if unit is not None:
            params["unit"] = unit

        res = self._get(endpoint, **params)

        if isinstance(res, dict) and isinstance(res.get("data"), list):
            for idx, row in enumerate(res["data"]):
                meta: Dict[str, Any] = {
                    "symbol": row.get("symbol", symbol),
                    "interval": row.get("interval", interval),
                }
                if exchange is not None or "exchange" in row:
                    meta["exchange"] = row.get("exchange", exchange)
                data_fields = {k: v for k, v in row.items() if k not in meta}
                res["data"][idx] = {**meta, **data_fields}
        return res

    # ------------------------------------------------------------------ #
    # Public APIs
    # ------------------------------------------------------------------ #
    def get_supported_exchange_pairs(self) -> Dict[str, Any]:
        """サポートされる取引所と銘柄の一覧を取得する。"""
        return self._get("/futures/supported-exchange-pairs")

    def get_fr_ohlc_history(
        self,
        *,
        exchange: str = "Bybit",
        symbol: str,
        interval: str = "1h",
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> Dict[str, Any]:
        return self._get_timeseries(
            "/futures/funding-rate/history",
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )

    # ------------------------------------------------------------------ #
    def get_price_ohlc_history(
        self,
        *,
        exchange: str = "Bybit",
        symbol: str,
        interval: str = "1h",
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> Dict[str, Any]:
        return self._get_timeseries(
            "/futures/price/history",
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )

    def get_oi_ohlc_history(
        self,
        *,
        exchange: str = "Bybit",
        symbol: str,
        interval: str = "1h",
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        unit: str | None = None
    ) -> Dict[str, Any]:
        return self._get_timeseries(
            "/futures/open-interest/history",
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            unit=unit,
        )

    def get_liquidation_history(
        self,
        *,
        exchange: str = "Bybit",
        symbol: str,
        interval: str = "1h",
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> Dict[str, Any]:
        """
        Pair Liquidation History（取引所×ペアの清算履歴）を取得する。
        Docs: /futures/liquidation/history

        Parameters
        ----------
        exchange : str, default "Bybit"
            取引所名（例: "Binance", "OKX", "Bybit" など）。
        symbol : str
            取引ペア（例: "BTCUSDT"）。
        interval : str, default "1h"
            集計間隔（プランにより最小粒度に制限あり）。
        limit : int | None, optional
            取得件数。
        start_time, end_time : int | None, optional
            期間指定（UNIX ミリ秒）。

        Returns
        -------
        dict
            レスポンス例: {"code":"0","data":[{"time":...,"long_liquidation_usd":...,"short_liquidation_usd":...}, ...]}
        """
        return self._get_timeseries(
            "/futures/liquidation/history",
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )