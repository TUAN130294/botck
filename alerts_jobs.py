# -*- coding: utf-8 -*-
# alerts_jobs.py — Monitor + Alerts + Status HTTP + News + Chart
# Áp dụng các cải tiến: Plotly chart, cảnh báo đa cấp.

import os, re, json, time, asyncio, logging, threading, html, hashlib, random
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import parse_qs
import pandas as pd
import mplfinance as mpf
# THAY ĐỔI: Thêm Plotly
import plotly.graph_objects as go
from config import CHART_DAYS, CHART_WIDTH, CHART_HEIGHT, CHART_THEME, CHART_FONT
from data_ta import fetch_historical_eod_data

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from telegram.ext import ContextTypes
from config import (
    TZ, STATUS_PORT, HEARTBEAT_CHAT_IDS,
    NEAR_EPS, MAX_TICKERS_PER_BATCH,
    NEWS_AUTO_SCHEDULE, NEWS_AUTO_IMPACT, NEWS_SOURCES,
    GEMINI_API_KEY, GEMINI_BASE_URLS, GEMINI_MODEL,
    NEAR_LEVEL_PERCENTAGE # <<< THÊM DÒNG NÀY
)

from config import (
    TZ, STATUS_PORT, HEARTBEAT_CHAT_IDS,
    NEAR_EPS, MAX_TICKERS_PER_BATCH,
    NEWS_AUTO_SCHEDULE, NEWS_AUTO_IMPACT, NEWS_SOURCES,
    GEMINI_API_KEY, GEMINI_BASE_URLS, GEMINI_MODEL
)
import data_ta
from data_ta import vn_now, is_trading_hours, fetch_stock_data_async, compute_intraday_technicals, atr
from news_service import fetch_and_analyze_news
from portfolio import (
    OWNER_DB, RULES, list_all_tickers_from_owner_db, groups_for_symbol,
    costs_for_symbol, propose_and_apply_rules, save_owner_db
)

# ---------- LOG ----------
log = logging.getLogger(__name__)

# ---------- Globals ----------
START_TS = time.time()
STATUS = {
    "start_ts": START_TS, "last_monitor_hw": None, "last_monitor_pending": None,
    "last_heartbeat": None, "last_alert": None
}
ALERT_FEED = deque(maxlen=50)
STATE_TK: Dict[str, Dict[str, Any]] = {}
LAST_NEWS_HASH = ""

TARGET_CHAT_IDS: List[int] = []
for tok in [t.strip() for t in (HEARTBEAT_CHAT_IDS or "").replace(";", ",").split(",") if t.strip()]:
    if tok.lstrip("-").isdigit():
        TARGET_CHAT_IDS.append(int(tok))

# ---------- GIAO DIỆN WEB ĐIỀU KHIỂN TEST ----------
def _fmt_ts(ts: Optional[float]) -> str:
    if not ts: return "—"
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M:%S")

