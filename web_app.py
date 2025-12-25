# -*- coding: utf-8 -*-
"""
web_app.py — Web Interface để quản lý cài đặt Bot Chứng khoán theo từng user
"""

import os
import json
import hashlib
import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pathlib import Path
import portfolio
from config import TARGET_CHAT_IDS, ADMIN_IDS
import data_ta
from data_ta import fetch_stock_data_async, compute_technicals
import asyncio
# Try to import nest_asyncio, if not available, use alternative method
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key-change-in-production-" + hashlib.sha256(str(os.urandom(32)).encode()).hexdigest()[:32])

# Jinja2 filter for formatting numbers
@app.template_filter('format_number')
def format_number(value):
    """Format number with commas"""
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return str(value)

# Data files
DATA_DIR = Path(__file__).resolve().parent
USERS_FILE = DATA_DIR / "web_users.json"

def _load_users():
    """Load users database"""
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    default_users = {
        "admin": {
            "password": hashlib.sha256("admin123".encode()).hexdigest(),
            "owner_id": "admin",
            "is_admin": True
        }
    }
    USERS_FILE.write_text(json.dumps(default_users, ensure_ascii=False, indent=2), encoding="utf-8")
    return default_users

def _save_users(users):
    """Save users database"""
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

def _load_owner_db():
    """Load owner database"""
    # Reload from file
    portfolio.OWNER_DB = portfolio._load_owner_db()
    return portfolio.OWNER_DB

def _save_owner_db():
    """Save owner database"""
    portfolio.save_owner_db(portfolio.OWNER_DB)
    # Reload after save
    portfolio.OWNER_DB = portfolio._load_owner_db()

def _load_rules():
    """Load rules database"""
    # Reload from file
    portfolio.RULES = portfolio._load_rules()
    return portfolio.RULES

def _save_rules():
    """Save rules database"""
    portfolio.save_rules(portfolio.RULES)
    # Reload after save
    portfolio.RULES = portfolio._load_rules()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        users = _load_users()
        if not users.get(session['username'], {}).get('is_admin', False):
            flash('Bạn không có quyền truy cập trang này.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Vui lòng nhập đầy đủ thông tin.', 'error')
            return render_template('login.html')
        
        users = _load_users()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username in users and users[username]['password'] == password_hash:
            session['username'] = username
            session['owner_id'] = users[username].get('owner_id', username)
            session['is_admin'] = users[username].get('is_admin', False)
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    owner_db = _load_owner_db()
    rules = _load_rules()
    owner_id = session.get('owner_id', session.get('username', ''))
    
    owner_data = owner_db.get('owners', {}).get(owner_id, {})
    hold_count = len(owner_data.get('HOLD', []))
    pending_count = len(owner_data.get('PENDING', []))
    watch_count = len(owner_data.get('WATCH', {}))
    
    rules = _load_rules()
    owner_id = session.get('owner_id', session.get('username', ''))
    
    owner_data = owner_db.get('owners', {}).get(owner_id, {})
    hold_list = owner_data.get('HOLD', [])
    pending_list = owner_data.get('PENDING', [])
    watch_dict = owner_data.get('WATCH', {})
    
    # Prepare watch list with details
    watch_list = []
    for ticker, watch_data in watch_dict.items():
        watch_list.append({
            'ticker': ticker,
            'levels': watch_data.get('levels', []),
            'note': watch_data.get('note', '')
        })
    
    return render_template('manage_stocks.html',
                         hold_list=hold_list,
                         pending_list=pending_list,
                         watch_list=watch_list,
                         owner_id=owner_id)

