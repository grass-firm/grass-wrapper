# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode, quote

import requests


class BybitError(RuntimeError):
    """Normalized error for non-zero retCode or transport-level failures."""

    def __init__(self, message: str, *, code: Optional[int] = None, payload: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}

    def __str__(self) -> str:
        base = super().__str__()
        if self.code is not None:
            return f"[retCode={self.code}] {base}"
        return base


@dataclass(slots=True)
class BybitConfig:
    """
    Basic configuration for Bybit client.
    - If testnet=True, base_url is forced to https://api-testnet.bybit.com
    - If broker_id is set, it is sent via X-Referer header (for API broker program)
    """
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: str = "https://api.bybit.com"
    testnet: bool = False
    recv_window_ms: int = 20_000
    timeout_sec: int = 10
    broker_id: Optional[str] = None  # sends `X-Referer` if provided

    @classmethod
    def from_env(cls) -> "BybitConfig":
        return cls(
            api_key=os.getenv("BYBIT_API_KEY"),
            api_secret=os.getenv("BYBIT_API_SECRET"),
            base_url=os.getenv("BYBIT_BASE_URL", "https://api.bybit.com"),
            testnet=os.getenv("BYBIT_TESTNET", "false").lower() in ("1", "true", "t", "yes", "y"),
            recv_window_ms=int(os.getenv("BYBIT_RECV_WINDOW", "20000")),
            timeout_sec=int(os.getenv("BYBIT_TIMEOUT", "10")),
            broker_id=os.getenv("BYBIT_BROKER_ID"),
        )