def _home_html():
    up = int(time.time() - STATUS["start_ts"]); hh = up//3600; mm = (up%3600)//60; ss = up%60
    rows = ""
    for item in list(ALERT_FEED)[:20]:
        txt = html.escape(item.get("text", ""))
        rows += f"<tr><td>{item['when']}</td><td>{txt}</td></tr>"
    
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>StockBot Status</title>
<style>body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:20px;line-height:1.6;}}
table{{border-collapse:collapse;width:100%;margin-top:1em;}}td,th{{border:1px solid #ddd;padding:8px;vertical-align:top}}
th{{background:#f4f4f4;text-align:left;}}code{{background:#f7f7f7;padding:2px 4px;border-radius:4px}}
a{{color:#007bff;text-decoration:none;}} a:hover{{text-decoration:underline;}}</style>
</head><body>
<h2>StockBot Status</h2>
<p>Uptime: <b>{hh:02d}:{mm:02d}:{ss:02d}</b> |
Trading hours: <b>{is_trading_hours()}</b> |
Targets: <code>{html.escape(str(TARGET_CHAT_IDS))}</code></p>
<ul>
  <li>Last monitor (HOLD/WATCH): {_fmt_ts(STATUS.get('last_monitor_hw'))}</li>
  <li>Last monitor (PENDING): {_fmt_ts(STATUS.get('last_monitor_pending'))}</li>
  <li>Last heartbeat: {_fmt_ts(STATUS.get('last_heartbeat'))}</li>
  <li>Last alert: {_fmt_ts(STATUS.get('last_alert'))}</li>
</ul>
<p><b><a href="/ui">➡️ Tới giao diện Test</a></b></p>
<h3>Recent alerts</h3>
<table><tr><th>Time</th><th>Message</th></tr>{rows or "<tr><td colspan='2'><i>No alerts yet</i></td></tr>"}</table>
</body></html>"""

def _ui_html(msg: str = ""):
    test_mode_status = "BẬT" if data_ta.TEST_MODE else "TẮT"
    test_rows = []
    for sym, rec in sorted(data_ta.TEST_FEED.items()):
        i = rec.get("i", 0); ticks = rec.get("ticks", [])
        nxt = ticks[i]["price"] if ticks and i < len(ticks) else "Hết"
        test_rows.append(f"<tr><td>{sym}</td><td>{i+1}/{len(ticks)}</td><td>{nxt}</td></tr>")
    tests_html = "".join(test_rows) or "<tr><td colspan='3'><i>Chưa có kịch bản</i></td></tr>"
    
    return f"""
    <!doctype html><html><head><meta charset="utf-8"><title>Bot Test UI</title>
    <style>
        body{{font-family:system-ui, sans-serif; padding:1em 2em; line-height:1.6;}}
        fieldset{{margin-top:1.5em; border:1px solid #ccc; border-radius: 8px; padding: 1em;}}
        legend{{font-weight:bold; font-size:1.1em;}}
        button{{padding: 8px 12px; cursor: pointer; border-radius: 6px; border: 1px solid #666;}}
        .btn-toggle-on{{background-color: #28a745; color: white;}}
        .btn-toggle-off{{background-color: #dc3545; color: white;}}
        input[type=text], input[type=number]{{padding: 6px; border-radius: 4px; border: 1px solid #ccc;}}
        table{{border-collapse:collapse;width:100%;margin-top:1em;}}
        td,th{{border:1px solid #ddd;padding:8px;}}
        th{{background:#f4f4f4;text-align:left;}}
    </style>
    </head><body>
    <h1>Bot Test UI</h1>
    {('<p style="color:green;font-weight:bold;">'+html.escape(msg)+'</p>' if msg else '')}
    
    <fieldset>
        <legend>Chế độ Test</legend>
        <p>Trạng thái hiện tại: <b>{test_mode_status}</b></p>
        <form method="POST" action="/ui" style="display:inline;">
            <input type="hidden" name="op" value="toggle_test">
            <button type="submit" class="{'btn-toggle-off' if data_ta.TEST_MODE else 'btn-toggle-on'}">
                {'Tắt' if data_ta.TEST_MODE else 'Bật'} chế độ Test
            </button>
        </form>
         <form method="POST" action="/ui" style="display:inline;">
            <input type="hidden" name="op" value="reset_ticks">
            <button type="submit">Reset tiến độ ticks</button>
        </form>
    </fieldset>

    <fieldset>
        <legend>Nạp kịch bản giá ảo</legend>
        <form method="POST" action="/ui">
            <input type="hidden" name="op" value="scenario">
            <p><label>Mã CK: <input type="text" name="sym" placeholder="SSI" required></label></p>
            <p><label>Chuỗi giá (cách nhau bằng dấu phẩy): <input type="text" name="prices" placeholder="35,35.2,35.8,36" required size="50"></label></p>
            <p><label>Khối lượng mỗi tick: <input type="number" name="vol" value="1000000" required></label></p>
            <button type="submit">Nạp kịch bản</button>
        </form>
    </fieldset>

    <h3>Kịch bản đang chạy</h3>
    <table border="1"><tr><th>Mã</th><th>Tiến độ</th><th>Giá tiếp theo</th></tr>{tests_html}</table>
    <p><a href="/">Trở về trang Status</a></p>
    </body></html>
    """

class _StatusHttpHandler(BaseHTTPRequestHandler):
    def _w(self, code: int, body: str, ctype="text/html; charset=utf-8"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        if self.path == "/ui":
            self._w(200, _ui_html())
        elif self.path.startswith("/health"):
             data = {"uptime_sec": int(time.time() - STATUS["start_ts"])}
             self._w(200, json.dumps(data), "application/json")
        else:
            self._w(200, _home_html())

    def do_POST(self):
        if self.path != "/ui":
            self._w(404, "Not Found")
            return
        length = int(self.headers.get("Content-Length", 0))
        form_data = parse_qs(self.rfile.read(length).decode("utf-8"))
        op = form_data.get("op", [""])[0]
        msg = ""
        
        try:
            if op == "toggle_test":
                data_ta.TEST_MODE = not data_ta.TEST_MODE
                msg = f"Đã {'BẬT' if data_ta.TEST_MODE else 'TẮT'} chế độ test."
            elif op == "reset_ticks":
                for sym in data_ta.TEST_FEED:
                    data_ta.TEST_FEED[sym]['i'] = 0
                msg = "Đã reset tiến độ của tất cả các ticks về vị trí đầu tiên."
            elif op == "scenario":
                sym = form_data.get("sym", [""])[0].upper().strip()
                prices = form_data.get("prices", [""])[0].strip()
                vol = int(form_data.get("vol", ["1000000"])[0])
                if not sym or not prices: raise ValueError("Thiếu mã hoặc chuỗi giá")
                
                ticks = [{"price": float(p.strip()), "vol": vol} for p in prices.split(",")]
                data_ta.TEST_FEED[sym] = {"i": 0, "ticks": ticks, "hist": {"c": [], "v": []}}
                msg = f"Đã nạp {len(ticks)} tick cho mã {sym}."
            elif op == "clear":
                sym = form_data.get("sym", [""])[0].upper().strip()
                if sym:
                    data_ta.TEST_FEED.pop(sym, None)
                    msg = f"Đã xóa kịch bản của {sym}."
                else:
                    data_ta.TEST_FEED.clear()
                    msg = "Đã xóa tất cả kịch bản."
        except Exception as e:
            msg = f"Lỗi: {e}"

        self._w(200, _ui_html(msg))

def start_status_server():
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", STATUS_PORT), _StatusHttpHandler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        log.info("Status server at http://127.0.0.1:%d (thread=%s)", STATUS_PORT, t.name)
        return srv
    except Exception as e:
        log.warning("Status server failed: %s", e)

# ---------- Telegram helpers ----------
async def _broadcast_text(context: ContextTypes.DEFAULT_TYPE, text: str):
    ts = time.time(); STATUS["last_alert"] = ts
    ALERT_FEED.appendleft({"ts": ts, "when": datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M:%S"),
                           "text": text[:2000]})
    if not TARGET_CHAT_IDS:
        log.warning("No TARGET_CHAT_IDS set; skip broadcast."); return
    for cid in TARGET_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")
        except Exception as e:
            log.warning("send to %s fail: %s", cid, e)

# ---------- Monitor Logic ----------
def _vol_band_str(vol: int, marks: List[int]) -> str:
    if not marks: return f"vol={vol:,}"
    passed = [m for m in marks if vol >= m]
    if not passed: return f"vol<{min(marks):,}"
    return f"vol≥{max(passed):,}"

def _cross_events(prev_price: Optional[float], curr_price: float, levels: List[float]) -> List[str]:
    if prev_price is None: return []
    ev: List[str] = []
    for lv in levels:
        if prev_price < lv <= curr_price: ev.append(f"↑{lv}")
        elif prev_price > lv >= curr_price: ev.append(f"↓{lv}")
    return ev

def owners_by_group_for_ticker(ticker: str) -> Tuple[List[str], List[str], List[str]]:
    holds, pend, watch = [], [], []
    for oid, b in OWNER_DB.get("owners", {}).items():
        if ticker in (b.get("HOLD") or []): holds.append(str(oid))
        if ticker in (b.get("PENDING") or []): pend.append(str(oid))
        if ticker in (b.get("WATCH") or {}): watch.append(str(oid))
    return holds, pend, watch

async def _emit(context: ContextTypes.DEFAULT_TYPE, owners_hold, owners_pending, owners_watch, note_rules, parts: List[str], s: str):
    # THAY ĐỔI: Sắp xếp lại thứ tự của tin nhắn
    # Đưa thông tin mã và giá (parts) lên trước, sau đó mới đến thông tin danh mục.
    owner_part = f"HOLD:{','.join(owners_hold) or '-'} | PENDING:{','.join(owners_pending) or '-'} | WATCH:{','.join(owners_watch) or '-'}"
    
    extra = ""
    if len(owners_hold) == 1:
        cdict = costs_for_symbol(s)
        c = cdict.get(owners_hold[0])
        if isinstance(c,(int,float)) and c:
            extra = f"\n(cost={c:.2f})"
            
    # Tin nhắn chính được ưu tiên thông tin về giá
    main_alert = f"({s}) {' | '.join(parts)}"
    text = f"⚡️ {main_alert} | {owner_part}{extra}"

    if note_rules: 
        text += f"\n{note_rules}"
        
    await _broadcast_text(context, text)
# Tìm hàm monitor_hold_watch và thay thế bằng phiên bản dưới đây

async def monitor_hold_watch(context: ContextTypes.DEFAULT_TYPE):
    STATUS["last_monitor_hw"] = time.time()
    if not is_trading_hours(): return
    tickers = list_all_tickers_from_owner_db()
    if not tickers: return

    for i in range(0, len(tickers), MAX_TICKERS_PER_BATCH):
        batch = tickers[i:i+MAX_TICKERS_PER_BATCH]
        datas = await asyncio.gather(*(fetch_stock_data_async(s) for s in batch))
        for s, d in zip(batch, datas):
            if not d or d.get("price") is None or d.get("vol_day") is None: continue
            
            price = float(d["price"])
            owners_hold, owners_pending, owners_watch = owners_by_group_for_ticker(s)
            rules = RULES.get(s, {})
            levels_full = sorted([float(x) for x in rules.get("levels", [])])
            
            st = STATE_TK.setdefault(s, {
                "last_price": None, 
                "initialized": False, 
                "triggered_pnl_alerts": set(),
                "triggered_near_alerts": set(),
                "last_alert_signature": None # THAY ĐỔI: Thêm trạng thái để chống trùng lặp
            })
            prev_price = st["last_price"]; st["last_price"] = price
            
            parts: List[str] = []

            # --- LOGIC CẢNH BÁO MỚI ---
            if prev_price is not None:
                triggered_near_set = st["triggered_near_alerts"]

                for level in levels_full:
                    near_threshold = level * (1 - NEAR_LEVEL_PERCENTAGE / 100.0)

                    if near_threshold < price < level and level not in triggered_near_set:
                        parts.append(f"TIẾN SÁT MỐC {level} (hiện tại: {price})")
                        triggered_near_set.add(level)

                    if prev_price < level <= price:
                        parts.append(f"{price} ↑{level}")
                        if level in triggered_near_set:
                            triggered_near_set.remove(level)

                    elif prev_price > level >= price:
                        parts.append(f"{price} ↓{level}")
                        if level in triggered_near_set:
                            triggered_near_set.remove(level)
                    
                    if price <= near_threshold and level in triggered_near_set:
                        triggered_near_set.remove(level)

            if d.get('eod_data') is not None and not d['eod_data'].empty:
                df_eod = d['eod_data']
                current_atr = atr(df_eod)
                
                if current_atr is not None and rules.get('major_levels'):
                    major_level = max(rules['major_levels'])
                    if price > major_level + current_atr:
                        parts.append(f"**BREAKOUT MẠNH**! Giá vượt {major_level} + ATR")
                
                if d.get('vol_day') is not None and d.get('eod_data') is not None and len(d['eod_data']) > 20:
                    avg_vol = d['eod_data']['Volume'].iloc[-20:-1].mean()
                    if d['vol_day'] > avg_vol * 2:
                        parts.append(f"**VOLUME BÙNG NỔ**! {d['vol_day']:,} ( >2x trung bình)")
                
            for oid in owners_hold:
                pass

            if parts:
                # THAY ĐỔI: Kiểm tra nếu nội dung cảnh báo giá khác với lần gửi trước
                alert_signature = " | ".join(parts)
                if alert_signature != st.get("last_alert_signature"):
                    await _emit(context, owners_hold, owners_pending, owners_watch, rules.get("note", ""), parts, s)
                    st["last_alert_signature"] = alert_signature # Cập nhật lại signature
                    
async def monitor_pending(context: ContextTypes.DEFAULT_TYPE):
    STATUS["last_monitor_pending"] = time.time()
    if not is_trading_hours(): return

async def heartbeat_job(context: ContextTypes.DEFAULT_TYPE):
    STATUS["last_heartbeat"] = time.time()
    await _broadcast_text(context, f"💓 Heartbeat {vn_now().strftime('%H:%M:%S')} | trading={is_trading_hours()}")

# ---------- News Logic ----------
def build_morning_news_message() -> str: 
    """Tạo bản tin sáng với tin tức mới nhất"""
    try:
        tickers = list_all_tickers_from_owner_db()
        all_news = fetch_and_analyze_news(NEWS_SOURCES, tickers, max_per_source=3)
        if not all_news:
            return "📰 **BẢN TIN SÁNG**\nKhông có tin tức mới trong 24h qua."
        message_parts = ["📰 **BẢN TIN SÁNG**\n"]
        message_parts.append(f"📊 Tổng cộng {len(all_news)} tin tức mới:")
        for i, news in enumerate(all_news[:5], 1):
            emoji = "🟢" if news.sentiment == "Tích cực" else "🔴" if news.sentiment == "Tiêu cực" else "⚪"
            related_tickers_str = f" ({', '.join(news.related_tickers)})" if news.related_tickers else ""
            message_parts.append(f"{i}. {emoji} [{html.unescape(news.title)}]({news.link})")
            message_parts.append(f"   📍 {news.source} | {news.type} | {news.sentiment}{related_tickers_str}")
        return "\n".join(message_parts)
    except Exception as e:
        log.error(f"Lỗi khi tạo bản tin sáng: {e}")
        return "📰 **BẢN TIN SÁNG**\nCó lỗi khi lấy tin tức."

async def morning_news_job(context: ContextTypes.DEFAULT_TYPE):
    """Job gửi bản tin sáng hàng ngày"""
    try:
        message = build_morning_news_message()
        await _broadcast_text(context, message)
        log.info("Đã gửi bản tin sáng thành công")
    except Exception as e:
        log.error(f"Lỗi khi gửi bản tin sáng: {e}")

async def maybe_push_news_if_changed(context: ContextTypes.DEFAULT_TYPE):
    """Kiểm tra và gửi tin tức mới nếu có thay đổi"""
    try:
        tickers = list_all_tickers_from_owner_db()
        all_news = fetch_and_analyze_news(NEWS_SOURCES, tickers, max_per_source=5)
        if not all_news:
            return
        news_hash = hashlib.sha256(json.dumps([html.unescape(n.title) for n in all_news], sort_keys=True).encode()).hexdigest()
        if STATUS.get('last_news_hash') != news_hash:
            STATUS['last_news_hash'] = news_hash
            message = "📰 **TIN TỨC MỚI**\n"
            for i, news in enumerate(all_news[:3], 1):
                emoji = "🟢" if news.sentiment == "Tích cực" else "🔴" if news.sentiment == "Tiêu cực" else "⚪"
                message += f"{i}. {emoji} [{html.unescape(news.title)}]({news.link})\n"
                message += f"   📍 {news.source} | {news.type} | {news.sentiment}\n\n"
            await _broadcast_text(context, message)
            log.info("Đã gửi thông báo tin tức mới")
    except Exception as e:
        log.error(f"Lỗi khi kiểm tra tin tức mới: {e}")

async def news_monitor_job(context: ContextTypes.DEFAULT_TYPE):
    global LAST_NEWS_HASH
    tickers = list_all_tickers_from_owner_db()
    all_news = fetch_and_analyze_news(NEWS_SOURCES, tickers)
    news_hash = hashlib.sha256(json.dumps([html.unescape(n.title) for n in all_news], sort_keys=True).encode()).hexdigest()
    if news_hash == LAST_NEWS_HASH:
        log.info("Không có tin tức mới, bỏ qua gửi thông báo.")
        return
    LAST_NEWS_HASH = news_hash
    important_news = [n for n in all_news if n.type in ["Vĩ mô", "Doanh nghiệp"] and n.sentiment in ["Tích cực", "Tiêu cực"]]
    if not important_news:
        log.info("Không có tin tức quan trọng mới.")
        return
    message_parts = ["\n📣 **CẬP NHẬT TIN TỨC QUAN TRỌNG**\n"]
    for n in important_news:
        emoji = "🟢" if n.sentiment == "Tích cực" else "🔴" if n.sentiment == "Tiêu cực" else "⚪"
        related_tickers_str = f"({', '.join(n.related_tickers)})" if n.related_tickers else ""
        message_parts.append(f"- {emoji} *{n.sentiment}* | `{n.type}` {related_tickers_str}: [{html.unescape(n.title)}]({n.link})")
    message = "\n".join(message_parts)
    await _broadcast_text(context, message)


# ---------- Chart Logic ----------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Trong file: alerts_jobs.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots # Thêm dòng này

# ... (các phần code khác giữ nguyên) ...

async def _render_chart_plotly(symbol: str, rules: Dict[str, Any], out_path: str) -> Optional[str]:
    """
    Vẽ biểu đồ Plotly tương tác và lưu dưới dạng file HTML.
    Trả về đường dẫn đến file nếu thành công, ngược lại trả về None.
    """
    df = data_ta.fetch_historical_eod_data(symbol, days=CHART_DAYS)
    df_vnindex = data_ta.fetch_historical_eod_data('VNINDEX', days=CHART_DAYS)

    if df is None or df.empty:
        log.warning(f"Không có đủ dữ liệu lịch sử để vẽ biểu đồ cho {symbol}.")
        return None

    # --- THAY ĐỔI: Tạo biểu đồ với 2 trục tung ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Thêm biểu đồ nến cho mã cổ phiếu vào trục tung chính
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name=symbol
    ), secondary_y=False)
    
    # Thêm VN-Index vào trục tung phụ
    if df_vnindex is not None and not df_vnindex.empty:
        fig.add_trace(go.Scatter(
            x=df_vnindex.index, 
            y=df_vnindex['Close'], 
            mode='lines', 
            name='VN-Index', 
            line=dict(color='yellow', width=1)
        ), secondary_y=True)

    # Thêm các đường ngang (levels) vào trục tung chính
    for level in rules.get('levels', []):
        fig.add_hline(y=level, line_dash="dash", annotation_text=f"Level: {level}", annotation_position="bottom right", secondary_y=False)

    for major_level in rules.get('major_levels', []):
        fig.add_hline(y=major_level, line_dash="dot", annotation_text=f"Major: {major_level}", annotation_position="top left", line_color="orange", secondary_y=False)
    
    # Tùy chỉnh layout và các trục
    fig.update_layout(
        title=f'Biểu đồ {symbol} so với VN-Index',
        xaxis_rangeslider_visible=False,
        template='plotly_dark' if CHART_THEME.lower() == 'dark' else 'plotly'
    )
    
    # Đặt tên cho các trục tung
    fig.update_yaxes(title_text=f"<b>Giá {symbol}</b>", secondary_y=False)
    fig.update_yaxes(title_text="<b>Chỉ số VN-Index</b>", secondary_y=True)
    
    try:
        fig.write_html(out_path)
        log.info(f"Đã lưu biểu đồ Plotly thành công tại: {out_path}")
        return out_path
    except Exception as e:
        log.error(f"Lỗi khi vẽ biểu đồ Plotly cho {symbol}: {e}", exc_info=True)
        return None

# === HÀM VẼ BIỂU ĐỒ GỐC (Dùng cho các lệnh cũ) ===
def _render_chart_png(symbol: str, rules: Dict[str, Any], out_path: str) -> Optional[str]:
    """
    Vẽ biểu đồ tài chính chi tiết và lưu dưới dạng file PNG.
    Trả về đường dẫn đến file nếu thành công, ngược lại trả về None.
    """
    df = fetch_historical_eod_data(symbol, days=CHART_DAYS)
    if df is None or df.empty:
        log.warning(f"Không có đủ dữ liệu lịch sử để vẽ biểu đồ cho {symbol}.")
        return None
    hlines_data = []
    colors = []
    styles = []
    levels = rules.get('levels', [])
    major_levels = rules.get('major_levels', [])
    if levels:
        hlines_data.extend(levels)
        colors.extend(['#cccccc'] * len(levels))
        styles.extend(['--'] * len(levels))
    if major_levels:
        hlines_data.extend(major_levels)
        colors.extend(['#ffc107'] * len(major_levels))
        styles.extend(['-'] * len(major_levels))
    theme = CHART_THEME.lower()
    style_name = 'nightclouds' if theme == 'dark' else 'yahoo'
    mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style=style_name, marketcolors=mc)
    plot_kwargs = {
        'type': 'candle',
        'style': s,
        'title': f'\nBiểu đồ {symbol} ({vn_now().strftime("%Y-%m-%d")})',
        'ylabel': 'Giá',
        'volume': True,
        'ylabel_lower': 'Khối lượng',
        'mav': (20, 50),
        'hlines': dict(hlines=hlines_data, colors=colors, linestyle=styles, linewidths=0.7),
        'figratio': (CHART_WIDTH / 100, CHART_HEIGHT / 100),
        'figscale': 1.0,
        'savefig': dict(fname=out_path, dpi=100, pad_inches=0.25)
    }
    try:
        log.info(f"Bắt đầu vẽ biểu đồ cho {symbol}...")
        mpf.plot(df, **plot_kwargs)
        log.info(f"Đã lưu biểu đồ thành công tại: {out_path}")
        return out_path
    except Exception as e:
        log.error(f"Lỗi khi vẽ biểu đồ cho {symbol}: {e}", exc_info=True)
        return None

# ---------- TÁC VỤ TỰ ĐỘNG MỚI ----------
async def refresh_all_active_rules_job(context: ContextTypes.DEFAULT_TYPE):
    log.info("Bắt đầu tác vụ tự động làm mới Rules...")
    tickers = list_all_tickers_from_owner_db()
    if not tickers:
        log.info("Không có mã nào trong danh mục, bỏ qua làm mới Rules.")
        return
    updated_count = 0
    failed_tickers = []
    for ticker in tickers:
        try:
            result = propose_and_apply_rules(ticker, mode="auto_refresh", replace_existing=True)
            if result.get("ok"):
                updated_count += 1
                log.info(f"Đã làm mới Rule cho {ticker}.")
            else:
                failed_tickers.append(ticker)
                log.warning(f"Làm mới Rule cho {ticker} thất bại: {result.get('msg')}")
            await asyncio.sleep(1) 
        except Exception as e:
            failed_tickers.append(ticker)
            log.error(f"Lỗi nghiêm trọng khi làm mới Rule cho {ticker}: {e}")
    summary_message = (
        f"🔄 **Hoàn tất làm mới Rules buổi sáng**\n\n"
        f"- ✅ Cập nhật thành công: {updated_count}/{len(tickers)} mã\n"
    )
    if failed_tickers:
        summary_message += f"- ❌ Thất bại: {len(failed_tickers)} mã ({', '.join(failed_tickers)})"
    await _broadcast_text(context, summary_message)
    log.info("Hoàn tất tác vụ làm mới Rules.")