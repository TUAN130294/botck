# -*- coding: utf-8 -*-
# app.py — Telegram x Gemini Stock Bot (Phiên bản hoàn chỉnh với giao diện tương tác)
# Áp dụng các cải tiến: Tích hợp Plotly chart, backtest nâng cao.

import os, json, time, asyncio, logging, random, re
from typing import List, Optional, Dict, Any, Tuple
from datetime import time as dtime, timedelta
import html
import hashlib
import plotly.graph_objects as go
from plotly.subplots import make_subplots # Thêm dòng này

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error as telegram_error
from telegram.ext import (
    Application, CommandHandler, ContextTypes, ConversationHandler, CallbackQueryHandler
)

from config import (
    TZ, TELEGRAM_BOT_TOKEN, STATUS_PORT,
    MONITOR_HW_INTERVAL, MONITOR_PENDING_INTERVAL, HEARTBEAT_INTERVAL,
    ADMIN_IDS, GEMINI_API_KEY, GEMINI_BASE_URLS, GEMINI_MODEL,
    NEWS_AUTO_SCHEDULE, NEWS_AUTO_IMPACT, NEWS_SOURCES
)

import data_ta
from data_ta import (
    vn_now, fetch_stock_data_async, compute_intraday_technicals, is_trading_hours,
    fetch_fundamental_data, find_divergences, compute_technicals, run_backtest
)

import portfolio
from portfolio import (
    OWNER_DB, RULES, ensure_owner, parse_ticker_list, propose_and_apply_rules,
    list_all_tickers_from_owner_db, fmt_session_line_compact, plan_compact,
    save_owner_db, save_rules, groups_for_symbol, tickers_in_use,
    prune_rules_not_in_use, costs_for_symbol
)

import alerts_jobs
from alerts_jobs import (
    monitor_hold_watch, monitor_pending, heartbeat_job, news_monitor_job,
    STATUS, ALERT_FEED, start_status_server, _render_chart_png, _render_chart_plotly, # THAY ĐỔI: Thêm _render_chart_plotly
    build_morning_news_message, morning_news_job, maybe_push_news_if_changed,
    refresh_all_active_rules_job, _fmt_ts, LAST_NEWS_HASH
)
from news_service import fetch_and_analyze_news, NewsArticle

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------- LOG ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---------- AI session ----------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "VN-StockBot/1.0 (+https://t.me)"})
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=1, connect=1, read=1, status=1, backoff_factor=0.3, status_forcelist=[429,500,502,503,504],
    allowed_methods=frozenset({"GET","POST"})
)))

def _ai_post(base_url: str, payload: dict, timeout: int = 45) -> dict:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GEMINI_API_KEY}"}
    r = SESSION.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status(); return r.json()

def gemini_generate(prompt: str, sys: str = "", model: Optional[str] = None, temperature: float = 0.35, timeout: int = 45) -> str:
    if not GEMINI_API_KEY: return "(Thiếu GEMINI_API_KEY)"
    payload = { "model": (model or GEMINI_MODEL).strip(), "messages": ([{"role":"system","content":sys}] if sys else []) + [{"role":"user","content":prompt}], "temperature": float(temperature) }
    endpoints = list(GEMINI_BASE_URLS) if GEMINI_BASE_URLS else ["https://api.key4u.shop"]
    random.shuffle(endpoints); last_error = None
    for base in endpoints:
        try:
            data = _ai_post(base, payload, timeout=timeout)
            content = (data.get("choices",[{}])[0].get("message",{}).get("content","") or "").strip()
            if content: return content
            last_error = RuntimeError("Empty AI response")
        except Exception as e:
            last_error = e; time.sleep(0.5)
    return f"(AI lỗi: {last_error})"

# ---------- Helpers ----------
def _fmtnum(x: Optional[float], nd=2) -> str:
    try: return f"{float(x):.{nd}f}"
    except (ValueError, TypeError): return "—"

def _side(a: Optional[float], b: Optional[float]) -> Optional[str]:
    if a is None or b is None: return None
    return "≈" if abs(a-b) <= 0.2 else ("trên" if a>b else "dưới")

def _resolve_owner_and_index(args: List[str], fallback_chat_id: int) -> Tuple[str, int]:
    if not args: return (str(fallback_chat_id), 0)
    first = args[0].strip().upper()
    if first in (portfolio.OWNER_DB.get("aliases") or {}): return (portfolio.OWNER_DB["aliases"][first], 1)
    if first == "ME": return (str(fallback_chat_id), 1)
    if first.lstrip("-").isdigit(): return (first, 1)
    return (str(fallback_chat_id), 0)
    
def _parse_pos_args(full_args_str: str) -> Tuple[Optional[float], Optional[int], Optional[str]]:
    cost, qty, note = None, None, None
    note_match = re.search(r'note=(.*)', full_args_str, re.IGNORECASE)
    if note_match:
        note = note_match.group(1).strip()
        full_args_str = full_args_str[:note_match.start()].strip()
    
    parts = full_args_str.split()
    if len(parts) >= 1:
        try: cost = float(parts[0])
        except ValueError: pass
    if len(parts) >= 2:
        try: qty = int(parts[1])
        except ValueError: pass
    return cost, qty, note
    
def _ticker_levels_from_tokens(tokens: List[str]) -> Tuple[List[float], Optional[int], Optional[str]]:
    levels, vol_req, note = [], None, None
    note_started = False; note_parts = []
    for tok in tokens:
        if note_started: note_parts.append(tok); continue
        if tok.lower().startswith("vol="): vol_req = int(tok[4:])
        elif tok.lower().startswith("note="): note_started = True; note_parts.append(tok[5:])
        else:
            try: levels.append(float(tok))
            except ValueError: pass
    if note_parts: note = " ".join(note_parts)
    return levels, vol_req, note
    
def _add_to_group(oid: str, group: str, tickers: List[str]) -> List[str]:
    ensure_owner(oid); b = portfolio.OWNER_DB["owners"][oid]; added = []
    current_list = b.setdefault(group, [])
    for t in tickers:
        if t not in current_list: current_list.append(t); added.append(t)
    save_owner_db(portfolio.OWNER_DB); return added

# ==============================================================================
# === NÂNG CẤP LÕI AI: PROMPT VÀ LOGIC PHÂN TÍCH ===
# ==============================================================================


# Trong file: app.py

# Trong file: app.py

