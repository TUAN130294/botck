# -*- coding: utf-8 -*-
"""
portfolio.py — lưu/đọc owner & rules + helpers
"""

import json, logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from config import NEAR_EPS, MAX_TICKERS_PER_BATCH
from data_ta import fetch_stock_data, compute_intraday_technicals

log = logging.getLogger(__name__)

DATA_DIR     = Path(__file__).resolve().parent
OWNER_DB_FILE= DATA_DIR / "owner_db.json"
RULES_FILE   = DATA_DIR / "rules.json"

def _default_owner_db() -> dict:
    return {"owners": {}, "aliases": {}}

def _load_owner_db() -> dict:
    if OWNER_DB_FILE.exists():
        try:
            data = json.loads(OWNER_DB_FILE.read_text(encoding="utf-8"))
            data.setdefault("owners", {}); data.setdefault("aliases", {})
            for _, b in data["owners"].items():
                b.setdefault("HOLD", []); b.setdefault("PENDING", []); b.setdefault("WATCH", {}); b.setdefault("HOLD_DTL", {})
            return data
        except Exception:
            pass
    data = _default_owner_db(); OWNER_DB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data

def _load_rules() -> Dict[str, Dict]:
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    RULES_FILE.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {}

def save_owner_db(data: dict):
    try:
        OWNER_DB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("save_owner_db fail: %s", e)

def save_rules(rules: Dict[str, Dict]):
    try:
        RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("save_rules fail: %s", e)

OWNER_DB = _load_owner_db()
RULES: Dict[str, Dict] = _load_rules()

def ensure_owner(oid: str):
    OWNER_DB["owners"].setdefault(oid, {"HOLD": [], "PENDING": [], "WATCH": {}, "HOLD_DTL": {}})

def parse_ticker_list(args: List[str]) -> List[str]:
    if not args: return []
    joined = " ".join(args).replace(";", ",").replace("/", ",").replace("|", ",")
    RESERVED = {"HOLD","PENDING","WATCH","ME","OWNER","ALIAS","SET","CLEAR","VOL","NOTE"}
    parts = []
    import re
    for chunk in re.split(r"[,\s]+", joined):
        c = chunk.strip().upper()
        if not c or c in RESERVED: continue
        if re.fullmatch(r"[A-Z0-9]+", c): parts.append(c)
    seen = set(); out = []
    for p in parts:
        if p not in seen:
            seen.add(p); out.append(p)
    return out

def list_all_tickers_from_owner_db() -> List[str]:
    tick = set()
    for _, b in OWNER_DB.get("owners", {}).items():
        tick.update(b.get("HOLD") or [])
        tick.update(b.get("PENDING") or [])
        tick.update((b.get("WATCH") or {}).keys())
    return sorted(tick)

def groups_for_symbol(sym: str) -> Dict[str, bool]:
    g = {"HOLD": False, "PENDING": False, "WATCH": False}
    for _, b in OWNER_DB.get("owners", {}).items():
        if sym in (b.get("HOLD") or []): g["HOLD"] = True
        if sym in (b.get("PENDING") or []): g["PENDING"] = True
        if sym in (b.get("WATCH") or {}): g["WATCH"] = True
    return g

def tickers_in_use() -> List[str]:
    return list_all_tickers_from_owner_db()

def prune_rules_not_in_use() -> List[str]:
    used = set(tickers_in_use()); rm = []
    for t in list(RULES.keys()):
        if t not in used:
            rm.append(t); RULES.pop(t, None)
    save_rules(RULES); return rm

def costs_for_symbol(sym: str) -> Dict[str, Optional[float]]:
    out = {}
    for oid, b in (OWNER_DB.get("owners") or {}).items():
        if sym in (b.get("HOLD") or []):
            c = (b.get("HOLD_DTL") or {}).get(sym, {}).get("cost")
            out[str(oid)] = (float(c) if isinstance(c,(int,float)) else None)
    return out

def _swing_levels(series: List[float], window: int = 4):
    if not series: return [], []
    highs, lows = [], []; n = len(series)
    for i in range(window, n - window):
        seg = series[i - window: i + window + 1]
        if series[i] == max(seg): highs.append(series[i])
        if series[i] == min(seg): lows.append(series[i])
    highs = sorted(set(round(x, 2) for x in highs)); lows = sorted(set(round(x, 2) for x in lows))
    return highs, lows

