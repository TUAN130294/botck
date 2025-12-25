# -*- coding: utf-8 -*-
"""
data_ta.py — nguồn dữ liệu & chỉ báo (Áp dụng các cải tiến)
"""

import time, json, re, logging, asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

import pytz, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import numpy as np
from scipy.signal import find_peaks

from config import TZ, NEAR_EPS, CACHE_TTL

log = logging.getLogger(__name__)

# --- TEST MODE GLOBALS ---
TEST_MODE: bool = False
TEST_FEED: Dict[str, Dict[str, Any]] = {}
# -------------------------

# -------- HTTP session --------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "VN-StockBot/1.0 (+https://t.me)"})
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=1, connect=1, read=1, status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset({"GET"})
)))

# THAY ĐỔI: Thêm API keys và endpoint cho Vietstock/Cafef (giả định)
VIETSTOCK_API_KEY = "" # Cần điền
CAFEF_API_KEY = "" # Cần điền
VIETSTOCK_API_ENDPOINT = "https://api.vietstock.vn/..."
CAFEF_API_ENDPOINT = "https://api.cafef.vn/..."

# -------- Time helpers --------
def vn_now() -> datetime:
    return datetime.now(TZ)

def is_trading_hours() -> bool:
    if TEST_MODE: return True
    now = vn_now(); wd = now.weekday()
    if wd >= 5: return False
    h, m = now.hour, now.minute
    morning = (9 <= h < 11) or (h == 11 and m <= 30)
    afternoon = (13 <= h < 15)
    return morning or afternoon

# -------- Utilities --------
def _get_json(url: str, timeout: int = 6) -> Optional[Any]:
    try:
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"GET fail {url}: {e}")
        return None

def derive_color_status(d: Dict[str, Any]) -> Dict[str, Any]:
    if not d: return d
    price = float(d.get("price") or 0.0)
    ref   = d.get("ref"); ceil = d.get("ceil"); floor = d.get("floor")
    color = "tham chiếu"; is_limit_up = False; is_limit_down = False
    if ref is not None:
        ref = float(ref)
        if ceil is not None and abs(price - float(ceil)) < 1e-6:
            color = "tím (trần)"; is_limit_up = True
        elif floor is not None and abs(price - float(floor)) < 1e-6:
            color = "sàn"; is_limit_down = True
        elif price > ref: color = "xanh"
        elif price < ref: color = "đỏ"
    d["color"] = color; d["is_limit_up"] = is_limit_up; d["is_limit_down"] = is_limit_down
    return d

# -------- BỘ ĐIỀU PHỐI (ORCHESTRATOR) TỐI ƯU HÓA --------
_DATA_CACHE: Dict[str, Dict[str, Any]] = {}

def fetch_historical_eod_data(symbol: str, days: int = 90, timeout: int = 15) -> Optional[pd.DataFrame]:
    log.info(f"Đang lấy dữ liệu EOD cho {symbol} trong {days} ngày qua.")
    try:
        end_date = vn_now()
        start_date = end_date - timedelta(days=days + 40)
        url = f"https://dchart-api.vndirect.com.vn/dchart/history?resolution=1D&symbol={symbol}&from={int(start_date.timestamp())}&to={int(end_date.timestamp())}"
        
        data = _get_json(url, timeout=timeout)
        if not data or data.get("s") != "ok" or not data.get("c"):
            log.warning(f"Không có dữ liệu lịch sử từ dchart-api cho {symbol}")
            return None
        
        df = pd.DataFrame({
            'Date': pd.to_datetime(data['t'], unit='s').tz_localize('UTC').tz_convert('Asia/Ho_Chi_Minh'),
            'Open': data['o'], 'High': data['h'], 'Low': data['l'], 'Close': data['c'], 'Volume': data['v']
        }).set_index('Date')
        
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(inplace=True)
        return df.sort_index().tail(days)
        
    except Exception as e:
        log.error(f"Lỗi xử lý dữ liệu EOD cho {symbol}: {e}")
        return None

