# Web App - Bot Chứng Khoán

## Mô tả

Web interface để quản lý cài đặt Bot Chứng khoán theo từng user. Cho phép:
- Đăng nhập theo user
- Quản lý cổ phiếu theo dõi (HOLD, PENDING, WATCH)
- Thiết lập các mốc cảnh báo giá
- Quản lý Telegram users để nhận cảnh báo
- Phân quyền admin/user

## Cài đặt

### 1. Cài đặt dependencies

```bash
pip install -r requirements_web.txt
```

### 2. Cấu hình

Set các biến môi trường (hoặc tạo file `.env`):

```bash
# Port cho web app (mặc định: 5000)
WEB_PORT=5000

# Secret key cho Flask session (quan trọng cho production)
FLASK_SECRET_KEY=your-secret-key-here

# Debug mode (True/False)
FLASK_DEBUG=False
```

### 3. Chạy web app

```bash
python web_app.py
```

Web app sẽ chạy tại: `http://localhost:5000`

### 4. Đăng nhập mặc định

- **Username**: `admin`
- **Password**: `admin123`

**⚠️ QUAN TRỌNG**: Đổi mật khẩu admin ngay sau lần đăng nhập đầu tiên!

## Deploy lên Production

### Option 1: Sử dụng Gunicorn (Khuyến nghị)

```bash
pip install gunicorn

# Chạy với Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web_app:app
```

### Option 2: Sử dụng uWSGI

```bash
pip install uwsgi

# Tạo file uwsgi.ini
[uwsgi]
module = web_app:app
master = true
processes = 4
socket = 0.0.0.0:5000
chmod-socket = 666
vacuum = true
die-on-term = true

# Chạy
uwsgi uwsgi.ini
```

### Option 3: Sử dụng Nginx làm reverse proxy

1. Cài đặt Nginx
2. Tạo file config `/etc/nginx/sites-available/botchungkhoan`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

3. Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/botchungkhoan /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Option 4: Sử dụng systemd service

Tạo file `/etc/systemd/system/botchungkhoan-web.service`:

```ini
[Unit]
Description=Bot Chứng Khoán Web App
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/BOTCHUNGKHOAN1.0
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 web_app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable và start:
```bash
sudo systemctl enable botchungkhoan-web
sudo systemctl start botchungkhoan-web
```

### SSL/HTTPS với Let's Encrypt

```bash
# Cài đặt certbot
sudo apt install certbot python3-certbot-nginx

# Lấy certificate
sudo certbot --nginx -d your-domain.com

# Auto-renew
sudo certbot renew --dry-run
```

## Cấu trúc File

```
BOTCHUNGKHOAN1.0/
├── web_app.py              # Flask app chính
├── requirements_web.txt    # Dependencies cho web
├── web_users.json          # Database users (tự động tạo)
├── telegram_users.json     # Telegram chat IDs (tự động tạo)
├── templates/             # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── manage_stocks.html
│   ├── manage_alerts.html
│   └── manage_users.html
└── static/                # CSS/JS
    ├── style.css
    └── script.js
```

## Tính năng

### 1. Đăng nhập/Authentication
- Session-based authentication
- Support multiple users
- Admin/user roles

### 2. Dashboard
- Tổng quan số lượng cổ phiếu
- Thống kê HOLD/PENDING/WATCH
- Quick actions

### 3. Quản lý Cổ phiếu
- Thêm/xóa mã vào HOLD
- Thêm/xóa mã vào PENDING
- Thêm/xóa/sửa mã trong WATCH (có mốc giá và ghi chú)

### 4. Quản lý Cảnh báo
- Thiết lập mốc giá (levels)
- Thiết lập mốc chính (major levels)
- Thiết lập ngưỡng khối lượng (vol marks)
- Ghi chú cho từng mã

### 5. Quản lý Users (Admin only)
- Tạo user mới
- Xem danh sách owners
- Quản lý Telegram chat IDs

## API Endpoints

### Stocks
- `POST /api/stocks/add` - Thêm cổ phiếu
- `POST /api/stocks/remove` - Xóa cổ phiếu
- `POST /api/stocks/update` - Cập nhật WATCH

### Alerts
- `POST /api/alerts/update` - Cập nhật cảnh báo

### Users
- `POST /api/users/create` - Tạo user (admin only)
- `POST /api/users/telegram/add` - Thêm Telegram user (admin only)
- `POST /api/users/telegram/remove` - Xóa Telegram user (admin only)

## Security Notes

1. **Đổi mật khẩu admin mặc định** ngay sau khi deploy
2. **Set FLASK_SECRET_KEY** mạnh và không chia sẻ
3. **Dùng HTTPS** trong production
4. **Giới hạn IP** nếu cần (qua Nginx/firewall)
5. **Backup định kỳ** các file JSON (owner_db.json, rules.json, web_users.json)

## Troubleshooting

### Port đã được sử dụng
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux
sudo lsof -i :5000
sudo kill -9 <PID>
```

### Lỗi import module
Đảm bảo đang chạy từ thư mục gốc của project:
```bash
cd /path/to/BOTCHUNGKHOAN1.0
python web_app.py
```

### Session không lưu
Kiểm tra `FLASK_SECRET_KEY` đã được set đúng chưa.

## Support

Nếu có vấn đề, kiểm tra:
1. Logs của Flask/Gunicorn
2. Browser console (F12)
3. Network tab để xem API calls

## License

Phục vụ cho dự án Bot Chứng Khoán cá nhân.