def build_prompt(symbols: List[str], snapshot: Dict[str, Dict[str, Any]], market_snapshot: Dict[str, Dict[str, Any]], news_by_symbol: Dict[str, List[NewsArticle]]) -> str:
    now_txt = vn_now().strftime("%Y-%m-%d %H:%M")
    lines = [f"Thời gian: {now_txt} (VN)"]

    if market_snapshot:
        # THAY ĐỔI: Xóa định dạng Markdown
        lines.append("\nBỐI CẢNH THỊ TRƯỜNG CHUNG:")
        for idx_symbol, idx_data in market_snapshot.items():
            if not idx_data: continue
            price = idx_data.get('price', 0); ref = idx_data.get('ref', price)
            change = price - ref; pct_change = (change / ref) * 100 if ref else 0
            rsi_val = (idx_data.get("tech") or {}).get("RSI14")
            rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "N/A"
            ema20 = (idx_data.get("tech") or {}).get("EMA20")
            pos_vs_ema20 = _side(price, ema20) if ema20 else "N/A"
            lines.append(f"- {idx_symbol}: {price:.2f} ({pct_change:+.2f}%) | RSI: {rsi_str} | Vị thế/EMA20: {pos_vs_ema20}")

    # THAY ĐỔI: Xóa định dạng Markdown
    lines.append("\nDỮ LIỆU GIÁ/VOL/TIN TỨC CỔ PHIẾU CHI TIẾT:")
    for s in symbols:
        sd = snapshot.get(s, {}) or {}; vol = sd.get("vol_day")
        vol_txt = f"{vol:,}" if isinstance(vol,int) else vol
        lines.append(f"- {s}: price={sd.get('price')} vol_day={vol_txt} | src={sd.get('source','?')} | as_of={sd.get('as_of','?')}")
        
        news_list = news_by_symbol.get(s, [])
        if news_list:
            lines.append(f"  - Tin tức gần đây:")
            for news_item in news_list:
                lines.append(f"    - [{news_item.sentiment}] ({news_item.type}): {news_item.title} (score: {news_item.sentiment_score:+.2f})")
        
        bt = sd.get('backtest')
        if bt and bt.get('ok') and bt.get('num_trades') > 0:
            lines.append(f"  - Backtest ({bt['strategy'].upper()} - {bt['days']} ngày): Lãi/Lỗ: {bt['pnl_vnd']:,.2f} VND ({bt['pnl_percent']:+.2f}%) | Sharpe: {bt['sharpe_ratio']:.2f}")

    # THAY ĐỔI: Xóa định dạng Markdown và làm rõ hơn
    lines.append("\nYÊU CẦU TRẢ LỜI:")
    lines.append("1. NGUYÊN TẮC BẮT BUỘC: Luôn diễn giải các chỉ báo của cổ phiếu (đặc biệt là RSI) trong mối tương quan với bối cảnh thị trường chung. Nếu cổ phiếu 'quá mua' nhưng thị trường chung đang trong uptrend mạnh, hãy nhấn mạnh rằng đó là dấu hiệu của động lượng mạnh và có thể tiếp diễn, thay vì chỉ cảnh báo rủi ro điều chỉnh một cách máy móc.")
    lines.append("2. Với mỗi mã cổ phiếu bên dưới, hãy phân tích ngắn gọn theo cấu trúc sau:")
    lines.append("   • Xu hướng/động lượng (kết hợp tin tức).")
    lines.append("   • Các mốc giá/vol quan trọng.")
    lines.append("   • Kết quả backtest.")
    lines.append("   • Kế hoạch hành động ngắn gọn.")
    lines.append("3. ĐỊNH DẠNG: Trình bày rõ ràng, dễ đọc. Sử dụng Markdown (`*in đậm*`, `_in nghiêng_`) một cách hợp lý, không lạm dụng. Xuống dòng giữa các mục để dễ theo dõi.")
    
    return "\n".join(lines)
def ai_analyze(symbols: List[str], snapshot: Dict[str, Dict[str, Any]], market_snapshot: Dict[str, Dict[str, Any]], news_by_symbol: Dict[str, List[NewsArticle]]) -> str:
    sys = ("Bạn là trợ lý phân tích chứng khoán VN ngắn hạn - kỷ luật và luôn nhận định trong bối cảnh thị trường chung. "
           "Trả lời ngắn gọn, rõ ràng, không khẳng định tuyệt đối. Dùng bullet khi hợp lý.")
    prompt = build_prompt(symbols, snapshot, market_snapshot, news_by_symbol)
    res = gemini_generate(prompt, sys)
    if res.startswith("(AI lỗi"):
        lines = ["⚠️ AI tạm thời gặp lỗi. Dưới đây là dữ liệu thô:"]
        for s in symbols:
            d = snapshot.get(s) or {}; t = d.get("tech") or {}
            lines.append(f"- {s}: giá={_fmtnum(d.get('price'))}, RSI={_fmtnum(t.get('RSI14'),0)}")
        return "\n".join(lines)
    return res
    
# ==============================================================================
# === GIAO DIỆN TƯƠNG TÁC CHO LỆNH /help ===
# ==============================================================================
HELP_MENU, HELP_CATEGORY = range(2)
(CB_HELP_PORTFOLIO, CB_HELP_ANALYSIS, CB_HELP_TRADING, CB_HELP_SYSTEM, CB_HELP_BACK) = (
    "help_portfolio", "help_analysis", "help_trading", "help_system", "help_back"
)

