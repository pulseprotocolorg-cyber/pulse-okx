"""
PULSE-OKX Adapter.

Bridge PULSE Protocol messages to OKX V5 API.
Same interface as pulse-binance — swap exchanges in one line.

Example:
    >>> from pulse_okx import OKXAdapter
    >>> adapter = OKXAdapter(api_key="...", api_secret="...", passphrase="...")
    >>> from pulse import PulseMessage
    >>> msg = PulseMessage(
    ...     action="ACT.QUERY.DATA",
    ...     parameters={"symbol": "BTC-USDT"}
    ... )
    >>> response = adapter.send(msg)
"""

from pulse_okx.adapter import OKXAdapter
from pulse_okx.version import __version__

__all__ = ["OKXAdapter", "__version__"]