def fetch_stock_data(symbol: str) -> Optional[Dict[str, Any]]:
    symbol = symbol.upper()
    now = vn_now()
    end_ts = int(now.timestamp())
    
    # THAY ĐỔI: Ưu tiên lấy dữ liệu từ nguồn địa phương (nếu có)
    # Ví dụ: fetch_vietstock_data(symbol)
    
    # LUÔN LẤY DỮ LIỆU CUỐI NGÀY ĐỂ TÍNH CÁC CHỈ BÁO
    df_eod = fetch_historical_eod_data(symbol, days=90)
    
    # Lấy dữ liệu trong ngày chỉ khi là giờ giao dịch
    data = {}; is_intraday = False
    if is_trading_hours():
        start_ts_intraday = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        url_intraday = f"https://dchart-api.vndirect.com.vn/dchart/history?resolution=1&symbol={symbol}&from={start_ts_intraday}&to={end_ts}"
        intraday_data = _get_json(url_intraday)

        if intraday_data and intraday_data.get("s") == "ok" and intraday_data.get("c"):
            closes = [float(c) for c in intraday_data.get("c", [])]
            vols = [int(v) for v in intraday_data.get("v", [])]
            data = {
                "price": closes[-1],
                "vol_day": sum(vols),
                "series_close": closes,
                "series_vol": vols,
                "source": "VND_DCHART_INTRADAY",
            }
            is_intraday = True

    # Nếu không có dữ liệu trong ngày, sử dụng dữ liệu cuối ngày
    if not is_intraday and df_eod is not None and not df_eod.empty:
        data = {
            "price": float(df_eod['Close'].iloc[-1]),
            "vol_day": int(df_eod['Volume'].iloc[-1]),
            "source": "VND_DCHART_EOD",
        }
    
    if not data:
        log.warning(f"Không có dữ liệu nào cho {symbol}")
        return None

    # Lấy giá tham chiếu từ dữ liệu cuối ngày
    ref_price = float(df_eod['Close'].iloc[-2]) if df_eod is not None and len(df_eod) > 1 else data["price"]
    data["ref"] = ref_price
    data["ceil"] = round(ref_price * 1.07, 2)
    data["floor"] = round(ref_price * 0.93, 2)
    data["as_of"] = now.strftime("%Y-%m-%d %H:%M")
    
    # Đính kèm toàn bộ DataFrame lịch sử
    data["eod_data"] = df_eod
    return derive_color_status(data)