async def help_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("📋 Quản lý Danh mục", callback_data=CB_HELP_PORTFOLIO), InlineKeyboardButton("🤖 AI & Phân tích", callback_data=CB_HELP_ANALYSIS)],
        [InlineKeyboardButton("💼 Giao dịch & Rủi ro", callback_data=CB_HELP_TRADING), InlineKeyboardButton("⚙️ Hệ thống", callback_data=CB_HELP_SYSTEM)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "📘 **Bot Trợ lý Chứng khoán**\n\nVui lòng chọn một danh mục để xem các lệnh có sẵn:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return HELP_MENU

async def help_show_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    category_texts = {
        CB_HELP_PORTFOLIO: "*/review [owner]*\n» Mở menu tương tác để xem lại toàn bộ danh mục.\n\n" "*/hold [owner] <MÃ...>* - Thêm mã vào danh sách HOLD.\n\n" "*/pending [owner] <MÃ...>* - Thêm mã vào danh sách PENDING.\n\n" "*/watch [owner] <MÃ> [mốc...]* - Theo dõi một mã với các mốc giá.\n\n" "*/rmowner <owner> <MÃ...>* - Xóa mã khỏi tất cả danh mục.",
        CB_HELP_ANALYSIS: "*/ai [owner|MÃ...]*\n» Chạy phân tích AI cho danh mục hoặc các mã cụ thể.\n\n" "*/div <MÃ>* - Quét và phân tích tín hiệu phân kỳ.\n\n" "*/chart <MÃ>* - Vẽ biểu đồ kỹ thuật.\n\n" "*/fa <MÃ>* - Lấy dữ liệu phân tích cơ bản (P/E, Vốn hóa...).\n\n" "*/diag <MÃ>* - Kiểm tra dữ liệu thô mà bot đang nhận được.\n\n" "*/backtest <MÃ> <ngày> [chiến lược]*\n» Chạy backtest chiến lược RSI, MACD, v.v.",
        CB_HELP_TRADING: "*/pos [owner] <MÃ> [giá] [sl]*\n» Ghi lại vị thế đang nắm giữ.\n\n" "*/trailingstop <MÃ> <phần_trăm>%*\n» Đặt lệnh dừng lỗ động (ví dụ: `5%`).\n\n" "*/size <MÃ> <giá_dừng_lỗ> <rủi_ro_VND>*\n» Tính toán khối lượng vào lệnh.",
        CB_HELP_SYSTEM: "*/status* - Xem trạng thái hoạt động của bot.\n\n" "*/ping* - Kiểm tra bot có đang chạy không.\n\n" "*/rules* - Xem các quy tắc đã lưu.\n\n" "*/ownerwl* - Xem danh sách mã của một owner.",
    }
    text = category_texts.get(query.data, "Không tìm thấy danh mục.")
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại Menu Chính", callback_data=CB_HELP_BACK)]])
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    return HELP_CATEGORY

# ==============================================================================
# === GIAO DIỆN TƯƠNG TÁC CHO LỆNH /review ===
# ==============================================================================
REVIEW_MENU, REVIEW_DETAIL = range(2)
(CB_HOLD, CB_PENDING, CB_WATCH, CB_ALL_AI, CB_BACK_REV, CB_END) = ("rev_hold", "rev_pending", "rev_watch", "rev_all_ai", "rev_back", "rev_end")

async def review_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    oid, _ = _resolve_owner_and_index(context.args, update.effective_user.id)
    context.user_data['review_oid'] = oid; b = portfolio.OWNER_DB.get("owners", {}).get(oid, {})
    keyboard = [
        [InlineKeyboardButton(f"💼 HOLD ({len(b.get('HOLD',[]))})", callback_data=CB_HOLD), InlineKeyboardButton(f"⏳ PENDING ({len(b.get('PENDING',[]))})", callback_data=CB_PENDING)],
        [InlineKeyboardButton(f"👀 WATCH ({len((b.get('WATCH') or {}).keys())})", callback_data=CB_WATCH), InlineKeyboardButton("🤖 AI Phân tích tất cả", callback_data=CB_ALL_AI)],
        [InlineKeyboardButton("❌ Đóng", callback_data=CB_END)],
    ]
    text = f"🧭 Review danh mục cho {oid}. Vui lòng chọn:"
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return REVIEW_MENU

async def review_show_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    category_map = {CB_HOLD: "HOLD", CB_PENDING: "PENDING", CB_WATCH: "WATCH"}
    category = category_map[query.data]; oid = context.user_data['review_oid']; b = portfolio.OWNER_DB.get("owners", {}).get(oid, {})
    tickers = sorted((b.get("WATCH") or {}).keys()) if category == "WATCH" else sorted(b.get(category, []))
    if not tickers: await query.answer(text=f"Danh mục {category} trống.", show_alert=True); return REVIEW_MENU
    
    context.user_data['current_category'] = category
    context.user_data['current_tickers'] = tickers

    await query.edit_message_text(text=f"⏳ Đang tải dữ liệu cho {len(tickers)} mã trong *{category}*...", parse_mode="Markdown")
    results = await asyncio.gather(*(fetch_stock_data_async(s) for s in tickers)); snap = {s: d for s, d in zip(tickers, results) if d}
    
    text_lines = [f"*{category} của {oid}* — {vn_now().strftime('%H:%M')}"]
    keyboard = []
    ticker_buttons = []
    for s in tickers:
        d = snap.get(s); r = portfolio.RULES.get(s, {})
        line = f"- `{s}`: "
        if not d: line += "(thiếu dữ liệu)"
        else:
            cost_info = ""
            if category == "HOLD":
                cost = (costs_for_symbol(s)).get(oid)
                if cost and d.get('price') is not None: pnl = (d['price'] - cost) / cost * 100; cost_info = f" | cost={cost:.2f} PnL={pnl:+.2f}%"
            line += fmt_session_line_compact(s, d, r).replace(f"- {s}: ","") + cost_info
        text_lines.append(line)
        ticker_buttons.append(InlineKeyboardButton(f"{s}", callback_data=f"rev_ticker_{s}"))
    
    keyboard.extend([ticker_buttons[i:i + 3] for i in range(0, len(ticker_buttons), 3)])
    keyboard.append([InlineKeyboardButton("⬅️ Quay lại", callback_data=CB_BACK_REV)])
    
    await query.edit_message_text(text="\n".join(text_lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return REVIEW_DETAIL

async def review_show_ticker_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    ticker = query.data.split('_')[-1]
    keyboard = [
        [InlineKeyboardButton(f"📊 Chart", callback_data=f"rev_chart_{ticker}"), InlineKeyboardButton(f"🤖 AI", callback_data=f"rev_ai_{ticker}")],
        [InlineKeyboardButton(f"🗑️ Xóa", callback_data=f"rev_rm_{ticker}")],
        [InlineKeyboardButton("⬅️ Quay lại danh sách", callback_data=CB_BACK_REV)]
    ]
    await query.edit_message_text(f"Hành động cho mã *{ticker}*:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return REVIEW_DETAIL

async def review_ticker_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    action, ticker = query.data.split('_', 2)[1:]
    oid = context.user_data['review_oid']
    category = context.user_data.get('current_category', 'HOLD')
    message = query.message

    await query.edit_message_text(f"⏳ Đang xử lý: *{action.upper()}* cho *{ticker}*...", parse_mode="Markdown")

    if action == "chart":
        await chart_cmd(update, context, ticker=ticker)
    elif action == "ai":
        await ai_cmd(update, context, symbols_override=[ticker])
    elif action == "rm":
        b = portfolio.OWNER_DB["owners"].get(oid, {})
        if category == "WATCH": b.get("WATCH", {}).pop(ticker, None)
        elif category in ["HOLD", "PENDING"] and ticker in b.get(category, []): b[category].remove(ticker)
        save_owner_db(portfolio.OWNER_DB)
        await message.reply_text(f"✅ Đã xóa `{ticker}` khỏi danh mục {category} của {oid}.", parse_mode="Markdown")
    
    query.data = f"rev_{category.lower()}"
    return await review_show_category(update, context)

async def review_ai_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    oid = context.user_data['review_oid']; b = portfolio.OWNER_DB.get("owners", {}).get(oid, {})
    symbols_to_analyze = sorted(set(b.get("HOLD", [])) | set(b.get("PENDING", [])) | set((b.get("WATCH") or {}).keys()))
    if not symbols_to_analyze: await query.answer(text="Danh mục trống.", show_alert=True); return REVIEW_MENU
    
    await query.edit_message_text(text=f"⏳ Đang lấy dữ liệu thị trường & {len(symbols_to_analyze)} mã để phân tích AI...")
    
    market_indices = ['VNINDEX', 'VN30']
    all_symbols_to_fetch = sorted(list(set(symbols_to_analyze + market_indices)))
    results = await asyncio.gather(*(fetch_stock_data_async(s) for s in all_symbols_to_fetch))
        
    full_snapshot: Dict[str, Dict[str, Any]] = {}
    for s, d in zip(all_symbols_to_fetch, results):
        if d:
            sd = dict(d); 
            sd["tech"] = compute_technicals(sd); 
            # CHẠY BACKTEST VÀ GẮN VÀO SNAPSHOT
            if s not in market_indices:
                sd['backtest'] = await asyncio.to_thread(run_backtest, s, 180, 'rsi_ema')
            full_snapshot[s] = sd

    market_snapshot = {s: full_snapshot.get(s) for s in market_indices if s in full_snapshot}
    stock_snapshot = {s: full_snapshot.get(s) for s in symbols_to_analyze if s in full_snapshot}
    
    if not stock_snapshot: await query.edit_message_text("⚠️ Không lấy được dữ liệu giá/vol cho các mã yêu cầu."); return REVIEW_DETAIL
    
    # Lấy thông tin tin tức
    all_news = await asyncio.to_thread(fetch_and_analyze_news, NEWS_SOURCES, symbols_to_analyze, max_per_source=20) # THAY ĐỔI: Tăng max_per_source
    news_by_symbol = {}
    for news_item in all_news:
        for ticker in news_item.related_tickers:
            news_by_symbol.setdefault(ticker, []).append(news_item)

    analysis = await asyncio.to_thread(ai_analyze, list(stock_snapshot.keys()), stock_snapshot, market_snapshot, news_by_symbol)
    
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data=CB_BACK_REV)]])
    text_to_send = "*🤖 Phân tích AI toàn danh mục (có ngữ cảnh thị trường):*\n" + analysis
    
    try:
        await query.edit_message_text(text=text_to_send, reply_markup=reply_markup, parse_mode="Markdown")
    except telegram_error.BadRequest:
        await query.edit_message_text(text=text_to_send, reply_markup=reply_markup)
            
    return REVIEW_DETAIL

