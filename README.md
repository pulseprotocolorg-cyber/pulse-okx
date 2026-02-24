# PULSE-OKX

**OKX adapter for PULSE Protocol — trade OKX with semantic messages.**

Write your trading bot once, run it on any exchange. Same code works with Binance, Bybit, Kraken — just change one line.

## Quick Start

```bash
pip install pulse-okx
```

```python
from pulse import PulseMessage
from pulse_okx import OKXAdapter

# Connect
adapter = OKXAdapter(
    api_key="your-key",
    api_secret="your-secret",
    passphrase="your-passphrase",
)
adapter.connect()

# Get BTC price
msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "BTC-USDT"})
response = adapter.send(msg)
print(response.content["parameters"]["result"])
```

## Switch Exchanges in One Line

```python
# from pulse_binance import BinanceAdapter as Adapter
from pulse_okx import OKXAdapter as Adapter

adapter = Adapter(api_key="...", api_secret="...")
```

Your bot code stays exactly the same. Only the import changes.

## Supported Actions

| PULSE Action | What It Does | OKX Endpoint |
|---|---|---|
| `ACT.QUERY.DATA` | Price, candles, order book | `/api/v5/market/ticker`, `/candles`, `/books` |
| `ACT.TRANSACT.REQUEST` | Place market/limit order | `/api/v5/trade/order` |
| `ACT.CANCEL` | Cancel an order | `/api/v5/trade/cancel-order` |
| `ACT.QUERY.STATUS` | Check order status | `/api/v5/trade/order` |
| `ACT.QUERY.LIST` | List open orders | `/api/v5/trade/orders-pending` |
| `ACT.QUERY.BALANCE` | Account balance | `/api/v5/account/balance` |

## Examples

### Query price

```python
msg = PulseMessage(
    action="ACT.QUERY.DATA",
    parameters={"symbol": "BTC-USDT", "type": "price"}
)
response = adapter.send(msg)
```

### Place a limit order

```python
msg = PulseMessage(
    action="ACT.TRANSACT.REQUEST",
    parameters={
        "symbol": "ETH-USDT",
        "side": "buy",
        "quantity": 0.1,
        "order_type": "limit",
        "price": 3000,
    }
)
response = adapter.send(msg)
```

## Features

- **HMAC-SHA256 + Base64 authentication** — OKX signing fully handled
- **Passphrase support** — required by OKX, just pass it to the constructor
- **Demo mode** — test with `OKXAdapter(demo=True)`, uses simulated trading
- **OKX pair format** — use `BTC-USDT`, `ETH-USDT` (with dashes)
- **Tiny footprint** — one file, ~10 KB

## OKX-Specific Notes

- OKX uses dashed pairs: `BTC-USDT` (not `BTCUSDT`)
- Passphrase is required in addition to API key and secret
- OKX V5 API returns `{"code": "0"}` for success
- Trade mode defaults to `cash` (spot). Pass `td_mode` to change
- Demo mode adds `x-simulated-trading: 1` header automatically

## Testing

```bash
pytest tests/ -q  # 35 tests, all mocked
```

## PULSE Ecosystem

| Package | Provider | Install |
|---|---|---|
| [pulse-protocol](https://pypi.org/project/pulse-protocol/) | Core | `pip install pulse-protocol` |
| [pulse-binance](https://pypi.org/project/pulse-binance/) | Binance | `pip install pulse-binance` |
| [pulse-bybit](https://pypi.org/project/pulse-bybit/) | Bybit | `pip install pulse-bybit` |
| [pulse-kraken](https://pypi.org/project/pulse-kraken/) | Kraken | `pip install pulse-kraken` |
| **pulse-okx** | **OKX** | `pip install pulse-okx` |
| [pulse-openai](https://pypi.org/project/pulse-openai/) | OpenAI | `pip install pulse-openai` |
| [pulse-anthropic](https://pypi.org/project/pulse-anthropic/) | Anthropic | `pip install pulse-anthropic` |
| [pulse-gateway](https://pypi.org/project/pulse-gateway/) | Gateway | `pip install pulse-gateway` |

## License

Apache 2.0 — open source, free forever.