@app.route('/api/stocks/add', methods=['POST'])
@login_required
def api_add_stock():
    owner_db = _load_owner_db()
    owner_id = session.get('owner_id', session.get('username', ''))

    data = request.get_json()
    group = data.get('group', '').upper()  # HOLD, PENDING, WATCH
    ticker = data.get('ticker', '').upper().strip()

    if not ticker or group not in ['HOLD', 'PENDING', 'WATCH']:
        return jsonify({'success': False, 'message': 'Dữ liệu không hợp lệ'}), 400

    portfolio.ensure_owner(owner_id)
    owner_data = portfolio.OWNER_DB['owners'][owner_id]

    # Check if ticker is new (not in any group)
    is_new_ticker = (
        ticker not in owner_data.get('HOLD', []) and
        ticker not in owner_data.get('PENDING', []) and
        ticker not in owner_data.get('WATCH', {})
    )

    if group == 'WATCH':
        levels = data.get('levels', [])
        note = data.get('note', '')
        watch_entry = owner_data['WATCH'].setdefault(ticker, {'levels': [], 'note': ''})
        if levels:
            watch_entry['levels'] = [float(x) for x in levels if x]
        if note:
            watch_entry['note'] = note
    else:
        if ticker not in owner_data[group]:
            owner_data[group].append(ticker)

    _save_owner_db()

    # Auto-propose rules for new ticker (like bot Telegram does)
    if is_new_ticker:
        try:
            result = portfolio.propose_and_apply_rules(ticker, mode="auto_add", replace_existing=False)
            if result.get('ok'):
                applied = result.get('applied', {})
                return jsonify({
                    'success': True,
                    'message': f'Đã thêm {ticker} vào {group}',
                    'auto_rules': True,
                    'rules': {
                        'levels': applied.get('levels', []),
                        'major_levels': applied.get('major', []),
                        'vol_marks': applied.get('vol_marks', [])
                    }
                })
        except Exception as e:
            logging.warning(f"Failed to auto-propose rules for {ticker}: {e}")

    return jsonify({'success': True, 'message': f'Đã thêm {ticker} vào {group}'})

@app.route('/api/stocks/remove', methods=['POST'])
@login_required
def api_remove_stock():
    owner_db = _load_owner_db()
    owner_id = session.get('owner_id', session.get('username', ''))
    
    data = request.get_json()
    group = data.get('group', '').upper()
    ticker = data.get('ticker', '').upper().strip()
    
    if not ticker or group not in ['HOLD', 'PENDING', 'WATCH']:
        return jsonify({'success': False, 'message': 'Dữ liệu không hợp lệ'}), 400
    
    owner_data = portfolio.OWNER_DB.get('owners', {}).get(owner_id, {})
    
    if group == 'WATCH':
        owner_data.get('WATCH', {}).pop(ticker, None)
    else:
        if ticker in owner_data.get(group, []):
            owner_data[group].remove(ticker)
    
    _save_owner_db()
    return jsonify({'success': True, 'message': f'Đã xóa {ticker} khỏi {group}'})

@app.route('/api/stocks/update', methods=['POST'])
@login_required
def api_update_stock():
    owner_db = _load_owner_db()
    owner_id = session.get('owner_id', session.get('username', ''))
    
    data = request.get_json()
    group = data.get('group', '').upper()
    ticker = data.get('ticker', '').upper().strip()
    
    if group != 'WATCH':
        return jsonify({'success': False, 'message': 'Chỉ có thể cập nhật WATCH'}), 400
    
    portfolio.ensure_owner(owner_id)
    owner_data = portfolio.OWNER_DB['owners'][owner_id]
    
    if ticker not in owner_data.get('WATCH', {}):
        return jsonify({'success': False, 'message': 'Mã không tồn tại trong WATCH'}), 404
    
    watch_entry = owner_data['WATCH'][ticker]
    if 'levels' in data:
        watch_entry['levels'] = [float(x) for x in data['levels'] if x]
    if 'note' in data:
        watch_entry['note'] = data['note']
    
    _save_owner_db()
    return jsonify({'success': True, 'message': f'Đã cập nhật {ticker}'})

@app.route('/manage/alerts')
@login_required
def manage_alerts():
    owner_db = _load_owner_db()
    rules = _load_rules()
    owner_id = session.get('owner_id', session.get('username', ''))
    
    owner_data = owner_db.get('owners', {}).get(owner_id, {})
    all_tickers = set(
        owner_data.get('HOLD', []) +
        owner_data.get('PENDING', []) +
        list(owner_data.get('WATCH', {}).keys())
    )
    
    alerts_list = []
    for ticker in sorted(all_tickers):
        rule = rules.get(ticker, {})
        alerts_list.append({
            'ticker': ticker,
            'levels': rule.get('levels', []),
            'major_levels': rule.get('major_levels', []),
            'vol_marks': rule.get('vol_marks', []),
            'note': rule.get('note', '')
        })
    
    return render_template('manage_alerts.html',
                         alerts_list=alerts_list,
                         owner_id=owner_id)

