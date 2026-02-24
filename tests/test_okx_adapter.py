"""Tests for OKX adapter. All mocked — no real API calls."""

import pytest
from unittest.mock import MagicMock

from pulse.message import PulseMessage
from pulse.adapter import AdapterError, AdapterConnectionError

from pulse_okx import OKXAdapter


# --- Mock Helpers ---


def mock_response(data_list, code="0", msg=""):
    """Create a mock OKX V5 response."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "code": code,
        "msg": msg,
        "data": data_list,
    }
    mock.raise_for_status.return_value = None
    return mock


# --- Fixtures ---


@pytest.fixture
def adapter():
    a = OKXAdapter(api_key="test-key", api_secret="test-secret", passphrase="test-pass")
    a._session = MagicMock()
    a.connected = True
    return a


@pytest.fixture
def price_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTC-USDT"},
        sender="test-bot",
    )


@pytest.fixture
def klines_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTC-USDT", "type": "klines", "interval": "1H"},
        sender="test-bot",
    )


@pytest.fixture
def buy_message():
    return PulseMessage(
        action="ACT.TRANSACT.REQUEST",
        parameters={"symbol": "BTC-USDT", "side": "BUY", "quantity": 0.001},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def cancel_message():
    return PulseMessage(
        action="ACT.CANCEL",
        parameters={"symbol": "BTC-USDT", "order_id": "123456"},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def status_message():
    return PulseMessage(
        action="ACT.QUERY.STATUS",
        parameters={"symbol": "BTC-USDT", "order_id": "123456"},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def balance_message():
    return PulseMessage(
        action="ACT.QUERY.BALANCE",
        parameters={},
        sender="test-bot",
        validate=False,
    )


# --- Test Initialization ---


class TestOKXAdapterInit:

    def test_basic_init(self):
        adapter = OKXAdapter(api_key="key", api_secret="secret", passphrase="pass")
        assert adapter.name == "okx"
        assert adapter.base_url == "https://www.okx.com"
        assert adapter.connected is False

    def test_demo_init(self):
        adapter = OKXAdapter(demo=True)
        assert adapter._demo is True

    def test_repr(self):
        adapter = OKXAdapter()
        assert "demo=False" in repr(adapter)
        assert "connected=False" in repr(adapter)


# --- Test to_native: Market Data ---


class TestToNativeMarketData:

    def test_price_query(self, adapter, price_message):
        native = adapter.to_native(price_message)
        assert native["method"] == "GET"
        assert native["endpoint"] == "/api/v5/market/ticker"
        assert native["params"]["instId"] == "BTC-USDT"
        assert native["signed"] is False

    def test_klines_query(self, adapter, klines_message):
        native = adapter.to_native(klines_message)
        assert native["endpoint"] == "/api/v5/market/candles"
        assert native["params"]["bar"] == "1H"

    def test_depth_query(self, adapter):
        msg = PulseMessage(
            action="ACT.QUERY.DATA",
            parameters={"symbol": "BTC-USDT", "type": "depth"},
        )
        native = adapter.to_native(msg)
        assert native["endpoint"] == "/api/v5/market/books"
        assert native["params"]["sz"] == "20"

    def test_symbol_uppercased(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "btc-usdt"})
        native = adapter.to_native(msg)
        assert native["params"]["instId"] == "BTC-USDT"

    def test_unknown_query_type_raises(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "BTC-USDT", "type": "invalid"})
        with pytest.raises(AdapterError, match="Unknown query type"):
            adapter.to_native(msg)

    def test_klines_no_symbol_raises(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"type": "klines"})
        with pytest.raises(AdapterError, match="Symbol required"):
            adapter.to_native(msg)

    def test_price_no_symbol_raises(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={})
        with pytest.raises(AdapterError, match="Symbol required"):
            adapter.to_native(msg)


# --- Test to_native: Orders ---


class TestToNativeOrders:

    def test_market_buy(self, adapter, buy_message):
        native = adapter.to_native(buy_message)
        assert native["method"] == "POST"
        assert native["endpoint"] == "/api/v5/trade/order"
        assert native["params"]["instId"] == "BTC-USDT"
        assert native["params"]["side"] == "buy"
        assert native["params"]["ordType"] == "market"
        assert native["params"]["sz"] == "0.001"
        assert native["params"]["tdMode"] == "cash"
        assert native["signed"] is True

    def test_sell_side(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTC-USDT", "side": "SELL", "quantity": 0.1},
            validate=False,
        )
        native = adapter.to_native(msg)
        assert native["params"]["side"] == "sell"

    def test_limit_order(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            validate=False,
            parameters={
                "symbol": "ETH-USDT", "side": "BUY", "quantity": 1,
                "order_type": "LIMIT", "price": 2000,
            },
        )
        native = adapter.to_native(msg)
        assert native["params"]["ordType"] == "limit"
        assert native["params"]["px"] == "2000"

    def test_limit_no_price_raises(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTC-USDT", "side": "BUY", "quantity": 1, "order_type": "LIMIT"},
            validate=False,
        )
        with pytest.raises(AdapterError, match="Price required"):
            adapter.to_native(msg)

    def test_order_missing_field_raises(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTC-USDT", "side": "BUY"},
            validate=False,
        )
        with pytest.raises(AdapterError, match="Missing required field"):
            adapter.to_native(msg)

    def test_cancel_order(self, adapter, cancel_message):
        native = adapter.to_native(cancel_message)
        assert native["method"] == "POST"
        assert native["endpoint"] == "/api/v5/trade/cancel-order"
        assert native["params"]["ordId"] == "123456"
        assert native["signed"] is True

    def test_cancel_no_symbol_raises(self, adapter):
        msg = PulseMessage(action="ACT.CANCEL", parameters={"order_id": "123"}, validate=False)
        with pytest.raises(AdapterError, match="Symbol required"):
            adapter.to_native(msg)

    def test_cancel_no_order_id_raises(self, adapter):
        msg = PulseMessage(action="ACT.CANCEL", parameters={"symbol": "BTC-USDT"}, validate=False)
        with pytest.raises(AdapterError, match="Order ID required"):
            adapter.to_native(msg)


# --- Test to_native: Account ---


class TestToNativeAccount:

    def test_order_status(self, adapter, status_message):
        native = adapter.to_native(status_message)
        assert native["endpoint"] == "/api/v5/trade/order"
        assert native["params"]["ordId"] == "123456"
        assert native["signed"] is True

    def test_open_orders(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.LIST", parameters={}, validate=False)
        native = adapter.to_native(msg)
        assert native["endpoint"] == "/api/v5/trade/orders-pending"
        assert native["signed"] is True

    def test_wallet_balance(self, adapter, balance_message):
        native = adapter.to_native(balance_message)
        assert native["endpoint"] == "/api/v5/account/balance"
        assert native["signed"] is True

    def test_unsupported_action_raises(self, adapter):
        msg = PulseMessage(action="ACT.CREATE.TEXT", parameters={}, validate=False)
        with pytest.raises(AdapterError, match="Unsupported action"):
            adapter.to_native(msg)


# --- Test call_api ---


class TestCallAPI:

    def test_get_request(self, adapter):
        adapter._session.get.return_value = mock_response(
            [{"instId": "BTC-USDT", "last": "65000.50"}]
        )
        result = adapter.call_api({
            "method": "GET",
            "endpoint": "/api/v5/market/ticker",
            "params": {"instId": "BTC-USDT"},
            "signed": False,
        })
        assert result[0]["last"] == "65000.50"

    def test_post_request(self, adapter):
        adapter._session.post.return_value = mock_response(
            [{"ordId": "123456", "sCode": "0"}]
        )
        result = adapter.call_api({
            "method": "POST",
            "endpoint": "/api/v5/trade/order",
            "params": {"instId": "BTC-USDT", "side": "buy", "sz": "0.001"},
            "signed": True,
        })
        assert result[0]["ordId"] == "123456"

    def test_api_error_response(self, adapter):
        adapter._session.get.return_value = mock_response(
            [], code="51000", msg="Parameter error"
        )
        with pytest.raises(AdapterError, match="Parameter error"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/api/v5/market/ticker",
                "params": {"instId": "INVALID"},
                "signed": False,
            })

    def test_connection_error(self, adapter):
        adapter._session.get.side_effect = ConnectionError("Network down")
        with pytest.raises(AdapterConnectionError, match="Cannot reach"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/api/v5/market/ticker",
                "signed": False,
            })

    def test_sign_without_key_raises(self, adapter):
        adapter._api_key = None
        with pytest.raises(AdapterError, match="API key"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/api/v5/account/balance",
                "params": {},
                "signed": True,
            })


# --- Test Full Pipeline ---


class TestFullPipeline:

    def test_price_query(self, adapter, price_message):
        adapter._session.get.return_value = mock_response(
            [{"instId": "BTC-USDT", "last": "65000.50"}]
        )
        response = adapter.send(price_message)
        assert response.type == "RESPONSE"
        assert response.envelope["sender"] == "adapter:okx"

    def test_order_pipeline(self, adapter, buy_message):
        adapter._session.post.return_value = mock_response(
            [{"ordId": "order-123", "sCode": "0"}]
        )
        response = adapter.send(buy_message)
        assert response.content["parameters"]["result"][0]["ordId"] == "order-123"

    def test_pipeline_tracks_requests(self, adapter, price_message):
        adapter._session.get.return_value = mock_response([{"last": "100"}])
        adapter.send(price_message)
        adapter.send(price_message)
        assert adapter._request_count == 2


# --- Test Signing ---


class TestSigning:

    def test_sign_generates_headers(self, adapter):
        headers = adapter._sign_request("GET", "/api/v5/account/balance", "")
        assert "OK-ACCESS-KEY" in headers
        assert "OK-ACCESS-SIGN" in headers
        assert "OK-ACCESS-TIMESTAMP" in headers
        assert "OK-ACCESS-PASSPHRASE" in headers
        assert headers["OK-ACCESS-KEY"] == "test-key"
        assert headers["OK-ACCESS-PASSPHRASE"] == "test-pass"


# --- Test Supported Actions ---


class TestSupportedActions:

    def test_supported_actions(self, adapter):
        actions = adapter.supported_actions
        assert "ACT.QUERY.DATA" in actions
        assert "ACT.TRANSACT.REQUEST" in actions
        assert "ACT.CANCEL" in actions
        assert len(actions) == 6

    def test_supports_check(self, adapter):
        assert adapter.supports("ACT.QUERY.DATA") is True
        assert adapter.supports("ACT.CREATE.TEXT") is False


# --- Test Exchange Switching ---


class TestExchangeSwitching:
    """Prove exchange switching works."""

    def test_same_actions_as_binance(self):
        from pulse_binance import BinanceAdapter
        binance = BinanceAdapter(api_key="k", api_secret="s")
        okx = OKXAdapter(api_key="k", api_secret="s", passphrase="p")
        assert set(binance.supported_actions) == set(okx.supported_actions)

    def test_same_message_works(self, adapter, price_message):
        adapter._session.get.return_value = mock_response([{"last": "65000"}])
        response = adapter.send(price_message)
        assert response.type == "RESPONSE"
