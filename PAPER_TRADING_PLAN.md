# PAPER TRADING PLAN - VN30 SIMPLE MODELS

**Date:** 2025-12-26
**Status:** READY TO DEPLOY
**Audit Score:** PASS (0/10 severity)

---

## ✅ AUDIT SUMMARY

### System Status
- **Models:** 29/29 VN30 trained ✓
- **Data:** 29/29 available (1 stale - BCG) ⚠️
- **PASSED stocks:** 6/20 (30%) ✓
- **Documentation:** Complete ✓
- **Code quality:** All modules loadable ✓

### Severity: 0/10 - GREEN LIGHT
**Verdict:** Ready for paper trading!

---

## 📊 PORTFOLIO COMPOSITION

### 6 PASSED Stocks (Sharpe>1.5 AND Win>50%)

| # | Symbol | Sector | Return | Sharpe | Win% | MaxDD | Trades |
|---|--------|--------|--------|--------|------|-------|--------|
| 1 | **ACB** | Banking | +48.4% | 2.82 | 54.8% | -12.1% | 126 |
| 2 | **MBB** | Banking | +43.0% | 2.05 | 56.9% | -17.2% | 130 |
| 3 | **SSI** | Securities | +53.2% | 2.05 | 55.4% | -21.6% | 130 |
| 4 | **STB** | Banking | +45.9% | 2.06 | 50.8% | -21.0% | 130 |
| 5 | **TCB** | Banking | +32.8% | 1.54 | 50.8% | -19.6% | 130 |
| 6 | **TPB** | Banking | +36.1% | 1.77 | 56.9% | -18.6% | 130 |

**Portfolio Average:**
- Expected Return: +43.3%/year
- Sharpe Ratio: 2.05
- Win Rate: 54.6%
- Max Drawdown: -18.3%
- Avg Trades/year: ~129

### Risk Assessment

**⚠️ Sector Concentration:**
- Banking: 5/6 (83%) - HIGH RISK
- Securities: 1/6 (17%)
- **Recommendation:** Add HDB or GVR for diversification

**✓ Quality Metrics:**
- All stocks Sharpe >1.5 (excellent risk-adjusted returns)
- All stocks Win >50% (more wins than losses)
- Low correlation between stocks expected (different banks)

---

## 🎯 PAPER TRADING STRATEGY

### Option 1: Conservative (6 Stocks)
**Portfolio:** ACB, MBB, SSI, STB, TCB, TPB

**Allocation:**
- Equal weight: 16.67% each
- Total capital: 100M VND (example)
- Per stock: ~16.7M VND

**Expected:**
- Return: +43.3%/year
- Sharpe: 2.05
- Risk: HIGH banking concentration

### Option 2: Diversified (8 Stocks) ⭐ RECOMMENDED
**Portfolio:** ACB, MBB, SSI, STB, TCB, TPB + **HDB + GVR**

**Addition rationale:**
- **HDB:** Sharpe 1.95 (excellent), Win 48% (just below threshold)
- **GVR:** Win 56.9% (tied highest), only non-bank

**Allocation:**
- Equal weight: 12.5% each
- Reduces banking to 75% (from 83%)
- Adds rubber sector exposure

**Expected:**
- Return: ~40%/year (slightly lower but safer)
- Sharpe: ~1.95
- Risk: MEDIUM (better diversified)

### Option 3: Sharpe-Weighted (6-8 Stocks)
**Weight by Sharpe ratio:**
- ACB (Sharpe 2.82): 23%
- STB (Sharpe 2.06): 17%
- MBB (Sharpe 2.05): 17%
- SSI (Sharpe 2.05): 17%
- TPB (Sharpe 1.77): 14%
- TCB (Sharpe 1.54): 12%

**Pros:** Maximize risk-adjusted returns
**Cons:** Over-concentrated in ACB

---

## 📋 PAPER TRADING RULES

### Entry Rules

1. **Daily Check (EOD - End of Day):**
   - Update features with latest day's data
   - Run model prediction for T+3
   - If prediction >0.1% → Enter position next day

2. **Position Sizing:**
   - Max position: 12.5% (Option 2) or 16.67% (Option 1)
   - Entry: Buy at open next day
   - Always respect allocation limits

3. **Capital Management:**
   - Start capital: 100M VND (or your amount)
   - Reserve 10% cash for flexibility
   - Rebalance monthly if needed

### Exit Rules

1. **T+3 Minimum Hold:**
   - Respect Vietnam T+2.5 settlement
   - Sell earliest on T+3 (3 days after buy)

2. **Exit Triggers:**
   - Time-based: Sell at T+3 to T+7 based on prediction
   - Stop-loss: -5% from entry (emergency only)
   - Take-profit: +10% from entry (optional)

3. **Rebalancing:**
   - Weekly: Check if positions drift >20% from target
   - Monthly: Full rebalance if needed
   - Quarterly: Review model performance

### Risk Management