def propose_and_apply_rules(ticker: str, mode: str, replace_existing: bool = False) -> dict:
    d = fetch_stock_data(ticker)
    if not d: return {"ok": False, "msg": "Không lấy được dữ liệu."}
    
    closes = d.get("series_close") or []
    price = float(d.get("price") or 0.0)
    hi, lo = _swing_levels(closes, window=4)
    hi_above = [x for x in hi if x > price][:3] or [round(price * 1.05, 1)]
    lo_below = [x for x in lo if x < price][-2:] or [round(price * 0.95, 1)]
    vol = int(d.get("vol_day") or 0)
    vol_marks = sorted(set([max(1_000_000, int(vol * 1.2)), max(2_000_000, int(vol * 1.5))]))

    rules = RULES.setdefault(ticker, {})
    
    if replace_existing:
        rules["levels"] = sorted(set([round(x,1) for x in (hi_above + lo_below)]))
        rules["major_levels"] = sorted(set([round(x,1) for x in hi_above[:2]]))
        rules["vol_marks"] = vol_marks
        rules["note"] = "Auto-refreshed from swing/EMA/VWAP"
    else:
        rules["levels"] = sorted(set([round(x,1) for x in (rules.get("levels") or []) + hi_above + lo_below]))
        rules["major_levels"] = sorted(set([round(x,1) for x in (rules.get("major_levels") or []) + hi_above[:2]]))
        rules["vol_marks"] = sorted(set((rules.get("vol_marks") or []) + vol_marks))
        if not rules.get("note"):
            rules["note"] = "Heuristic from swing/EMA/VWAP"

    save_rules(RULES)

    applied = {"ticker": ticker, "mode": mode, "levels": rules["levels"], "major": rules["major_levels"], "vol_marks": rules["vol_marks"], "note": rules.get("note","")}
    return {"ok": True, "applied": applied}

def fmt_session_line_compact(s: str, d: Dict[str, Any], rules: Dict[str, Any]) -> str:
    price = float(d.get("price", 0))
    lv_major = [float(x) for x in rules.get("major_levels") or []]
    above = sorted([lv for lv in lv_major if lv >= price])[:1]
    below = sorted([lv for lv in lv_major if lv <= price])[-1:]
    halls = []
    def _diff_pct(p, lv):
        if not lv: return ""
        dp = p - lv; pct = (dp/lv)*100
        return f"Δ={dp:+.2f} ({pct:+.2f}%)"
    if below: halls.append(f"↓{below[0]} ({_diff_pct(price, below[0])})")
    if above: halls.append(f"↑{above[0]} ({_diff_pct(price, above[0])})")
    vm = rules.get("vol_marks") or []
    vol_hint = f" | vol≥{max(vm):,}" if vm else ""
    tech = compute_intraday_technicals(d)
    hints = []
    if tech.get("RSI14") is not None: hints.append(f"RSI={tech['RSI14']:.0f}")
    if tech.get("EMA20") is not None: hints.append(f"{'trên' if price>=tech['EMA20'] else 'dưới'}EMA20")
    if tech.get("VWAP")  is not None: hints.append(f"{'trên' if price>=tech['VWAP']  else 'dưới'}VWAP")
    return f"- {s}: giá={price:.2f} | " + ("; ".join(halls) if halls else "—") + vol_hint + (" | " + ", ".join(hints) if hints else "")

def plan_compact(s: str, d: Dict[str, Any], rules: Dict[str, Any], group: str, show: bool = True) -> str:
    if not show: return ""
    price = float(d.get("price", 0) or 0)
    major = [float(x) for x in rules.get("major_levels") or []]
    vol_marks = [int(x) for x in rules.get("vol_marks") or []]
    hints = []
    if group == "HOLD":
        hints.append("giữ/trailing EMA20; chốt khi tới major")
    elif group == "WATCH":
        up = sorted([lv for lv in major if lv >= price])[:1]
        trig = f"mua khi ↑{up[0]}" if up else "đợi breakout"
        if vol_marks: trig += f" + vol≥{max(vol_marks):,}"
        hints.append(trig)
    else: # PENDING
        hints.append("hạn chế tăng tỉ trọng khi hàng chưa về")
    return " | Kế hoạch: " + "; ".join(hints)