async def review_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text(text="Đã đóng menu review.")
    return ConversationHandler.END
    
# ==============================================================================
# === CÁC LỆNH COMMAND MỚI VÀ ĐƯỢC SỬA LỖI ===
# ==============================================================================

async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, symbols_override: Optional[List[str]] = None):
    oid, idx = _resolve_owner_and_index(context.args, update.effective_user.id)
    
    symbols_to_analyze = symbols_override
    if not symbols_to_analyze:
        tail_args = context.args[idx:]; txt = " ".join(tail_args).strip()
        symbols_to_analyze = parse_ticker_list([txt]) if txt else []
        if not symbols_to_analyze:
            if txt:
                await update.message.reply_text(f"⚠️ Không thể nhận diện mã `{txt}`."); return
            else:
                b = portfolio.OWNER_DB.get("owners", {}).get(oid, {})
                symbols_to_analyze = sorted(set(b.get("HOLD", []) or []) | set(b.get("PENDING", []) or []) | set((b.get("WATCH") or {}).keys()))
    
    if not symbols_to_analyze:
        await update.message.reply_text(f"({oid}) chưa có mã nào để phân tích."); return
    
    await update.message.reply_text("⏳ Lấy dữ liệu thị trường & cổ phiếu để phân tích AI…")
    
    market_indices = ['VNINDEX', 'VN30']
    all_symbols_to_fetch = sorted(list(set(symbols_to_analyze + market_indices)))
    results = await asyncio.gather(*(fetch_stock_data_async(s) for s in all_symbols_to_fetch))
        
    full_snapshot: Dict[str, Dict[str, Any]] = {}
    for s, d in zip(all_symbols_to_fetch, results):
        if d:
            sd = dict(d); 
            sd["tech"] = compute_technicals(sd); 
            if s not in market_indices:
                sd['backtest'] = await asyncio.to_thread(run_backtest, s, 180, 'rsi_ema')
            full_snapshot[s] = sd
    
    market_snapshot = {s: full_snapshot.get(s) for s in market_indices if s in full_snapshot}
    stock_snapshot = {s: full_snapshot.get(s) for s in symbols_to_analyze if s in full_snapshot}
    
    if not stock_snapshot: await update.message.reply_text("⚠️ Không lấy được dữ liệu giá/vol cho các mã yêu cầu."); return
    
    all_news = await asyncio.to_thread(fetch_and_analyze_news, NEWS_SOURCES, symbols_to_analyze, max_per_source=20)
    news_by_symbol = {}
    for news_item in all_news:
        for ticker in news_item.related_tickers:
            news_by_symbol.setdefault(ticker, []).append(news_item)

    analysis = await asyncio.to_thread(ai_analyze, list(stock_snapshot.keys()), stock_snapshot, market_snapshot, news_by_symbol)
    
    vnindex_info = "VN-Index: (không có dữ liệu)"
    if 'VNINDEX' in market_snapshot:
        vi = market_snapshot['VNINDEX']; price = vi.get('price', 0); change = price - vi.get('ref', price)
        pct_change = (change / vi.get('ref', 1)) * 100 if vi.get('ref') else 0
        vnindex_info = f"VN-Index: {price:.2f} ({change:+.2f} / {pct_change:+.2f}%)"
    
    # THAY ĐỔI: Thêm parse_mode="Markdown" để định dạng tin nhắn
    text_to_send = f"{vnindex_info}\n\n🤖 Phân tích AI (có ngữ cảnh thị trường):\n{analysis}"
    try:
        await update.message.reply_text(text_to_send, parse_mode="Markdown")
    except telegram_error.BadRequest:
        # Nếu AI trả về Markdown lỗi, gửi dưới dạng văn bản thường để tránh crash
        await update.message.reply_text(text_to_send)

DIVERGENCE_GUIDE = """
BẢN CHẤT CỦA PHÂN KỲ CHỈ BÁO KỸ THUẬT:
1. Phân kỳ mang ý nghĩa CẢNH BÁO về xung lực của xu hướng. Nó kh\xf4ng phải t\xedn hi\x1ec7u đảo chi\u1ec1u tức th\xec.
2. Phân kỳ thường xuất hiện ở s\xf3ng cuối (s\xf3ng 5). Nó chỉ được XÁC NHẬN khi s\xf3ng cuối đ\xf3 tạo đỉnh/đ\xe1y v\xe0 bắt đầu g\xe3y xu hướng nhỏ hơn. Đừng h\xe0nh động chỉ v\xec thấy ph\xe2n kỳ.
3. Tinh tu\xfd l\xe0 nhận biết v\xf9ng bi\xean độ m\xe0 xu hướng trung hạn v\xe0 d\xe0i hạn "C\xd3 TH\u1ec2" m\xe2u thuẫn, v\xe0 lấy ph\xe2n kỳ l\xe0m dấu hiệu XÁC NHẬN cho v\xf9ng đ\xf3.
"""