@app.route('/api/alerts/update', methods=['POST'])
@login_required
def api_update_alerts():
    rules = _load_rules()
    owner_db = _load_owner_db()
    owner_id = session.get('owner_id', session.get('username', ''))
    
    data = request.get_json()
    ticker = data.get('ticker', '').upper().strip()
    
    if not ticker:
        return jsonify({'success': False, 'message': 'Mã cổ phiếu không hợp lệ'}), 400
    
    # Check if user owns this ticker
    owner_data = owner_db.get('owners', {}).get(owner_id, {})
    all_user_tickers = set(
        owner_data.get('HOLD', []) +
        owner_data.get('PENDING', []) +
        list(owner_data.get('WATCH', {}).keys())
    )
    
    if ticker not in all_user_tickers:
        return jsonify({'success': False, 'message': 'Bạn không có quyền chỉnh sửa mã này'}), 403
    
    rule = rules.setdefault(ticker, {})
    
    if 'levels' in data:
        rule['levels'] = [float(x) for x in data['levels'] if x]
    if 'major_levels' in data:
        rule['major_levels'] = [float(x) for x in data['major_levels'] if x]
    if 'vol_marks' in data:
        rule['vol_marks'] = [int(x) for x in data['vol_marks'] if x]
    if 'note' in data:
        rule['note'] = data['note']
    
    _save_rules()
    return jsonify({'success': True, 'message': f'Đã cập nhật cảnh báo cho {ticker}'})

@app.route('/manage/users')
@login_required
@admin_required
def manage_users():
    owner_db = _load_owner_db()
    users = _load_users()
    
    # Get all owners
    owners_list = []
    for owner_id, owner_data in owner_db.get('owners', {}).items():
        hold_list = owner_data.get('HOLD', [])
        pending_list = owner_data.get('PENDING', [])
        watch_list = list(owner_data.get('WATCH', {}).keys())
        
        # Count unique tickers (avoid duplicates)
        ticker_count = len(set(hold_list + pending_list + watch_list))
        
        owners_list.append({
            'owner_id': owner_id,
            'hold_count': len(hold_list),
            'pending_count': len(pending_list),
            'watch_count': len(watch_list),
            'ticker_count': ticker_count
        })
    
    # Get Telegram users
    telegram_users = list(TARGET_CHAT_IDS) if TARGET_CHAT_IDS else []
    
    return render_template('manage_users.html',
                         owners_list=owners_list,
                         telegram_users=telegram_users,
                         users=users)