async def fetch_stock_data_async(symbol: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    rec = _DATA_CACHE.get(symbol)
    if rec and not TEST_MODE and now - rec["ts"] < CACHE_TTL:
        return rec["data"]
    data = await asyncio.to_thread(fetch_stock_data, symbol)
    if data:
        _DATA_CACHE[symbol] = {"ts": now, "data": data}
    return data
    
def fetch_fundamental_data(symbol: str) -> Optional[Dict[str, Any]]:
    url = f"https://www.fireant.vn/api/Data/Finance/LastestFinancialInfo?symbol={symbol}"
    data = _get_json(url)
    if not data: return None
    try:
        pe = round(data.get("PE"), 2) if data.get("PE") is not None else "N/A"
        market_cap = data.get("MarketCapitalization", 0)
        market_cap_str = f"{market_cap / 1_000_000_000_000:.2f} nghìn tỷ" if market_cap > 1e12 else f"{market_cap / 1_000_000_000:.2f} tỷ"
        return {"P/E": pe, "Vốn hóa": market_cap_str}
    except Exception as e:
        log.error(f"Lỗi xử lý dữ liệu cơ bản cho {symbol}: {e}")
        return None

def ema(series: List[float], period: int) -> Optional[float]:
    if not series or len(series) < period: return None
    return pd.Series(series).ewm(span=period, adjust=False).mean().iloc[-1]

# Trong file: data_ta.py

def rsi(series: List[float], period: int = 14) -> Optional[float]:
    """
    THAY ĐỔI: Sử dụng phương pháp tính RSI bằng EMA (Wilder's smoothing) để ổn định và chính xác hơn.
    """
    if not series or len(series) < period + 1:
        return None
    
    s = pd.Series(series)
    delta = s.diff()
    
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Sử dụng Exponential Moving Average (tương đương Wilder's smoothing)
    avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    
    # Xử lý trường hợp không có loss (thị trường tăng liên tục)
    if avg_loss.iloc[-1] == 0:
        return 100.0 if avg_gain.iloc[-1] > 0 else 50.0
        
    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
    
    rsi_val = 100 - (100 / (1 + rs))
    
    return round(rsi_val, 2)

def macd(series: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[Optional[float], Optional[float]]:
    if len(series or []) < slow + signal: return (None, None)
    s = pd.Series(series)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return (round(macd_line.iloc[-1], 4), round(signal_line.iloc[-1], 4))

def vwap(series_close: List[float], series_vol: List[int]) -> Optional[float]:
    if not series_close or not series_vol or len(series_close) != len(series_vol): return None
    q = pd.Series(series_vol)
    p = pd.Series(series_close)
    if q.sum() == 0: return None
    return (p * q).sum() / q.sum()

def bollinger_bands(series: List[float], period: int = 20, std_dev: int = 2) -> Tuple[Optional[float], Optional[float]]:
    if not series or len(series) < period: return None, None
    s = pd.Series(series)
    sma = s.rolling(window=period).mean().iloc[-1]
    std = s.rolling(window=period).std().iloc[-1]
    return round(sma + std_dev * std, 2), round(sma - std_dev * std, 2)

def atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """THAY ĐỔI: Thêm hàm tính Average True Range (ATR)."""
    if df is None or df.empty or len(df) < period: return None
    df['high_low'] = df['High'] - df['Low']
    df['high_close'] = np.abs(df['High'] - df['Close'].shift())
    df['low_close'] = np.abs(df['Low'] - df['Close'].shift())
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr'] = df['tr'].ewm(span=period, adjust=False).mean()
    return df['atr'].iloc[-1]
    
def compute_technicals(data: Dict[str, Any]) -> Dict[str, Optional[float]]:
    # Ưu tiên dữ liệu trong ngày nếu có
    closes = data.get("series_close")
    vols = data.get("series_vol")
    
    # Nếu không có dữ liệu trong ngày, sử dụng dữ liệu cuối ngày
    df_eod = data.get("eod_data")
    if not closes and df_eod is not None and not df_eod.empty:
         closes = df_eod['Close'].tolist()
         vols = df_eod['Volume'].tolist()
    
    if not closes: return {}

    bb_upper, bb_lower = bollinger_bands(closes)
    out = {
        "EMA20": ema(closes, 20), "EMA50": ema(closes, 50), "RSI14": rsi(closes, 14),
        "VWAP": vwap(closes, vols) if closes and vols else None,
        "BB_UPPER": bb_upper, "BB_LOWER": bb_lower
    }
    m, s = macd(closes, 12, 26, 9); out["MACD"] = m; out["SIGNAL"] = s
    
    # THAY ĐỔI: Thêm ATR vào kết quả
    if df_eod is not None and not df_eod.empty:
        out['ATR'] = atr(df_eod)

    return out

def compute_intraday_technicals(d: Dict[str, Any]) -> Dict[str, Optional[float]]:
    # Vẫn giữ hàm này để tương thích ngược, nhưng nó sẽ gọi hàm mới
    return compute_technicals(d)

def find_divergences(symbol: str, days: int = 180) -> dict:
    df = fetch_historical_eod_data(symbol, days=days)
    if df is None or df.empty or len(df) < 30:
        return {"ok": False, "msg": "Không đủ dữ liệu lịch sử."}

    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df.dropna(inplace=True)

    if df.empty: return {"ok": False, "msg": "Lỗi khi tính toán RSI."}

    price_peaks, _ = find_peaks(df['Close'], distance=5, prominence=df['Close'].std() * 0.5)
    price_troughs, _ = find_peaks(-df['Close'], distance=5, prominence=df['Close'].std() * 0.5)
    rsi_peaks, _ = find_peaks(df['RSI'], distance=5, prominence=df['RSI'].std() * 0.5)
    rsi_troughs, _ = find_peaks(-df['RSI'], distance=5, prominence=-df['RSI'].std() * 0.5)

    results = {"ok": True, "bearish": [], "bullish": []}

    if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
        for i in range(len(price_peaks) - 1, 0, -1):
            for j in range(len(rsi_peaks) - 1, 0, -1):
                if abs(price_peaks[i] - rsi_peaks[j]) < 5 and \
                   (df['Close'].iloc[price_peaks[i]] > df['Close'].iloc[price_peaks[i-1]]) and \
                   (df['RSI'].iloc[rsi_peaks[j]] < df['RSI'].iloc[rsi_peaks[j-1]]):
                    results["bearish"].append({
                        "price_peak_1": (df.index[price_peaks[i-1]].strftime('%d-%m'), round(df['Close'].iloc[price_peaks[i-1]], 2)),
                        "price_peak_2": (df.index[price_peaks[i]].strftime('%d-%m'), round(df['Close'].iloc[price_peaks[i]], 2)),
                        "rsi_peak_1": round(df['RSI'].iloc[rsi_peaks[j-1]], 1),
                        "rsi_peak_2": round(df['RSI'].iloc[rsi_peaks[j]], 1),
                    })
                    break
            if results["bearish"]: break
    
    if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
        for i in range(len(price_troughs) - 1, 0, -1):
            for j in range(len(rsi_troughs) - 1, 0, -1):
                if abs(price_troughs[i] - rsi_troughs[j]) < 5 and \
                   (df['Close'].iloc[price_troughs[i]] < df['Close'].iloc[price_troughs[i-1]]) and \
                   (df['RSI'].iloc[rsi_troughs[j]] > df['RSI'].iloc[rsi_troughs[j-1]]):
                    results["bullish"].append({
                        "price_trough_1": (df.index[price_troughs[i-1]].strftime('%d-%m'), round(df['Close'].iloc[price_troughs[i-1]], 2)),
                        "price_trough_2": (df.index[price_troughs[i]].strftime('%d-%m'), round(df['Close'].iloc[price_troughs[i]], 2)),
                        "rsi_trough_1": round(df['RSI'].iloc[rsi_troughs[j-1]], 1),
                        "rsi_trough_2": round(df['RSI'].iloc[rsi_troughs[j]], 1),
                    })
                    break
            if results["bullish"]: break

    return results

def run_backtest(symbol: str, days: int, strategy: str = 'rsi') -> dict:
    df = fetch_historical_eod_data(symbol, days=days)
    if df is None or df.empty or len(df) < 30:
        return {"ok": False, "msg": "Không đủ dữ liệu để backtest. Cần tối thiểu 30 ngày."}
    
    # THAY ĐỔI: Thêm phí giao dịch
    TRANSACTION_FEE = 0.0015 # 0.15% phí giao dịch
    
    initial_cash = 100_000_000
    cash = initial_cash
    shares = 0
    trades = []
    
    df['RSI'] = df['Close'].diff(1).fillna(0).apply(lambda x: x if x > 0 else 0).ewm(span=14, adjust=False).mean() / df['Close'].diff(1).fillna(0).abs().ewm(span=14, adjust=False).mean() * 100
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    macd_series = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = macd_series
    df['SIGNAL'] = macd_series.ewm(span=9, adjust=False).mean()
    
    df.dropna(inplace=True)
    
    if df.empty:
        return {"ok": False, "msg": "Lỗi khi tính toán các chỉ báo, không có đủ dữ liệu."}
        
    for i in range(1, len(df)):
        price = df['Close'].iloc[i]
        
        buy_signal = False
        sell_signal = False
        
        if strategy == 'rsi':
            prev_rsi = df['RSI'].iloc[i-1]
            current_rsi = df['RSI'].iloc[i]
            if prev_rsi <= 40 and current_rsi > 40:
                buy_signal = True
            elif prev_rsi >= 60 and current_rsi < 60:
                sell_signal = True
        
        elif strategy == 'rsi_ema':
            prev_rsi = df['RSI'].iloc[i-1]
            current_rsi = df['RSI'].iloc[i]
            current_ema20 = df['EMA20'].iloc[i]
            if prev_rsi <= 40 and current_rsi > 40 and price > current_ema20:
                buy_signal = True
            elif prev_rsi >= 60 and current_rsi < 60:
                sell_signal = True

        elif strategy == 'macd':
            prev_macd = df['MACD'].iloc[i-1]
            current_macd = df['MACD'].iloc[i]
            prev_signal = df['SIGNAL'].iloc[i-1]
            current_signal = df['SIGNAL'].iloc[i]
            if prev_macd < prev_signal and current_macd >= current_signal:
                buy_signal = True
            elif prev_macd > prev_signal and current_macd <= current_signal:
                sell_signal = True

        if buy_signal and cash > price * 100 * (1 + TRANSACTION_FEE):
            qty = (cash // (price * 100)) * 100
            if qty > 0:
                shares += qty
                cash -= qty * price * (1 + TRANSACTION_FEE) # THAY ĐỔI: Trừ phí mua
                trades.append({'date': df.index[i].strftime('%Y-%m-%d'), 'action': 'BUY', 'price': price, 'qty': qty})
        elif sell_signal and shares > 0:
            cash += shares * price * (1 - TRANSACTION_FEE) # THAY ĐỔI: Trừ phí bán
            trades.append({'date': df.index[i].strftime('%Y-%m-%d'), 'action': 'SELL', 'price': price, 'qty': shares})
            shares = 0
            
    if shares > 0:
        price = df['Close'].iloc[-1]
        cash += shares * price * (1 - TRANSACTION_FEE) # THAY ĐỔI: Trừ phí bán cuối cùng
        shares = 0

    final_value = cash + shares * df['Close'].iloc[-1]
    pnl = final_value - initial_cash
    pnl_percent = (pnl / initial_cash) * 100
    
    # THAY ĐỔI: Tính Sharpe Ratio
    df['daily_return'] = df['Close'].pct_change()
    sharpe_ratio = (df['daily_return'].mean() / df['daily_return'].std()) * np.sqrt(252) if df['daily_return'].std() > 0 else 0
    
    return {
        "ok": True,
        "symbol": symbol,
        "days": days,
        "strategy": strategy,
        "initial_cash": initial_cash,
        "final_value": final_value,
        "pnl_vnd": pnl,
        "pnl_percent": pnl_percent,
        "trades": trades,
        "num_trades": len([t for t in trades if t['action'] == 'BUY']),
        "sharpe_ratio": sharpe_ratio
    }

# ==============================================================================
# === MARKET OVERVIEW & FOREIGN FLOW DATA (Dành cho Dashboard) ===
# ==============================================================================

def fetch_market_overview() -> Dict[str, Any]:
    """
    Lấy thông tin tổng quan thị trường: VNIndex, VN30, HNX-Index
    Trả về dict với các chỉ số chính
    """
    try:
        indices = ['VNINDEX', 'VN30', 'HNX']
        results = {}
        
        for index_symbol in indices:
            data = fetch_stock_data(index_symbol)
            if data and data.get('price'):
                price = float(data['price'])
                ref = float(data.get('ref', price))
                change = price - ref
                pct_change = (change / ref * 100) if ref else 0
                
                results[index_symbol] = {
                    'price': price,
                    'ref': ref,
                    'change': change,
                    'pct_change': pct_change,
                    'color': data.get('color', 'tham chiếu'),
                    'vol_day': data.get('vol_day', 0),
                    'as_of': data.get('as_of', vn_now().strftime("%Y-%m-%d %H:%M"))
                }
        
        return {'ok': True, 'data': results, 'timestamp': vn_now().strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as e:
        log.error(f"Lỗi khi lấy market overview: {e}")
        return {'ok': False, 'msg': str(e)}

def fetch_foreign_flow(days: int = 5) -> Dict[str, Any]:
    """
    Lấy dữ liệu dòng tiền nước ngoài (Foreign Flow) trong N ngày gần nhất
    Sử dụng API từ VNDirect hoặc nguồn khác
    """
    try:
        # URL API để lấy dữ liệu foreign flow
        # Ví dụ: https://finfo-api.vndirect.com.vn/v4/foreign_flows
        # Tạm thời trả về dữ liệu mẫu, cần cập nhật API thực tế
        
        end_date = vn_now()
        start_date = end_date - timedelta(days=days)
        
        # TODO: Thay thế bằng API thực tế
        # url = f"https://finfo-api.vndirect.com.vn/v4/foreign_flows?from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}"
        # data = _get_json(url)
        
        # Dữ liệu mẫu (cần thay thế bằng API thực)
        sample_data = {
            'dates': [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days-1, -1, -1)],
            'buy_value': [2500, 2800, 3200, 2900, 3100],  # Tỷ VND
            'sell_value': [2300, 2600, 3000, 2800, 2900],
            'net_value': [200, 200, 200, 100, 200]
        }
        
        return {
            'ok': True,
            'data': sample_data,
            'note': 'Dữ liệu mẫu - cần cập nhật API thực tế'
        }
    except Exception as e:
        log.error(f"Lỗi khi lấy foreign flow: {e}")
        return {'ok': False, 'msg': str(e)}

def fetch_sector_performance() -> Dict[str, Any]:
    """
    Lấy hiệu suất các ngành (Sectors) trong phiên giao dịch
    Trả về danh sách các ngành với % thay đổi
    """
    try:
        # Danh sách các ngành chính trên TTCK Việt Nam
        sectors = {
            'Ngân hàng': ['VCB', 'TCB', 'MBB', 'VPB', 'ACB'],
            'Chứng khoán': ['SSI', 'VND', 'HCM', 'VCI'],
            'Bất động sản': ['VHM', 'VIC', 'NVL', 'DXG'],
            'Thép': ['HPG', 'HSG', 'NKG'],
            'Dầu khí': ['GAS', 'PVD', 'PVS'],
            'Bán lẻ': ['MWG', 'FRT', 'PNJ'],
            'Công nghệ': ['FPT', 'CMG'],
        }
        
        sector_results = []
        
        for sector_name, tickers in sectors.items():
            changes = []
            for ticker in tickers:
                try:
                    data = fetch_stock_data(ticker)
                    if data and data.get('price'):
                        price = float(data['price'])
                        ref = float(data.get('ref', price))
                        pct_change = ((price - ref) / ref * 100) if ref else 0
                        changes.append(pct_change)
                except:
                    continue
            
            if changes:
                avg_change = sum(changes) / len(changes)
                sector_results.append({
                    'name': sector_name,
                    'change': round(avg_change, 2),
                    'tickers_count': len(tickers),
                    'color': 'green' if avg_change > 0 else 'red' if avg_change < 0 else 'gray'
                })
        
        # Sắp xếp theo % thay đổi giảm dần
        sector_results.sort(key=lambda x: x['change'], reverse=True)
        
        return {
            'ok': True,
            'data': sector_results,
            'timestamp': vn_now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        log.error(f"Lỗi khi lấy sector performance: {e}")
        return {'ok': False, 'msg': str(e)}