async def div_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Cú pháp: /div <MÃ>"); return
    sym = context.args[0].upper()
    await update.message.reply_text(f"🔎 Đang quét tín hiệu phân kỳ cho {sym} (khung 180 ngày)...")
    div_data = await asyncio.to_thread(find_divergences, sym)
    if not div_data.get("ok"): await update.message.reply_text(f"Lỗi: {div_data.get('msg', 'Không xác định')}"); return
    bearish_div = div_data.get("bearish"); bullish_div = div_data.get("bullish")
    if not bearish_div and not bullish_div:
        await update.message.reply_text(f"Không tìm thấy tín hiệu phân kỳ rõ ràng nào cho {sym} trong thời gian gần đây."); return
    prompt_lines = [f"Mã cổ phiếu: {sym}", "Tín hiệu phân kỳ RSI(14) gần nhất được phát hiện:"]
    if bearish_div:
        b = bearish_div[0]
        prompt_lines.append(f"- PHÂN KỲ ÂM (Cảnh báo suy yếu):")
        prompt_lines.append(f"  - Đỉnh giá: {b['price_peak_1'][1]} ({b['price_peak_1'][0]}) -> {b['price_peak_2'][1]} ({b['price_peak_2'][0]}) (HH)")
        prompt_lines.append(f"  - Đỉnh RSI: {b['rsi_peak_1']} -> {b['rsi_peak_2']} (LH)")
    if bullish_div:
        b = bullish_div[0]
        prompt_lines.append(f"- PHÂN KỲ DƯƠNG (Cảnh báo tạo đáy):")
        prompt_lines.append(f"  - Đáy giá: {b['price_trough_1'][1]} ({b['price_trough_1'][0]}) -> {b['price_trough_2'][1]} ({b['price_trough_2'][0]}) (LL)")
        prompt_lines.append(f"  - Đáy RSI: {b['rsi_trough_1']} -> {b['rsi_trough_2']} (HL)")
    prompt_lines.append("\nYÊU CẦU PHÂN TÍCH:")
    prompt_lines.append("Dựa trên các nguy\xean tắc v\xe0 triết l\xfd trong t\xe0i liệu hướng dẫn, h\xe3y ph\xe2n t\xedch \xfd nghĩa của t\xedn hiệu n\xe0y. KH\xd4NG đưa ra khuyến nghị mua/b\xe1n. Tập trung v\xe0o:")
    prompt_lines.append("1. \xdd nghĩa cảnh b\xe1o của t\xedn hiệu n\xe0y l\xe0 g\xec (về xung lực, về khả năng đ\xe2y l\xe0 s\xf3ng cuối)?")
    prompt_lines.append("2. Cần những t\xedn hiệu n\xe0o để XÁC NHẬN sự ph\xe2n kỳ n\xe0y c\xf3 hiệu lực?")
    prompt_lines.append("3. Lời khuy\xean về quản trị rủi ro hoặc l\xean kế hoạch h\xe0nh động khi thấy t\xedn hiệu n\xe0y l\xe0 g\xec?")
    analysis = await asyncio.to_thread(gemini_generate, "\n".join(prompt_lines), sys=DIVERGENCE_GUIDE, temperature=0.5)
    header = f"**🔍 Ph\xe2n t\xedch Ph\xe2n kỳ cho {sym}**\n\n"
    await update.message.reply_text(header + "🤖 **Diễn giải của AI:**\n" + analysis, parse_mode="Markdown")

async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ticker: Optional[str] = None):
    sym = ticker or (context.args[0].upper() if context.args else None)
    if not sym:
        if update.effective_message:
            await update.effective_message.reply_text("Cú pháp: /chart <MÃ>")
        return
    message_to_edit = None
    try:
        if update.callback_query: message_to_edit = await update.callback_query.message.reply_text(f"⏳ Đang vẽ biểu đồ cho {sym}...")
        else: message_to_edit = await update.message.reply_text(f"⏳ Đang vẽ biểu đồ cho {sym}...")
    except Exception as e: log.warning(f"Không thể gửi tin nhắn chờ cho chart: {e}")
    # THAY ĐỔI: Sử dụng hàm vẽ biểu đồ Plotly
    out_path = os.path.join(os.getcwd(), f"chart_{sym}_{int(time.time())}.html")
    # FIX: Await the async function directly
    path = await alerts_jobs._render_chart_plotly(sym, portfolio.RULES.get(sym, {}), out_path)
    if message_to_edit: await message_to_edit.delete()
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as html_file:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=html_file, caption=f"Biểu đồ tương tác {sym} (mở bằng trình duyệt)")
        finally:
            os.remove(path)
    else: await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Không thể tạo biểu đồ cho {sym}.")

async def fa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Cú pháp: /fa <MÃ>"); return
    sym = context.args[0].upper(); await update.message.reply_text(f"⏳ Đang lấy dữ liệu cơ bản cho {sym}...")
    data = await asyncio.to_thread(fetch_fundamental_data, sym)
    if not data: await update.message.reply_text(f"Không tìm thấy dữ liệu cho {sym}."); return
    lines = [f"**Phân tích cơ bản: {sym}**"] + [f"- {k}: {v}" for k, v in data.items()]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
