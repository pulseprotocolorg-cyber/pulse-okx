"""OKX adapter for PULSE Protocol.

Translates PULSE semantic messages to OKX V5 API.
Same interface as BinanceAdapter — swap exchanges in one line.

Example:
    >>> adapter = OKXAdapter(api_key="...", api_secret="...", passphrase="...")
    >>> msg = PulseMessage(
    ...     action="ACT.QUERY.DATA",
    ...     parameters={"symbol": "BTC-USDT"}
    ... )
    >>> response = adapter.send(msg)
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from pulse.message import PulseMessage
from pulse.adapter import PulseAdapter, AdapterError, AdapterConnectionError


# OKX V5 API endpoints
ENDPOINTS = {
    "ticker": "/api/v5/market/ticker",
    "candles": "/api/v5/market/candles",
    "books": "/api/v5/market/books",
    "server_time": "/api/v5/public/time",
    "place_order": "/api/v5/trade/order",
    "cancel_order": "/api/v5/trade/cancel-order",
    "order_detail": "/api/v5/trade/order",
    "open_orders": "/api/v5/trade/orders-pending",
    "balance": "/api/v5/account/balance",
}

# Map PULSE actions to OKX operations
ACTION_MAP = {
    "ACT.QUERY.DATA": "query",
    "ACT.QUERY.STATUS": "order_status",
    "ACT.TRANSACT.REQUEST": "place_order",
    "ACT.CANCEL": "cancel_order",
    "ACT.QUERY.LIST": "open_orders",
    "ACT.QUERY.BALANCE": "balance",
}


class OKXAdapter(PulseAdapter):
    """PULSE adapter for OKX exchange (V5 API).

    Translates PULSE semantic actions to OKX V5 API.
    Same interface as BinanceAdapter — switch exchanges in one line.

    Supported PULSE actions:
        - ACT.QUERY.DATA — get ticker price, candles, order book
        - ACT.QUERY.STATUS — check order status
        - ACT.QUERY.LIST — list open orders
        - ACT.QUERY.BALANCE — get account balance
        - ACT.TRANSACT.REQUEST — place an order (BUY/SELL)
        - ACT.CANCEL — cancel an order

    Note: OKX requires a passphrase in addition to api_key and api_secret.
    Symbol format uses dashes: "BTC-USDT" (not "BTCUSDT").

    Example:
        >>> adapter = OKXAdapter(
        ...     api_key="...", api_secret="...", passphrase="..."
        ... )
        >>> msg = PulseMessage(
        ...     action="ACT.QUERY.DATA",
        ...     parameters={"symbol": "BTC-USDT"}
        ... )
        >>> response = adapter.send(msg)
    """

    BASE_URL = "https://www.okx.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        demo: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name="okx",
            base_url=self.BASE_URL,
            config=config or {},
        )
        self._api_key = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        self._demo = demo
        self._session: Optional[requests.Session] = None

    def connect(self) -> None:
        """Initialize HTTP session and verify connectivity."""
        self._session = requests.Session()
        if self._demo:
            self._session.headers.update({"x-simulated-trading": "1"})

        try:
            resp = self._session.get(
                f"{self.base_url}{ENDPOINTS['server_time']}", timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "0":
                raise AdapterConnectionError(
                    f"OKX API error: {data.get('msg', 'Unknown')}"
                )
            self.connected = True
        except requests.ConnectionError as e:
            raise AdapterConnectionError(f"Cannot reach OKX API: {e}") from e
        except requests.HTTPError as e:
            raise AdapterConnectionError(f"OKX API error: {e}") from e

    def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            self._session.close()
        self._session = None
        self.connected = False

    def to_native(self, message: PulseMessage) -> Dict[str, Any]:
        """Convert PULSE message to OKX API request."""
        action = message.content["action"]
        params = message.content.get("parameters", {})
        operation = ACTION_MAP.get(action)

        if not operation:
            raise AdapterError(
                f"Unsupported action '{action}'. Supported: {list(ACTION_MAP.keys())}"
            )

        if operation == "query":
            return self._build_query_request(params)
        elif operation == "place_order":
            return self._build_order_request(params)
        elif operation == "cancel_order":
            return self._build_cancel_request(params)
        elif operation == "order_status":
            return self._build_status_request(params)
        elif operation == "open_orders":
            return self._build_open_orders_request(params)
        elif operation == "balance":
            return self._build_balance_request(params)

        raise AdapterError(f"Unknown operation: {operation}")

    def call_api(self, native_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute OKX API call."""
        if not self._session:
            self._ensure_session()

        method = native_request["method"]
        endpoint = native_request["endpoint"]
        params = native_request.get("params", {})
        signed = native_request.get("signed", False)

        try:
            if method == "GET":
                query_string = ""
                if params:
                    query_string = "?" + urlencode(params)
                url = f"{self.base_url}{endpoint}{query_string}"

                headers = {}
                if signed:
                    if not self._api_key or not self._api_secret:
                        raise AdapterError(
                            "API key, secret, and passphrase required for signed requests."
                        )
                    headers = self._sign_request("GET", endpoint + query_string, "")

                resp = self._session.get(url, headers=headers, timeout=10)

            elif method == "POST":
                url = f"{self.base_url}{endpoint}"
                body = json.dumps(params)

                headers = {"Content-Type": "application/json"}
                if signed:
                    if not self._api_key or not self._api_secret:
                        raise AdapterError(
                            "API key, secret, and passphrase required for signed requests."
                        )
                    headers.update(self._sign_request("POST", endpoint, body))

                resp = self._session.post(url, data=body, headers=headers, timeout=10)
            else:
                raise AdapterError(f"Unknown HTTP method: {method}")

            data = resp.json()

            # OKX uses code "0" for success
            code = data.get("code", "0")
            if code != "0":
                msg = data.get("msg", "Unknown error")
                raise AdapterError(f"OKX error {code}: {msg}")

            return data.get("data", data)

        except (requests.ConnectionError, ConnectionError) as e:
            raise AdapterConnectionError(f"Cannot reach OKX: {e}") from e
        except (requests.Timeout, TimeoutError) as e:
            raise AdapterConnectionError(f"OKX request timed out: {e}") from e
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(f"OKX request failed: {e}") from e

    def from_native(self, native_response: Any) -> PulseMessage:
        """Convert OKX response to PULSE message."""
        return PulseMessage(
            action="ACT.RESPOND",
            parameters={"result": native_response},
            validate=False,
        )

    @property
    def supported_actions(self) -> List[str]:
        return list(ACTION_MAP.keys())

    # --- Request Builders ---

    def _build_query_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build market data query."""
        symbol = params.get("symbol")
        query_type = params.get("type", "price")

        if query_type in ("price", "24h"):
            if not symbol:
                raise AdapterError("Symbol required for ticker query.")
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["ticker"],
                "params": {"instId": symbol.upper()},
                "signed": False,
            }

        elif query_type == "klines":
            if not symbol:
                raise AdapterError("Symbol required for klines query.")
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["candles"],
                "params": {
                    "instId": symbol.upper(),
                    "bar": params.get("interval", "1H"),
                    "limit": str(params.get("limit", 100)),
                },
                "signed": False,
            }

        elif query_type == "depth":
            if not symbol:
                raise AdapterError("Symbol required for depth query.")
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["books"],
                "params": {
                    "instId": symbol.upper(),
                    "sz": str(params.get("limit", 20)),
                },
                "signed": False,
            }

        raise AdapterError(
            f"Unknown query type '{query_type}'. Use: price, 24h, klines, depth."
        )

    def _build_order_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order placement request."""
        required = ["symbol", "side", "quantity"]
        for field in required:
            if field not in params:
                raise AdapterError(
                    f"Missing required field '{field}' for order placement."
                )

        order_params = {
            "instId": params["symbol"].upper(),
            "tdMode": params.get("td_mode", "cash"),
            "side": params["side"].lower(),
            "ordType": params.get("order_type", "market").lower(),
            "sz": str(params["quantity"]),
        }

        if order_params["ordType"] == "limit":
            if "price" not in params:
                raise AdapterError("Price required for LIMIT orders.")
            order_params["px"] = str(params["price"])

        return {
            "method": "POST",
            "endpoint": ENDPOINTS["place_order"],
            "params": order_params,
            "signed": True,
        }

    def _build_cancel_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order cancellation request."""
        if "symbol" not in params:
            raise AdapterError("Symbol required for order cancellation.")
        if "order_id" not in params:
            raise AdapterError("Order ID required for cancellation.")

        return {
            "method": "POST",
            "endpoint": ENDPOINTS["cancel_order"],
            "params": {
                "instId": params["symbol"].upper(),
                "ordId": str(params["order_id"]),
            },
            "signed": True,
        }

    def _build_status_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order status query."""
        if "symbol" not in params:
            raise AdapterError("Symbol required for order status query.")
        if "order_id" not in params:
            raise AdapterError("Order ID required for status query.")

        return {
            "method": "GET",
            "endpoint": ENDPOINTS["order_detail"],
            "params": {
                "instId": params["symbol"].upper(),
                "ordId": str(params["order_id"]),
            },
            "signed": True,
        }

    def _build_open_orders_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build open orders query."""
        req_params = {}
        if "symbol" in params:
            req_params["instId"] = params["symbol"].upper()

        return {
            "method": "GET",
            "endpoint": ENDPOINTS["open_orders"],
            "params": req_params,
            "signed": True,
        }

    def _build_balance_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build balance query."""
        req_params = {}
        if "currency" in params:
            req_params["ccy"] = params["currency"].upper()

        return {
            "method": "GET",
            "endpoint": ENDPOINTS["balance"],
            "params": req_params,
            "signed": True,
        }

    # --- Signing ---

    def _sign_request(
        self, method: str, request_path: str, body: str
    ) -> Dict[str, str]:
        """Generate OKX API signature.

        Algorithm:
        1. timestamp = ISO 8601 UTC time
        2. prehash = timestamp + method + request_path + body
        3. signature = base64(HMAC-SHA256(prehash, secret))
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
            f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"

        prehash = f"{timestamp}{method}{request_path}{body}"

        signature = base64.b64encode(
            hmac.new(
                self._api_secret.encode("utf-8"),
                prehash.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        return {
            "OK-ACCESS-KEY": self._api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self._passphrase or "",
        }

    def _ensure_session(self) -> None:
        if not self._session:
            self._session = requests.Session()
            if self._demo:
                self._session.headers.update({"x-simulated-trading": "1"})

    def __repr__(self) -> str:
        return f"OKXAdapter(demo={self._demo}, connected={self.connected})"
