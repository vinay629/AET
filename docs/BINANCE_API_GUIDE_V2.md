# Binance API Complete Guide (Latest - May 7, 2026)

> **Based on official Binance Spot API Documentation**
> **Last Updated:** May 7, 2026 (Latest Commit: 18a5f24)
> **Source:** https://github.com/binance/binance-spot-api-docs
>
> **This is the current/recommended version.** For the older guide, see `BINANCE_API_GUIDE.md`.

---

## Table of Contents

1. [Latest Changes (May 2026)](#latest-changes-may-2026)
2. [Overview](#overview)
3. [API Base Endpoints](#api-base-endpoints)
4. [REST API Reference](#rest-api-reference)
5. [WebSocket Streams](#websocket-streams)
6. [WebSocket API](#websocket-api)
7. [Authentication & Security](#authentication--security)
8. [Rate Limits](#rate-limits)
9. [Error Handling](#error-handling)
10. [Data Formats](#data-formats)
11. [Order Types & Trading](#order-types--trading)
12. [Best Practices](#best-practices)
13. [Implementation Examples](#implementation-examples)

---

## Latest Changes (May 2026)

### May 7, 2026 (Commit 18a5f24 - Latest)

#### New Features:
- **`serverShutdown` Event**: Added to WebSocket API and WebSocket Streams
  - Sent 10 minutes before disconnection
  - Applies to: WebSocket API, WebSocket Streams

- **Historical Block Trades**
  - New REST Endpoint: `GET /api/v3/historicalBlockTrades`
  - New WebSocket API Method: `blockTrades.historical`

- **`expiryReason` Field**
  - Added to order query responses
  - Explains why an order expired (e.g., price range execution rule)
  - Applies to:
    - `GET /api/v3/order`
    - `GET /api/v3/allOrders`
    - `GET /api/v3/orderList`
    - `GET /api/v3/allOrderList`
    - WebSocket API: `order.status`, `allOrders`, `orderList.status`, `allOrderLists`

- **SBE Schema 3:4 Released**
  - New message: `BlockTradesResponse`
  - New type: `blockTradeId`
  - New field: `expiryReason` in `OrderResponse` and `OrdersResponse`
  - **Schema 3:3 deprecated** (retirement in 6 months)

- **Filter Updates**
  - `PERCENT_PRICE`, `PERCENT_PRICE_BY_SIDE`, `MIN_NOTIONAL`, `NOTIONAL` filters now use [reference price](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/price_range_execution_rules.md) when available
  - Falls back to previous behavior when reference price doesn't exist or is null

#### Deployment Schedule:
- **May 8, 2026 at 06:00 UTC** (may take several hours to complete)

---

## Overview

The Binance API provides programmatic access to Binance's trading engine, market data, and account management features.

### API Types

| Type | Description | Base URL |
|------|-------------|----------|
| **REST API** | Request-response style, for most operations | `https://api.binance.com` |
| **WebSocket Streams** | Real-time market data | `wss://stream.binance.com:9443/ws` |
| **WebSocket API** | Real-time bidirectional API | `wss://ws-api.binance.com:443/ws-api/v3` |

### Alternative Base URLs (Better Performance)

```python
# Better performance endpoints
BASE_URLS = [
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]
```

> **Note:** `api1`-`api4` have better performance but less stability.

### Market Data Only Endpoint

For public market data without API limits:
```python
DATA_API_URL = "https://data-api.binance.vision"
```

---

## API Base Endpoints

### REST API Base URLs

```python
# Primary
BASE_URL = "https://api.binance.com"

# Alternatives (better performance)
BASE_URLS = [
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]

# Market data only (no rate limits for public endpoints)
DATA_API_URL = "https://data-api.binance.vision"
```

### WebSocket Base URLs

```python
# Combined streams
WS_BASE_URL = "wss://stream.binance.com:9443/ws"

# Single stream
WS_STREAM_URL = "wss://stream.binance.com:9443/stream"

# WebSocket API
WS_API_URL = "wss://ws-api.binance.com:443/ws-api/v3"

# Market data only
WS_DATA_URL = "wss://data-stream.binance.vision"
```

---

## REST API Reference

### General Endpoints

#### Test Connectivity
```
GET /api/v3/ping
```
**Weight:** 1
**Parameters:** None

**Response:**
```json
{}
```

#### Check Server Time
```
GET /api/v3/time
```
**Weight:** 1
**Parameters:** None

**Response:**
```json
{
    "serverTime": 1499827319559
}
```

#### Exchange Information
```
GET /api/v3/exchangeInfo
```
**Weight:** 20

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | NO | Single symbol (e.g., BTCUSDT) |
| symbols | ARRAY OF STRING | NO | Multiple symbols |
| permissions | ENUM | NO | SPOT, MARGIN, LEVERAGED |
| showPermissionSets | BOOLEAN | NO | Show permission sets |
| symbolStatus | ENUM | NO | TRADING, HALT, BREAK |

**Response:**
```json
{
    "timezone": "UTC",
    "serverTime": 1565246363776,
    "rateLimits": [...],
    "exchangeFilters": [...],
    "symbols": [
        {
            "symbol": "ETHBTC",
            "status": "TRADING",
            "baseAsset": "ETH",
            "baseAssetPrecision": 8,
            "quoteAsset": "BTC",
            "quotePrecision": 8,
            "orderTypes": ["LIMIT", "MARKET", "STOP_LOSS", ...],
            "icebergAllowed": true,
            "ocoAllowed": true,
            "isSpotTradingAllowed": true,
            "filters": [...],
            "permissions": ["SPOT", "MARGIN"],
            "permissionSets": [["SPOT"], ["MARGIN"]]
        }
    ]
}
```

#### Query Execution Rules (New - March 2026)
```
GET /api/v3/executionRules
```
**Weight:** 2-40 (based on parameters)

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | NO | Single symbol |
| symbols | STRING | NO | Multiple symbols |
| symbolStatus | ENUM | NO | TRADING, HALT, BREAK |

**Response:**
```json
{
    "symbolRules": [
        {
            "symbol": "BAZUSD",
            "rules": [
                {
                    "ruleType": "PRICE_RANGE",
                    "bidLimitMultUp": "1.0001",
                    "bidLimitMultDown": "0.9999",
                    "askLimitMultUp": "1.0001",
                    "askLimitMultDown": "0.9999"
                }
            ]
        }
    ]
}
```

#### Reference Price (New - March 2026)
```
GET /api/v3/referencePrice
```
**Weight:** 2

**Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| symbol | STRING | YES |

**Response:**
```json
{
    "symbol": "BAZUSD",
    "referencePrice": "10.00",
    "timestamp": 1770736694138
}
```

#### Reference Price Calculation (New - March 2026)
```
GET /api/v3/referencePrice/calculation
```
**Weight:** 2

**Response:**
```json
{
    "symbol": "BAZUSD",
    "calculationType": "ARITHMETIC_MEAN",
    "bucketCount": 10,
    "bucketWidthMs": 1000
}
```

---

### Market Data Endpoints

#### Order Book (Depth)
```
GET /api/v3/depth
```
**Weight:** 5-250 (based on limit)

| Limit | Weight |
|-------|--------|
| 1-100 | 5 |
| 101-500 | 25 |
| 501-1000 | 50 |
| 1001-5000 | 250 |

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | STRING | YES | | Trading pair |
| limit | INT | NO | 100 | Max 5000 |
| symbolStatus | ENUM | NO | | TRADING, HALT, BREAK |

#### Recent Trades List
```
GET /api/v3/trades
```
**Weight:** 25 (changed from 2 in Aug 2023)

#### Historical Block Trades (New - May 2026)
```
GET /api/v3/historicalBlockTrades
```
**Weight:** 25

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| fromId | LONG | YES | Block trade ID to fetch from |
| limit | LONG | NO | Default: 500; Max: 1000 |

**Response:**
```json
[
  {
    "id": 582,
    "price": "0.052",
    "qty": "5838",
    "quoteQty": "303.576",
    "time": 1772506983321,
    "isBuyerMaker": true
  }
]
```

#### Historical Trades
```
GET /api/v3/historicalTrades
```
**Weight:** 25

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| limit | INT | NO | Default 500, Max 1000 |
| fromId | LONG | NO | TradeId to fetch from |

#### Compressed/Aggregate Trades
```
GET /api/v3/aggTrades
```
**Weight:** 2 (changed from 1 in March 2025)

#### Kline/Candlestick Data
```
GET /api/v3/klines
```
**Weight:** 2

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| interval | ENUM | YES | See intervals below |
| startTime | LONG | NO | |
| endTime | LONG | NO | |
| timeZone | STRING | NO | Default: 0 (UTC) |
| limit | INT | NO | Default: 500, Max: 1000 |

**Supported Kline Intervals:**

| Interval | Values |
|----------|--------|
| Seconds | `1s` |
| Minutes | `1m`, `3m`, `5m`, `15m`, `30m` |
| Hours | `1h`, `2h`, `4h`, `6h`, `8h`, `12h` |
| Days | `1d`, `3d` |
| Weeks | `1w` |
| Months | `1M` |

#### Reference Price Stream (New - March 2026)
```
<symbol>@referencePrice
```
**Update Speed:** 1000ms

**Payload:**
```json
{
    "e": "referencePrice",
    "s": "BAZUSD",
    "r": "1.00",
    "t": 1770313263917
}
```

---

### Trading Endpoints

#### New Order
```
POST /api/v3/order
```
**Weight:** 1
**Unfilled Order Count:** +1

**New Field (May 2026):** `expiryReason` - Returned for expired orders

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| side | ENUM | YES | BUY or SELL |
| type | ENUM | YES | See Order Types |
| timeInForce | ENUM | NO | GTC, IOC, FOK |
| quantity | DECIMAL | NO* | *Required for some order types |
| quoteOrderQty | DECIMAL | NO* | |
| price | DECIMAL | NO* | |
| newClientOrderId | STRING | NO | Unique ID |
| stopPrice | DECIMAL | NO | For STOP_LOSS, etc. |
| trailingDelta | LONG | NO | For trailing stop orders |
| icebergQty | DECIMAL | NO | For iceberg orders |
| newOrderRespType | ENUM | NO | ACK, RESULT, FULL |
| selfTradePreventionMode | ENUM | NO | NONE, EXPIRE_MAKER, EXPIRE_TAKER, EXPIRE_BOTH |
| recvWindow | DECIMAL | NO | Max 60000 (supports microseconds) |
| timestamp | LONG | YES | |

**New Field in Response (May 2026):**
```json
{
    "expiryReason": "INSUFFICIENT_LIQUIDITY"  // Why order expired
}
```

#### Query Order
```
GET /api/v3/order
```
**Weight:** 4

**New Field (May 2026):** `expiryReason` - Returned for expired orders

#### All Orders
```
GET /api/v3/allOrders
```
**Weight:** 20

**New Field (May 2026):** `expiryReason` - Returned for expired orders

#### Order List Queries
```
GET /api/v3/orderList
GET /api/v3/allOrderList
GET /api/v3/openOrderList
```
**New Field (May 2026):** `expiryReason` - Returned for expired order lists

---

## WebSocket Streams

### Server Shutdown Event (New - May 2026)

`serverShutdown` event is sent 10 minutes before disconnection.

**Raw stream:**
```json
{
    "e": "serverShutdown",
    "E": 1770123456789
}
```

**Combined stream:**
```json
{
    "stream": "!serverShutdown",
    "data": {
        "e": "serverShutdown",
        "E": 1770123456789
    }
}
```

> **Note:** Establish a new connection as soon as possible to prevent interruption.

### General Information

- **Base endpoint:** `wss://stream.binance.com:9443` or `wss://stream.binance.com:443`
- **Stream types:**
  - Single stream: `/ws/<streamName>`
  - Combined stream: `/stream?streams=<stream1>/<stream2>/...`
- **Combined stream format:** `{"stream":"<streamName>","data":<rawPayload>}`
- **Symbol format:** All symbols are lowercase
- **Connection lifetime:** 24 hours (expect disconnection)
- **Ping/Pong:** Server sends ping every 20 seconds; respond with pong within 1 minute
- **Time units:** Add `timeUnit=MICROSECOND` or `timeUnit=microsecond` for microsecond timestamps

### Stream Limits

- **Message rate:** 5 incoming messages per second (PING, PONG, control messages)
- **Max streams per connection:** 1024
- **Connection rate limit:** 300 per 5 minutes per IP

### Available Streams

| Stream | Format | Update Speed |
|--------|--------|--------------|
| Reference Price | `<symbol>@referencePrice` | 1000ms |
| Aggregate Trade | `<symbol>@aggTrade` | Real-time |
| Trade | `<symbol>@trade` | Real-time |
| Kline | `<symbol>@kline_<interval>` | 1000ms (1s), 2000ms (others) |
| Kline with timezone | `<symbol>@kline_<interval>@+08:00` | 2000ms |
| Mini Ticker | `<symbol>@miniTicker` | 1000ms |
| All Mini Tickers | `!miniTicker@arr` | 1000ms |
| Ticker | `<symbol>@ticker` | 1000ms |
| Rolling Window | `<symbol>@ticker_<window>` | 1000ms |
| Book Ticker | `<symbol>@bookTicker` | Real-time |
| Partial Depth | `<symbol>@depth<levels>` | Real-time |
| Diff Depth | `<symbol>@depth@100ms` | 100ms |

### Live Subscribe/Unsubscribe (WebSocket Streams)

```json
// Subscribe
{
    "method": "SUBSCRIBE",
    "params": ["btcusdt@aggTrade", "btcusdt@depth"],
    "id": 1
}

// Unsubscribe
{
    "method": "UNSUBSCRIBE",
    "params": ["btcusdt@depth"],
    "id": 312
}

// List subscriptions
{
    "method": "LIST_SUBSCRIPTIONS",
    "id": 3
}
```

---

## WebSocket API

The WebSocket API provides request-response functionality over WebSocket.

**Base URL:**
```
wss://ws-api.binance.com:443/ws-api/v3
```

**Request Format:**
```json
{
    "id": "unique-id",
    "method": "order.place",
    "params": {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "price": "40000",
        "quantity": "0.001"
    }
}
```

**Response Format:**
```json
{
    "id": "unique-id",
    "status": 200,
    "result": { ... },
    "rateLimits": [...]
}
```

### New Methods (May 2026)

- `blockTrades.historical` - Query historical block trades
- `executionRules` - Query price range execution rules
- `referencePrice` - Get reference price
- `referencePrice.calculation` - Get reference price calculation method

### User Data Stream Subscription (New - Aug 2024)

Subscribe to user data without logging in first:
```json
{
    "method": "userDataStream.subscribe.signature",
    "params": {
        "apiKey": "your_api_key"
    },
    "id": 1
}
```

---

## Authentication & Security

### API Key Types

| Type | Signature Algorithm | Case Sensitive | Recommended |
|------|-------------------|-----------------|--------------|
| **HMAC** | HMAC-SHA256 | No | |
| **RSA** | RSASSA-PKCS1-v1_5 with SHA-256 | Yes | |
| **Ed25519** | Ed25519 with SHA-256 | Yes | ✅ Yes |

> **Recommendation:** Use Ed25519 keys for best performance and security.

### SIGNED Endpoints

All endpoints with security type `TRADE` and `USER_DATA` require:
1. `X-MBX-APIKEY` header
2. `signature` parameter
3. `timestamp` parameter

### Signature Generation (HMAC Example)

```python
import hmac
import hashlib
from urllib.parse import urlencode

def generate_signature(secret_key, params):
    query_string = urlencode(params)
    signature = hmac.new(
        secret_key.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature
```

### Timing Security

```
recvWindow: Maximum 60000 ms (default: 5000 ms)
             Supports microseconds (e.g., 6000.346)
timestamp: Current time in ms or μs
```

---

## Rate Limits

### Rate Limit Types

| Type | Description |
|------|-------------|
| **REQUEST_WEIGHT** | General API weight |
| **ORDERS** | Order placement rate |
| **RAW_REQUESTS** | Total requests (300,000 per 5 min since March 2026) |

### Rate Limit Headers

| Header | Description |
|--------|-------------|
| `X-MBX-USED-WEIGHT-<interval>` | Current used weight |
| `X-MBX-ORDER-COUNT-<interval>` | Current order count |
| `Retry-After` | Seconds to wait (with 429/418) |

### Weight Changes (March 2026)

**Successful requests now have 0 weight** for:
- `POST /api/v3/order`
- `POST /api/v3/sor/order`
- `DELETE /api/v3/order`
- `DELETE /api/v3/openOrders`
- `POST /api/v3/order/cancelReplace`
- And all order list placement endpoints

> **Note:** Failed requests still charged the documented weight.

---

## Error Handling

### Common Error Codes (New - 2026)

| Code | Message | Description |
|------|---------|-------------|
| -1003 | TOO_MANY_REQUESTS | Rate limit exceeded |
| -1022 | INVALID_SIGNATURE | Invalid signature |
| -1121 | INVALID_SYMBOL | Invalid symbol |
| -2013 | NO_SUCH_ORDER | Order not found |
| -2026 | ORDER_ARCHIVED | Order archived (>90 days) |
| -2038 | ORDER_AMEND_FAILED | Order amend failed |
| -2039 | COMBINATION_INVALID | Both orderId & origClientOrderId not found |

### New Error Responses (May 2026)

**Expired Order with Reason:**
```json
{
    "orderId": 28,
    "status": "EXPIRED",
    "expiryReason": "INSUFFICIENT_LIQUIDITY"
}
```

---

## Data Formats

### Timestamps

- **Default:** Milliseconds (ms)
- **Microseconds:** Add header `X-MBX-TIME-UNIT: MICROSECOND` or URL parameter `timeUnit=microsecond`
- **Range validation:** Timestamps before 2017-01-01 or >10 seconds in future are rejected

### Price & Quantity Precision

- Defined per symbol in `exchangeInfo`
- Use `baseAssetPrecision` and `quotePrecision`
- Respect `LOT_SIZE` and `MIN_NOTIONAL` filters
- **New:** Filters now use reference price when available

### Enumerations

#### Order Side
- `BUY`
- `SELL`

#### Self-Trade Prevention Mode (Updated)
- `NONE`
- `EXPIRE_MAKER`
- `EXPIRE_TAKER`
- `EXPIRE_BOTH`
- `TRANSFER` (New - Dec 2025)

#### Expiry Reasons (New - May 2026)
- `INSUFFICIENT_LIQUIDITY`
- `PRICE_RANGE_EXCEEDED`

---

## Order Types & Trading

### New Features (2026)

#### Price Range Execution Rule (March 2026)
- Filters use reference price when available
- Applies to: `PERCENT_PRICE`, `PERCENT_PRICE_BY_SIDE`, `MIN_NOTIONAL`, `NOTIONAL`

#### Block Trades (May 2026)
- New endpoint: `GET /api/v3/historicalBlockTrades`
- Block trade ID tracking

#### Order Amend Keep Priority (April 2025)
```
PUT /api/v3/order/amend/keepPriority
```
**Weight:** 4 (changed from 1 in April 2025)
**Unfilled Order Count:** 0

### Order Types

| Type | Required Parameters |
|------|----------------------|
| LIMIT | timeInForce, quantity, price |
| MARKET | quantity OR quoteOrderQty |
| STOP_LOSS | quantity, stopPrice |
| STOP_LOSS_LIMIT | timeInForce, quantity, price, stopPrice |
| TAKE_PROFIT | quantity, stopPrice |
| TAKE_PROFIT_LIMIT | timeInForce, quantity, price, stopPrice |
| LIMIT_MAKER | quantity, price |

---

## Best Practices

### 1. Handle New `serverShutdown` Event
```python
def on_message(ws, message):
    data = json.loads(message)
    if data.get('e') == 'serverShutdown':
        print("Server shutting down in 10 minutes!")
        # Establish new connection
```

### 2. Check `expiryReason` Field
```python
def handle_order_status(order):
    if order['status'] == 'EXPIRED':
        reason = order.get('expiryReason', 'UNKNOWN')
        print(f"Order expired due to: {reason}")
```

### 3. Use Ed25519 Keys
- Better performance
- Better security
- Case-sensitive signatures

### 4. Respect Rate Limit Changes (March 2026)
- Successful orders now have 0 weight
- Failed orders still charged
- RAW_REQUESTS limit: 300,000 per 5 min

### 5. Handle Block Trades
```python
# New endpoint for block trades
response = requests.get(
    f"{BASE_URL}/api/v3/historicalBlockTrades",
    params={'symbol': 'BTCUSDT', 'fromId': 582}
)
```

---

## Implementation Examples

### Updated Client with New Features (May 2026)

```python
import requests
import hmac
import hashlib
from urllib.parse import urlencode
from datetime import datetime

class BinanceClient2026:
    """Updated client with May 2026 features."""

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.binance.com"
        self.session = requests.Session()
        self.session.headers.update({'X-MBX-APIKEY': api_key})

    def get_block_trades(self, symbol, from_id):
        """New endpoint - May 2026"""
        params = {
            'symbol': symbol,
            'fromId': from_id,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        params = self._sign(params)
        return self.session.get(
            f"{self.base_url}/api/v3/historicalBlockTrades",
            params=params
        ).json()

    def get_reference_price(self, symbol):
        """Get reference price - March 2026"""
        return self.session.get(
            f"{self.base_url}/api/v3/referencePrice",
            params={'symbol': symbol}
        ).json()

    def _sign(self, params):
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        return params
```

### WebSocket with serverShutdown Handling

```python
import websocket
import json
import threading

class BinanceWS2026:
    """WebSocket client with serverShutdown handling."""

    def __init__(self):
        self.ws = None
        self.reconnecting = False

    def on_message(self, ws, message):
        data = json.loads(message)

        # Handle serverShutdown (New - May 2026)
        if data.get('e') == 'serverShutdown':
            print("Server shutting down! Reconnecting...")
            self.reconnecting = True
            self.reconnect()
            return

        # Process other messages
        print(data)

    def reconnect(self):
        """Establish new connection before disconnection."""
        if not self.reconnecting:
            thread = threading.Thread(target=self.start)
            thread.start()

    def start(self):
        self.ws = websocket.WebSocketApp(
            "wss://stream.binance.com:9443/ws/btcusdt@trade",
            on_message=self.on_message
        )
        self.ws.run_forever()
```

---

## Quick Reference - New Features (2026)

| Feature | Endpoint/Method | Date |
|--------|-------------------|------|
| serverShutdown event | WebSocket API/Streams | May 2026 |
| Block Trades | `GET /api/v3/historicalBlockTrades` | May 2026 |
| expiryReason field | Order queries | May 2026 |
| SBE 3:4 | New schema | May 2026 |
| Reference Price | `GET /api/v3/referencePrice` | March 2026 |
| Execution Rules | `GET /api/v3/executionRules` | March 2026 |
| 0 weight for successful orders | Trading endpoints | March 2026 |
| Ed25519 keys | All signed endpoints | July 2023 |
| STP Transfer mode | Order placement | Dec 2025 |

---

## Resources

- **Official Docs:** https://github.com/binance/binance-spot-api-docs
- **Latest Changelog:** https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md
- **API Status:** https://t.me/binance_api_announcements
- **Testnet:** https://testnet.binance.vision/
- **Python Connector:** https://github.com/binance/binance-connector-python

---

*This guide reflects the latest Binance Spot API changes as of May 7, 2026 (Commit 18a5f24). Always refer to the official documentation for the most up-to-date information.*