# ==============================================================================
# === CÁC LỆNH COMMAND CƠ BẢN (ĐÃ BỔ SUNG) ===
# ==============================================================================
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(f"✅ Alive {vn_now().strftime('%H:%M:%S')}")
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = int(time.time() - alerts_jobs.STATUS["start_ts"])
    uptime_str = str(timedelta(seconds=uptime))
    last_hw = alerts_jobs._fmt_ts(alerts_jobs.STATUS.get("last_monitor_hw"))
    last_pending = alerts_jobs._fmt_ts(alerts_jobs.STATUS.get("last_monitor_pending"))
    last_hb = alerts_jobs._fmt_ts(alerts_jobs.STATUS.get("last_heartbeat"))
    text = (
        f"**Bot Status**\n"
        f"- Uptime: `{uptime_str}`\n"
        f"- Last HOLD/WATCH scan: `{last_hw}`\n"
        f"- Last PENDING scan: `{last_pending}`\n"
        f"- Last Heartbeat: `{last_hb}`\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        await update.effective_chat.send_message(f"ID của bạn: `{update.effective_chat.id}`", parse_mode="Markdown")
async def owners_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["**Owners**"]
    for oid, b in portfolio.OWNER_DB.get("owners", {}).items():
        tickers = portfolio.list_all_tickers_from_owner_db()
        lines.append(f"- `{oid}`: {len(b.get('HOLD', []))} HOLD, {len(b.get('PENDING', []))} PENDING, {len((b.get('WATCH') or {}).keys())} WATCH")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
async def alias_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Cú pháp: /alias <alias> <owner_id>")
        return
    alias, oid = context.args[0], context.args[1]
    portfolio.OWNER_DB["aliases"][alias] = oid
    portfolio.save_owner_db(portfolio.OWNER_DB)
    await update.message.reply_text(f"Đã đặt alias `{alias}` cho `{oid}`.", parse_mode="Markdown")
async def ownerwl_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid, _ = _resolve_owner_and_index(context.args, update.effective_user.id)
    b = portfolio.OWNER_DB.get("owners", {}).get(oid, {})
    if not b:
        await update.message.reply_text(f"Không tìm thấy owner `{oid}`.")
        return
    text = f"**Danh mục của {oid}:**\n"
    text += f"**HOLD**: {', '.join(b.get('HOLD', [])) or '-'}\n"
    text += f"**PENDING**: {', '.join(b.get('PENDING', [])) or '-'}\n"
    text += f"**WATCH**: {', '.join((b.get('WATCH') or {}).keys()) or '-'}"
    await update.message.reply_text(text, parse_mode="Markdown")
async def pos_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid, idx = _resolve_owner_and_index(context.args, update.effective_user.id)
    tickers = parse_ticker_list(context.args[idx:idx+1])
    if not tickers:
        await update.message.reply_text("Cú pháp: /pos [owner] <MÃ> [giá] [sl] [note=...]")
        return
    sym = tickers[0]
    cost, qty, note = _parse_pos_args(" ".join(context.args[idx+1:]))
    ensure_owner(oid)
    pos_detail = portfolio.OWNER_DB["owners"][oid]["HOLD_DTL"].setdefault(sym, {})
    if cost is not None: pos_detail["cost"] = cost
    if qty is not None: pos_detail["qty"] = qty
    if note is not None: pos_detail["note"] = note
    save_owner_db(portfolio.OWNER_DB)
    await update.message.reply_text(f"✅ Đã cập nhật vị thế cho `{sym}` của `{oid}`.", parse_mode="Markdown")
async def trailingstop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /trailingstop <MÃ> <phần_trăm>%")
        return
    oid, idx = _resolve_owner_and_index(context.args, update.effective_user.id)
    tickers = parse_ticker_list(context.args[idx:idx+1])
    if not tickers:
        await update.message.reply_text("Cú pháp: /trailingstop <MÃ> <phần_trăm>%")
        return
    sym = tickers[0]
    percent_str = context.args[idx+1].replace("%", "")
    try:
        percent = float(percent_str)
        if not (0 < percent <= 100): raise ValueError
    except ValueError:
        await update.message.reply_text("Phần trăm không hợp lệ. Vui lòng nhập số từ 0.1 đến 100.")
        return
    ensure_owner(oid)
    pos_detail = portfolio.OWNER_DB["owners"][oid]["HOLD_DTL"].setdefault(sym, {})
    pos_detail["trailing_stop"] = {"percent": percent, "peak": None}
    save_owner_db(portfolio.OWNER_DB)
    await update.message.reply_text(f"Đã đặt Trailing Stop `{percent}%` cho `{sym}` của `{oid}`.", parse_mode="Markdown")
async def size_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Cú pháp: /size <MÃ> <giá_dừng_lỗ> <rủi_ro_VND>")
        return
    sym, stop_price_str, risk_vnd_str = context.args[:3]
    try:
        stop_price = float(stop_price_str.replace(",", ""))
        risk_vnd = int(risk_vnd_str.replace(",", ""))
        d = await fetch_stock_data_async(sym)
        if not d or d.get("price") is None:
            await update.message.reply_text(f"Không lấy được giá hiện tại của `{sym}`.", parse_mode="Markdown")
            return
        entry_price = float(d["price"])
        if entry_price <= stop_price:
            await update.message.reply_text("Giá dừng lỗ phải thấp hơn giá hiện tại.", parse_mode="Markdown")
            return
        loss_per_share = entry_price - stop_price
        if loss_per_share <= 0:
            await update.message.reply_text("Lỗi: Giá dừng lỗ không hợp lệ.", parse_mode="Markdown")
            return
        qty = int(risk_vnd / loss_per_share)
        await update.message.reply_text(f"**Tính toán khối lượng:**\n- Mua `{qty}` cổ phiếu `{sym}`\n- Giá vào: `{entry_price}`\n- Dừng lỗ: `{stop_price}`\n- Rủi ro: `{risk_vnd}` VND", parse_mode="Markdown")
    except (ValueError, TypeError) as e:
        await update.message.reply_text(f"Lỗi cú pháp: Vui lòng kiểm tra các số bạn đã nhập.\nLỗi: {e}", parse_mode="Markdown")
async def hold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid, idx = _resolve_owner_and_index(context.args, update.effective_user.id)
    tickers = parse_ticker_list(context.args[idx:])
    if not tickers:
        await update.message.reply_text("Cú pháp: /hold [owner] <MÃ...>")
        return
    added = _add_to_group(oid, "HOLD", tickers)
    await update.message.reply_text(f"✅ Đã thêm `{', '.join(added)}` vào danh mục HOLD của `{oid}`.", parse_mode="Markdown")
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid, idx = _resolve_owner_and_index(context.args, update.effective_user.id)
    tickers = parse_ticker_list(context.args[idx:])
    if not tickers:
        await update.message.reply_text("Cú pháp: /pending [owner] <MÃ...>")
        return
    added = _add_to_group(oid, "PENDING", tickers)
    await update.message.reply_text(f"✅ Đã thêm `{', '.join(added)}` vào danh mục PENDING của `{oid}`.", parse_mode="Markdown")
async def rmowner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid, idx = _resolve_owner_and_index(context.args, update.effective_user.id)
    tickers = parse_ticker_list(context.args[idx:])
    if not tickers:
        await update.message.reply_text("Cú pháp: /rmowner [owner] <MÃ...>")
        return
    ensure_owner(oid)
    b = portfolio.OWNER_DB["owners"][oid]
    for t in tickers:
        for group in ["HOLD", "PENDING"]:
            if t in b.get(group, []): b[group].remove(t)
        if t in (b.get("WATCH") or {}): b["WATCH"].pop(t, None)
    save_owner_db(portfolio.OWNER_DB)
    await update.message.reply_text(f"✅ Đã xóa `{', '.join(tickers)}` khỏi danh mục của `{oid}`.", parse_mode="Markdown")
async def watch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid, idx = _resolve_owner_and_index(context.args, update.effective_user.id)
    tickers = parse_ticker_list(context.args[idx:idx+1])
    if not tickers:
        await update.message.reply_text("Cú pháp: /watch [owner] <MÃ> [mốc_giá_1] [mốc_giá_2...]")
        return
    sym = tickers[0]
    levels, _, note = _ticker_levels_from_tokens(context.args[idx+1:])
    ensure_owner(oid)
    b = portfolio.OWNER_DB["owners"][oid]
    watch_entry = b["WATCH"].setdefault(sym, {"levels": [], "note": ""})
    if levels: watch_entry["levels"] = levels
    if note is not None: watch_entry["note"] = note
    save_owner_db(portfolio.OWNER_DB)
    await update.message.reply_text(f"✅ Đã thêm `{sym}` vào WATCH của `{oid}` với các mốc giá {levels}.", parse_mode="Markdown")
async def diag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Cú pháp: /diag <MÃ>"); return
    s = context.args[0].upper(); d = await fetch_stock_data_async(s)
    if not d: await update.message.reply_text(f"❌ Không lấy được dữ liệu cho {s}."); return
    
    # THAY ĐỔI: Thêm ATR vào kết quả diag
    df = d.get('eod_data')
    atr_val = data_ta.atr(df) if df is not None and not df.empty else None
    
    lines = [f"🔎 **DIAG {s}**"] + [f"- `{k}`: {v}" for k, v in d.items()]
    lines.append(f"- `ATR`: {atr_val}") # THAY ĐỔI: Thêm dòng ATR
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
async def rulesrefresh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Bắt đầu làm mới Rules..."); asyncio.create_task(alerts_jobs.refresh_all_active_rules_job(context))
async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📐 RULES:"]
    for t, r in portfolio.RULES.items():
        # Collect watch levels from all owners
        wl_set = set()
        owners = (portfolio.OWNER_DB or {}).get("owners", {})
        for oid, b in owners.items():
            w = (b.get("WATCH") or {}).get(t) or {}
            for x in w.get("levels", []) or []:
                try:
                    wl_set.add(float(x))
                except Exception:
                    pass
        wl_txt = f" | watch_levels={sorted(wl_set)}" if wl_set else ""
        lines.append(f"- {t}: levels={r.get('levels')} | major={r.get('major_levels')}{wl_txt}")
    await update.message.reply_text("\n".join(lines)[:3900])

async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bạn đang sử dụng lệnh /news cũ. Vui lòng dùng /news_enhanced để xem tin tức đã phân tích.")
    
async def backtest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /backtest <MÃ> <số_ngày> [chiến lược]\n"
                                        "Các chiến lược: `rsi` (mặc định), `rsi_ema`, `macd`\n"
                                        "Ví dụ: `/backtest SSI 180 rsi_ema`", parse_mode="Markdown")
        return
    symbol, days_str = context.args[0].upper(), context.args[1]
    strategy = context.args[2].lower() if len(context.args) > 2 else 'rsi'
    
    if strategy not in ['rsi', 'rsi_ema', 'macd']:
        await update.message.reply_text("Chiến lược không hợp lệ. Vui lòng chọn một trong các tùy chọn: `rsi`, `rsi_ema`, `macd`.", parse_mode="Markdown")
        return
        
    try:
        days = int(days_str)
        if days < 30 or days > 365:
            await update.message.reply_text("Số ngày phải từ 30 đến 365.", parse_mode="Markdown")
            return
    except ValueError:
        await update.message.reply_text("Số ngày không hợp lệ. Vui lòng nhập một số.", parse_mode="Markdown")
        return
        
    await update.message.reply_text(f"⏳ Đang chạy backtest chiến lược `{strategy.upper()}` cho `{symbol}` trong {days} ngày...", parse_mode="Markdown")
    
    result = await asyncio.to_thread(run_backtest, symbol, days, strategy)
    
    if not result["ok"]:
        await update.message.reply_text(f"❌ Lỗi backtest: {result['msg']}", parse_mode="Markdown")
        return
        
    trades_summary = "\n".join([f"- {t['date']}: {t['action']} {t['qty'] or ''} cổ phiếu tại giá {t['price']}" for t in result['trades']])

    response = (
        f"**📊 Kết quả Backtest cho `{result['symbol']}` ({result['days']} ngày)**\n\n"
        f"- **Chiến lược:** {result['strategy'].upper()}\n"
        f"- **Vốn ban đầu:** {result['initial_cash']:,} VND\n"
        f"- **Giá trị cuối cùng:** {result['final_value']:,.2f} VND\n"
        f"- **Lãi/Lỗ:** {result['pnl_vnd']:,.2f} VND ({result['pnl_percent']:+.2f}%)\n"
        f"- **Sharpe Ratio:** {result.get('sharpe_ratio', 'N/A'):.2f}\n" # THAY ĐỔI: Thêm Sharpe Ratio
        f"- **Tổng số lệnh:** {result['num_trades']} mua\n\n"
        f"**Chi tiết giao dịch:**\n{trades_summary}"
    )
    
    await update.message.reply_text(response, parse_mode="Markdown")

