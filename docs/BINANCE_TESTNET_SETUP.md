# Binance Testnet Setup Guide for M5.2

**Last Updated: May 2026**

## 🚨 IMPORTANT: Testnet vs Production

**Testnet uses DIFFERENT API keys than production!**
- Production: https://api.binance.com (real money)
- Testnet: https://testnet.binance.vision (demo money only)

---

## Step 1: Create Testnet Account

1. Go to https://testnet.binance.vision/
2. Click **"Log In with GitHub"**
3. Authorize the application
4. You'll be redirected to your testnet dashboard

---

## Step 2: Generate Testnet API Keys

1. In the testnet dashboard, click **"Generate"** or **"Create API Key"**
2. Give it a name (e.g., "BAET_Testnet")
3. Copy the **API Key** and **Secret Key**
4. **Save these keys** - you'll need them for `.env`

**⚠️ Note:** Testnet keys are different from production keys!

---

## Step 3: Update `.env` File

Replace the API keys in your `.env` file with the TESTNET keys:

```bash
# Binance TESTNET API Credentials (Demo - NO REAL MONEY)
# Get these from: https://testnet.binance.vision/
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_SECRET_KEY=your_testnet_secret_here

# Live trading (also use testnet keys for Phase 3)
BAET_LIVE_BINANCE_API_KEY=your_testnet_api_key_here
BAET_LIVE_BINANCE_API_SECRET=your_testnet_secret_here

# Environment
BAET_MODE=live
```

---

## Step 4: Testnet Automatically Gives You Demo Funds

✅ When you log into testnet, you automatically receive:
- 1 BTC
- 1 ETH
- 1 BNB
- 1,000 USDT
- And other demo assets

**These are NOT real assets** - they can only be used on testnet.

---

## Step 5: Verify Testnet Connection

Run the test script:

```bash
cd d:\project\AET
python test_observation_mode.py
```

**Expected output:**
```
✅ Connected to Binance TESTNET (demo/sandbox)
✅ Observation client created successfully
✅ Account info retrieved
   Account Type: SPOT
   Can Trade: True
   Total USDT Value: $1000.00  # Demo money
   Balances: {'BTC': ..., 'ETH': ..., 'USDT': ...}
```

---

## Step 6: Start Dashboard

```bash
streamlit run src/baet/dashboard/app.py
```

Dashboard will show:
- 🔴 **LIVE MODE ACTIVE** (but it's testnet - no real money)
- Demo account balance
- Real-time prices
- Signal validation (no orders placed in observation mode)

---

## 📋 Testnet vs Production Comparison

| Feature | Testnet | Production |
|---------|----------|-------------|
| URL | testnet.binance.vision | api.binance.com |
| Real Money | ❌ No | ✅ Yes |
| API Keys | Separate (from testnet site) | Separate (from binance.com) |
| Initial Balance | Auto: 1 BTC, 1 ETH, 1000 USDT | Your deposit |
| Reset | Monthly reset | Never |
| Safe for Testing | ✅ Yes | ❌ No |

---

## 🚨 Common Mistakes

### ❌ Mistake 1: Using production keys for testnet
**Error:** `APIError(code=-2015): Invalid API-key, IP, or permissions for action.`

**Fix:** Get testnet keys from https://testnet.binance.vision/ (not binance.com)

---

### ❌ Mistake 2: Forgetting `testnet=True`
**Error:** Charges real money!

**Fix:** Ensure `config/live.yaml` has:
```yaml
live:
  testnet: true  # MUST be true for demo
```

---

### ❌ Mistake 3: Transferring real money for testnet
**Error:** Lost money!

**Fix:** Testnet gives you demo funds automatically - **NEVER transfer real money to testnet!**

---

## ✅ Verification Checklist

Before proceeding to Phase 3 (Observation Mode), verify:

- [ ] Logged into https://testnet.binance.vision/
- [ ] Generated testnet API keys
- [ ] Updated `.env` with testnet keys
- [ ] Ran `python test_observation_mode.py` successfully
- [ ] See "Connected to Binance TESTNET" message
- [ ] Account shows demo balance (not $0.00)
- [ ] Dashboard shows 🔴 LIVE MODE ACTIVE
- [ ] Dashboard shows demo account balance

---

## 🚀 Next Steps After Testnet Setup

1. **Phase 3 (Day 1-2): Observation Mode**
   - Run dashboard
   - Monitor signals (no orders placed)
   - Verify signal quality

2. **Phase 3 (Day 3-4): First Testnet Order**
   - Place small order ($10-20 demo money)
   - Monitor fill quality
   - Verify everything works

3. **Phase 4: Only after testnet success**
   - Consider using production with real money
   - Transfer only $50-100 real money
   - Follow same observation → small order → scale up

---

## 📞 Need Help?

- Testnet Docs: https://github.com/binance/binance-spot-api-docs/blob/master/testnet/CHANGELOG.md
- Testnet FAQ: https://testnet.binance.vision/ (scroll down)
- API Docs: https://binance-docs.github.io/apidocs/spot/en/

---

**Remember: Testnet is for testing ONLY. No real money involved! 🎉**
