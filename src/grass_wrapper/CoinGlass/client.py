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
        """
        Funding‑Rate OHLC ヒストリカルデータを取得する。

        Parameters
        ----------
        exchange : str, default Bybit
            先物取引所名（例: ``Binance``, ``OKX`` など）。  
            対応取引所は「supported-exchange-pair」APIで取得できます。
        symbol : str
            取引ペア（例: ``BTCUSDT``）。  
            対応ペアは同じく「supported-exchange-pair」APIで取得できます。
        interval : str, default 1h
            データの集計時間足。指定可能値：  
            ``1m, 3m, 5m, 15m, 30m, 1h, 4h, 6h, 8h, 12h, 1d, 1w``。
        limit : int | None, optional
            取得件数の上限。既定 ``1000``、最大 ``4500``。
        start_time : int | None, optional
            取得開始タイムスタンプ（UNIXエポック **ミリ秒**）。例：``1641522717000``。
        end_time : int | None, optional
            取得終了タイムスタンプ（UNIXエポック **ミリ秒**）。例：``1641522717000``。

        Returns
        -------
        dict
            Funding‑Rate OHLC データ。レスポンスフォーマットは公式仕様に準拠。
        """
        params: Dict[str, Any] = {
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if limit is not None:
            params["limit"] = limit

        res = self._get("/futures/funding-rate/history", **params)

        # --- enrich: add meta fields to each OHLC row -----------------------
        if isinstance(res, dict) and isinstance(res.get("data"), list):
            for idx, row in enumerate(res["data"]):
                # enrich keys without overwriting existing values
                meta = {
                    "exchange": row.get("exchange", exchange),
                    "symbol": row.get("symbol", symbol),
                    "interval": row.get("interval", interval),
                }
                # keep the original OHLC key order
                ohlc_part = {k: v for k, v in row.items() if k not in meta}
                # replace row with ordered dict (Python 3.7+ preserves insertion order)
                res["data"][idx] = {**meta, **ohlc_part}
        # --------------------------------------------------------------------

        return res

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
        """
        Spot Price OHLC ヒストリカルデータを取得する。

        Parameters
        ----------
        exchange : str, default Bybit
            スポット取引所名（例: ``Binance``, ``OKX`` など）。
        symbol : str
            取引ペア（例: ``BTCUSDT``）。
        interval : str, default 1h
            データの集計時間足。指定可能値：  
            ``1m, 3m, 5m, 15m, 30m, 1h, 4h, 6h, 8h, 12h, 1d, 1w``。
        limit : int | None, optional
            取得件数の上限。既定 ``1000``、最大 ``4500``。
        start_time : int | None, optional
            取得開始タイムスタンプ（UNIXエポック **ミリ秒**）。
        end_time : int | None, optional
            取得終了タイムスタンプ（UNIXエポック **ミリ秒**）。

        Returns
        -------
        dict
            Price OHLC データ。レスポンスフォーマットは公式仕様に準拠。
        """
        params: Dict[str, Any] = {
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if limit is not None:
            params["limit"] = limit

        res = self._get("/futures/price/history", **params)

        # --- enrich: add meta fields to each OHLC row -----------------------
        if isinstance(res, dict) and isinstance(res.get("data"), list):
            for idx, row in enumerate(res["data"]):
                meta = {
                    "exchange": row.get("exchange", exchange),
                    "symbol": row.get("symbol", symbol),
                    "interval": row.get("interval", interval),
                }
                ohlc_part = {k: v for k, v in row.items() if k not in meta}
                res["data"][idx] = {**meta, **ohlc_part}
        # --------------------------------------------------------------------

        return res