# (MỚI) Lệnh để lấy và hiển thị tin tức nâng cao - Cải thiện để hiển thị nhiều tin hơn
async def news_enhanced_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang thu thập và phân tích tin tức nâng cao...")
    
    tickers = portfolio.list_all_tickers_from_owner_db()
    all_news = await asyncio.to_thread(fetch_and_analyze_news, NEWS_SOURCES, tickers, max_per_source=20)
    if not all_news:
        await update.message.reply_text("Không có tin tức nào trong thời điểm hiện tại.")
        return
    unique_news = []
    seen_titles = set()
    for news in all_news:
        if news.title not in seen_titles:
            seen_titles.add(news.title)
            unique_news.append(news)
    log.info(f"Đã lọc {len(all_news)} tin thành {len(unique_news)} tin duy nhất")
    high_priority = [n for n in unique_news if n.type in ["Vĩ mô", "Doanh nghiệp"] and n.sentiment in ["Tích cực", "Tiêu cực"]]
    medium_priority = [n for n in unique_news if n.type in ["Vĩ mô", "Doanh nghiệp"] and n.sentiment == "Trung tính"]
    other_news = [n for n in unique_news if n.type not in ["Vĩ mô", "Doanh nghiệp"]]
    message_parts = ["📣 **TIN TỨC ĐƯỢC PHÂN TÍCH**\n"]
    if high_priority:
        message_parts.append("🔥 **TIN TỨC QUAN TRỌNG:**")
        for n in high_priority[:8]:
            emoji = "🟢" if n.sentiment == "Tích cực" else "🔴" if n.sentiment == "Tiêu cực" else "⚪"
            related_tickers_str = f"({', '.join(n.related_tickers)})" if n.related_tickers else ""
            message_parts.append(f"- {emoji} *{n.sentiment}* | `{n.type}` {related_tickers_str}: [{html.unescape(n.title)}]({n.link})")
        message_parts.append("")
    if medium_priority:
        message_parts.append("📊 **TIN TỨC TRUNG BÌNH:**")
        for n in medium_priority[:5]:
            emoji = "⚪"
            related_tickers_str = f"({', '.join(n.related_tickers)})" if n.related_tickers else ""
            message_parts.append(f"- {emoji} *{n.sentiment}* | `{n.type}` {related_tickers_str}: [{html.unescape(n.title)}]({n.link})")
        message_parts.append("")
    if other_news:
        message_parts.append("📰 **TIN TỨC KHÁC:**")
        for n in other_news[:3]:
            emoji = "🟡"
            related_tickers_str = f"({', '.join(n.related_tickers)})" if n.related_tickers else ""
            message_parts.append(f"- {emoji} *{n.sentiment}* | `{n.type}` {related_tickers_str}: [{html.unescape(n.title)}]({n.link})")
    message_parts.append(f"\n📈 **THỐNG KÊ:** Tổng cộng {len(unique_news)} tin tức duy nhất")
    message_parts.append(f"- Tin quan trọng: {len(high_priority)}")
    message_parts.append(f"- Tin trung bình: {len(medium_priority)}")
    message_parts.append(f"- Tin khác: {len(other_news)}")
    message = "\n".join(message_parts)
    if len(message) > 4000:
        part1 = message[:4000]
        part2 = message[4000:]
        try:
            await update.message.reply_text(part1, parse_mode="Markdown")
            await update.message.reply_text(part2, parse_mode="Markdown")
        except telegram_error.BadRequest:
            await update.message.reply_text(part1)
            await update.message.reply_text(part2)
    else:
        try:
            await update.message.reply_text(message, parse_mode="Markdown")
        except telegram_error.BadRequest:
            await update.message.reply_text(message)
    news_hash = hashlib.sha256(json.dumps([html.unescape(n.title) for n in unique_news], sort_keys=True).encode()).hexdigest()
    alerts_jobs.LAST_NEWS_HASH = news_hash