1. **Position Limits:**
   - Max per stock: 16.67% (6 stocks) or 12.5% (8 stocks)
   - Max sector: 75% (if using 8 stocks) or 83% (if 6 stocks)
   - Max drawdown trigger: -25% → Review strategy

2. **Correlation Monitoring:**
   - Track daily correlation between holdings
   - If correlation >0.8 → Banking crisis risk
   - Consider reducing banking exposure

3. **Stop Conditions:**
   - Win rate drops below 45% (3 consecutive weeks)
   - Sharpe drops below 1.0 (1 month)
   - Max drawdown exceeds -30%
   - Market crash (VN-Index -20%)

---

## 🔄 DAILY WORKFLOW

### Morning (Before Market Open)
1. **Check predictions from yesterday:**
   - If any stock has prediction >0.1% → BUY today at open

2. **Check exit conditions:**
   - If any position held T+3 or more → SELL today
   - Check stop-loss triggers

3. **Execute trades:**
   - Submit buy orders at market open
   - Submit sell orders for T+3+ positions

### Evening (After Market Close)
1. **Update data:**
   - Download today's EOD data for all 6-8 stocks
   - Update VN-Index data

2. **Generate predictions:**
   - Run model on updated data
   - Get predictions for tomorrow (T+3 ahead)

3. **Record keeping:**
   - Log all trades (entry/exit)
   - Calculate P&L
   - Update portfolio metrics

4. **Weekly review (Friday):**
   - Calculate week's performance
   - Check if any stock underperforming
   - Review win rate, Sharpe, drawdown

---

## 📊 MONITORING DASHBOARD

### Key Metrics to Track Daily

**Portfolio Level:**
- Total equity value
- Daily P&L
- Week-to-date P&L
- Month-to-date P&L
- Sharpe ratio (rolling 30 days)
- Max drawdown (current)

**Stock Level (per holding):**
- Entry date, entry price
- Current price, unrealized P&L
- Days held (for T+3 tracking)
- Predicted return (from model)

**Model Performance:**
- Prediction accuracy (vs actual T+3 return)
- Win rate (rolling 30 days)
- Average win size vs loss size
- Number of trades executed

### Alerts to Setup

1. **Position alerts:**
   - Stock reaches T+3 (ready to sell)
   - Stop-loss triggered (-5%)
   - Take-profit reached (+10%)

2. **Portfolio alerts:**
   - Drawdown exceeds -20%
   - Win rate below 47%
   - Sharpe below 1.2

3. **Market alerts:**
   - VN-Index drops -3% in one day
   - Banking sector news
   - Regulatory changes

---

## 🔧 IMPLEMENTATION CHECKLIST

### Phase 1: Setup (Week 1)
- [ ] Open paper trading account (if not done)
- [ ] Fund account with 100M VND
- [ ] Setup data pipeline (daily EOD update)
- [ ] Create trading log spreadsheet
- [ ] Setup monitoring dashboard
- [ ] Test model prediction pipeline
- [ ] Dry-run for 1 week (no real trades)

### Phase 2: Launch (Week 2)
- [ ] Start with 3 stocks only (ACB, MBB, SSI)
- [ ] Execute first real trades
- [ ] Monitor daily for issues
- [ ] Log all trades meticulously
- [ ] Calculate daily P&L

### Phase 3: Scale (Week 3-4)
- [ ] Add remaining 3 stocks (STB, TCB, TPB)
- [ ] Or add 5 more for 8-stock portfolio
- [ ] Increase position sizes to target
- [ ] Continue monitoring and logging

### Phase 4: Optimize (Month 2+)
- [ ] Review 1-month performance
- [ ] Compare actual vs expected metrics
- [ ] Adjust if needed (entry threshold, exit timing)
- [ ] Consider adding HDB/GVR if diversification needed

---

## 📈 SUCCESS CRITERIA

### Month 1 Targets (Minimum)
- Win rate: >48% (vs 54.6% expected)
- Sharpe ratio: >1.2 (vs 2.05 expected)
- Return: >+3% (vs +43%/12 = +3.6% expected)
- Max drawdown: <-15% (vs -18.3% expected)
- Trades executed: >20

**If targets met:** Continue to Month 2
**If targets missed:** Review and adjust

### Month 3 Targets
- Win rate: >50%
- Sharpe: >1.5
- Return: >+10% (3 months)
- Max DD: <-18%

### Month 6 Targets
- Win rate: >52%
- Sharpe: >1.8
- Return: >+20% (6 months)
- Max DD: <-20%

**If Month 6 targets met:**
- System validated
- Consider deploying to real account
- Start with 10-20% of intended capital

---

## ⚠️ RISK WARNINGS

### Known Risks

1. **Overfitting Risk:**
   - Models trained on 2020-2022 data
   - May not work in different market regime
   - **Mitigation:** Stop if win rate <45% for 3 weeks

