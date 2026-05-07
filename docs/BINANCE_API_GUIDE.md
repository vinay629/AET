# Binance API Complete Guide

> **Based on official Binance Spot API Documentation**  
> **Last Updated:** May 2026 (API Docs v2.0)  
> **Source:** https://github.com/binance/binance-spot-api-docs

---

## Table of Contents

1. [Overview](#overview)
2. [API Base Endpoints](#api-base-endpoints)
3. [REST API Reference](#rest-api-reference)
4. [WebSocket Streams](#websocket-streams)
5. [WebSocket API](#websocket-api)
6. [Authentication & Security](#authentication--security)
7. [Rate Limits](#rate-limits)
8. [Error Handling](#error-handling)
9. [Data Formats](#data-formats)
10. [Order Types & Trading](#order-types--trading)
11. [Best Practices](#best-practices)
12. [Implementation Examples](#implementation-examples)

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

```
https://api-gcp.binance.com
https://api1.binance.com
https://api2.binance.com
https://api3.binance.com
https://api4.binance.com
```

> **Note:** `api1`-`api4` have better performance but less stability.

### Market Data Only Endpoint

For public market data without API limits:
```
https://data-api.binance.vision
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

#### Query Execution Rules
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

**Response:**
```json
{
    "lastUpdateId": 1027024,
    "bids": [["4.00000000", "431.00000000"]],
    "asks": [["4.00000200", "12.00000000"]]
}
```

#### Recent Trades List
```
GET /api/v3/trades
```
**Weight:** 25

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | STRING | YES | | Trading pair |
| limit | INT | NO | 500 | Max 1000 |

**Response:**
```json
[
    {
        "id": 28457,
        "price": "4.00000100",
        "qty": "12.00000000",
        "quoteQty": "48.000012",
        "time": 1499865549590,
        "isBuyerMaker": true,
        "isBestMatch": true
    }
]
```

#### Historical Block Trades (New - May 2026)
```
GET /api/v3/historicalBlockTrades
```
**Weight:** 25

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | Trading pair |
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
**Weight:** 4

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| fromId | LONG | NO | Aggregate trade ID |
| startTime | LONG | NO | Timestamp in ms |
| endTime | LONG | NO | Timestamp in ms |
| limit | INT | NO | Default 500, Max 1000 |

**Response:**
```json
[
    {
        "a": 26129,           // Aggregate tradeId
        "p": "0.01634790",   // Price
        "q": "4.70443515",   // Quantity
        "f": 27781,           // First tradeId
        "l": 27781,           // Last tradeId
        "T": 1498793709153,   // Timestamp
        "m": true,             // Was buyer the maker?
        "M": true              // Was trade best price match?
    }
]
```

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

**Response:**
```json
[
    [
        1499040000000,      // Open time
        "0.01634790",       // Open price
        "0.80000000",       // High price
        "0.01575800",       // Low price
        "0.01577100",       // Close price
        "148976.11427815",  // Volume
        1499644799999,      // Close time
        "2434.19055334",    // Quote asset volume
        308,                 // Number of trades
        "1756.87402397",    // Taker buy base volume
        "28.46694368",      // Taker buy quote volume
        "0"                  // Unused field
    ]
]
```

#### UIKlines (Optimized for Charts)
```
GET /api/v3/uiKlines
```
**Weight:** 2  
Same parameters as klines, optimized for UI display.

#### Current Average Price
```
GET /api/v3/avgPrice
```
**Weight:** 2

**Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| symbol | STRING | YES |

**Response:**
```json
{
    "mins": 5,
    "price": "9.35751834",
    "closeTime": 1694061154503
}
```

#### 24hr Ticker Price Change Statistics
```
GET /api/v3/ticker/24hr
```
**Weight:** 1-80 (based on symbols)

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | NO | Single symbol |
| symbols | STRING | NO | Multiple symbols (max 100) |
| type | ENUM | NO | FULL or MINI |
| symbolStatus | ENUM | NO | TRADING, HALT, BREAK |

**Response (FULL):**
```json
{
    "symbol": "BNBBTC",
    "priceChange": "-94.99999800",
    "priceChangePercent": "-95.960",
    "weightedAvgPrice": "0.29628482",
    "prevClosePrice": "0.10002000",
    "lastPrice": "4.00000200",
    "lastQty": "200.00000000",
    "bidPrice": "4.00000000",
    "bidQty": "100.00000000",
    "askPrice": "4.00000200",
    "askQty": "100.00000000",
    "openPrice": "99.00000000",
    "highPrice": "100.00000000",
    "lowPrice": "0.10000000",
    "volume": "8913.30000000",
    "quoteVolume": "15.30000000",
    "openTime": 1499783499040,
    "closeTime": 1499869899040,
    "firstId": 28385,
    "lastId": 28460,
    "count": 76
}
```

#### Symbol Price Ticker
```
GET /api/v3/ticker/price
```
**Weight:** 1-4

**Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| symbol | STRING | NO |
| symbols | STRING | NO |

**Response:**
```json
{
    "symbol": "LTCBTC",
    "price": "4.00000200"
}
```

#### Symbol Order Book Ticker
```
GET /api/v3/ticker/bookTicker
```
**Weight:** 1-4

**Response:**
```json
{
    "symbol": "LTCBTC",
    "bidPrice": "4.00000000",
    "bidQty": "431.00000000",
    "askPrice": "4.00000200",
    "askQty": "9.00000000"
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

**New Field (May 2026):** `expiryReason` - Returned for expired orders to explain why the order expired (e.g., price range execution rule).

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
| icebergQty | DECIMAL | NO | For iceberg orders |
| newOrderRespType | ENUM | NO | ACK, RESULT, FULL |
| recvWindow | DECIMAL | NO | Max 60000 |
| timestamp | LONG | YES | |

**Order Types & Required Parameters:**

| Type | Required Parameters |
|------|----------------------|
| LIMIT | timeInForce, quantity, price |
| MARKET | quantity OR quoteOrderQty |
| STOP_LOSS | quantity, stopPrice |
| STOP_LOSS_LIMIT | timeInForce, quantity, price, stopPrice |
| TAKE_PROFIT | quantity, stopPrice |
| TAKE_PROFIT_LIMIT | timeInForce, quantity, price, stopPrice |
| LIMIT_MAKER | quantity, price |

**Response (ACK):**
```json
{
    "symbol": "BTCUSDT",
    "orderId": 28,
    "orderListId": -1,
    "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
    "transactTime": 1507725176595
}
```

**Response (FULL):**
```json
{
    "symbol": "BTCUSDT",
    "orderId": 28,
    "orderListId": -1,
    "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
    "transactTime": 1507725176595,
    "price": "0.00000000",
    "origQty": "10.00000000",
    "executedQty": "10.00000000",
    "cummulativeQuoteQty": "10.00000000",
    "status": "FILLED",
    "timeInForce": "GTC",
    "type": "MARKET",
    "side": "SELL",
    "fills": [
        {
            "price": "4000.00000000",
            "qty": "1.00000000",
            "commission": "4.00000000",
            "commissionAsset": "USDT",
            "tradeId": 56
        }
    ]
}
```

#### Test New Order
```
POST /api/v3/order/test
```
**Weight:** 1-20  
Validates order but doesn't submit to matching engine.

#### Cancel Order
```
DELETE /api/v3/order
```
**Weight:** 1

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| orderId | LONG | NO* | *Either orderId or origClientOrderId |
| origClientOrderId | STRING | NO* | |
| newClientOrderId | STRING | NO | |
| recvWindow | DECIMAL | NO | |
| timestamp | LONG | YES | |

#### Cancel All Open Orders
```
DELETE /api/v3/openOrders
```
**Weight:** 1  
Cancels all open orders on a symbol.

#### Cancel and Replace Order
```
POST /api/v3/order/cancelReplace
```
**Weight:** 1  
**Unfilled Order Count:** +1

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| cancelReplaceMode | ENUM | YES | STOP_ON_FAILURE, ALLOW_FAILURE |
| cancelOrderId | LONG | NO* | |
| cancelOrigClientOrderId | STRING | NO* | |
| side | ENUM | YES | |
| type | ENUM | YES | |
| timestamp | LONG | YES | |

#### Order Amend Keep Priority
```
PUT /api/v3/order/amend/keepPriority
```
**Weight:** 4  
**Unfilled Order Count:** 0

Reduces quantity of existing open order.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| orderId | LONG | NO* | |
| origClientOrderId | STRING | NO* | |
| newQty | DECIMAL | YES | Must be less than current qty |
| timestamp | LONG | YES | |

---

### Order Lists (OCO, OTO, OTOCO)

#### New OCO Order (Deprecated)
```
POST /api/v3/order/oco
```
**Weight:** 1  
**Unfilled Order Count:** +2

#### New OCO Order
```
POST /api/v3/orderList/oco
```
**Weight:** 1  
**Unfilled Order Count:** +2

#### New OTO Order
```
POST /api/v3/orderList/oto
```
**Weight:** 1  
**Unfilled Order Count:** +2

#### New OTOCO Order
```
POST /api/v3/orderList/otoco
```
**Weight:** 1  
**Unfilled Order Count:** +3

#### New OPO Order
```
POST /api/v3/orderList/opo
```
**Weight:** 1  
**Unfilled Order Count:** +2

#### New OPOCO Order
```
POST /api/v3/orderList/opoco
```
**Weight:** 1  
**Unfilled Order Count:** +3

#### Cancel Order List
```
DELETE /api/v3/orderList
```
**Weight:** 1

---

### SOR (Smart Order Routing)

#### New Order Using SOR
```
POST /api/v3/sor/order
```
**Weight:** 1  
Routes order across multiple liquidity pools.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | STRING | YES | |
| side | ENUM | YES | BUY or SELL |
| type | ENUM | YES | LIMIT or MARKET only |
| quantity | DECIMAL | YES | |
| price | DECIMAL | NO | Required for LIMIT |
| timeInForce | ENUM | NO | |
| timestamp | LONG | YES | |

---

### Account Endpoints

#### Account Information
```
GET /api/v3/account
```
**Weight:** 20

**Response:**
```json
{
    "makerCommission": 15,
    "takerCommission": 15,
    "buyerCommission": 0,
    "sellerCommission": 0,
    "canTrade": true,
    "canWithdraw": true,
    "canDeposit": true,
    "accountType": "SPOT",
    "balances": [
        {
            "asset": "BTC",
            "free": "4723846.89208129",
            "locked": "0.00000000"
        }
    ],
    "permissions": ["SPOT"]
}
```

#### Query Order
```
GET /api/v3/order
```
**Weight:** 4

**New Field (May 2026):** `expiryReason` - Returned for expired orders. Also appears in `GET /api/v3/allOrders` and `GET /api/v3/orderList`.

#### Current Open Orders
```
GET /api/v3/openOrders
```
**Weight:** 6 (single symbol) or 80 (all symbols)

#### All Orders
```
GET /api/v3/allOrders
```
**Weight:** 20

#### Account Trade List
```
GET /api/v3/myTrades
```
**Weight:** 5-20

#### Query Unfilled Order Count
```
GET /api/v3/rateLimit/order
```
**Weight:** 40

**Response:**
```json
[
    {
        "rateLimitType": "ORDERS",
        "interval": "SECOND",
        "intervalNum": 10,
        "limit": 50,
        "count": 0
    }
]
```

#### Query Commission Rates
```
GET /api/v3/account/commission
```
**Weight:** 20

---

## WebSocket Streams

### Connection Options

#### Single Stream
```
wss://stream.binance.com:9443/ws/<streamName>
```

#### Combined Streams
```
wss://stream.binance.com:9443/stream?streams=<streamName1>/<streamName2>/...
```

### Market Streams

#### Kline/Candlestick Streams
```
<symbol>@kline_<interval>
```

**Example:** `btcusdt@kline_1m`

**Payload:**
```json
{
    "e": "kline",
    "E": 1499404907056,
    "s": "ETHBTC",
    "k": {
        "t": 1499404860000,
        "T": 1499404919999,
        "s": "ETHBTC",
        "i": "1m",
        "f": "1499404860000",
        "L": "1499404919999",
        "o": "0.10278577",
        "c": "0.10278645",
        "h": "0.10278712",
        "l": "0.10278518",
        "v": "58.14692951",
        "n": 63,
        "x": false,
        "q": "5.96466206",
        "V": "25.16848245",
        "Q": "2.58436663",
        "B": "0"
    }
}
```

#### Trade Streams
```
<symbol>@trade
```

#### AggTrade Streams
```
<symbol>@aggTrade
```

#### Order Book Streams
```
<symbol>@depth<levels>[@100ms|@1000ms]
```

**Examples:**
- `btcusdt@depth` (default 1000ms)
- `btcusdt@depth5` (top 5 levels)
- `btcusdt@depth10@100ms` (100ms updates)

#### Ticker Streams
```
<symbol>@ticker          // Individual symbol
!ticker@arr            // All symbols (mini)
!miniTicker@arr         // All symbols (mini)
!bookTicker            // All book tickers
```

### User Data Stream

#### Subscribe to User Data
```
POST /api/v3/userDataStream
```
**Weight:** 1

**Response:**
```json
{
    "listenKey": "pqia91pl6rlAkxP1QysrCrkBg8SY7K6U6o2m5MkFaUyGmkM"
}
```

**Stream Format:**
```
wss://stream.binance.com:9443/ws/<listenKey>
```

**Events:**
- Account Update (`outboundAccountPosition`)
- Balance Update (`balanceUpdate`)
- Execution Report (`executionReport`)
- List Status (`listStatus`)

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

---

## Authentication & Security

### API Key Types

| Type | Signature Algorithm | Case Sensitive |
|------|-------------------|-----------------|
| **HMAC** | HMAC-SHA256 | No |
| **RSA** | RSASSA-PKCS1-v1_5 with SHA-256 | Yes |
| **Ed25519** | Ed25519 with SHA-256 | Yes (Recommended) |

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

# Usage
params = {
    'symbol': 'BTCUSDT',
    'side': 'BUY',
    'type': 'LIMIT',
    'price': '40000',
    'quantity': '0.001',
    'timestamp': 1499827319559
}

signature = generate_signature('your_secret_key', params)
```

### Timing Security

```
recvWindow: Maximum 60000 ms (default: 5000 ms)
timestamp: Current time in ms or μs
```

**Server-side validation:**
```python
if (timestamp < (serverTime + 1000) && 
    (serverTime - timestamp) <= recvWindow) {
    // Process request
}
```

---

## Rate Limits

### Rate Limit Types

| Type | Description |
|------|-------------|
| **REQUEST_WEIGHT** | General API weight |
| **ORDERS** | Order placement rate |
| **RAW_REQUESTS** | Total requests |

### Rate Limit Headers

| Header | Description |
|--------|-------------|
| `X-MBX-USED-WEIGHT-<interval>` | Current used weight |
| `X-MBX-ORDER-COUNT-<interval>` | Current order count |
| `Retry-After` | Seconds to wait (with 429/418) |

### Rate Limit Intervals

| Interval | Letter | Example |
|----------|--------|---------|
| Second | S | 10 requests/second |
| Minute | M | 1200 requests/minute |
| Hour | H | 48000 requests/hour |
| Day | D | 100000 requests/day |

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | WAF Block (rate limit violation) |
| 404 | Not Found |
| 429 | Too Many Requests |
| 418 | IP Banned (auto-ban after repeated 429s) |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Error Handling

### Error Response Format

```json
{
    "code": -1121,
    "msg": "Invalid symbol."
}
```

### Common Error Codes

| Code | Message | Description |
|------|---------|-------------|
| -1000 | UNKNOWN | Unknown error |
| -1001 | DISCONNECTED | Internal server error |
| -1002 | UNAUTHORIZED | Invalid API key |
| -1003 | TOO_MANY_REQUESTS | Rate limit exceeded |
| -1007 | TIMEOUT | Request timeout |
| -1015 | TOO_MANY_ORDERS | Order rate limit exceeded |
| -1016 | SERVICE_SHUTTING_DOWN | Service unavailable |
| -1020 | UNSUPPORTED_OPERATION | Invalid request |
| -1021 | INVALID_TIMESTAMP | Timestamp out of recvWindow |
| -1022 | INVALID_SIGNATURE | Invalid signature |
| -1121 | INVALID_SYMBOL | Invalid symbol |
| -1125 | INVALID_LISTEN_KEY | Invalid listen key |
| -2010 | NEW_ORDER_REJECTED | Order rejected |
| -2011 | CANCEL_REJECTED | Cancel rejected |
| -2013 | NO_SUCH_ORDER | Order not found |
| -2014 | BAD_API_KEY_FMT | Invalid API key format |
| -2022 | ORDER_CANCEL_REPLACE_FAILED | Cancel-replace failed |

### Error Handling Best Practices

```python
import time
import requests

def make_request(url, params, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return response.json()
        
        elif response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
        
        elif response.status_code == 418:
            retry_after = int(response.headers.get('Retry-After', 300))
            print(f"IP banned. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
        
        else:
            error = response.json()
            print(f"Error {error['code']}: {error['msg']}")
            return None
    
    return None
```

---

## Data Formats

### Timestamps

- **Default:** Milliseconds (ms)
- **Microseconds:** Add header `X-MBX-TIME-UNIT: MICROSECOND`

### Price & Quantity Precision

- Defined per symbol in `exchangeInfo`
- Use `baseAssetPrecision` and `quotePrecision`
- Respect `LOT_SIZE` and `MIN_NOTIONAL` filters

### Enumerations

#### Order Side
- `BUY`
- `SELL`

#### Order Type
- `LIMIT`
- `MARKET`
- `STOP_LOSS`
- `STOP_LOSS_LIMIT`
- `TAKE_PROFIT`
- `TAKE_PROFIT_LIMIT`
- `LIMIT_MAKER`

#### Time In Force
- `GTC` (Good Till Canceled)
- `IOC` (Immediate or Cancel)
- `FOK` (Fill or Kill)

#### Order Status
- `NEW`
- `PARTIALLY_FILLED`
- `FILLED`
- `CANCELED`
- `PENDING_CANCEL` (currently unused)
- `REJECTED`
- `EXPIRED`

#### Self-Trade Prevention Mode
- `NONE`
- `EXPIRE_MAKER`
- `EXPIRE_TAKER`
- `EXPIRE_BOTH`

---

## Order Types & Trading

### Order Type Details

#### LIMIT Order
```python
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "timeInForce": "GTC",
    "quantity": "0.001",
    "price": "40000"
}
```

#### MARKET Order
```python
# By base quantity
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "quantity": "0.001"
}

# By quote quantity
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "quoteOrderQty": "40"
}
```

#### STOP_LOSS Order
```python
{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "STOP_LOSS",
    "quantity": "0.001",
    "stopPrice": "39000"
}
```

#### STOP_LOSS_LIMIT Order
```python
{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "STOP_LOSS_LIMIT",
    "timeInForce": "GTC",
    "quantity": "0.001",
    "price": "38500",
    "stopPrice": "39000"
}
```

#### OCO (One-Cancels-Other)
```python
{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "quantity": "0.001",
    "aboveType": "LIMIT_MAKER",
    "abovePrice": "42000",
    "belowType": "STOP_LOSS",
    "belowStopPrice": "39000"
}
```

### Trailing Stop Orders

Use `trailingDelta` parameter:

```python
{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "STOP_LOSS",
    "quantity": "0.001",
    "trailingDelta": 100  // 100 price points
}
```

### Iceberg Orders

Use `icebergQty` with `timeInForce: GTC`:

```python
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "timeInForce": "GTC",
    "quantity": "1.000",
    "price": "40000",
    "icebergQty": "0.100"  // Visible quantity
}
```

---

## Best Practices

### 1. Rate Limit Management

```python
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_requests, period):
        self.max_requests = max_requests
        self.period = period
        self.requests = deque()
    
    def wait_if_needed(self):
        now = time.time()
        # Remove old requests
        while self.requests and self.requests[0] < now - self.period:
            self.requests.popleft()
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] - (now - self.period)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.requests.append(now)
```

### 2. Use WebSocket for Real-Time Data

```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    # Process real-time data
    print(data)

ws = websocket.WebSocketApp(
    "wss://stream.binance.com:9443/ws/btcusdt@kline_1m",
    on_message=on_message
)
ws.run_forever()
```

### 3. Handle Time Synchronization

```python
def get_server_time():
    response = requests.get(f"{BASE_URL}/api/v3/time")
    return response.json()['serverTime']

def synchronized_timestamp():
    server_time = get_server_time()
    local_time = int(time.time() * 1000)
    offset = server_time - local_time
    return int(time.time() * 1000) + offset
```

### 4. Respect Symbol Filters

Always check `exchangeInfo` for:
- `LOT_SIZE` (quantity precision)
- `MIN_NOTIONAL` (minimum order value)
- `PRICE_FILTER` (price precision)
- `PERCENT_PRICE` (price deviation limits)

### 5. Use Appropriate Base URLs

```python
# For market data only (no rate limits)
DATA_API = "https://data-api.binance.vision"

# For trading (better performance)
TRADING_API = "https://api1.binance.com"  # or api2, api3, api4
```

### 6. Implement Proper Error Handling

```python
def safe_request(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except requests.exceptions.Timeout:
        print("Request timeout")
        return None
    except requests.exceptions.ConnectionError:
        print("Connection error")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

### 7. Use Ed25519 Keys for Trading

Ed25519 provides:
- Better performance (faster signature verification)
- Better security
- Case-sensitive signatures (more secure)

---

## Implementation Examples

### Complete REST Client Example

```python
import requests
import hmac
import hashlib
from urllib.parse import urlencode
from datetime import datetime

class BinanceClient:
    def __init__(self, api_key, api_secret, base_url="https://api.binance.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key
        })
    
    def _sign(self, params):
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        return params
    
    def get_klines(self, symbol, interval, limit=500, startTime=None, endTime=None):
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if startTime:
            params['startTime'] = startTime
        if endTime:
            params['endTime'] = endTime
        
        response = self.session.get(
            f"{self.base_url}/api/v3/klines",
            params=params
        )
        return response.json()
    
    def place_order(self, symbol, side, type, quantity, **kwargs):
        params = {
            'symbol': symbol,
            'side': side,
            'type': type,
            'quantity': quantity,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        params.update(kwargs)
        params = self._sign(params)
        
        response = self.session.post(
            f"{self.base_url}/api/v3/order",
            params=params
        )
        return response.json()
    
    def get_account(self):
        params = {
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        params = self._sign(params)
        
        response = self.session.get(
            f"{self.base_url}/api/v3/account",
            params=params
        )
        return response.json()

# Usage
client = BinanceClient('your_api_key', 'your_api_secret')

# Get klines
klines = client.get_klines('BTCUSDT', '1h', limit=100)

# Place order
order = client.place_order(
    'BTCUSDT',
    'BUY',
    'LIMIT',
    '0.001',
    price='40000',
    timeInForce='GTC'
)

# Get account
account = client.get_account()
```

### WebSocket Stream Example

```python
import websocket
import json
import threading

class BinanceWebSocket:
    def __init__(self, streams):
        self.streams = streams
        self.ws = None
        self.callbacks = {}
    
    def on_message(self, ws, message):
        data = json.loads(message)
        
        if 'stream' in data:
            stream_name = data['stream']
            payload = data['data']
        else:
            stream_name = None
            payload = data
        
        if stream_name in self.callbacks:
            self.callbacks[stream_name](payload)
    
    def subscribe(self, stream_name, callback):
        self.callbacks[stream_name] = callback
    
    def start(self):
        streams_param = '/'.join(self.streams)
        url = f"wss://stream.binance.com:9443/stream?streams={streams_param}"
        
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self.on_message
        )
        self.ws.run_forever()
    
    def run_in_thread(self):
        thread = threading.Thread(target=self.start)
        thread.daemon = True
        thread.start()
        return thread

# Usage
def handle_kline(data):
    kline = data['k']
    print(f"Symbol: {kline['s']}, Close: {kline['c']}")

ws = BinanceWebSocket(['btcusdt@kline_1m'])
ws.subscribe('btcusdt@kline_1m', handle_kline)
ws.run_in_thread()
```

### Integration with Your BAET Project

Based on your `src/baet/data/binance.py`, here's how to extend it:

```python
# Add to your BinanceHistoricalProvider
class EnhancedBinanceProvider(BinanceHistoricalProvider):
    def __init__(self, settings):
        super().__init__(settings)
        self.session = requests.Session()
    
    def get_exchange_info(self, symbol=None):
        """Fetch exchange info for symbol validation."""
        params = {}
        if symbol:
            params['symbol'] = symbol
        url = f"{self.settings.binance.rest_base_url}/api/v3/exchangeInfo"
        response = self.session.get(url, params=params)
        return response.json()
    
    def get_account_info(self):
        """Fetch account information (requires API key)."""
        params = {'timestamp': int(time.time() * 1000)}
        # Add signature logic here
        url = f"{self.settings.binance.rest_base_url}/api/v3/account"
        response = self.session.get(url, params=params)
        return response.json()
```

---

## Quick Reference

### Most Common Endpoints

| Use Case | Endpoint | Weight |
|----------|----------|--------|
| Test connectivity | `GET /api/v3/ping` | 1 |
| Get server time | `GET /api/v3/time` | 1 |
| Get klines | `GET /api/v3/klines` | 2 |
| Get ticker | `GET /api/v3/ticker/24hr` | 1-80 |
| Place order | `POST /api/v3/order` | 1 |
| Get account | `GET /api/v3/account` | 20 |
| Get open orders | `GET /api/v3/openOrders` | 6-80 |

### WebSocket Stream Naming

| Stream | Format |
|--------|--------|
| Kline | `<symbol>@kline_<interval>` |
| Trade | `<symbol>@trade` |
| AggTrade | `<symbol>@aggTrade` |
| Depth | `<symbol>@depth<levels>` |
| Ticker | `<symbol>@ticker` |

---

## Resources

- **Official Docs:** https://github.com/binance/binance-spot-api-docs
- **API Status:** https://t.me/binance_api_announcements
- **API Support:** https://dev.binance.vision/
- **Testnet:** https://testnet.binance.vision/
- **Postman Collection:** https://github.com/binance/binance-api-postman
- **Python Connector:** https://github.com/binance/binance-connector-python

---

*This guide is based on the official Binance API documentation as of May 2026. Always refer to the official documentation for the most up-to-date information.*