# ==============================================================================
# === MAIN APPLICATION SETUP ===
# ==============================================================================
# THAY ĐỔI: Thêm job cảnh báo divergence và job lấy tin tức nâng cao
async def divergence_monitor_job(context: ContextTypes.DEFAULT_TYPE):
    log.info("Kiểm tra divergence RSI...")
    tickers = portfolio.list_all_tickers_from_owner_db()
    for ticker in tickers:
        div_result = data_ta.find_divergences(ticker)
        if div_result["ok"] and (div_result["bearish"] or div_result["bullish"]):
            message = f"⚠️ **CẢNH BÁO PHÂN KỲ RSI cho {ticker}**\n\n"
            if div_result["bearish"]:
                b = div_result["bearish"][0]
                message += f"- **Phân kỳ Âm (Suy yếu)**:\n  Giá tạo đỉnh sau cao hơn đỉnh trước ({b['price_peak_1'][1]} -> {b['price_peak_2'][1]})\n  RSI tạo đỉnh sau thấp hơn đỉnh trước ({b['rsi_peak_1']} -> {b['rsi_peak_2']})\n"
            if div_result["bullish"]:
                b = div_result["bullish"][0]
                message += f"- **Phân kỳ Dương (Tạo đáy)**:\n  Giá tạo đáy sau thấp hơn đáy trước ({b['price_trough_1'][1]} -> {b['price_trough_2'][1]})\n  RSI tạo đáy sau cao hơn đáy trước ({b['rsi_trough_1']} -> {b['rsi_trough_2']})\n"
            await alerts_jobs._broadcast_text(context, message)

def register_handlers(app: Application):
    help_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("help", help_start)],
        states={
            HELP_MENU: [CallbackQueryHandler(help_show_category, pattern="^help_")],
            HELP_CATEGORY: [CallbackQueryHandler(help_start, pattern=f"^{CB_HELP_BACK}$")],
        },
        fallbacks=[CommandHandler("help", help_start)], per_message=False
    )
    review_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("review", review_start)],
        states={
            REVIEW_MENU: [
                CallbackQueryHandler(review_show_category, pattern=f"^(?:{CB_HOLD}|{CB_PENDING}|{CB_WATCH})$"),
                CallbackQueryHandler(review_ai_all, pattern=f"^{CB_ALL_AI}$"),
                CallbackQueryHandler(review_end, pattern=f"^{CB_END}$"),
            ],
            REVIEW_DETAIL: [
                CallbackQueryHandler(review_start, pattern=f"^{CB_BACK_REV}$"),
                CallbackQueryHandler(review_show_ticker_menu, pattern="^rev_ticker_"),
                CallbackQueryHandler(review_ticker_action, pattern="^rev_(chart|ai|rm)_"),
                CallbackQueryHandler(review_show_category, pattern=f"^(?:{CB_HOLD}|{CB_PENDING}|{CB_WATCH})$")
            ],
        },
        fallbacks=[CommandHandler("review", review_start)], per_message=False
    )
    app.add_handler(help_conv_handler)
    app.add_handler(review_conv_handler)

    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("owners", owners_cmd))
    app.add_handler(CommandHandler("alias", alias_cmd))
    app.add_handler(CommandHandler("ownerwl", ownerwl_cmd))
    app.add_handler(CommandHandler("pos", pos_cmd))
    app.add_handler(CommandHandler("trailingstop", trailingstop_cmd))
    app.add_handler(CommandHandler("size", size_cmd))
    app.add_handler(CommandHandler("hold", hold_cmd))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("rmowner", rmowner_cmd))
    app.add_handler(CommandHandler("watch", watch_cmd))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("rulesrefresh", rulesrefresh_cmd))
    app.add_handler(CommandHandler("ai", ai_cmd))
    app.add_handler(CommandHandler("tech", ai_cmd))
    app.add_handler(CommandHandler("fa", fa_cmd))
    app.add_handler(CommandHandler("diag", diag_cmd))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(CommandHandler("div", div_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("backtest", backtest_cmd))
    app.add_handler(CommandHandler("news_enhanced", news_enhanced_cmd))
    app.add_handler(CommandHandler("divergence", divergence_monitor_job)) # THAY ĐỔI: Thêm lệnh divergence

def main():
    alerts_jobs.start_status_server()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(app)

    jq = app.job_queue
    jq.run_repeating(alerts_jobs.monitor_hold_watch, interval=MONITOR_HW_INTERVAL, first=5, name="monitor_hw")
    jq.run_repeating(alerts_jobs.monitor_pending, interval=MONITOR_PENDING_INTERVAL, first=10, name="monitor_pending")
    jq.run_repeating(alerts_jobs.heartbeat_job, interval=HEARTBEAT_INTERVAL, first=30, name="heartbeat")
    jq.run_repeating(alerts_jobs.news_monitor_job, interval=int(NEWS_AUTO_SCHEDULE), first=15, name="news_monitor")
    jq.run_daily(alerts_jobs.refresh_all_active_rules_job, time=dtime(hour=8, minute=0, tzinfo=TZ), name="refresh_rules")
    jq.run_repeating(divergence_monitor_job, interval=3600, first=60, name="divergence_monitor") # THAY ĐỔI: Thêm job monitor divergence

    log.info("Bot started. Status server: http://127.0.0.1:%d", STATUS_PORT)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()