@app.route('/api/users/telegram/add', methods=['POST'])
@login_required
@admin_required
def api_add_telegram_user():
    data = request.get_json()
    chat_id = data.get('chat_id', '').strip()
    
    try:
        chat_id_int = int(chat_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'Chat ID phải là số'}), 400
    
    # Update config or save to a separate file
    # For now, we'll save to web_users.json or create a telegram_users.json
    telegram_file = DATA_DIR / "telegram_users.json"
    if telegram_file.exists():
        telegram_users = json.loads(telegram_file.read_text(encoding="utf-8"))
    else:
        telegram_users = {"chat_ids": list(TARGET_CHAT_IDS) if TARGET_CHAT_IDS else []}
    
    if chat_id_int not in telegram_users.get('chat_ids', []):
        telegram_users['chat_ids'].append(chat_id_int)
        telegram_file.write_text(json.dumps(telegram_users, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({'success': True, 'message': f'Đã thêm Telegram user: {chat_id_int}'})
    else:
        return jsonify({'success': False, 'message': 'User đã tồn tại'}), 400

@app.route('/api/users/telegram/remove', methods=['POST'])
@login_required
@admin_required
def api_remove_telegram_user():
    data = request.get_json()
    chat_id = data.get('chat_id', '').strip()
    
    try:
        chat_id_int = int(chat_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'Chat ID phải là số'}), 400
    
    telegram_file = DATA_DIR / "telegram_users.json"
    if telegram_file.exists():
        telegram_users = json.loads(telegram_file.read_text(encoding="utf-8"))
        if chat_id_int in telegram_users.get('chat_ids', []):
            telegram_users['chat_ids'].remove(chat_id_int)
            telegram_file.write_text(json.dumps(telegram_users, ensure_ascii=False, indent=2), encoding="utf-8")
            return jsonify({'success': True, 'message': f'Đã xóa Telegram user: {chat_id_int}'})
    
    return jsonify({'success': False, 'message': 'User không tồn tại'}), 404

@app.route('/api/users/create', methods=['POST'])
@login_required
@admin_required
def api_create_user():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    owner_id = data.get('owner_id', '').strip() or username
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Vui lòng nhập đầy đủ thông tin'}), 400
    
    users = _load_users()
    
    if username in users:
        return jsonify({'success': False, 'message': 'Tên đăng nhập đã tồn tại'}), 400
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    users[username] = {
        'password': password_hash,
        'owner_id': owner_id,
        'is_admin': False
    }
    
    _save_users(users)
    
    # Ensure owner exists in owner_db
    portfolio.ensure_owner(owner_id)
    _save_owner_db()
    
    return jsonify({'success': True, 'message': f'Đã tạo user: {username}'})

@app.route('/api/realtime-price/<ticker>')
@login_required
def api_realtime_price(ticker):
    """Get realtime price for a ticker"""
    try:
        ticker = ticker.upper().strip()
        # Use async function with proper event loop handling
        try:
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
        except (ImportError, RuntimeError):
            # Fallback: use sync version
            import data_ta
            data = data_ta.fetch_stock_data(ticker)
        else:
            data = loop.run_until_complete(fetch_stock_data_async(ticker))
        
        if data and data.get('price'):
            price = float(data['price'])
            ref = float(data.get('ref', price))
            change = ((price - ref) / ref * 100) if ref else 0
            
            return jsonify({
                'success': True,
                'price': price,
                'change': change,
                'volume': data.get('vol_day', 0),
                'source': data.get('source', 'Unknown')
            })
        else:
            return jsonify({'success': False, 'message': 'Không lấy được dữ liệu giá'}), 404
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': str(e) + '\n' + traceback.format_exc()}), 500

@app.route('/api/ai-analyze-levels/<ticker>')
@login_required
def api_ai_analyze_levels(ticker):
    """AI analyze and suggest price levels for a ticker"""
    try:
        ticker = ticker.upper().strip()
        
        # Check if user owns this ticker
        owner_db = _load_owner_db()
        owner_id = session.get('owner_id', session.get('username', ''))
        owner_data = owner_db.get('owners', {}).get(owner_id, {})
        all_user_tickers = set(
            owner_data.get('HOLD', []) +
            owner_data.get('PENDING', []) +
            list(owner_data.get('WATCH', {}).keys())
        )
        
        if ticker not in all_user_tickers:
            return jsonify({'success': False, 'message': 'Bạn không có quyền phân tích mã này'}), 403
        
        # Fetch realtime data
        try:
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            data = loop.run_until_complete(fetch_stock_data_async(ticker))
        except (ImportError, RuntimeError):
            # Fallback: use sync version
            import data_ta
            data = data_ta.fetch_stock_data(ticker)
        
        if not data or not data.get('price'):
            return jsonify({'success': False, 'message': 'Không lấy được dữ liệu giá'}), 404
        
        price = float(data['price'])
        ref = float(data.get('ref', price))
        change = ((price - ref) / ref * 100) if ref else 0
        
        # Compute technicals
        tech = compute_technicals(data)
        
        # Use portfolio function to propose levels
        result = portfolio.propose_and_apply_rules(ticker, mode="ai_analysis", replace_existing=False)
        
        if result.get('ok'):
            applied = result.get('applied', {})
            suggested_levels = applied.get('levels', [])
            major_levels = applied.get('major', [])
            
            # Build AI prompt
            prompt = f"""Phân tích cổ phiếu {ticker}:
- Giá hiện tại: {price:.2f} VND
- Thay đổi: {change:+.2f}%
- RSI(14): {tech.get('RSI14', 'N/A')}
- EMA20: {tech.get('EMA20', 'N/A')}
- VWAP: {tech.get('VWAP', 'N/A')}
- Khối lượng: {data.get('vol_day', 0):,}

Các mốc giá đề xuất:
- Levels: {suggested_levels}
- Major levels: {major_levels}

Hãy phân tích ngắn gọn về các mốc giá này và đề xuất chiến lược giao dịch dựa trên giá hiện tại."""
            
            # Use gemini from app.py
            try:
                from app import gemini_generate
                ai_analysis = gemini_generate(prompt, sys="Bạn là chuyên gia phân tích kỹ thuật chứng khoán VN. Trả lời ngắn gọn, rõ ràng.")
            except Exception as e:
                ai_analysis = f"Không thể gọi AI: {str(e)}"
            
            return jsonify({
                'success': True,
                'price_info': {
                    'price': price,
                    'change': change,
                    'volume': data.get('vol_day', 0)
                },
                'analysis': ai_analysis,
                'suggested_levels': suggested_levels,
                'suggested_major_levels': major_levels
            })
        else:
            return jsonify({'success': False, 'message': result.get('msg', 'Không thể phân tích')}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': str(e) + '\n' + traceback.format_exc()}), 500

@app.route('/api/alerts/get/<ticker>')
@login_required
def api_get_alert(ticker):
    """Get current alert rules for a ticker"""
    try:
        ticker = ticker.upper().strip()
        rules = _load_rules()
        
        # Check if user owns this ticker
        owner_db = _load_owner_db()
        owner_id = session.get('owner_id', session.get('username', ''))
        owner_data = owner_db.get('owners', {}).get(owner_id, {})
        all_user_tickers = set(
            owner_data.get('HOLD', []) +
            owner_data.get('PENDING', []) +
            list(owner_data.get('WATCH', {}).keys())
        )
        
        if ticker not in all_user_tickers:
            return jsonify({'success': False, 'message': 'Bạn không có quyền xem mã này'}), 403
        
        rule = rules.get(ticker, {})
        
        return jsonify({
            'success': True,
            'rule': {
                'levels': rule.get('levels', []),
                'major_levels': rule.get('major_levels', []),
                'vol_marks': rule.get('vol_marks', []),
                'note': rule.get('note', '')
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/alerts/refresh/<ticker>', methods=['POST'])
@login_required
def api_refresh_alert_rules(ticker):
    """Refresh alert rules for a specific ticker"""
    try:
        ticker = ticker.upper().strip()

        # Check if user owns this ticker
        owner_db = _load_owner_db()
        owner_id = session.get('owner_id', session.get('username', ''))
        owner_data = owner_db.get('owners', {}).get(owner_id, {})
        all_user_tickers = set(
            owner_data.get('HOLD', []) +
            owner_data.get('PENDING', []) +
            list(owner_data.get('WATCH', {}).keys())
        )

        if ticker not in all_user_tickers:
            return jsonify({'success': False, 'message': 'Bạn không có quyền refresh mã này'}), 403

        # Call propose_and_apply_rules with replace_existing=False to merge with existing rules
        result = portfolio.propose_and_apply_rules(ticker, mode="manual_refresh", replace_existing=False)

        if result.get('ok'):
            applied = result.get('applied', {})
            return jsonify({
                'success': True,
                'message': f'Đã refresh rules cho {ticker}',
                'rules': {
                    'levels': applied.get('levels', []),
                    'major_levels': applied.get('major', []),
                    'vol_marks': applied.get('vol_marks', []),
                    'note': applied.get('note', '')
                }
            })
        else:
            return jsonify({'success': False, 'message': result.get('msg', 'Không thể refresh')}), 500

    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': str(e) + '\n' + traceback.format_exc()}), 500

@app.route('/api/alerts/refresh-all', methods=['POST'])
@login_required
def api_refresh_all_alert_rules():
    """Refresh alert rules for all tickers of current user"""
    try:
        owner_db = _load_owner_db()
        owner_id = session.get('owner_id', session.get('username', ''))
        owner_data = owner_db.get('owners', {}).get(owner_id, {})
        all_user_tickers = set(
            owner_data.get('HOLD', []) +
            owner_data.get('PENDING', []) +
            list(owner_data.get('WATCH', {}).keys())
        )

        if not all_user_tickers:
            return jsonify({'success': False, 'message': 'Không có mã nào để refresh'}), 400

        success_count = 0
        failed_tickers = []

        for ticker in all_user_tickers:
            try:
                result = portfolio.propose_and_apply_rules(ticker, mode="auto_refresh", replace_existing=False)
                if result.get('ok'):
                    success_count += 1
                else:
                    failed_tickers.append(ticker)
            except Exception as e:
                logging.warning(f"Failed to refresh rules for {ticker}: {e}")
                failed_tickers.append(ticker)

        message = f'Đã refresh {success_count}/{len(all_user_tickers)} mã'
        if failed_tickers:
            message += f'. Lỗi: {", ".join(failed_tickers)}'

        return jsonify({
            'success': True,
            'message': message,
            'success_count': success_count,
            'total': len(all_user_tickers),
            'failed': failed_tickers
        })

    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': str(e) + '\n' + traceback.format_exc()}), 500

@app.route('/tools')
@login_required
def tools():
    return render_template('tools.html')

@app.route('/api/chart/<ticker>')
@login_required
def api_get_chart(ticker):
    """Get interactive Plotly chart for a ticker"""
    try:
        ticker = ticker.upper().strip()

        # Check if user owns this ticker
        owner_db = _load_owner_db()
        owner_id = session.get('owner_id', session.get('username', ''))
        owner_data = owner_db.get('owners', {}).get(owner_id, {})
        all_user_tickers = set(
            owner_data.get('HOLD', []) +
            owner_data.get('PENDING', []) +
            list(owner_data.get('WATCH', {}).keys())
        )

        if ticker not in all_user_tickers:
            return jsonify({'success': False, 'message': 'Bạn không có quyền xem chart của mã này'}), 403

        # Get rules for this ticker
        rules = _load_rules()
        ticker_rules = rules.get(ticker, {})

        # Generate chart HTML
        import tempfile
        from pathlib import Path
        import alerts_jobs

        # Create temp file for chart
        temp_dir = Path(tempfile.gettempdir())
        chart_path = temp_dir / f"chart_{ticker}_{owner_id}.html"

        # Use asyncio to run the async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result_path = loop.run_until_complete(
            alerts_jobs._render_chart_plotly(ticker, ticker_rules, str(chart_path))
        )

        if result_path and Path(result_path).exists():
            # Read the HTML content
            chart_html = Path(result_path).read_text(encoding='utf-8')
            return jsonify({
                'success': True,
                'chart_html': chart_html
            })
        else:
            return jsonify({'success': False, 'message': 'Không thể tạo chart'}), 500

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/market-ticker')
def api_market_ticker():
    """HTMX endpoint for market ticker"""
    try:
        market_overview = data_ta.fetch_market_overview()
        if market_overview.get('ok'):
            return render_template('partials/market_ticker.html', 
                                 market_data=market_overview['data'],
                                 timestamp=market_overview.get('timestamp'))
        return '<div class="text-rose-500 px-4">Lỗi tải dữ liệu</div>'
    except Exception as e:
        return f'<div class="text-rose-500 px-4">Error: {str(e)}</div>'

@app.route('/api/market-overview-table')
def api_market_overview_table():
    """HTMX endpoint for market overview table"""
    try:
        market_overview = data_ta.fetch_market_overview()
        if market_overview.get('ok'):
            return render_template('partials/market_table.html', 
                                 market_data=market_overview['data'])
        return '<tr><td colspan="5" class="text-center text-rose-500 py-4">Lỗi tải dữ liệu</td></tr>'
    except Exception as e:
        return f'<tr><td colspan="5" class="text-center text-rose-500 py-4">Error: {str(e)}</td></tr>'

@app.route('/api/foreign-flow')
def api_foreign_flow():
    """HTMX endpoint for foreign flow"""
    try:
        foreign_flow = data_ta.fetch_foreign_flow(days=5)
        return render_template('partials/foreign_flow.html', foreign_flow=foreign_flow)
    except Exception as e:
        return f'<div class="text-rose-500 text-center p-4">Lỗi tải dữ liệu: {str(e)}</div>'

@app.route('/api/sector-performance')
def api_sector_performance():
    """HTMX endpoint for sector performance"""
    try:
        sector_performance = data_ta.fetch_sector_performance()
        return render_template('partials/sector_performance.html', sector_performance=sector_performance)
    except Exception as e:
        return f'<div class="text-rose-500 text-center p-4">Lỗi tải dữ liệu: {str(e)}</div>'

@app.route('/stock/<ticker>')
@login_required
def stock_detail(ticker):
    """Stock detail page"""
    ticker = ticker.upper().strip()
    return render_template('stock_detail.html', ticker=ticker)

@app.route('/api/history/<ticker>')
@login_required
def api_stock_history(ticker):
    """Get historical data for chart"""
    try:
        ticker = ticker.upper().strip()
        df = data_ta.fetch_historical_eod_data(ticker, days=180)
        
        if df is not None and not df.empty:
            # Format for TradingView Lightweight Charts
            # [{ time: '2018-12-22', open: 75.16, high: 82.84, low: 36.16, close: 45.72 }]
            data = []
            for index, row in df.iterrows():
                data.append({
                    'time': index.strftime('%Y-%m-%d'),
                    'open': row['Open'],
                    'high': row['High'],
                    'low': row['Low'],
                    'close': row['Close'],
                    'volume': row['Volume']
                })
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'message': 'No data'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



    except Exception as e:
        import traceback
        logging.error(f"Error generating chart: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    # Load initial data
    _load_owner_db()
    _load_rules()
    _load_users()
    
    port = int(os.getenv('WEB_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)