class Bybit:
    """
    Lightweight Bybit V5 REST client (public & private).
    Only depends on `requests`. All methods return decoded JSON (`dict`).

    Sign spec:
      sign = hex(HMAC_SHA256(secret, f"{ts}{apiKey}{recvWindow}{body_or_query}"))
      headers: X-BAPI-API-KEY / X-BAPI-TIMESTAMP / X-BAPI-RECV-WINDOW / X-BAPI-SIGN
    """

    def __init__(self, config: Optional[BybitConfig] = None, session: Optional[requests.Session] = None) -> None:
        cfg = config or BybitConfig.from_env()
        if cfg.testnet:
            cfg.base_url = "https://api-testnet.bybit.com"

        self._cfg = cfg
        self._session = session or requests.Session()
        self._time_offset_ms = 0  # updated by sync_time()

        # Basic validation for private calls
        self._has_keys = bool(cfg.api_key and cfg.api_secret)

    # ---------- Low-level utilities ----------

    @property
    def base_url(self) -> str:
        return self._cfg.base_url.rstrip("/")

    def _now_ms(self) -> int:
        # Use local time + optional offset from sync_time()
        return int(time.time() * 1000) + self._time_offset_ms

    def _sign(self, prehash: str) -> str:
        if not self._cfg.api_secret:
            raise BybitError("API secret not set (required for private endpoints)")
        return hmac.new(self._cfg.api_secret.encode(), prehash.encode(), hashlib.sha256).hexdigest()

    def _headers(self, signed: bool, signature: Optional[str], timestamp_ms: int) -> Dict[str, str]:
        headers = {
            "User-Agent": "grass-wrapper/Bybit",
            "Accept": "application/json",
        }
        if signed:
            if not self._cfg.api_key:
                raise BybitError("API key not set (required for private endpoints)")
            headers.update(
                {
                    "X-BAPI-API-KEY": self._cfg.api_key,
                    "X-BAPI-TIMESTAMP": str(timestamp_ms),
                    "X-BAPI-RECV-WINDOW": str(self._cfg.recv_window_ms),
                    "X-BAPI-SIGN": signature or "",
                    "Content-Type": "application/json",
                }
            )
            if self._cfg.broker_id:
                # Broker program header (optional)
                headers["X-Referer"] = self._cfg.broker_id
        return headers

    def _canonical_query(self, params: Optional[Dict[str, Any]]) -> str:
        if not params:
            return ""
        # Sort keys and percent-encode values consistently
        return urlencode(sorted(params.items()), doseq=True, quote_via=quote, safe="")

    def _canonical_body(self, body: Optional[Dict[str, Any]]) -> str:
        if not body:
            return ""
        # Deterministic JSON (no spaces). sort_keys=True keeps order stable for signing
        return json.dumps(body, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        private: bool = False,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        ts = self._now_ms()

        # For GET: sign queryString; For POST: sign jsonBodyString
        query_str = self._canonical_query(params)
        body_str = self._canonical_body(body)

        prehash = f"{ts}{self._cfg.api_key or ''}{self._cfg.recv_window_ms}{body_str if method.upper() != 'GET' else query_str}"
        signature = self._sign(prehash) if private else None

        headers = self._headers(signed=private, signature=signature, timestamp_ms=ts)

        try:
            resp = self._session.request(
                method=method.upper(),
                url=url if not query_str else f"{url}?{query_str}",
                data=body_str if method.upper() != "GET" and body_str else None,
                headers=headers,
                timeout=self._cfg.timeout_sec,
            )
        except requests.RequestException as e:
            raise BybitError(f"Network error: {e!r}")

        # Parse JSON
        try:
            data = resp.json()
        except ValueError:
            raise BybitError(f"Non-JSON response (status {resp.status_code})", payload={"text": resp.text})

        # Normalize Bybit response (retCode/retMsg)
        ret_code = data.get("retCode")
        if resp.status_code != 200 or (ret_code is not None and ret_code != 0):
            raise BybitError(data.get("retMsg", f"HTTP {resp.status_code}"), code=ret_code, payload=data)

        return data

    # ---------- Time sync ----------

    def server_time(self) -> Dict[str, Any]:
        """GET /v5/market/time — public server timestamp (ms)."""
        # Base URL differs by env. Official example shows testnet; mainnet works as well.
        # https://bybit-exchange.github.io/docs/api-explorer/v5/market/time
        return self._request("GET", "/v5/market/time")

    def sync_time(self) -> int:
        """
        Sync local offset using /v5/market/time. Returns current offset (ms).
        Keep your local clock NTP-synchronized for best results.
        """
        t0 = int(time.time() * 1000)
        res = self.server_time()
        server_ts = int(res.get("time", t0))
        t1 = int(time.time() * 1000)
        # crude RTT-compensation: use midpoint
        local_mid = (t0 + t1) // 2
        self._time_offset_ms = server_ts - local_mid
        return self._time_offset_ms

    # ---------- Public market data ----------

    def instruments_info(
        self,
        *,
        category: str,
        symbol: Optional[str] = None,
        baseCoin: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /v5/market/instruments-info"""
        params: Dict[str, Any] = {"category": category}
        if symbol:
            params["symbol"] = symbol
        if baseCoin:
            params["baseCoin"] = baseCoin
        if limit is not None:
            params["limit"] = str(limit)
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/v5/market/instruments-info", params=params)

    def tickers(self, *, category: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """GET /v5/market/tickers"""
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/v5/market/tickers", params=params)

    def kline(
        self,
        *,
        category: str,
        symbol: str,
        interval: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """GET /v5/market/kline"""
        params: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
        }
        if start is not None:
            params["start"] = str(start)
        if end is not None:
            params["end"] = str(end)
        if limit is not None:
            params["limit"] = str(limit)
        return self._request("GET", "/v5/market/kline", params=params)

    # ---------- Private account / trading ----------

    def wallet_balance(self, *, accountType: str = "UNIFIED", coin: Optional[str] = None) -> Dict[str, Any]:
        """GET /v5/account/wallet-balance"""
        if not self._has_keys:
            raise BybitError("API key/secret required")
        params = {"accountType": accountType}
        if coin:
            params["coin"] = coin
        return self._request("GET", "/v5/account/wallet-balance", params=params, private=True)

    def positions(self, *, category: str, symbol: Optional[str] = None, settleCoin: Optional[str] = None) -> Dict[str, Any]:
        """GET /v5/position/list"""
        if not self._has_keys:
            raise BybitError("API key/secret required")
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        if settleCoin:
            params["settleCoin"] = settleCoin
        return self._request("GET", "/v5/position/list", params=params, private=True)

    def place_order(
        self,
        *,
        category: str,
        symbol: str,
        side: str,
        orderType: str,
        qty: str | float | int,
        price: Optional[str | float | int] = None,
        timeInForce: str = "GTC",
        positionIdx: Optional[int] = None,
        reduceOnly: Optional[bool] = None,
        orderLinkId: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """POST /v5/order/create"""
        if not self._has_keys:
            raise BybitError("API key/secret required")
        body: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": orderType,
            "qty": str(qty),
            "timeInForce": timeInForce,
        }
        if price is not None:
            body["price"] = str(price)
        if positionIdx is not None:
            body["positionIdx"] = positionIdx
        if reduceOnly is not None:
            body["reduceOnly"] = reduceOnly
        if orderLinkId:
            body["orderLinkId"] = orderLinkId
        if extra:
            body.update(extra)
        return self._request("POST", "/v5/order/create", body=body, private=True)

    def cancel_order(
        self,
        *,
        category: str,
        symbol: str,
        orderId: Optional[str] = None,
        orderLinkId: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v5/order/cancel"""
        if not self._has_keys:
            raise BybitError("API key/secret required")
        if not (orderId or orderLinkId):
            raise ValueError("orderId or orderLinkId required")
        body = {"category": category, "symbol": symbol}
        if orderId:
            body["orderId"] = orderId
        if orderLinkId:
            body["orderLinkId"] = orderLinkId
        return self._request("POST", "/v5/order/cancel", body=body, private=True)

    def cancel_all(self, *, category: str, symbol: str) -> Dict[str, Any]:
        """POST /v5/order/cancel-all"""
        if not self._has_keys:
            raise BybitError("API key/secret required")
        body = {"category": category, "symbol": symbol}
        return self._request("POST", "/v5/order/cancel-all", body=body, private=True)