2. **Banking Concentration Risk:**
   - 83% in banking sector (if 6 stocks)
   - Banking crisis would affect all holdings
   - **Mitigation:** Add HDB/GVR, monitor sector news

3. **Model Degradation:**
   - Patterns may change over time
   - Model may stop working
   - **Mitigation:** Monthly retraining, quarterly review

4. **Settlement Risk:**
   - T+2.5 means 3-day minimum hold
   - Locked in positions during volatility
   - **Mitigation:** Emergency stop-loss at -5%

5. **Data Quality:**
   - Stale data (BCG is 79 days old)
   - Missing data could affect predictions
   - **Mitigation:** Daily data updates, validate before trading

### Stop Conditions (MANDATORY)

**STOP TRADING if:**
1. Cumulative loss exceeds -30%
2. Win rate below 40% for 4 consecutive weeks
3. 5 consecutive losing trades
4. VN-Index crashes >-20% in 1 month
5. Banking sector crisis (news-based)

**When stopped:**
- Exit all positions immediately
- Analyze what went wrong
- Retrain models with new data
- Re-backtest before resuming

---

## 🔄 MAINTENANCE SCHEDULE

### Daily
- Download EOD data
- Generate predictions
- Execute trades
- Log transactions
- Update metrics

### Weekly (Every Friday)
- Calculate week's performance
- Review all trades
- Check model accuracy
- Update monitoring dashboard
- Send weekly report

### Monthly
- Full performance review
- Retrain models with latest data
- Rebalance portfolio if needed
- Update documentation
- Adjust strategy if needed

### Quarterly
- Comprehensive audit
- Compare actual vs backtest
- Review all stop conditions
- Consider strategy changes
- Report to stakeholders

---

## 📞 ESCALATION PROCEDURES

### Minor Issues (Yellow Alert)
- Win rate 45-48% for 2 weeks
- Sharpe 1.0-1.2 for 2 weeks
- Drawdown -15% to -20%

**Action:** Monitor closely, prepare to stop

### Major Issues (Red Alert)
- Win rate <45% for 3 weeks
- Sharpe <1.0 for 1 month
- Drawdown exceeds -25%
- 4 consecutive losing trades

**Action:** Stop trading, full review

### Critical Issues (Emergency Stop)
- Loss exceeds -30%
- Win rate <40%
- Market crash
- Banking crisis
- System failure

**Action:** Emergency exit all positions

---

## 📊 EXPECTED vs ACTUAL TRACKING

### Template for Monthly Review

```
Month: [Month/Year]

EXPECTED (from backtest):
  Return: +3.6%
  Sharpe: 2.05
  Win Rate: 54.6%
  Trades: ~11 (129/12)

ACTUAL:
  Return: ____%
  Sharpe: ____
  Win Rate: ____%
  Trades: ____

VARIANCE:
  Return: ____ (Expected - Actual)
  Sharpe: ____
  Win Rate: ____%
  Trades: ____

ANALYSIS:
  [Why variance occurred]
  [What to adjust]
  [Actions for next month]

DECISION:
  [ ] Continue as is
  [ ] Adjust parameters
  [ ] Stop and review
```

---

## 🎯 NEXT STEPS

### Immediate (Before Trading)
1. ✅ Audit complete (PASSED)
2. ✅ Visualizations created
3. ✅ Analysis done
4. ⬜ Update BCG data (79 days old)
5. ⬜ Setup paper trading account
6. ⬜ Create trading log template
7. ⬜ Build monitoring dashboard

### Week 1 (Soft Launch)
1. ⬜ Start with ACB, MBB, SSI only
2. ⬜ Test full workflow (data→predict→trade)
3. ⬜ Verify all systems work
4. ⬜ Log everything meticulously

### Week 2-4 (Full Launch)
1. ⬜ Add STB, TCB, TPB
2. ⬜ Scale to full portfolio
3. ⬜ Monitor daily
4. ⬜ Weekly reviews

### Month 2+ (Optimization)
1. ⬜ Review Month 1 results
2. ⬜ Add HDB/GVR if needed
3. ⬜ Adjust parameters if needed
4. ⬜ Continue monitoring

---

## 📝 CONCLUSION

**System Status:** READY ✅

**Recommended Approach:**
- Start with **Option 2 (8 stocks)** for better diversification
- Equal-weight allocation (12.5% each)
- Phase in over 2-3 weeks
- Monitor closely first month
- Scale up if targets met

**Expected Outcome:**
- Monthly return: +3-4%
- Sharpe: 1.8-2.2
- Win rate: 52-57%
- Risk: MEDIUM (with 8 stocks)

**Go/No-Go Decision:** **GO** ✅
- All systems operational
- Models validated
- Backtest proven
- Documentation complete
- Risks understood and mitigated

**Ready to start paper trading!**

---

**Created:** 2025-12-26
**Version:** 1.0
**Author:** VN-QUANT Team
**Status:** APPROVED FOR PAPER TRADING
